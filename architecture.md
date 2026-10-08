# Architecture

Principle: every component must solve a stated problem. Reasoning order: Problem, Requirement, Options, Pros/Cons, Trade-offs, Decision, Implementation.

## 1. Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Frontend | React, Vite, Tailwind CSS | Restaurant/admin dashboard only. |
| Backend | Python, FastAPI | REST APIs, auth, agent execution, Gmail, payments, webhooks, rate limiting. |
| Database | Supabase (PostgreSQL) | Orders, menu, payments, agent logs. Transactions and constraints give idempotency. |
| Auth | Supabase Auth (JWT) | Already in the stack. Verified in FastAPI. |
| Agent | LangChain/LangGraph agent with middleware | Tool calling, state, human-in-the-loop, limits. |
| LLM | Provider API (to be chosen) | Intent understanding and tool selection. |
| Email | Gmail API + Google OAuth | Zero cost channel, no customer app. |
| Payment | Razorpay Test API + webhooks | Payment truth from verified webhook, not the client. |
| Redis | Undecided | Only if chosen for shared rate-limit counters, queue, or cache. |
| Deployment | Vercel / Render / Railway (considered) | Public deployment. |

Not used: RAG, vector DB, Kafka, Kubernetes, microservices, multi-agent, LLM gateway, API gateway.

## 2. System Flow

```
Customer -> Gmail -> Gmail poller (or push)
                         |
                         v
               Store email (unique gmail_message_id)
                         |
                         v
                 Rate limiter (per sender + global LLM)
                  |                      |
              allowed                 blocked
                  |                      |
                  v                      v
            Run agent now        Queue job (status QUEUED)
                  ^                      |
                  |                  Worker paces itself
                  +----------------------+
                         |
                         v
                      Agent
        (middleware: limits, retry, approval, validation)
                         |
        +----------------+------------------+
        v                v                  v
   Menu/Inventory    Create Order      Payment Link
   (cached reads)   (DB transaction)   (Razorpay)
                         |
                         v
                  Email to customer (Gmail)

Customer pays -> Razorpay webhook -> FastAPI
   -> verify signature -> dedupe event ID -> mark PAID -> confirmation email
```

Dashboard path:
```
React -> FastAPI (auth + role check + HTTP rate limit) -> Supabase
```

Same function runs the agent whether the job runs now or later. The worker is a delayed caller.

## 3. Agent Design

### Tools (each tied to a real task)
Gmail read, Gmail send (templated), menu lookup, inventory check, customer lookup, calculate price, create order, generate payment link, order status.

### Rules for tools
- Customer identity comes from the email sender via backend context, never from LLM arguments.
- LLM returns item IDs and quantities. Code calculates totals from DB prices.
- No tool can set an order to PAID. Only the verified webhook can.
- No "list all customers" or "send arbitrary email" tool.

### Middleware (guardrails chosen)
| Middleware | Where | Reason |
|---|---|---|
| ModelCallLimit | Whole run | Loop must end; cost cap. |
| ToolCallLimit | Whole run, tighter on `create_order` and `generate_payment_link` (max 1 each) | One email cannot create several orders. |
| HumanInTheLoop | `cancel_order`, refund, custom email | Irreversible or costly actions. Needs a checkpointer to pause and resume. |
| ToolRetry | Read-only tools only | Transient failures. Never on non-idempotent tools. |
| ModelRetry | LLM call, only 429 and 5xx | LLM API fails briefly. |
| Output validator (custom, after agent) | Final reply | Allow only the payment-link domain, no other URLs, no leaked internal data. |

Outside middleware: Pydantic schemas on tool arguments (item exists, quantity bounds), order state machine in code.

Suggested wrap order, outer to inner: ModelCallLimit, ToolCallLimit, ModelRetry, HumanInTheLoop, ToolRetry, output validation. Verify against installed library docs.

## 4. System Design Concepts

### Authentication
Supabase Auth JWT verified by a FastAPI dependency on dashboard routes. Webhook uses signature verification instead. Gmail uses a separate Google OAuth flow; refresh token encrypted at rest.

### Authorization
Roles: `owner` (settings, approvals, refunds, Gmail connect) and `staff` (view orders, edit menu). Implemented as `require_role(...)` dependency. Open: single versus multi-restaurant; FastAPI-only checks versus adding Supabase RLS.

### Idempotency
Database unique constraints are the guard, not code `if` checks.
- Inbound email: unique `gmail_message_id`.
- Webhook: unique Razorpay event ID; duplicates return 200.
- Payment link: check `order.payment_link_id` before creating.
- Outbound email: unique `(order_id, email_type)`; at-least-once (record after send) proposed.

### Timeouts
- LLM about 30 to 60s. Gmail and Razorpay: about 10s connect, 10 to 15s read.
- DB statement timeout.
- Whole agent run wrapped in an overall timeout.
- Inner timeouts shorter than outer; retries must fit inside the run timeout.

### Retries
- Library: tenacity for plain calls, middleware for the agent.
- Retry only transient errors (429, 5xx, connect timeouts) with exponential backoff and jitter, max 3 to 4 tries, respect `Retry-After`.
- Never retry 4xx validation or auth errors.
- Retry non-idempotent calls only once idempotency protects them.
- After max retries, mark `FAILED` and surface on the Emails page.

### Rate Limiting
Two separate problems:
1. HTTP API (login, dashboard): per IP and per user. Webhook limit loose or none.
2. Email path (where LLM cost lives): per sender per hour/day, plus global daily LLM budget.

Backend options: in-memory (slowapi), Redis (shared across instances, survives restart, TTL expiry), Postgres counter. Algorithm options: fixed window, sliding window, token bucket (pairs well with worker pacing).

### Queueing (requirement: blocked requests are queued, not dropped)
- Allowed: run now. Blocked: enqueue, worker processes later.
- Worker pulls a job only when the limiter has capacity (leaky bucket behavior), otherwise the queue does not protect the LLM.
- Job states: `QUEUED`, `RUNNING`, `DONE`, `FAILED`, `EXPIRED`.
- Lease timeout returns stuck `RUNNING` jobs to `QUEUED`; requires idempotent tools.
- Job key is `gmail_message_id`.
- Proposed bounds: per-sender cap, job TTL, global cap, with a cheap fixed reply when over cap, so every request still gets an outcome. Fairness via per-sender limits or sub-queues.

### Caching (menu and static data)
- Cache menu items, prices, categories, settings for read paths: the agent's menu lookup tool and the dashboard menu list.
- Never cache for order creation or price calculation; those read the DB inside the transaction.
- Invalidation: explicit delete on menu update plus short TTL (60 to 300s) as a safety net.
- Options: in-process TTL cache (cachetools), Redis, HTTP cache headers for the dashboard. Measure before and after.

## 5. Data (initial tables)
users/roles, customers, menu_items, inventory (or availability flag), orders, order_items, payments, payment_events (unique event ID), emails (unique gmail_message_id), jobs (if Postgres queue), agent_runs, tool_calls, approvals, settings.

Indexes: unique `gmail_message_id`, unique webhook event ID, orders by status and created time, customer email, payment link ID.

## 6. Observability
Run ID per email carried through logs. Per run: tool calls, latency per step, model call count, tokens, cost, errors. Feeds the Agent Activity dashboard page. Dedicated tracing tools (Langfuse, OpenTelemetry) only when logs stop answering questions.

## 7. Open Decisions
1. Optional middleware: model fallback, PII masking, summarization (each yes/no).
2. Single or multi-restaurant.
3. Authorization: FastAPI-only or plus Supabase RLS.
4. Redis now or later (rate limit and cache backend).
5. Outbound email: at-least-once or at-most-once.
6. Queue scope: email/agent path only, or dashboard HTTP too.
7. Queue bounds: per-sender cap, TTL, global cap, or unbounded.
8. Queue backend: Postgres jobs table, hand-rolled Redis, Arq, Redis Streams.
9. Limiter algorithm: fixed window, sliding window, token bucket.
10. Fairness: single FIFO or per-sender.
11. Gmail intake: polling or Pub/Sub push.
12. Inventory page versus availability toggle; Customers and Invoices pages.
13. MCP: not in V1 unless a second client or agent needs the same tools.

## 8. Scaling Path
One FastAPI instance, then multiple instances behind a load balancer only when one instance saturates. Then process-local state (counters, cache) breaks, so shared Redis becomes necessary. Gmail poller must run on a single instance or hold a lock.
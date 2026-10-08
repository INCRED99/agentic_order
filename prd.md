# PRD: AI Restaurant Order System (Gmail + Agent)

## 1. Summary
An agentic restaurant order management system. Customers order by emailing the restaurant through Gmail. An AI agent reads the email, understands the request, uses tools (menu, inventory, orders, payments), creates the order, sends a Razorpay payment link by email, and confirms after payment. Restaurant staff monitor and control everything from a React dashboard.

This is not a chatbot. The agent acts on real business data through tools, under guardrails.

## 2. Problem
- Small restaurants take orders through scattered channels (calls, DMs, email) and handle them by hand.
- Manual order taking is slow, error-prone, and hard to track against payments.
- Customers should not need an app or account to order.

## 3. Target Users
| User | Need |
|---|---|
| Customer | Order by plain email, ask about menu, get payment link and confirmation, ask for cancellation. No app install. |
| Restaurant owner | Visibility into every order and agent action, approve risky actions, control menu, kill switch for the agent. |
| Restaurant staff | View orders and payments, update menu and availability. Limited permissions. |

Goal beyond the product: demonstrate real backend, agentic AI, and system-design reasoning (every component has a stated reason).

## 4. Goals
- Customer email to confirmed, paid order with no human involvement for normal orders.
- Agent handles varied natural language (quantities, modifications, menu questions, cancellations).
- Payment truth comes only from a verified Razorpay webhook.
- Owner can see and audit everything the agent did.
- Public deployment, costing near zero during build and testing (Gmail, Razorpay Test).

## 5. Non-Goals
- No RAG, no vector database (no retrieval requirement; menu fits in a tool call).
- No WhatsApp/Twilio in the current scope (Gmail only).
- No separate customer-facing app.
- No microservices, Kafka, or Kubernetes.

## 6. Core Customer Flow
1. Customer emails an order.
2. Backend fetches the email via Gmail API.
3. Agent extracts items, quantities, customer info.
4. Agent checks menu and inventory.
5. Backend calculates the total from database prices (not the LLM).
6. Pending order created.
7. Razorpay Test payment link generated.
8. Payment link emailed to the customer.
9. Customer pays.
10. Razorpay webhook reaches backend, signature verified.
11. Order marked PAID.
12. Confirmation email sent.

Other supported intents: menu questions ("What pizzas do you have?"), order status, cancellation request (requires approval).

## 7. Features

### 7.1 Agent (V1)
- Intent understanding for order, menu question, status, cancel.
- Tools only where a real task needs them: menu lookup, inventory check, customer lookup, calculate price, create order, generate payment link, order status, Gmail read/send.
- Human approval for risky actions (cancel, refund, sensitive or custom emails).

### 7.2 Restaurant Dashboard (V1)
- **Orders:** list, filter by status, detail with original email, items, total, payment state, link to agent run.
- **Approvals:** queue of agent-proposed risky actions; approve or reject.
- **Menu:** items, prices, availability.
- **Payments:** payment link state (created, paid, failed, expired), webhook events.
- **Emails:** inbound and outbound log; flags for unparseable, suspected injection, needs human.
- **Agent Activity:** per-run tool calls, latency, tokens, cost, errors.
- **Settings:** Gmail OAuth connection, agent on/off switch, approval thresholds.

### 7.3 Later / Undecided
- Customers page (V2).
- Inventory as separate page versus a merged availability toggle in Menu (open).
- Invoices (skip unless own invoice PDF is needed).

### 7.4 Production Concepts in Scope
Authentication, authorization, idempotency, timeouts, retries, rate limiting (with queueing), caching of menu and static data. Each tied to a concrete requirement in `architecture.md`.

## 8. Rate Limiting and Queueing Requirement
- Request passes the limiter: process immediately.
- Request blocked by the limiter: enqueue and process later by a worker. Not dropped.
- Worker must itself respect the limiter, otherwise the queue does not protect the LLM.
- Open: bounds on the queue (per-sender cap, TTL, global cap), fairness, queue scope (email/agent path versus dashboard HTTP). See `architecture.md` open decisions.

## 9. Security Requirements
- Dashboard authentication and role-based authorization.
- Gmail via Google OAuth only; refresh token encrypted at rest; all secrets on backend only.
- Email content is untrusted data (prompt injection).
- Agent gets minimum tool permissions; no tool can mark an order PAID.
- Webhook signature verification.

## 10. Success Criteria
- A normal order email results in a paid, confirmed order without human action.
- Duplicate emails or duplicate webhooks never create duplicate orders or confirmations.
- An injected instruction in an email cannot read other customers' data or send arbitrary links.
- Owner can reconstruct what happened for any order from the dashboard.
- Each architectural component can be explained as problem, requirement, decision, trade-off.

## 11. Phases
- **V1:** working workflow (React, FastAPI, agent, Gmail, Supabase, Razorpay Test), with core guardrails, auth, idempotency, timeouts.
- **V2:** production hardening where triggers are hit (queue and worker, Redis if chosen, observability, caching).
- **V3:** scale only if needed (multiple instances, load balancer).
# Rules: What to Use, What to Avoid

Master rule: every decision needs a reason. If a component cannot be explained as Problem, Requirement, Decision, Trade-off, do not add it.

## 1. Use

### Stack
- React + Vite + Tailwind for the dashboard.
- FastAPI (Python) backend; Pydantic for all request, tool, and output schemas.
- Supabase/PostgreSQL as the single database.
- Supabase Auth JWT for dashboard login; Google OAuth for Gmail.
- Razorpay Test API with webhooks.
- LangChain/LangGraph agent with middleware.
- `httpx` with explicit timeouts for all external calls; `tenacity` for retries outside the agent.

### Agent guardrails
- ModelCallLimit, ToolCallLimit, HumanInTheLoop, ToolRetry, ModelRetry, output validator.
- Pydantic schemas on every tool argument.
- Order state machine in code.

### Data integrity
- Database unique constraints for idempotency (`gmail_message_id`, webhook event ID, `(order_id, email_type)`).
- DB transactions for order, items, inventory changes.
- Indexes on lookup fields used by webhooks and dedupe.

### Operations
- Structured logs with a run ID per email.
- Secrets in environment variables, backend only; Gmail refresh token encrypted at rest.
- Rate limits at two levels: HTTP API, and email/LLM path.
- Queue blocked work instead of dropping it, with bounds (see Open Decisions).
- Menu/static data caching with explicit invalidation plus short TTL.

## 2. Avoid

### Technologies without a real need
- RAG and vector databases (no retrieval requirement).
- Kafka, Kubernetes, microservices.
- Multi-agent orchestration.
- Multiple databases.
- LLM gateway, API gateway.
- Multiple backend instances and load balancer before one instance is saturated.
- MCP in V1 (add only if tools must be shared with other clients or agents).
- Twilio/WhatsApp in current scope.

### Agent behavior
- LLM computing prices or totals.
- LLM supplying customer IDs or any identity to tools.
- Any tool that sets an order to PAID. Only the verified webhook does.
- Tools like "list all customers" or "send arbitrary email".
- Treating email content as instructions. It is untrusted data.
- Emailing URLs other than the generated payment link domain.
- Retrying non-idempotent calls (create order, create payment link) without idempotency protection.
- Unlimited agent loops, unlimited tool calls, no run timeout.

### Engineering
- Trusting the frontend for payment success.
- Process-local state for anything that must be shared across instances (once scaling).
- Caching anything used in order creation or price calculation.
- Idempotency via code `if` checks alone (races defeat them).
- Putting API keys, OAuth tokens, or secrets in React or in the repository.
- Unbounded queues and unbounded job retries.
- Adding a component only because it looks good on a diagram.

## 3. Decision Process (for every technology choice)
1. Problem
2. Requirement
3. Realistic alternatives
4. Pros and cons of each
5. Trade-offs (gain versus give up)
6. Decision (owner decides, assistant challenges over-engineering and misunderstandings)
7. Implementation

## 4. Open Decisions
See `architecture.md`, section 7. Update this file when each is decided.
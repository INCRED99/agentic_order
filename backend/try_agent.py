import sys  # read the email id and optional test text from the command line

from app.agent import run_agent  # the code under test
from app.agent_tools import make_run_context  # builds the per-mail state

OWNER_ID = "afc925d9-f8c5-4650-a6b8-2939c0b6c72f"  # your test owner from the handoff

if len(sys.argv) < 2:  # no email id given
    raise SystemExit('usage: python try_agent.py <email_id> ["optional test mail text"]')  # stop with a clear message

run = make_run_context(OWNER_ID, sys.argv[1])  # state for this mail, sender comes from the stored row
mail_text = sys.argv[2] if len(sys.argv) > 2 else None  # optional text that replaces the stored body

try:  # the run can fail on purpose (limits) or by accident (Groq, DB)
    outcome = run_agent(run, mail_text)  # run the agent with the real LLM
except Exception as exc:  # any failure
    print("RUN FAILED:", type(exc).__name__, "-", exc)  # show the error type and text
    print("steps so far:", run.steps)  # what the tools did before the failure
    raise SystemExit(1)  # exit with an error code

print("model_calls:", outcome.model_calls)  # how many model answers were used
print("tokens:", outcome.tokens)  # total tokens, compare with the 8K per minute limit
print("order_id:", run.order_id)  # the order this run made, None when none
print("ended_reason:", run.ended_reason)  # link_sent, asked, approval or None
print("steps:")  # header
for step in run.steps:  # one line per tool call
    print("  ", step)  # tool, summary, ok
print("final_text:", outcome.final_text)  # the last LLM message
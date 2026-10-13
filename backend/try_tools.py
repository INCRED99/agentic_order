import sys  # read the email id from the command line

from app.agent_tools import build_tools, make_run_context  # the code under test

OWNER_ID = "afc925d9-f8c5-4650-a6b8-2939c0b6c72f"  # your test owner from the handoff

if len(sys.argv) < 2:  # no email id given
    raise SystemExit("usage: python try_tools.py <email_id>")  # stop with a clear message

run = make_run_context(OWNER_ID, sys.argv[1])  # build the context for this mail
tools = {t.name: t for t in build_tools(run)}  # tool name -> tool object

print("--- get_menu ---")  # section title
print(tools["get_menu"].invoke({}))  # call the tool directly, no LLM
print("--- create_order (dish 1, quantity 1) ---")  # section title
print(tools["create_order"].invoke({"items": [{"item_no": 1, "quantity": 1}]}))  # make a pending order
print("--- run state ---")  # section title
print("order_id:", run.order_id)  # the order this run made
print("steps:", run.steps)  # the run log
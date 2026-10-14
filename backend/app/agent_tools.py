import logging  # write problems to the server log
from dataclasses import dataclass, field  # small class that holds the state of ONE agent run
from email.utils import parseaddr  # splits "Name <a@b.com>" into name and address, also accepts a bare address

from langchain_core.tools import tool  # decorator that turns a Python function into a tool the LLM can call
from pydantic import BaseModel  # describes the shape of one order line for the LLM

from app.db import db  # shared Supabase client (service role, every query MUST filter by owner_id)
from app.inbox import send_mail  # SMTP sender: send_mail(to, subject, body, in_reply_to=None)
from app.payment_mail import send_payment_link_mail  # returns "sent" or "already_sent", raises on failure
from app.payments import PaymentError  # raised when an order cannot take a payment link

log = logging.getLogger(__name__)  # logger named after this file

MAX_MENU_ROWS = 60  # most dishes sent to the LLM, keeps the token cost small (D58 says revisit past about 40)
MAX_QUESTION_CHARS = 500  # longest question ask_customer may send
MAX_REASON_CHARS = 300  # longest reason request_approval may store
MAX_NAME_CHARS = 80  # longest customer name we store from the mail header
ALLOWED_ACTIONS = ("apply_discount", "cancel_order", "refund_order", "accept_large_order", "substitute_item")  # the actions the Approvals page knows (D38)

# DECISION PROBLEM: what should a tool do when something goes wrong?
# Options: (1) raise the error and let the agent loop crash, (2) return a short plain text message the LLM can read and react to.
# Chosen: option 2 for every business problem (unknown dish, no stock, bad input). Reason: the LLM can fix a typo or ask the customer, a crash cannot.
# Cost: we must write the messages ourselves. One tool, send_payment_link, still raises on unexpected errors (see below).

# DECISION PROBLEM: how does the LLM name a dish?
# Options: (1) it copies a uuid from get_menu, (2) it uses the small number shown in get_menu (D58 = a).
# Chosen: option 2. Reason: a number costs 1 token, a uuid about 20, and the LLM cannot invent a valid uuid.
# Cost: the number to uuid map lives in memory for one run only, so create_order must come after get_menu in the same run.


@dataclass  # generates __init__ for us
class RunContext:  # everything the tools need to know about ONE mail, filled by code, never by the LLM (D61 = a)
    owner_id: str  # the restaurant, comes from slug routing
    email_id: str  # id of the inbound mail row in the emails table
    from_email: str  # the sender header as stored in emails
    subject: str  # subject of the inbound mail
    message_id: str  # RFC Message-ID of the inbound mail, used for same-thread replies
    agent_run_id: str | None = None  # id of the agent_runs row, set by the worker, may be None in tests
    menu_map: dict[int, str] = field(default_factory=dict)  # dish number shown to the LLM -> real menu_item uuid
    order_id: str | None = None  # the order this run created, None until create_order works
    ended_reason: str | None = None  # why the run should end: "link_sent", "asked", "approval" or None
    already_handled: bool = False  # True when create_order found an order from an earlier run of this same mail (D47), customer mails are then blocked in code
    steps: list[dict] = field(default_factory=list)  # log of {tool, summary, ok}, never holds mail text (D51)


def make_run_context(owner_id: str, email_id: str, agent_run_id: str | None = None) -> RunContext:  # builds the context for one mail
    rows = (  # load the inbound mail row
        db.table("emails")  # read from the emails table
        .select("id,from_email,subject,gmail_message_id")  # only what the tools need
        .eq("id", email_id)  # this mail
        .eq("owner_id", owner_id)  # owner guard
        .limit(1)  # one row
        .execute()  # send the query
        .data  # the list of rows
    )
    if not rows:  # no such mail for this owner
        raise ValueError("email not found for this owner")  # loud failure, the worker marks the run failed
    row = rows[0]  # the one row
    return RunContext(  # build the context object
        owner_id=owner_id,  # the restaurant
        email_id=row["id"],  # the mail id
        from_email=row.get("from_email") or "",  # sender header, empty string when missing
        subject=row.get("subject") or "",  # subject, empty string when missing
        message_id=row.get("gmail_message_id") or "",  # threading id, empty string when missing
        agent_run_id=agent_run_id,  # run log id
    )


def _first(rows):  # supabase returns a list of rows, we want one row or None
    return rows[0] if rows else None  # first row, or None when nothing matched


def _wrap_id(message_id: str) -> str:  # In-Reply-To needs angle brackets around the id (same helper as payment_mail.py)
    message_id = message_id.strip()  # remove stray spaces
    if message_id.startswith("<") and message_id.endswith(">"):  # already wrapped
        return message_id  # keep as it is
    return f"<{message_id}>"  # add the brackets


def _rupees(paise: int) -> str:  # paise to a display string, money stays integer everywhere else
    return f"{paise / 100:.2f}"  # two decimals, for text only


def _exc_text(exc: Exception) -> str:  # best readable text of a database or payment error
    return str(getattr(exc, "message", None) or exc)  # APIError has .message, other errors fall back to str()


def _step(run: RunContext, tool_name: str, summary: str, ok: bool) -> None:  # add one line to the run log
    run.steps.append({"tool": tool_name, "summary": summary, "ok": ok})  # summary is written by us, never copied from the mail (D51)


def _sender(run: RunContext) -> tuple[str, str]:  # (display name, lowercase address) of the mail sender
    name, address = parseaddr(run.from_email)  # works for "Name <a@b.com>" and for "a@b.com"
    return name.strip()[:MAX_NAME_CHARS], address.strip().lower()  # cap the name, lowercase the address (customers are unique on owner + email)


def _find_or_create_customer(run: RunContext) -> str | None:  # D57 = b: only called when an order is really made
    name, address = _sender(run)  # who wrote the mail
    if not address:  # header had no readable address
        return None  # caller returns a message
    existing = _first(  # step 1: look for the customer
        db.table("customers")  # read from the customers table
        .select("id")  # only the id
        .eq("owner_id", run.owner_id)  # owner guard
        .eq("email", address)  # this sender
        .limit(1)  # one row (unique owner_id + email)
        .execute()  # send the query
        .data  # the list of rows
    )
    if existing:  # customer already known
        return existing["id"]  # use it
    try:  # step 2: create the customer
        created = (  # insert and read the new row back
            db.table("customers")  # write to the customers table
            .insert({"owner_id": run.owner_id, "email": address, "name": name or None})  # name may be empty
            .execute()  # send the insert
            .data  # the new row
        )
        if created:  # insert returned the row
            return created[0]["id"]  # use it
    except Exception:  # most likely the unique key: another run created the same customer a moment ago
        log.info("customer insert lost a race for owner %s, reading it again", run.owner_id)  # not an error, just a race
    again = _first(  # step 3: read again after a lost race
        db.table("customers")  # read from the customers table
        .select("id")  # only the id
        .eq("owner_id", run.owner_id)  # owner guard
        .eq("email", address)  # this sender
        .limit(1)  # one row
        .execute()  # send the query
        .data  # the list of rows
    )
    return again["id"] if again else None  # id, or None when it still does not exist


# DECISION PROBLEM: how do we turn database error codes into text for the LLM?
# Options: (1) pass the raw error, (2) match known codes from create_pending_order and write our own sentence.
# Chosen: option 2. Reason: raw errors can hold uuids (item_not_found lists ids) and the LLM must never see ids.
# Cost: a new error code in the SQL function needs a new line here. Unknown codes fall back to a generic sentence.
ORDER_ERRORS = (  # (code in the DB message, sentence for the LLM, include the DB detail?)
    ("too_many_lines", "Too many different dishes in one order. Ask the customer to split it.", False),  # many lines
    ("quantity_too_large", "One quantity is too large for an automatic order. Ask the owner to approve a large order.", False),  # big quantity
    ("total_too_large", "The total is too large for an automatic order. Ask the owner to approve a large order.", False),  # big total
    ("item_unavailable", "A dish is not available right now.", True),  # detail holds dish names, safe to show
    ("insufficient_stock", "Not enough stock.", True),  # detail holds dish name and numbers, safe to show
    ("item_not_found", "A dish number was not found. Call get_menu again and use its numbers.", False),  # detail holds ids, hide it
    ("invalid_items", "The order lines are not valid.", False),  # bad shape
)


class OrderLine(BaseModel):  # one line of an order as the LLM must send it
    item_no: int  # the dish number from get_menu
    quantity: int  # how many portions


def build_tools(run: RunContext) -> list:  # returns the five tools, each one bound to THIS run (closure)
    @tool  # the docstring below is what the LLM reads as the tool description, so it is written for the LLM
    def get_menu() -> str:
        """List the dishes the restaurant can sell right now. Each line starts with a dish number. Use these numbers in create_order."""
        try:  # database reads can fail
            dishes = (  # the available dishes of this restaurant
                db.table("menu_items")  # read from the menu table
                .select("id,name,price_paise,category")  # what the LLM needs to choose
                .eq("owner_id", run.owner_id)  # owner guard
                .eq("is_available", True)  # hide dishes the owner switched off
                .order("category")  # group by category
                .order("name")  # stable order inside a category
                .limit(MAX_MENU_ROWS)  # cap the size
                .execute()  # send the query
                .data  # the list of rows
            )
            stock_rows = (  # stock of this restaurant
                db.table("inventory")  # read from the stock table
                .select("menu_item_id,quantity")  # which dish, how many left
                .eq("owner_id", run.owner_id)  # owner guard
                .execute()  # send the query
                .data  # the list of rows
            )
        except Exception:  # any database problem
            log.exception("get_menu failed for owner %s", run.owner_id)  # log with traceback
            _step(run, "get_menu", "menu could not be loaded", False)  # record the failure
            return "The menu could not be loaded right now."  # plain text for the LLM
        stock = {row["menu_item_id"]: row["quantity"] for row in stock_rows}  # dish id -> quantity left
        run.menu_map.clear()  # start a fresh number map for this call
        lines = []  # text lines for the LLM
        for number, dish in enumerate(dishes, start=1):  # number the dishes 1, 2, 3 ...
            run.menu_map[number] = dish["id"]  # remember which uuid this number means
            if dish["id"] in stock:  # stock is tracked for this dish
                left = stock[dish["id"]]  # quantity left
                stock_text = "out of stock" if left <= 0 else f"stock {left}"  # zero or less means sold out
            else:  # no inventory row means stock is not tracked (earlier decision)
                stock_text = "stock not tracked"  # say so
            lines.append(f"{number}. {dish['name']} ({dish['category']}) - Rs {_rupees(dish['price_paise'])} - {stock_text}")  # one menu line
        _step(run, "get_menu", f"{len(lines)} dishes listed", True)  # record the success
        if not lines:  # nothing to sell
            return "The menu is empty."  # plain text for the LLM
        return "\n".join(lines)  # the whole menu as text

    @tool  # the docstring below is what the LLM reads
    def create_order(items: list[OrderLine]) -> str:
        """Create a pending order from the customer's mail. items is a list of {item_no, quantity} using the dish numbers from get_menu. Call get_menu first. Never send prices."""
        if run.order_id:  # this run already made an order
            return "An order already exists for this mail. Call send_payment_link."  # do not make another
        if not items:  # empty list
            return "The order has no dishes."  # plain text for the LLM
        merged: dict[str, int] = {}  # real dish uuid -> total quantity (same dish twice is added up)
        for line in items:  # check every line
            dish_id = run.menu_map.get(line.item_no)  # number -> uuid, from the get_menu call of this run
            if dish_id is None:  # number not in the map
                return f"Dish number {line.item_no} is not on the menu list. Call get_menu and use its numbers."  # tell the LLM how to fix it
            if line.quantity < 1:  # zero or negative
                return "Every quantity must be at least 1."  # plain text for the LLM
            merged[dish_id] = merged.get(dish_id, 0) + line.quantity  # add up repeated dishes
        customer_id = _find_or_create_customer(run)  # D57 = b: find or create the customer now
        if customer_id is None:  # sender address could not be read
            _step(run, "create_order", "sender address unreadable", False)  # record the failure
            return "The customer address could not be read from the mail. Ask the owner for approval."  # plain text for the LLM
        payload = [{"menu_item_id": dish_id, "quantity": qty} for dish_id, qty in merged.items()]  # the shape create_pending_order expects
        try:  # the database function can raise business errors
            result = (  # one all-or-nothing call (D22)
                db.rpc(  # call a Postgres function
                    "create_pending_order",  # function name from migration 011
                    {  # parameter names confirmed in the handoff
                        "p_owner_id": run.owner_id,  # restaurant, from code
                        "p_customer_id": customer_id,  # customer, from code
                        "p_source_email_id": run.email_id,  # the mail, from code
                        "p_items": payload,  # dishes and quantities, prices come from the DB
                    },
                )
                .execute()  # send the call
                .data  # the jsonb result
            )
        except Exception as exc:  # business error or database problem
            message = _exc_text(exc)  # readable text of the error
            for code, sentence, with_detail in ORDER_ERRORS:  # look for a known code
                if code in message:  # known code found
                    _step(run, "create_order", f"rejected: {code}", False)  # record the reason code only
                    return f"{sentence} ({message[:200]})" if with_detail else sentence  # detail only when it is safe
            log.exception("create_order failed for owner %s", run.owner_id)  # unknown error, log with traceback
            _step(run, "create_order", "unknown database error", False)  # record the failure
            return "The order could not be created right now."  # plain text for the LLM
        if isinstance(result, list):  # some client versions wrap the jsonb in a list
            result = result[0] if result else {}  # take the first item
        order_id = (result or {}).get("order_id")  # the new or first order
        if not order_id:  # function returned no order
            _step(run, "create_order", "no order id returned", False)  # record the failure
            return "The order could not be created right now."  # plain text for the LLM
        run.order_id = str(order_id)  # remember the order for send_payment_link and request_approval
        total = _rupees(result.get("total_paise", 0))  # total from the DB, never from the LLM (D29)
        if result.get("already_existed"):  # same mail ran before (D47)
            run.already_handled = True  # hard flag, ask_customer checks it, the LLM cannot override it
            _step(run, "create_order", "order already existed", True)  # record it
            return f"An order already exists for this mail, total Rs {total}. Nothing was changed. Call send_payment_link."  # plain text for the LLM
    # DECISION PROBLEM: what should send_payment_link do when sending fails with an unexpected error (Razorpay down, SMTP down)?
    # Options: (1) catch it and return text, (2) let the exception go up so ToolRetryMiddleware can retry (D28), and a final failure marks the run failed.
    # Chosen: option 2 for unexpected errors. Reason: a payment link is the sale itself, a retry and then a failed run (reclaimed later, D59) is better than the LLM giving up politely.
    # Cost: a failed run is visible only in agent_runs. PaymentError (order cannot take a link) is a business error and still returns text.
    @tool  # the docstring below is what the LLM reads
    def send_payment_link() -> str:
        """Email the payment link for the order created in this run to the customer, in the same mail thread. Takes no arguments. Call it once, after create_order."""
        if not run.order_id:  # no order made in this run
            return "No order exists yet. Call create_order first."  # plain text for the LLM
        try:  # the mail function can fail
            status = send_payment_link_mail(run.owner_id, run.order_id)  # owner and order come from code (D29)
        except PaymentError as exc:  # business error, for example payment_not_open or link_expired
            _step(run, "send_payment_link", "payment error", False)  # record the failure
            return f"A payment link cannot be sent for this order: {_exc_text(exc)[:200]}"  # plain text for the LLM
        except Exception:  # unexpected error
            _step(run, "send_payment_link", "unexpected error", False)  # record the failure
            raise  # let ToolRetryMiddleware or the worker handle it
        run.ended_reason = "link_sent"  # the job is finished
        _step(run, "send_payment_link", status, True)  # status is "sent" or "already_sent"
        if status == "already_sent":  # D39 guard said the mail was sent before
            return "The payment link was already mailed. The task is finished."  # plain text for the LLM
        return "The payment link was mailed to the customer. The task is finished."  # plain text for the LLM

    # DECISION PROBLEM: how do we stop ask_customer from becoming a spam or phishing tool when the LLM is fooled?
    # Options: (1) trust the LLM text, (2) cap the length, block links, and send only to the mail sender.
    # Chosen: option 2. Reason: the question text is the only free text we send out. A fooled LLM could put a phishing link in it.
    # Cost: a real question that needs a link is blocked. Daily volume is limited by D55 (5 runs per owner per day) plus one call per run (ToolCallLimit, set in the agent file).
    @tool  # the docstring below is what the LLM reads
    def ask_customer(question: str) -> str:
        """Ask the customer ONE short question by email when the order is unclear (unknown dish, missing quantity). Plain text, no links. After this tool, stop."""
        text = (question or "").strip()  # clean the text
        if run.already_handled:  # this mail already has an order from an earlier run
            _step(run, "ask_customer", "blocked: mail already handled", True)  # record it, no mail text
            return "This mail was already handled. Stop now and call no other tool."  # plain text for the LLM, no customer mail is sent
        if not text:  # nothing to send
            return "The question is empty."  # plain text for the LLM
        if len(text) > MAX_QUESTION_CHARS:  # too long
            return f"The question is too long. Keep it under {MAX_QUESTION_CHARS} characters."  # plain text for the LLM
        lowered = text.lower()  # for the link check
        if "http" in lowered or "www." in lowered:  # no links allowed
            return "The question must not contain links."  # plain text for the LLM
        name, address = _sender(run)  # who to write to, from the stored mail, never from the LLM
        if not address:  # header had no readable address
            return "The customer address could not be read from the mail."  # plain text for the LLM
        original = " ".join(run.subject.split()) or "your order"  # one-line subject, no line breaks
        subject = original if original.lower().startswith("re:") else f"Re: {original}"  # add Re: once, never twice
        reply_to = _wrap_id(run.message_id) if run.message_id else None  # same thread when we know the id (D27)
        body = f"Hi {name or 'there'},\n\n{text}\n\nThank you,\nThe restaurant team\n"  # greeting, question, sign-off, all plain text
        try:  # SMTP can fail
            send_mail(to=address, subject=subject, body=body, in_reply_to=reply_to)  # send in the same thread
        except Exception:  # any send failure
            log.exception("ask_customer mail failed for owner %s", run.owner_id)  # log with traceback
            _step(run, "ask_customer", "mail failed", False)  # record the failure
            return "The question could not be sent right now."  # plain text for the LLM
        run.ended_reason = "asked"  # the answer will arrive as a new mail and a new run (D50 = c)
        _step(run, "ask_customer", "question sent", True)  # record the success
        return "The question was sent to the customer. Stop now and call no other tool."  # plain text for the LLM

    @tool  # the docstring below is what the LLM reads
    def request_approval(action: str, reason: str) -> str:
        """Ask the restaurant owner to decide a risky case (large order, discount, cancel, refund, substitute dish). action must be one of: apply_discount, cancel_order, refund_order, accept_large_order, substitute_item. Give a short reason. After this tool, stop."""
        if action not in ALLOWED_ACTIONS:  # unknown action
            return f"Unknown action. Use one of: {', '.join(ALLOWED_ACTIONS)}."  # tell the LLM the valid list
        clean_reason = (reason or "").strip()[:MAX_REASON_CHARS]  # cut long reasons instead of rejecting them
        if not clean_reason:  # no reason given
            return "A short reason is required."  # plain text for the LLM
        try:  # the insert can fail
            (  # write the approval row
                db.table("approvals")  # write to the approvals table
                .insert(  # one new row
                    {  # column names confirmed in the handoff and the column query
                        "owner_id": run.owner_id,  # restaurant, from code
                        "order_id": run.order_id,  # may be None, the column allows null
                        "action": action,  # one of the allowed actions
                        "status": "pending",  # stored lowercase, the API maps it to uppercase
                        "reason": clean_reason,  # plain text, the dashboard must show it as text
                        "agent_run_id": run.agent_run_id,  # link to the run log, may be None in tests
                    }
                )
                .execute()  # send the insert
            )
        except Exception:  # any database problem
            log.exception("request_approval failed for owner %s", run.owner_id)  # log with traceback
            _step(run, "request_approval", "insert failed", False)  # record the failure
            return "The approval request could not be saved right now."  # plain text for the LLM
        run.ended_reason = "approval"  # the owner decides, the run ends (D49 = b)
        _step(run, "request_approval", f"approval requested: {action}", True)  # record the success
        return "The owner was asked to decide. Stop now and call no other tool."  # plain text for the LLM

    return [get_menu, create_order, send_payment_link, ask_customer, request_approval]  # the five tools for create_agent
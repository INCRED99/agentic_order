import logging
from dataclasses import dataclass, field
from email.utils import parseaddr

from langchain_core.tools import tool
from pydantic import BaseModel

from app.db import db
from app.inbox import send_mail
from app.payment_mail import send_payment_link_mail
from app.payments import PaymentError

log = logging.getLogger(__name__)

MAX_MENU_ROWS = 60
MAX_QUESTION_CHARS = 500
MAX_REASON_CHARS = 300
MAX_NAME_CHARS = 80
MAX_PER_DISH = 10          # NEW: more than this of one dish needs staff approval
MAX_TOTAL_PORTIONS = 25    # NEW: more than this in total needs staff approval
ALLOWED_ACTIONS = ("apply_discount", "cancel_order", "refund_order", "accept_large_order", "substitute_item")


def is_large_order(merged: dict[str, int]) -> bool:  # NEW: merged = dish uuid -> total quantity
    return any(q > MAX_PER_DISH for q in merged.values()) or sum(merged.values()) > MAX_TOTAL_PORTIONS


@dataclass
class RunContext:
    owner_id: str
    email_id: str
    from_email: str
    subject: str
    message_id: str
    agent_run_id: str | None = None
    menu_map: dict[int, str] = field(default_factory=dict)
    order_id: str | None = None
    ended_reason: str | None = None
    already_handled: bool = False
    steps: list[dict] = field(default_factory=list)


def make_run_context(owner_id: str, email_id: str, agent_run_id: str | None = None) -> RunContext:
    rows = (
        db.table("emails")
        .select("id,from_email,subject,gmail_message_id")
        .eq("id", email_id)
        .eq("owner_id", owner_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise ValueError("email not found for this owner")
    row = rows[0]
    return RunContext(
        owner_id=owner_id,
        email_id=row["id"],
        from_email=row.get("from_email") or "",
        subject=row.get("subject") or "",
        message_id=row.get("gmail_message_id") or "",
        agent_run_id=agent_run_id,
    )


def _first(rows):
    return rows[0] if rows else None


def _wrap_id(message_id: str) -> str:
    message_id = message_id.strip()
    if message_id.startswith("<") and message_id.endswith(">"):
        return message_id
    return f"<{message_id}>"


def _rupees(paise: int) -> str:
    return f"{paise / 100:.2f}"


def _exc_text(exc: Exception) -> str:
    return str(getattr(exc, "message", None) or exc)


def _step(run: RunContext, tool_name: str, summary: str, ok: bool) -> None:
    run.steps.append({"tool": tool_name, "summary": summary, "ok": ok})


def _sender(run: RunContext) -> tuple[str, str]:
    name, address = parseaddr(run.from_email)
    return name.strip()[:MAX_NAME_CHARS], address.strip().lower()


def _find_or_create_customer(run: RunContext) -> str | None:
    name, address = _sender(run)
    if not address:
        return None
    existing = _first(
        db.table("customers").select("id")
        .eq("owner_id", run.owner_id).eq("email", address)
        .limit(1).execute().data
    )
    if existing:
        return existing["id"]
    try:
        created = (
            db.table("customers")
            .insert({"owner_id": run.owner_id, "email": address, "name": name or None})
            .execute().data
        )
        if created:
            return created[0]["id"]
    except Exception:
        log.info("customer insert lost a race for owner %s, reading it again", run.owner_id)
    again = _first(
        db.table("customers").select("id")
        .eq("owner_id", run.owner_id).eq("email", address)
        .limit(1).execute().data
    )
    return again["id"] if again else None


ORDER_ERRORS = (
    ("too_many_lines", "Too many different dishes in one order. Ask the customer to split it.", False),
    ("quantity_too_large", "One quantity is too large for an automatic order. Ask the owner to approve a large order.", False),
    ("total_too_large", "The total is too large for an automatic order. Ask the owner to approve a large order.", False),
    ("item_unavailable", "A dish is not available right now.", True),
    ("insufficient_stock", "Not enough stock.", True),
    ("item_not_found", "A dish number was not found. Call get_menu again and use its numbers.", False),
    ("invalid_items", "The order lines are not valid.", False),
)


class OrderLine(BaseModel):
    item_no: int
    quantity: int


def build_tools(run: RunContext) -> list:
    @tool
    def get_menu() -> str:
        """List the dishes the restaurant can sell right now. Each line starts with a dish number. Use these numbers in create_order."""
        try:
            dishes = (
                db.table("menu_items")
                .select("id,name,price_paise,category")
                .eq("owner_id", run.owner_id)
                .eq("is_available", True)
                .order("category").order("name")
                .limit(MAX_MENU_ROWS)
                .execute().data
            )
            stock_rows = (
                db.table("inventory").select("menu_item_id,quantity")
                .eq("owner_id", run.owner_id).execute().data
            )
        except Exception:
            log.exception("get_menu failed for owner %s", run.owner_id)
            _step(run, "get_menu", "menu could not be loaded", False)
            return "The menu could not be loaded right now."
        stock = {row["menu_item_id"]: row["quantity"] for row in stock_rows}
        run.menu_map.clear()
        lines = []
        for number, dish in enumerate(dishes, start=1):
            run.menu_map[number] = dish["id"]
            if dish["id"] in stock:
                left = stock[dish["id"]]
                stock_text = "out of stock" if left <= 0 else f"stock {left}"
            else:
                stock_text = "stock not tracked"
            lines.append(f"{number}. {dish['name']} ({dish['category']}) - Rs {_rupees(dish['price_paise'])} - {stock_text}")
        _step(run, "get_menu", f"{len(lines)} dishes listed", True)
        if not lines:
            return "The menu is empty."
        return "\n".join(lines)

    @tool
    def create_order(items: list[OrderLine]) -> str:
        """Create a pending order from the customer's mail. items is a list of {item_no, quantity} using the dish numbers from get_menu. Call get_menu first. Never send prices."""
        if run.order_id:
            return "An order already exists for this mail. Call send_payment_link."
        if not items:
            return "The order has no dishes."
        merged: dict[str, int] = {}
        for line in items:
            dish_id = run.menu_map.get(line.item_no)
            if dish_id is None:
                return f"Dish number {line.item_no} is not on the menu list. Call get_menu and use its numbers."
            if line.quantity < 1:
                return "Every quantity must be at least 1."
            merged[dish_id] = merged.get(dish_id, 0) + line.quantity

        # NEW: code enforces the large-order rule, the LLM cannot skip it
        if is_large_order(merged):
            _step(run, "create_order", "blocked: large order", True)
            return ("This is a large order and needs staff approval. Do not create it. "
                    "Call request_approval with accept_large_order and the same items.")

        customer_id = _find_or_create_customer(run)
        if customer_id is None:
            _step(run, "create_order", "sender address unreadable", False)
            return "The customer address could not be read from the mail. Ask the owner for approval."
        payload = [{"menu_item_id": dish_id, "quantity": qty} for dish_id, qty in merged.items()]
        try:
            result = (
                db.rpc(
                    "create_pending_order",
                    {
                        "p_owner_id": run.owner_id,
                        "p_customer_id": customer_id,
                        "p_source_email_id": run.email_id,
                        "p_items": payload,
                    },
                )
                .execute().data
            )
        except Exception as exc:
            message = _exc_text(exc)
            for code, sentence, with_detail in ORDER_ERRORS:
                if code in message:
                    _step(run, "create_order", f"rejected: {code}", False)
                    return f"{sentence} ({message[:200]})" if with_detail else sentence
            log.exception("create_order failed for owner %s", run.owner_id)
            _step(run, "create_order", "unknown database error", False)
            return "The order could not be created right now."
        if isinstance(result, list):
            result = result[0] if result else {}
        order_id = (result or {}).get("order_id")
        if not order_id:
            _step(run, "create_order", "no order id returned", False)
            return "The order could not be created right now."
        run.order_id = str(order_id)
        total = _rupees(result.get("total_paise", 0))
        if result.get("already_existed"):
            run.already_handled = True
            _step(run, "create_order", "order already existed", True)
            return f"An order already exists for this mail, total Rs {total}. Nothing was changed. Call send_payment_link."
        # NEW: this return was missing, the LLM got None on success
        _step(run, "create_order", "order created", True)
        return f"Order created, total Rs {total}."

    @tool
    def send_payment_link(note: str | None = None) -> str:
        """Email the payment link for the order created in this run to the customer, in the same mail thread.
        If some requested dishes were not on the menu or were out of stock, pass a polite note in 'note' explaining that those dishes were excluded and the payment link is for the accepted items.
        Call it once, after create_order."""
        if not run.order_id:
            return "No order exists yet. Call create_order first."
        try:
            status = send_payment_link_mail(run.owner_id, run.order_id, intro=note)
        except PaymentError as exc:
            _step(run, "send_payment_link", "payment error", False)
            return f"A payment link cannot be sent for this order: {_exc_text(exc)[:200]}"
        except Exception:
            _step(run, "send_payment_link", "unexpected error", False)
            raise
        run.ended_reason = "link_sent"
        _step(run, "send_payment_link", status, True)
        if status == "already_sent":
            return "The payment link was already mailed. The task is finished."
        return "The payment link was mailed to the customer. The task is finished."

    @tool
    def ask_customer(question: str) -> str:
        """Ask the customer ONE short question by email when the order is unclear (unknown dish, missing quantity). Plain text, no links. After this tool, stop."""
        text = (question or "").strip()
        if run.already_handled:
            _step(run, "ask_customer", "blocked: mail already handled", True)
            return "This mail was already handled. Stop now and call no other tool."
        if not text:
            return "The question is empty."
        if len(text) > MAX_QUESTION_CHARS:
            return f"The question is too long. Keep it under {MAX_QUESTION_CHARS} characters."
        lowered = text.lower()
        if "http" in lowered or "www." in lowered:
            return "The question must not contain links."
        name, address = _sender(run)
        if not address:
            return "The customer address could not be read from the mail."
        original = " ".join(run.subject.split()) or "your order"
        subject = original if original.lower().startswith("re:") else f"Re: {original}"
        reply_to = _wrap_id(run.message_id) if run.message_id else None
        body = f"Hi {name or 'there'},\n\n{text}\n\nThank you,\nThe restaurant team\n"
        try:
            send_mail(to=address, subject=subject, body=body, in_reply_to=reply_to)
        except Exception:
            log.exception("ask_customer mail failed for owner %s", run.owner_id)
            _step(run, "ask_customer", "mail failed", False)
            return "The question could not be sent right now."
        run.ended_reason = "asked"
        _step(run, "ask_customer", "question sent", True)
        return "The question was sent to the customer. Stop now and call no other tool."

    @tool
    def request_approval(
        action: str,
        reason: str,
        discount_percent: int | None = None,  # NEW
        items: list[OrderLine] | None = None,  # NEW
    ) -> str:
        """Ask the restaurant owner to decide a risky case (large order, discount, cancel, refund, substitute dish). action must be one of: apply_discount, cancel_order, refund_order, accept_large_order, substitute_item. Give a short reason. For apply_discount also give discount_percent (1 to 100). For accept_large_order give items using the dish numbers from get_menu. After this tool, stop."""
        if action not in ALLOWED_ACTIONS:
            return f"Unknown action. Use one of: {', '.join(ALLOWED_ACTIONS)}."
        clean_reason = (reason or "").strip()[:MAX_REASON_CHARS]
        if not clean_reason:
            return "A short reason is required."
        if action == "apply_discount":
            if discount_percent is None:
                discount_percent = 10
            else:
                try:
                    discount_percent = max(1, min(100, int(discount_percent)))
                except (ValueError, TypeError):
                    discount_percent = 10

        payload = None  # NEW: items are stored so the owner's approval can create the order later
        if items:
            lines = []
            for line in items:
                dish_id = run.menu_map.get(line.item_no)
                if dish_id is None or line.quantity < 1:
                    return "Items are not valid. Call get_menu and use its numbers."
                lines.append({"menu_item_id": dish_id, "quantity": line.quantity})
            payload = {"items": lines}
        if action == "accept_large_order" and not payload:
            return "accept_large_order needs the items. Call get_menu first, then send items."

        try:
            (
                db.table("approvals")
                .insert(
                    {
                        "owner_id": run.owner_id,
                        "order_id": run.order_id,
                        "action": action,
                        "status": "pending",
                        "reason": clean_reason,
                        "agent_run_id": run.agent_run_id,
                        "discount_percent": discount_percent if action == "apply_discount" else None,  # NEW
                        "payload": payload,  # NEW
                        "source_email_id": run.email_id,  # NEW
                    }
                )
                .execute()
            )
        except Exception:
            log.exception("request_approval failed for owner %s", run.owner_id)
            _step(run, "request_approval", "insert failed", False)
            return "The approval request could not be saved right now."
        run.ended_reason = "approval"
        _step(run, "request_approval", f"approval requested: {action}", True)
        return "The owner was asked to decide. Stop now and call no other tool."

    return [get_menu, create_order, send_payment_link, ask_customer, request_approval]
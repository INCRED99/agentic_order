import logging
from datetime import datetime, timezone

from app.db import db
from app.inbox import send_mail
from app.payments import get_or_create_payment_link

log = logging.getLogger(__name__)


def _first(rows):
    return rows[0] if rows else None


def _wrap_id(message_id: str) -> str:
    message_id = message_id.strip()
    if message_id.startswith("<") and message_id.endswith(">"):
        return message_id
    return f"<{message_id}>"


def send_payment_link_mail(owner_id: str, order_id: str, intro: str | None = None, force: bool = False) -> str:
    get_or_create_payment_link(owner_id, order_id)
    pay = _first(
        db.table("payments")
        .select("payment_link_url,payment_link_expires_at")
        .eq("order_id", order_id)
        .eq("owner_id", owner_id)
        .limit(1)
        .execute()
        .data
    )
    if pay is None or not pay.get("payment_link_url"):
        raise RuntimeError("payment link missing after get_or_create_payment_link")

    claim_time = datetime.now(timezone.utc).isoformat()
    if not force:
        claimed = (
            db.table("payments")
            .update({"link_emailed_at": claim_time})
            .eq("order_id", order_id)
            .eq("owner_id", owner_id)
            .is_("link_emailed_at", "null")
            .execute()
            .data
        )
        if not claimed:
            return "already_sent"
    else:
        db.table("payments").update({"link_emailed_at": claim_time}).eq("order_id", order_id).eq("owner_id", owner_id).execute()

    try:
        order = _first(
            db.table("orders")
            .select("customer_id,source_email_id,total_paise")
            .eq("id", order_id)
            .eq("owner_id", owner_id)
            .limit(1)
            .execute()
            .data
        )
        if order is None:
            raise RuntimeError("order vanished before the mail")
        customer = _first(
            db.table("customers")
            .select("email,name")
            .eq("id", order["customer_id"])
            .eq("owner_id", owner_id)
            .limit(1)
            .execute()
            .data
        )
        if customer is None or not customer.get("email"):
            raise RuntimeError("customer email missing")
        source = None
        if order.get("source_email_id"):
            source = _first(
                db.table("emails")
                .select("gmail_message_id,subject")
                .eq("id", order["source_email_id"])
                .eq("owner_id", owner_id)
                .limit(1)
                .execute()
                .data
            )
        subject = "Your payment link"
        reply_to = None
        if source:
            original = (source.get("subject") or "your order").strip()
            subject = original if original.lower().startswith("re:") else f"Re: {original}"
            if source.get("gmail_message_id"):
                reply_to = _wrap_id(source["gmail_message_id"])
        rupees = order["total_paise"] / 100
        intro_text = f"{intro}\n\n" if intro else ""  # NEW
        body = (
            f"Hi {customer.get('name') or 'there'},\n\n"
            f"{intro_text}"  # NEW: approval text and link travel in ONE mail
            f"Your order total is Rs {rupees:.2f}.\n"
            f"Pay here: {pay['payment_link_url']}\n\n"
            "This link works for 24 hours. After that, please send a new order.\n"
        )
        send_mail(to=customer["email"], subject=subject, body=body, in_reply_to=reply_to)
    except Exception:
        (
            db.table("payments")
            .update({"link_emailed_at": None})
            .eq("order_id", order_id)
            .eq("owner_id", owner_id)
            .eq("link_emailed_at", claim_time)
            .execute()
        )
        log.exception("payment link mail failed for order %s, claim reset", order_id)
        raise
    return "sent"
import logging  # write problems to the server log
from datetime import datetime, timezone  # timestamp for the claim

from app.db import db  # shared Supabase client (service role, every query MUST filter by owner_id)
from app.inbox import send_mail  # SMTP sender: send_mail(to, subject, body, in_reply_to=None)
from app.payments import get_or_create_payment_link  # D25/D32: creates the link or reuses the stored one

log = logging.getLogger(__name__)  # logger named after this file

# DECISION PROBLEM (D39, chosen by the user): how to stop a double send of the link mail.
# Options: (a) DB flag claimed with one update, (b) search the Gmail Sent folder, (c) no guard.
# Chosen: a. Reason: one atomic update says who won, same claim-first idea as D32.
# Cost: if SMTP fails after the claim, we must reset the flag, or the mail never goes.

# DECISION PROBLEM (open, small): what if SMTP sent the mail but then raised (timeout after delivery)?
# Option 1: reset the flag, the retry may send a second mail (at-least-once).
# Option 2: keep the flag, the customer may get no mail (at-most-once).
# Chosen here: option 1. Reason: a missing payment link loses the sale, a double link only annoys.
# The link is the same URL, so a double mail cannot cause a double charge.


def _first(rows):  # supabase returns a list of rows, we want one row or None
    return rows[0] if rows else None  # first row, or None when nothing matched


def _wrap_id(message_id: str) -> str:  # In-Reply-To needs angle brackets around the id
    message_id = message_id.strip()  # remove stray spaces
    if message_id.startswith("<") and message_id.endswith(">"):  # already wrapped
        return message_id  # keep as it is
    return f"<{message_id}>"  # add the brackets


def send_payment_link_mail(owner_id: str, order_id: str) -> str:  # returns "sent" or "already_sent"
    get_or_create_payment_link(owner_id, order_id)  # step 1: make sure the link exists (raises PaymentError if the order cannot take one)
    pay = _first(  # step 2: read the link from OUR database, not from the return value
        db.table("payments")  # read from the payments table
        .select("payment_link_url,payment_link_expires_at")  # the two facts the mail needs
        .eq("order_id", order_id)  # this order
        .eq("owner_id", owner_id)  # owner guard
        .limit(1)  # one row (unique order_id)
        .execute()  # send the query
        .data  # the list of rows
    )
    if pay is None or not pay.get("payment_link_url"):  # link missing after creation
        raise RuntimeError("payment link missing after get_or_create_payment_link")  # loud failure, ToolRetry or the caller handles it

    claim_time = datetime.now(timezone.utc).isoformat()  # the claim timestamp
    claimed = (  # step 3: claim first (D39). One update, only one caller can change null to a value
        db.table("payments")  # update the payments table
        .update({"link_emailed_at": claim_time})  # mark "a sender took this job"
        .eq("order_id", order_id)  # this order
        .eq("owner_id", owner_id)  # owner guard
        .is_("link_emailed_at", "null")  # ONLY if nobody claimed before: this line is the whole guard
        .execute()  # send the update
        .data  # rows that really changed
    )
    if not claimed:  # zero rows changed: another call already claimed
        return "already_sent"  # do nothing, this is the safe answer

    try:  # step 4: from here a failure must give the claim back
        order = _first(  # load the order
            db.table("orders")  # read from the orders table
            .select("customer_id,source_email_id,total_paise")  # customer, original mail, amount
            .eq("id", order_id)  # this order
            .eq("owner_id", owner_id)  # owner guard
            .limit(1)  # one row
            .execute()  # send the query
            .data  # the list of rows
        )
        if order is None:  # should not happen, get_or_create_payment_link checked it
            raise RuntimeError("order vanished before the mail")  # loud failure
        customer = _first(  # load the customer email
            db.table("customers")  # read from the customers table
            .select("email,name")  # what the mail needs
            .eq("id", order["customer_id"])  # customer of this order
            .eq("owner_id", owner_id)  # owner guard
            .limit(1)  # one row
            .execute()  # send the query
            .data  # the list of rows
        )
        if customer is None or not customer.get("email"):  # nobody to write to
            raise RuntimeError("customer email missing")  # loud failure
        source = None  # the original order mail, may be missing
        if order.get("source_email_id"):  # only look when the order knows its mail
            source = _first(  # load the original mail
                db.table("emails")  # read from the emails table
                .select("gmail_message_id,subject")  # threading id and subject
                .eq("id", order["source_email_id"])  # the order mail
                .eq("owner_id", owner_id)  # owner guard
                .limit(1)  # one row
                .execute()  # send the query
                .data  # the list of rows
            )
        subject = "Your payment link"  # fallback subject when there is no original mail
        reply_to = None  # fallback: new thread
        if source:  # same-thread reply (D27)
            original = (source.get("subject") or "your order").strip()  # original subject text
            subject = original if original.lower().startswith("re:") else f"Re: {original}"  # add Re: once, never twice
            if source.get("gmail_message_id"):  # we know the RFC Message-ID
                reply_to = _wrap_id(source["gmail_message_id"])  # In-Reply-To keeps the thread
        rupees = order["total_paise"] / 100  # paise to rupees for the text only, money stays integer in the DB
        body = (  # plain text body
            f"Hi {customer.get('name') or 'there'},\n\n"  # greeting
            f"Your order total is Rs {rupees:.2f}.\n"  # amount from the stored total, never from the agent (D29)
            f"Pay here: {pay['payment_link_url']}\n\n"  # the link
            "This link works for 24 hours. After that, please send a new order.\n"  # D26 and D30 in plain words
        )
        send_mail(to=customer["email"], subject=subject, body=body, in_reply_to=reply_to)  # step 5: send in the same thread
    except Exception:  # any failure after the claim
        (  # give the claim back so a retry can send
            db.table("payments")  # update the payments table
            .update({"link_emailed_at": None})  # reset to "not sent"
            .eq("order_id", order_id)  # this order
            .eq("owner_id", owner_id)  # owner guard
            .eq("link_emailed_at", claim_time)  # reset ONLY our own claim, never someone else's
            .execute()  # send the update
        )
        log.exception("payment link mail failed for order %s, claim reset", order_id)  # log with traceback
        raise  # let the caller (ToolRetry) see the failure
    return "sent"  # done
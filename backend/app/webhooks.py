import json  # parse the webhook body after the signature is verified
import logging  # write problems to the server log instead of losing them

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request  # router, post-response tasks, 401 error, raw request access
from starlette.concurrency import run_in_threadpool  # run our sync database code without blocking the event loop

from app.db import db  # shared Supabase client (service role, bypasses RLS)
from app.inbox import send_mail  # SMTP sender, signature: send_mail(to, subject, body, in_reply_to=None)  (CHECK the import path)
from app.razorpay_client import verify_webhook_signature  # HMAC check, signature: (raw_body, signature_header)

log = logging.getLogger(__name__)  # logger named after this file

router = APIRouter(prefix="/webhooks", tags=["webhooks"])  # every route below starts with /webhooks

REFUND_ACTION = "refund_order"  # action name the Approvals UI already knows (D38, found in Approvals.tsx)

# DECISION PROBLEM (D36, chosen by the user): when to send the confirmation mail.
# Options: (1) inside the request, (2) after the response with BackgroundTasks, (3) a mail queue.
# Chosen: option 2. Reason: Razorpay waits for our answer, and SMTP can be slow.
# Cost: if the server dies after responding, the mail is lost. A mail queue fixes that (V2).


def _first(rows):  # supabase returns a list of rows, we want one row or None
    return rows[0] if rows else None  # first row, or None when nothing matched


def _load(order_id: str):  # read the order and its payment row from OUR database
    order = _first(  # one order or None
        db.table("orders")  # read from the orders table
        .select("id,owner_id,status,total_paise,customer_id")  # only the columns this handler needs
        .eq("id", order_id)  # find by id (no owner filter yet: owner_id comes FROM this row, never from the webhook body)
        .limit(1)  # at most one row
        .execute()  # send the query
        .data  # the list of rows
    )
    if order is None:  # unknown order id
        return None, None  # nothing else to load
    payment = _first(  # one payment row or None (unique order_id, from 008)
        db.table("payments")  # read from the payments table
        .select("id,razorpay_payment_link_id,razorpay_payment_id,status")  # columns needed for checks
        .eq("order_id", order["id"])  # the payment row of this order
        .eq("owner_id", order["owner_id"])  # owner guard, owner_id taken from the DB row
        .limit(1)  # at most one row
        .execute()  # send the query
        .data  # the list of rows
    )
    return order, payment  # both may be used by the caller


def _create_refund_approval(order: dict, payment_id: str, amount: int, why: str):  # D37: owner decides about the refund
    existing = (  # look for a refund approval already made for this same payment (webhook retries)
        db.table("approvals")  # read from the approvals table
        .select("id")  # only need to know if one exists
        .eq("owner_id", order["owner_id"])  # owner guard
        .eq("order_id", order["id"])  # same order
        .eq("action", REFUND_ACTION)  # same kind of approval
        .like("reason", f"%{payment_id}%")  # reason text contains the payment id, so one payment gives one approval
        .limit(1)  # one is enough
        .execute()  # send the query
        .data  # the list of rows
    )
    if existing:  # already created by an earlier delivery of this webhook
        return  # do nothing, stay idempotent
    db.table("approvals").insert(  # create the approval for the owner
        {  # one row
            "owner_id": order["owner_id"],  # owner from the DB row
            "order_id": order["id"],  # which order
            "action": REFUND_ACTION,  # the UI shows this as "Refund order"
            "status": "pending",  # waits for the owner decision
            "reason": f"{why} (razorpay payment {payment_id}, amount {amount} paise)",  # human text plus the payment id used above
        }  # end of row
    ).execute()  # send the insert


def _send_confirmation(owner_id: str, customer_id: str, order_id: str, outcome: str):  # runs AFTER the response (D36)
    try:  # a mail failure must never undo a PAID order
        customer = _first(  # find the customer email
            db.table("customers")  # read from the customers table
            .select("email,name")  # only what the mail needs
            .eq("id", customer_id)  # the customer of this order
            .eq("owner_id", owner_id)  # owner guard
            .limit(1)  # one row
            .execute()  # send the query
            .data  # the list of rows
        )
        if customer is None or not customer.get("email"):  # no address to write to
            log.error("confirmation mail skipped, no customer email for order %s", order_id)  # leave a trace
            return  # stop here
        if outcome == "paid_out_of_stock":  # D20: paid but stock was short
            body = (  # honest text, the owner is reviewing
                "We received your payment, thank you. One item is short on stock, "
                "so the restaurant will contact you shortly about your order.\n"
            )
        else:  # normal case
            body = "We received your payment, thank you. Your order is confirmed and the kitchen has it.\n"  # normal text
        send_mail(  # send through our own SMTP
            to=customer["email"],  # customer address
            subject=f"Payment received for your order {order_id[:8]}",  # short order reference
            body=body,  # text chosen above
            # TODO: pass in_reply_to=<original message id> to keep the same thread. Needs the stored Message-ID of the order mail.
        )
    except Exception:  # any mail error
        log.exception("confirmation mail failed for order %s (order stays PAID)", order_id)  # log with traceback


def _process(raw: bytes, signature: str):  # all sync work, returns (http_status_text, mail_job_or_None)
    if not verify_webhook_signature(raw, signature):  # step 1: forged or corrupted body
        raise HTTPException(status_code=401, detail="bad signature")  # reject, Razorpay will not trust this path
    body = json.loads(raw)  # safe to parse now, the sender is proven
    if body.get("event") != "payment_link.paid":  # step 2: only this event matters
        return "ignored", None  # return 200, never make Razorpay retry other events
    # UNVERIFIED payload names (written from memory of the docs). Verify with a real test payment (D35).
    link = body.get("payload", {}).get("payment_link", {}).get("entity", {})  # the payment link object
    pay = body.get("payload", {}).get("payment", {}).get("entity", {})  # the payment object
    link_id = link.get("id")  # Razorpay link id
    order_id = link.get("reference_id")  # our order id (D25: reference_id = order_id)
    payment_id = pay.get("id")  # Razorpay payment id, the idempotency key
    amount = pay.get("amount")  # paid amount in paise
    if not (link_id and order_id and payment_id and isinstance(amount, int)):  # any field missing
        log.error("webhook payload missing fields: %s", list(body.get("payload", {}).keys()))  # trace without dumping the body
        return "bad_payload", None  # 200 on purpose, retrying will not fix a payload shape problem
    order, payment = _load(order_id)  # step 3: load from OUR database
    if order is None or payment is None:  # order or payment row unknown
        log.error("webhook for unknown order %s", order_id)  # trace it
        return "order_not_found", None  # 200, nothing to do
    if payment.get("razorpay_payment_link_id") != link_id:  # the link in the body is not the link we stored
        log.error("link id mismatch for order %s", order_id)  # suspicious, trace it
        return "link_mismatch", None  # 200, do not trust it
    if payment.get("razorpay_payment_id") == payment_id:  # this exact payment was processed before
        return "already_paid", None  # duplicate delivery, do nothing (idempotency)
    if order["status"] != "PENDING":  # step 4: money arrived for an order that cannot take it (D37)
        _create_refund_approval(order, payment_id, amount, f"Payment arrived but order is {order['status']}")  # owner decides
        return "refund_approval", None  # 200
    if amount != order["total_paise"]:  # amount differs from the stored total (D37)
        _create_refund_approval(order, payment_id, amount, f"Amount {amount} differs from total {order['total_paise']}")  # owner decides
        return "refund_approval", None  # 200
    try:  # step 5: one Postgres function does the whole PAID transition
               res = db.rpc(  # call the function
            "mark_order_paid",  # created by 006
            {  # parameter names must match 006 exactly
                "p_owner_id": order["owner_id"],  # owner from the DB row
                "p_order_id": order["id"],  # the order
                "p_payment_link_id": link_id,  # the link id
                "p_payment_id": payment_id,  # the payment id
                "p_amount_paise": amount,  # the amount
            },
        ).execute()  # send the call
    except Exception as exc:  # the function raises named errors
        text = str(exc)  # error text contains the name
        if "order_not_pending" in text or "amount_mismatch" in text:  # race: state changed after our checks
            _create_refund_approval(order, payment_id, amount, f"mark_order_paid refused: {text[:80]}")  # owner decides
            return "refund_approval", None  # 200
        if "order_not_found" in text:  # order vanished
            log.error("mark_order_paid: order_not_found %s", order_id)  # trace it
            return "order_not_found", None  # 200
        raise  # unknown error: let it become a 500, Razorpay retries later
    outcome = str(res.data)  # result word, shape not verified (CHECK: could be dict)
    if "already_paid" in outcome:  # another request won the race
        return "already_paid", None  # 200, no mail
    kind = "paid_out_of_stock" if "paid_out_of_stock" in outcome else "paid"  # pick mail text
    return kind, (order["owner_id"], order["customer_id"], order["id"], kind)  # mail job for after the response


@router.post("/razorpay")  # POST /webhooks/razorpay
async def razorpay_webhook(request: Request, background: BackgroundTasks):  # async only because reading the raw body needs await
    raw = await request.body()  # raw bytes FIRST, the signature is computed over exactly these bytes
    signature = request.headers.get("X-Razorpay-Signature", "")  # signature header, empty string if missing
    result, mail_job = await run_in_threadpool(_process, raw, signature)  # run the sync logic in a worker thread
    if mail_job is not None:  # a confirmation mail is due
        background.add_task(_send_confirmation, *mail_job)  # runs after the response is sent (D36)
    return {"ok": True, "result": result}  # 200 so Razorpay stops retrying
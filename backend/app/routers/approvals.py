import logging  # log lines for failures that must not break the request
from datetime import datetime, timezone  # used to stamp the decision time in UTC
from email.utils import parseaddr  # pulls the plain address out of "Name <a@b.com>"

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query  # BackgroundTasks runs the mail after the response is sent
from postgrest.exceptions import APIError  # error raised when Postgres rejects a query, has a .code

from app.db import db  # the shared Supabase client (service role, bypasses RLS)
from app.deps import current_user_id  # verifies the token and returns the owner_id
from app.inbox import send_mail  # sends a mail through our SMTP account
from app.payment_mail import send_payment_link_mail
from app.agent_tools import _find_or_create_customer, make_run_context
from app.schemas import ApprovalOut  # response shape, defined in schemas.py

log = logging.getLogger("approvals")  # logger name shown in every line
# Logging rule: ids and reasons only, never mail bodies, subjects or approval reasons.

router = APIRouter(prefix="/approvals", tags=["approvals"])  # every route below starts with /approvals
COLS = "id,order_id,action,reason,status,created_at,decided_at"  # the fields the UI needs (needs migration 005)
ORDER_ACTIONS = {"apply_discount", "accept_large_order", "substitute_item"}  # requests about a new order, a reject can invite a normal re-order
SIGN_OFF = "\n\nThank you,\nThe restaurant team\n"  # same closing as the agent's mails


def _to_approval(row: dict) -> dict:  # database row -> ApprovalOut shape
    return {  # the shape the UI expects
        "id": row["id"],  # approval id
        "order_id": row.get("order_id"),  # None when the approval is not about an order
        "action": row["action"],  # for example accept_large_order
        "reason": row.get("reason") or "",  # empty text replaces null, so the UI always gets a string
        "status": row["status"].upper(),  # D1: database stores lowercase, the UI expects uppercase
        "created_at": row["created_at"],  # ISO timestamp string
        "decided_at": row.get("decided_at"),  # None while pending
    }


@router.get("", response_model=list[ApprovalOut])  # GET /approvals
def list_approvals(  # newest approvals first
    owner_id: str = Depends(current_user_id),  # owner_id comes from the verified token only
    limit: int = Query(100, ge=1, le=200),  # page size, default 100, max 200
):
    res = (  # build the query step by step
        db.table("approvals")  # read from the approvals table
        .select(COLS)  # only the fields we need
        .eq("owner_id", owner_id)  # THE guard: without this line every restaurant's approvals would leak
        .order("created_at", desc=True)  # newest first
        .limit(limit)  # cap the result size
        .execute()  # send the query to Supabase
    )
    return [_to_approval(r) for r in res.data]  # convert each row, FastAPI turns the list into JSON


# DECISION PROBLEM: two clicks (or two browser tabs) can decide the same approval at the same time.
# Options: (1) read the status, then update, (2) one UPDATE that only matches rows still pending.
# Chosen: option 2. Reason: the database checks "still pending" and writes in one step, so a race cannot decide twice.
# Cost: when nothing was updated we run a second query to tell "not found" (404) from "already decided" (409).
# D49: the decision is recorded here. The effect and the customer mail are done by _finish, after this succeeds.
def _decide(owner_id: str, approval_id: str, new_status: str) -> dict:  # shared by approve and reject, returns the RAW database row
    try:  # database calls can fail
        res = (  # build the update
            db.table("approvals")  # target table
            .update({"status": new_status, "decided_at": datetime.now(timezone.utc).isoformat()})  # new status and the time of the decision
            .eq("id", approval_id)  # which approval
            .eq("owner_id", owner_id)  # and it must belong to this owner, an id alone is not enough
            .eq("status", "pending")  # and it must still be pending, this line blocks double decisions
            .execute()  # send it
        )
        if res.data:  # one row changed, the decision is saved
            return res.data[0]  # the raw row, _finish needs agent_run_id and order_id from it
        exists = (  # nothing changed, find out why
            db.table("approvals")  # target table
            .select("id")  # only the id
            .eq("id", approval_id)  # which approval
            .eq("owner_id", owner_id)  # only this owner's approvals
            .limit(1)  # at most one row
            .execute()  # send it
        )
    except APIError as e:  # for example an id that is not a valid UUID
        if e.code == "22P02":  # 22P02 = invalid text representation
            raise HTTPException(404, "Approval not found")  # a malformed id is just "not found"
        raise HTTPException(500, "Database error")  # anything else is unexpected
    if not exists.data:  # no such approval for this owner
        raise HTTPException(404, "Approval not found")  # same answer for "no such id" and "not yours", so ids cannot be probed
    raise HTTPException(409, "Approval was already decided")  # it exists but is no longer pending


def _thread_id(message_id: str | None) -> str | None:  # A11: make sure the Message-ID has angle brackets
    mid = (message_id or "").strip()  # clean the text
    if not mid:  # nothing stored
        return None  # no threading
    return mid if mid.startswith("<") else f"<{mid}>"  # add brackets when missing


def _rupees(paise: int) -> str:
    return f"{paise / 100:.2f}"


def _find_recipient(owner_id: str, row: dict) -> tuple[str, str, str | None] | None:
    source_eid = row.get("source_email_id")
    if source_eid:
        mails = (
            db.table("emails")
            .select("from_email,subject,gmail_message_id")
            .eq("id", source_eid)
            .eq("owner_id", owner_id)
            .limit(1)
            .execute()
            .data
        )
        if mails:
            address = parseaddr(mails[0].get("from_email") or "")[1]
            if address:
                base = " ".join((mails[0].get("subject") or "").split()) or "your order"
                subject = base if base.lower().startswith("re:") else f"Re: {base}"
                return address, subject, _thread_id(mails[0].get("gmail_message_id"))

    run_id = row.get("agent_run_id")
    if run_id:
        runs = db.table("agent_runs").select("email_id").eq("id", run_id).eq("owner_id", owner_id).limit(1).execute().data
        if runs:
            mails = (
                db.table("emails")
                .select("from_email,subject,gmail_message_id")
                .eq("id", runs[0]["email_id"])
                .eq("owner_id", owner_id)
                .limit(1)
                .execute()
                .data
            )
            if mails:
                address = parseaddr(mails[0].get("from_email") or "")[1]
                if address:
                    base = " ".join((mails[0].get("subject") or "").split()) or "your order"
                    subject = base if base.lower().startswith("re:") else f"Re: {base}"
                    return address, subject, _thread_id(mails[0].get("gmail_message_id"))

    order_id = row.get("order_id")
    if order_id:
        orders = db.table("orders").select("customer_id,source_email_id").eq("id", order_id).eq("owner_id", owner_id).limit(1).execute().data
        if orders:
            if orders[0].get("source_email_id"):
                mails = db.table("emails").select("from_email,subject,gmail_message_id").eq("id", orders[0]["source_email_id"]).eq("owner_id", owner_id).limit(1).execute().data
                if mails:
                    address = parseaddr(mails[0].get("from_email") or "")[1]
                    if address:
                        base = " ".join((mails[0].get("subject") or "").split()) or "your order"
                        subject = base if base.lower().startswith("re:") else f"Re: {base}"
                        return address, subject, _thread_id(mails[0].get("gmail_message_id"))
            customers = db.table("customers").select("email").eq("id", orders[0]["customer_id"]).eq("owner_id", owner_id).limit(1).execute().data
            if customers and customers[0].get("email"):
                return customers[0]["email"], "Your order", None

    return None


def _send_customer_mail(owner_id: str, row: dict, body: str) -> None:
    target = _find_recipient(owner_id, row)
    if not target:
        log.warning("approval %s decided, no recipient found", row.get("id"))
        return
    address, subject, in_reply_to = target
    full_body = f"Hello,\n\n{body}{SIGN_OFF}"
    send_mail(to=address, subject=subject, body=full_body, in_reply_to=in_reply_to)


def _cancel_pending_order(owner_id: str, order_id: str) -> bool:
    res = (
        db.table("orders")
        .update({"status": "CANCELLED"})
        .eq("id", order_id)
        .eq("owner_id", owner_id)
        .eq("status", "PENDING")
        .execute()
    )
    return bool(res.data)


def _process_approval_decision(owner_id: str, row: dict, approved: bool) -> None:
    action = row.get("action")
    order_id = row.get("order_id")
    pct = row.get("discount_percent") or 10

    # Fallback: if order_id is missing, look up order by source_email_id
    if not order_id and row.get("source_email_id"):
        order_rows = (
            db.table("orders")
            .select("id")
            .eq("source_email_id", row["source_email_id"])
            .eq("owner_id", owner_id)
            .limit(1)
            .execute()
            .data
        )
        if order_rows:
            order_id = order_rows[0]["id"]

    try:
        # 1. APPLY DISCOUNT
        if action == "apply_discount":
            if order_id:
                order_rows = (
                    db.table("orders")
                    .select("id,status,total_paise,original_total_paise")
                    .eq("id", order_id)
                    .eq("owner_id", owner_id)
                    .limit(1)
                    .execute()
                    .data
                )
                if not order_rows:
                    log.warning("order %s not found for approval %s", order_id, row.get("id"))
                    return
                order = order_rows[0]

                if approved:
                    if order.get("status") != "PENDING":
                        _send_customer_mail(owner_id, row, "This order is no longer pending. Please send a new order if you would like to place an order.")
                        return
                    original = order.get("original_total_paise") or order["total_paise"]
                    new_total = original * (100 - pct) // 100
                    db.table("orders").update({
                        "original_total_paise": original,
                        "total_paise": new_total,
                        "discount_percent": pct,
                    }).eq("id", order_id).eq("owner_id", owner_id).execute()

                    intro = (
                        f"Great news! Your request for a {pct}% discount has been approved by the restaurant.\n"
                        f"Your discounted order total is Rs {_rupees(new_total)} (discounted from Rs {_rupees(original)})."
                    )
                    send_payment_link_mail(owner_id, order_id, intro=intro, force=True)
                else:
                    # Discount REJECTED, but the order is accepted at the regular menu price!
                    intro = (
                        f"Your request for a {pct}% discount could not be approved by the restaurant staff.\n"
                        f"However, your order for the accepted menu items has been confirmed at the regular price of Rs {_rupees(order['total_paise'])}."
                    )
                    send_payment_link_mail(owner_id, order_id, intro=intro, force=True)
                return

            else:
                # Customer asked for discount without dishes
                if approved:
                    _send_customer_mail(owner_id, row, f"Your request for a {pct}% discount has been approved! Please reply to this email with the dishes you want to order, and we will apply your discount.")
                else:
                    _send_customer_mail(owner_id, row, "Your request for a discount could not be approved by the restaurant staff.")
                return

        # 2. ACCEPT LARGE ORDER
        if action == "accept_large_order":
            if approved:
                if not order_id and row.get("payload", {}).get("items") and row.get("source_email_id"):
                    run = make_run_context(owner_id, row["source_email_id"])
                    customer_id = _find_or_create_customer(run)
                    if customer_id:
                        res = db.rpc("create_pending_order", {
                            "p_owner_id": owner_id,
                            "p_customer_id": customer_id,
                            "p_source_email_id": row["source_email_id"],
                            "p_items": row["payload"]["items"],
                        }).execute().data
                        if isinstance(res, list):
                            res = res[0] if res else {}
                        order_id = (res or {}).get("order_id")
                        if order_id:
                            db.table("approvals").update({"order_id": order_id}).eq("id", row["id"]).execute()

                if order_id:
                    order_rows = db.table("orders").select("total_paise").eq("id", order_id).eq("owner_id", owner_id).limit(1).execute().data
                    total_text = f"Rs {_rupees(order_rows[0]['total_paise'])}" if order_rows else ""
                    intro = f"Your large order has been approved by the restaurant team! {('Total: ' + total_text) if total_text else ''}"
                    send_payment_link_mail(owner_id, str(order_id), intro=intro, force=True)
                else:
                    _send_customer_mail(owner_id, row, "Your large order has been approved. The restaurant team will contact you shortly.")
            else:
                _send_customer_mail(owner_id, row, "Your large order request could not be accepted at this time due to kitchen capacity. You are welcome to place a smaller order from our regular menu.")
            return

        # 3. CANCEL ORDER
        if action == "cancel_order":
            if approved:
                if order_id:
                    _cancel_pending_order(owner_id, order_id)
                _send_customer_mail(owner_id, row, "Your order cancellation request has been approved. Your order has been cancelled and no payment is needed.")
            else:
                _send_customer_mail(owner_id, row, "Your cancellation request could not be approved because your order is already being prepared by the kitchen.")
            return

        # 4. REFUND ORDER
        if action == "refund_order":
            if approved:
                _send_customer_mail(owner_id, row, "Your refund request has been approved. The restaurant team will process your refund shortly.")
            else:
                _send_customer_mail(owner_id, row, "Your refund request could not be approved. Please contact the restaurant directly if you have any questions.")
            return

        # 5. SUBSTITUTE ITEM
        if action == "substitute_item":
            if approved:
                _send_customer_mail(owner_id, row, "Your item substitution request has been approved! The kitchen will prepare your updated items.")
            else:
                _send_customer_mail(owner_id, row, "Your item substitution request could not be approved. Your order will be prepared with the original menu items.")
            return

        # FALLBACK
        if approved:
            _send_customer_mail(owner_id, row, "The restaurant team has approved your request.")
        else:
            _send_customer_mail(owner_id, row, "The restaurant team could not approve your request.")

    except Exception:
        log.exception("process_approval_decision failed for approval %s", row.get("id"))


@router.post("/{approval_id}/approve", response_model=ApprovalOut)  # POST /approvals/<id>/approve
def approve(approval_id: str, background: BackgroundTasks, owner_id: str = Depends(current_user_id)):
    row = _decide(owner_id, approval_id, "approved")
    background.add_task(_process_approval_decision, owner_id, row, True)
    return _to_approval(row)


@router.post("/{approval_id}/reject", response_model=ApprovalOut)  # POST /approvals/<id>/reject
def reject(approval_id: str, background: BackgroundTasks, owner_id: str = Depends(current_user_id)):
    row = _decide(owner_id, approval_id, "rejected")
    background.add_task(_process_approval_decision, owner_id, row, False)
    return _to_approval(row)
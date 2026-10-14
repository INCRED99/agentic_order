import logging  # log lines for failures that must not break the request
from datetime import datetime, timezone  # used to stamp the decision time in UTC
from email.utils import parseaddr  # pulls the plain address out of "Name <a@b.com>"

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query  # BackgroundTasks runs the mail after the response is sent
from postgrest.exceptions import APIError  # error raised when Postgres rejects a query, has a .code

from app.db import db  # the shared Supabase client (service role, bypasses RLS)
from app.deps import current_user_id  # verifies the token and returns the owner_id
from app.inbox import send_mail  # sends a mail through our SMTP account
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


def _find_recipient(owner_id: str, row: dict) -> tuple[str, str, str | None] | None:  # A10: (address, subject, thread id) or None
    run_id = row.get("agent_run_id")  # the run that asked for this approval, None for webhook approvals
    if run_id:  # try the original mail first, so the reply lands in the customer's thread
        runs = db.table("agent_runs").select("email_id").eq("id", run_id).eq("owner_id", owner_id).limit(1).execute().data  # owner guard
        if runs:  # the run still exists (deleting it sets agent_run_id to null, D52)
            mails = (  # the customer's mail
                db.table("emails")  # the mail table
                .select("from_email,subject,gmail_message_id")  # only what a reply needs
                .eq("id", runs[0]["email_id"])  # the mail of that run
                .eq("owner_id", owner_id)  # owner guard
                .limit(1)  # one row
                .execute()  # run it
                .data  # list of rows
            )
            if mails:  # mail found
                address = parseaddr(mails[0].get("from_email") or "")[1]  # plain address only
                if address:  # readable
                    base = " ".join((mails[0].get("subject") or "").split()) or "your order"  # one-line subject
                    subject = base if base.lower().startswith("re:") else f"Re: {base}"  # add Re: once
                    return address, subject, _thread_id(mails[0].get("gmail_message_id"))  # same-thread reply
    order_id = row.get("order_id")  # fallback: approvals created by the webhook have an order but no run
    if order_id:  # an order is known
        orders = db.table("orders").select("customer_id").eq("id", order_id).eq("owner_id", owner_id).limit(1).execute().data  # owner guard
        if orders:  # order found
            customers = db.table("customers").select("email").eq("id", orders[0]["customer_id"]).eq("owner_id", owner_id).limit(1).execute().data  # owner guard
            if customers and customers[0].get("email"):  # customer has an address
                return customers[0]["email"], "Your order", None  # new thread, no original mail to reply to
    return None  # nobody to write to


# DECISION PROBLEM: what text goes to the customer?
# Options: (1) include the approval reason, (2) fixed text per action and decision.
# Chosen: option 2 (A9). Reason: the reason comes from the LLM, which read untrusted mail. It could carry links or tricks.
# Cost: the customer gets no explanation, the owner can write one by hand.
def _message_body(action: str, approved: bool, cancelled: bool) -> str:  # fixed customer text
    if approved:  # owner said yes
        if action == "cancel_order" and cancelled:  # we really cancelled the order
            return "Your order was cancelled as you asked. Please do not pay the payment link we sent earlier."  # honest, effect was done
        if action == "cancel_order":  # approved but the order was not PENDING any more
            return "The restaurant approved your cancellation request. The restaurant team will contact you to finish it."  # owner must act by hand
        if action == "refund_order":  # A8: no money moved by code
            return "The restaurant approved your refund request. The restaurant team will process it and contact you."  # owner refunds by hand
        return "The restaurant approved your request. The restaurant team will contact you to finish it."  # A8: owner finishes by hand
    if action in ORDER_ACTIONS:  # owner said no to an order-type request
        return "The restaurant could not approve your request. You are welcome to send a new order by email at the regular menu prices."  # D-assumed from handoff
    return "The restaurant could not approve your request. Please contact the restaurant directly."  # cancel or refund rejected


def _notify(owner_id: str, row: dict, approved: bool, cancelled: bool) -> None:  # background task: send the customer mail
    try:  # nothing here may crash the server
        target = _find_recipient(owner_id, row)  # who to write to
        if target is None:  # nobody known
            log.warning("approval %s decided, no recipient for the mail", row.get("id"))  # id only
            return  # nothing to send
        address, subject, in_reply_to = target  # unpack
        body = "Hello,\n\n" + _message_body(row["action"], approved, cancelled) + SIGN_OFF  # fixed text only
        send_mail(address, subject, body, in_reply_to=in_reply_to)  # same thread when we know the id
        log.info("approval %s decision mail sent", row.get("id"))  # no address in the log
    except Exception:  # SMTP or database problem
        log.exception("approval %s decision mail failed", row.get("id"))  # A7: the decision stays saved


def _cancel_pending_order(owner_id: str, order_id: str) -> bool:  # A8: the only real effect in V1
    res = (  # one guarded update
        db.table("orders")  # the orders table
        .update({"status": "CANCELLED"})  # new status
        .eq("id", order_id)  # this order
        .eq("owner_id", owner_id)  # owner guard
        .eq("status", "PENDING")  # never cancel a PAID order here, that needs a refund
        .execute()  # run it
    )
    return bool(res.data)  # True when a row changed


# DECISION PROBLEM: the decision and its effect are two separate writes, not one transaction.
# Options: (1) effect first, then decision, (2) decision first, then effect, (3) one Postgres function for both.
# Chosen: option 2, same as D36. Reason: the pending guard in _decide stops double clicks, so the effect runs once.
# Cost: a crash between the two leaves "approved" with the order still PENDING. V2: a reconcile job or option 3.
# Known gap: a cancelled order's Razorpay link stays payable. If paid later, the webhook (D37) files a refund approval.
def _finish(background: BackgroundTasks, owner_id: str, row: dict, approved: bool) -> None:  # effect, then queue the mail
    cancelled = False  # becomes True only when we really cancelled something
    if approved and row["action"] == "cancel_order" and row.get("order_id"):  # the only action with a code effect
        try:  # database can fail
            cancelled = _cancel_pending_order(owner_id, row["order_id"])  # guarded update
        except Exception:  # keep the request alive
            log.exception("approval %s: cancel effect failed", row.get("id"))  # owner can cancel by hand
    background.add_task(_notify, owner_id, row, approved, cancelled)  # runs after the response, A7


@router.post("/{approval_id}/approve", response_model=ApprovalOut)  # POST /approvals/<id>/approve
def approve(approval_id: str, background: BackgroundTasks, owner_id: str = Depends(current_user_id)):  # approval_id from the URL
    row = _decide(owner_id, approval_id, "approved")  # record the approval
    _finish(background, owner_id, row, approved=True)  # effect and customer mail
    return _to_approval(row)  # answer the dashboard


@router.post("/{approval_id}/reject", response_model=ApprovalOut)  # POST /approvals/<id>/reject
def reject(approval_id: str, background: BackgroundTasks, owner_id: str = Depends(current_user_id)):  # approval_id from the URL
    row = _decide(owner_id, approval_id, "rejected")  # record the rejection
    _finish(background, owner_id, row, approved=False)  # customer mail only
    return _to_approval(row)  # answer the dashboard
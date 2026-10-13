from datetime import datetime, timezone  # used to stamp the decision time in UTC

from fastapi import APIRouter, Depends, HTTPException, Query  # APIRouter groups routes, Depends injects deps.py, HTTPException returns errors, Query validates URL parameters
from postgrest.exceptions import APIError  # error raised when Postgres rejects a query, has a .code

from app.db import db  # the shared Supabase client (service role, bypasses RLS)
from app.deps import current_user_id  # verifies the token and returns the owner_id
from app.schemas import ApprovalOut  # response shape, defined in schemas.py

router = APIRouter(prefix="/approvals", tags=["approvals"])  # every route below starts with /approvals
COLS = "id,order_id,action,reason,status,created_at,decided_at"  # the fields the UI needs (needs migration 005)


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
# D11 (user's decision): this only records the decision. It does not change the order or send money anywhere.
# The real effect (cancel, refund, send link) comes later with order plumbing and agent resume.
def _decide(owner_id: str, approval_id: str, new_status: str) -> dict:  # shared by approve and reject
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
            return _to_approval(res.data[0])  # return the updated approval
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


@router.post("/{approval_id}/approve", response_model=ApprovalOut)  # POST /approvals/<id>/approve
def approve(approval_id: str, owner_id: str = Depends(current_user_id)):  # approval_id from the URL
    return _decide(owner_id, approval_id, "approved")  # record the approval


@router.post("/{approval_id}/reject", response_model=ApprovalOut)  # POST /approvals/<id>/reject
def reject(approval_id: str, owner_id: str = Depends(current_user_id)):  # approval_id from the URL
    return _decide(owner_id, approval_id, "rejected")  # record the rejection
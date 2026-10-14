from typing import Literal  # restricts direction and status to known values

from fastapi import APIRouter, Depends, Query  # APIRouter groups routes, Depends injects deps.py, Query validates URL parameters
from pydantic import BaseModel  # response shape (A13: models live in the router file)

from app.db import db  # the shared Supabase client (service role, bypasses RLS)
from app.deps import current_user_id  # verifies the token and returns the owner_id

router = APIRouter(prefix="/emails", tags=["emails"])  # every route below starts with /emails
COLS = "id,direction,from_email,to_email,subject,body,status,created_at"  # body is read only to cut a preview, it is never sent
PREVIEW_CHARS = 160  # A21: how much of the body leaves the backend


class EmailOut(BaseModel):  # one mail as the Emails page shows it
    id: str  # emails id
    direction: Literal["INBOUND", "OUTBOUND"]  # the UI uses uppercase, the database lowercase
    address: str  # sender when inbound, recipient when outbound
    subject: str  # trimmed subject, plain text
    preview: str  # first characters of the body, plain text
    created_at: str  # ISO timestamp string
    order_id: str | None = None  # the order this mail became, None when it did not
    status: Literal["received", "processing", "processed", "failed"]  # progress of the agent step


# DECISION PROBLEM: the page shows which order a mail became, but emails has no order column.
# Options: (1) add emails.order_id, (2) look up orders.source_email_id for the mails on this page.
# Chosen: option 2. Reason: orders already store source_email_id with a unique key, no migration needed.
# Cost: a second query per page load, filtered by owner_id too.
@router.get("", response_model=list[EmailOut])  # GET /emails
def list_emails(  # newest mails first
    owner_id: str = Depends(current_user_id),  # owner_id comes from the verified token only
    limit: int = Query(50, ge=1, le=200),  # default 50, max 200
):
    rows = (  # the mails of this restaurant
        db.table("emails")  # the mail table
        .select(COLS)  # only the fields we need
        .eq("owner_id", owner_id)  # THE guard: without this line every restaurant's mail would leak
        .order("created_at", desc=True)  # newest first
        .limit(limit)  # cap the result size
        .execute()  # send the query to Supabase
        .data  # list of rows
    )
    order_by_mail: dict[str, str] = {}  # mail id -> order id
    if rows:  # skip the query when there are no mails
        orders = (  # orders created from these mails
            db.table("orders")  # the orders table
            .select("id,source_email_id")  # only the link
            .in_("source_email_id", [r["id"] for r in rows])  # the mails on this page
            .eq("owner_id", owner_id)  # owner guard on the second query too
            .execute()  # run it
            .data  # list of rows
        )
        order_by_mail = {o["source_email_id"]: o["id"] for o in orders}  # lookup by mail id
    result = []  # the answer list
    for r in rows:  # one entry per mail
        inbound = r["direction"] == "inbound"  # which side is the customer
        result.append(  # build one entry
            {
                "id": r["id"],  # mail id
                "direction": r["direction"].upper(),  # D1 style: database lowercase, UI uppercase
                "address": (r.get("from_email") if inbound else r.get("to_email")) or "",  # the customer's address
                "subject": r.get("subject") or "",  # empty text replaces null
                "preview": " ".join((r.get("body") or "").split())[:PREVIEW_CHARS],  # one line, cut short
                "created_at": r["created_at"],  # ISO string
                "order_id": order_by_mail.get(r["id"]),  # None when no order
                "status": r["status"],  # already one of the four words
            }
        )
    return result  # FastAPI checks it against EmailOut and turns it into JSON
from typing import Literal  # restricts status to the four known values

from fastapi import APIRouter, Depends, Query  # APIRouter groups routes, Depends injects deps.py, Query validates URL parameters
from pydantic import BaseModel  # response shapes (A13)

from app.db import db  # the shared Supabase client (service role, bypasses RLS)
from app.deps import current_user_id  # verifies the token and returns the owner_id

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])  # every route below starts with /agent-runs
COLS = "id,email_id,status,model_calls,tokens,steps,error,started_at"  # run fields the page needs


class AgentStepOut(BaseModel):  # one tool call of a run
    tool: str  # tool name, for example create_order
    summary: str  # short text written by our code, never mail text (D51)
    ok: bool  # True when the step worked


class AgentRunOut(BaseModel):  # one run as the Agent Activity page shows it
    id: str  # agent_runs id
    email_from: str  # sender of the mail that started the run
    email_subject: str  # subject of that mail
    started_at: str  # ISO timestamp string
    status: Literal["RUNNING", "SUCCESS", "WAITING_APPROVAL", "FAILED"]  # A12
    model_calls: int  # LLM calls used by the run
    tokens: int  # tokens used by the run
    steps: list[AgentStepOut]  # tool calls in order
    error: str | None = None  # exception type name only, for failed runs


# DECISION PROBLEM: the page needs the mail's sender and subject, but agent_runs stores only email_id.
# Options: (1) copy sender and subject into agent_runs, (2) a second query on emails for the ids on this page.
# Chosen: option 2. Reason: no migration, and mail text stays in one table only (D51 keeps it out of agent_runs).
# Cost: two queries per page load. Fine for 50 rows. The second query filters by owner_id too.
@router.get("", response_model=list[AgentRunOut])  # GET /agent-runs
def list_agent_runs(  # newest runs first
    owner_id: str = Depends(current_user_id),  # owner_id comes from the verified token only
    limit: int = Query(50, ge=1, le=200),  # A14: default 50, max 200
):
    runs = (  # the runs of this restaurant
        db.table("agent_runs")  # the run log
        .select(COLS)  # only the fields we need
        .eq("owner_id", owner_id)  # THE guard: without this line every restaurant's runs would leak
        .order("started_at", desc=True)  # newest first
        .limit(limit)  # cap the result size
        .execute()  # send the query to Supabase
        .data  # list of rows
    )
    email_ids = list({r["email_id"] for r in runs if r.get("email_id")})  # distinct mail ids, at most 200
    mails: dict[str, dict] = {}  # mail id -> row
    if email_ids:  # skip the query when there are no runs
        rows = (  # sender and subject of those mails
            db.table("emails")  # the mail table
            .select("id,from_email,subject")  # only what the page shows
            .in_("id", email_ids)  # the mails of these runs
            .eq("owner_id", owner_id)  # owner guard on the second query too
            .execute()  # run it
            .data  # list of rows
        )
        mails = {m["id"]: m for m in rows}  # lookup by id
    result = []  # the answer list
    for r in runs:  # one entry per run
        mail = mails.get(r.get("email_id"), {})  # empty dict when the mail is gone
        result.append(  # build one run
            {
                "id": r["id"],  # run id
                "email_from": mail.get("from_email") or "",  # empty text when unknown
                "email_subject": mail.get("subject") or "",  # empty text when unknown
                "started_at": r["started_at"],  # ISO string from the database
                "status": r["status"],  # already uppercase in the database
                "model_calls": r.get("model_calls") or 0,  # null becomes 0
                "tokens": r.get("tokens") or 0,  # null becomes 0
                "steps": r.get("steps") or [],  # null becomes an empty list
                "error": r.get("error"),  # None for good runs
            }
        )
    return result  # FastAPI checks it against AgentRunOut and turns it into JSON
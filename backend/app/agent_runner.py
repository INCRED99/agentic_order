import logging  # status lines in the terminal
from datetime import datetime, timedelta, timezone  # time windows for limits

from app.agent import run_agent  # runs the LLM agent for one mail
from app.agent_tools import make_run_context  # builds the per-mail context
from app.db import db  # Supabase client (service role, bypasses RLS)

log = logging.getLogger("agent_runner")  # logger name shown in every line
# Logging rule (same as worker.py): ids and reasons only, never mail bodies or subjects.

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # same timestamp format worker.py uses for filters (safe in URLs)
RUN_STALE_MINUTES = 10  # D59: a run still RUNNING after this long is "worker lost"
MAX_RUNS_PER_MAIL = 2  # D59: after 2 runs a mail is marked failed
OWNER_RUNS_PER_DAY = 50  # D55: per restaurant per UTC day
OWNER_RUNS_PER_MINUTE = 1  # D55: per restaurant, spreads the load
GLOBAL_TOKENS_PER_DAY = 160_000  # D55: 80 percent of Groq's 200K per day
MAX_RUNS_PER_PASS = 3  # A3: keep one worker pass short so polling and sweep stay on time
CANDIDATE_LIMIT = 20  # A3: how many oldest received mails we look at per pass
WORKER_LOST = "worker lost"  # error text of a reclaimed run, also used to exclude it from the daily cap


def _now() -> datetime:  # one place for "now" in UTC
    return datetime.now(timezone.utc)  # timezone-aware UTC time


def _stamp(moment: datetime) -> str:  # datetime to the string format used in filters
    return moment.strftime(TIME_FORMAT)  # example: 2026-10-14T08:15:30Z


def _day_start() -> str:  # start of the current UTC day (A2)
    return _stamp(_now().replace(hour=0, minute=0, second=0, microsecond=0))  # midnight UTC


# DECISION PROBLEM: where do the D55 caps live and how are they counted?
# Options: (1) Python constants + counting agent_runs rows, (2) settings in config.py/.env, (3) Redis counters.
# Chosen: option 1 (A1). Reason: no Redis in V1 (D55), rows already exist, no config change.
# Cost: changing a cap means editing this file. Move to config.py when Dev wants to tune without code edits.
def tokens_used_today() -> int:  # D55: global guard, sum of tokens of all runs today
    rows = db.table("agent_runs").select("tokens").gte("started_at", _day_start()).execute().data  # all runs today
    return sum((r.get("tokens") or 0) for r in rows)  # None counts as 0


def owner_block_reason(owner_id: str) -> str | None:  # why this restaurant may not start a run now, or None
    day_rows = (  # runs of this owner today
        db.table("agent_runs")  # the run log
        .select("id,error")  # error is needed to skip reclaimed runs
        .eq("owner_id", owner_id)  # owner guard, every query filters by owner_id
        .gte("started_at", _day_start())  # since midnight UTC
        .execute()  # run it
        .data  # list of rows
    )
    counted = [r for r in day_rows if r.get("error") != WORKER_LOST]  # D59: reclaimed runs do not count (None != text is fine here)
    if len(counted) >= OWNER_RUNS_PER_DAY:  # daily cap reached
        return "daily_cap"  # reason for the log
    minute_ago = _stamp(_now() - timedelta(minutes=1))  # one minute window
    recent = (  # runs started in the last minute
        db.table("agent_runs")  # the run log
        .select("id", count="exact")  # count only
        .eq("owner_id", owner_id)  # owner guard
        .gte("started_at", minute_ago)  # last 60 seconds
        .limit(1)  # no rows needed
        .execute()  # run it
    )
    if (recent.count or 0) >= OWNER_RUNS_PER_MINUTE:  # minute cap reached
        return "minute_cap"  # reason for the log
    return None  # free to run


def runs_for_mail(owner_id: str, email_id: str) -> int:  # how many runs this mail already had
    res = (  # count runs of this mail
        db.table("agent_runs")  # the run log
        .select("id", count="exact")  # count only
        .eq("owner_id", owner_id)  # owner guard
        .eq("email_id", email_id)  # this mail
        .limit(1)  # no rows needed
        .execute()  # run it
    )
    return res.count or 0  # None becomes 0


def set_mail_status(owner_id: str, email_id: str, new_status: str, only_if: str) -> None:  # guarded status change
    (  # update only when the mail still has the expected old status
        db.table("emails")  # the mail table
        .update({"status": new_status})  # new status
        .eq("id", email_id)  # this mail
        .eq("owner_id", owner_id)  # owner guard
        .eq("status", only_if)  # compare and swap, never overwrite someone else's change
        .execute()  # run it
    )


def reclaim_stuck_runs() -> None:  # D59: free mails whose run died with the worker
    cutoff = _stamp(_now() - timedelta(minutes=RUN_STALE_MINUTES))  # older than this is stuck
    stuck = (  # runs still RUNNING after the cutoff
        db.table("agent_runs")  # the run log
        .select("id,owner_id,email_id")  # what we need to fix them
        .eq("status", "RUNNING")  # still marked running
        .lt("started_at", cutoff)  # started long ago
        .execute()  # run it
        .data  # list of rows
    )
    for run in stuck:  # one by one
        marked = (  # mark FAILED only if still RUNNING
            db.table("agent_runs")  # the run log
            .update({"status": "FAILED", "error": WORKER_LOST, "finished_at": _stamp(_now())})  # close the run
            .eq("id", run["id"])  # this run
            .eq("owner_id", run["owner_id"])  # owner guard
            .eq("status", "RUNNING")  # guard against a race
            .execute()  # run it
            .data  # empty list when nothing matched
        )
        if not marked:  # someone else closed it first
            continue  # nothing more to do
        total = runs_for_mail(run["owner_id"], run["email_id"])  # includes the run we just closed
        new_status = "failed" if total >= MAX_RUNS_PER_MAIL else "received"  # D59: give up after 2 runs
        set_mail_status(run["owner_id"], run["email_id"], new_status, only_if="processing")  # release the mail
        log.warning("reclaimed run %s, mail %s now %s", run["id"], run["email_id"], new_status)  # ids only


def claim_mail(owner_id: str, email_id: str) -> bool:  # D48: received -> processing, only one worker wins
    claimed = (  # update with a condition on the old status
        db.table("emails")  # the mail table
        .update({"status": "processing"})  # new status
        .eq("id", email_id)  # this mail
        .eq("owner_id", owner_id)  # owner guard
        .eq("status", "received")  # only if nobody claimed it yet
        .execute()  # run it
        .data  # empty list when the condition failed
    )
    return bool(claimed)  # True means we own the mail now


def finish_run(owner_id: str, run_id: str, status: str, run, outcome, error: str | None) -> None:  # write the result of one run
    (  # one update with everything
        db.table("agent_runs")  # the run log
        .update(  # fields to write
            {
                "status": status,  # SUCCESS, WAITING_APPROVAL or FAILED
                "model_calls": outcome.model_calls if outcome else 0,  # 0 when the run crashed
                "tokens": outcome.tokens if outcome else 0,  # 0 when the run crashed (A4: crashed runs are not counted in the token guard)
                "steps": run.steps if run else [],  # list of {tool, summary, ok}, never mail text (D51)
                "order_id": run.order_id if run else None,  # order made by this run, if any
                "error": error,  # exception type name only, no mail text
                "finished_at": _stamp(_now()),  # close time
            }
        )
        .eq("id", run_id)  # this run
        .eq("owner_id", owner_id)  # owner guard
        .execute()  # run it
    )


# DECISION PROBLEM: what happens to the mail when the agent raises an exception?
# Options: (1) mark mail failed at once, (2) put it back to received so it retries up to 2 runs.
# Chosen: option 1 (A4), as in the handoff spec. Reason: model errors on Groq free tier often repeat,
# a retry loop burns the daily quota. Cost: a short Groq outage loses that mail until a human resets it.
def run_one(mail: dict) -> bool:  # claim and run one mail, True when a run was started
    owner_id, email_id = mail["owner_id"], mail["id"]  # who and which mail
    if not claim_mail(owner_id, email_id):  # lost the race or status changed
        return False  # nothing started
    try:  # create the run row
        inserted = (  # new agent_runs row
            db.table("agent_runs")  # the run log
            .insert(  # explicit values, we do not know which columns have defaults
                {
                    "owner_id": owner_id,  # restaurant
                    "email_id": email_id,  # the mail
                    "status": "RUNNING",  # in progress
                    "model_calls": 0,  # filled at the end
                    "tokens": 0,  # filled at the end
                    "steps": [],  # filled at the end
                    "started_at": _stamp(_now()),  # start time, used by the caps and by reclaim
                }
            )
            .execute()  # run it
            .data  # the inserted row
        )
        run_id = inserted[0]["id"]  # id of the new run
    except Exception:  # no run row means reclaim could never find this mail
        log.exception("could not create agent run for mail %s", email_id)  # log with traceback
        set_mail_status(owner_id, email_id, "received", only_if="processing")  # give the mail back
        return False  # nothing started
    run = None  # filled when the context is built
    outcome = None  # filled when the agent finishes
    try:  # the agent can fail in many ways
        run = make_run_context(owner_id, email_id, run_id)  # context for the tools
        outcome = run_agent(run)  # the LLM loop with tools (A5: no mail_text override)
    except Exception as exc:  # any failure of the agent
        log.exception("agent run %s failed", run_id)  # traceback shows file and line; exception text is not mail text
        try:  # closing the run can fail too
            finish_run(owner_id, run_id, "FAILED", run, outcome, type(exc).__name__)  # error = type name only
        except Exception:  # database problem
            log.exception("could not close failed run %s", run_id)  # reclaim will close it after 10 minutes
            return True  # the run did start
        set_mail_status(owner_id, email_id, "failed", only_if="processing")  # A4: no automatic retry
        return True  # the run did start
    status = "WAITING_APPROVAL" if run.ended_reason == "approval" else "SUCCESS"  # D49: approval ends the run, owner decides later
    try:  # write the result
        finish_run(owner_id, run_id, status, run, outcome, None)  # no error
        set_mail_status(owner_id, email_id, "processed", only_if="processing")  # mail is done
    except Exception:  # database problem after a good run
        log.exception("could not store result of run %s", run_id)  # run stays RUNNING, reclaim fixes it later
    log.info("run %s done status=%s reason=%s calls=%s tokens=%s", run_id, status, run.ended_reason, outcome.model_calls, outcome.tokens)  # numbers only
    return True  # the run did start


def process_received_mails() -> None:  # called by worker.main() after every poll
    try:  # reclaim must not block new runs
        reclaim_stuck_runs()  # D59
    except Exception:  # database error
        log.exception("reclaim failed")  # log and go on
    candidates = (  # oldest received inbound mails first
        db.table("emails")  # the mail table
        .select("id,owner_id")  # all we need
        .eq("status", "received")  # waiting for the agent
        .eq("direction", "inbound")  # customer mail only
        .order("created_at")  # oldest first
        .limit(CANDIDATE_LIMIT)  # A3
        .execute()  # run it
        .data  # list of rows
    )
    started = 0  # runs started in this pass
    blocked_owners: set[str] = set()  # owners over their cap in this pass
    for mail in candidates:  # one by one
        if started >= MAX_RUNS_PER_PASS:  # enough work for this pass
            break  # the worker goes back to polling
        owner_id = mail["owner_id"]  # restaurant of this mail
        if owner_id in blocked_owners:  # already known to be over cap
            continue  # mail stays received (D55)
        if runs_for_mail(owner_id, mail["id"]) >= MAX_RUNS_PER_MAIL:  # D59: too many runs already
            set_mail_status(owner_id, mail["id"], "failed", only_if="received")  # give up on this mail
            log.warning("mail %s failed: too many runs", mail["id"])  # id only
            continue  # next mail
        if tokens_used_today() >= GLOBAL_TOKENS_PER_DAY:  # D55: global guard
            log.warning("global token guard hit, no more runs today")  # nothing is lost, mails stay received
            break  # stop the whole pass
        reason = owner_block_reason(owner_id)  # per-owner caps
        if reason:  # over cap
            blocked_owners.add(owner_id)  # skip this owner for the rest of the pass
            log.info("owner %s blocked: %s", owner_id, reason)  # reason only
            continue  # mail stays received
        if run_one(mail):  # claim and run
            started += 1  # count it
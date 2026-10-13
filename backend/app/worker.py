import logging  # status lines in the terminal
import re  # used to avoid "Re: Re:" subjects
import time  # sleep between polls
from datetime import datetime, timedelta, timezone  # time window for reply limits

from postgrest.exceptions import APIError  # database error with a .code

from app.config import settings  # intervals, limits, credentials
from app.db import db  # Supabase client (service role)
from app.inbox import (  # mail helpers
    body_text,  # readable body
    fetch_message,  # download one mail
    fetch_message_id,  # download only the id
    is_automated,  # robot check
    list_recent_uids,  # mail from the lookback window
    open_imap,  # connect to Gmail
    send_mail,  # send a reply
    sender_of,  # plain From address
)
from app.routing import extract_slug, find_owner, same_inbox  # which restaurant is this mail for
from app.sweep import expire_unpaid_orders  # D42: the expiry sweep
log = logging.getLogger("worker")  # logger name shown in every line
SWEEP_INTERVAL_SECONDS = 300  # run the expiry sweep every 5 minutes
# We log message ids and reasons only, never mail bodies or subjects, because they are customers' private text.

UNKNOWN_REPLY = (  # text of the "unknown address" answer
    "Hello,\n\n"  # greeting
    "This address is not linked to a restaurant. "  # the problem
    "Please send your order to the order address shown on the restaurant's dashboard.\n\n"  # what to do
    "This is an automatic message."  # honest label
)


def known_ids(ids: list[str]) -> set[str]:  # which of these Message-IDs are already stored
    found: set[str] = set()  # collects ids we have seen
    for table, col in (("emails", "gmail_message_id"), ("unrouted_emails", "message_id")):  # both places a mail can land
        for i in range(0, len(ids), 100):  # ask in chunks of 100 so the URL stays short
            chunk = ids[i : i + 100]  # one chunk
            res = db.table(table).select(col).in_(col, chunk).execute()  # rows that already exist
            found.update(r[col] for r in res.data)  # remember them
    return found  # skip these in the poll
    # This lookup is only a speed-up. The unique keys on both tables are the real guarantee.


def within_reply_limits(sender: str) -> bool:  # may we send an "unknown address" reply to this sender now
    since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")  # 24 hours ago
    per_sender = (  # replies already sent to this sender in the last day
        db.table("unrouted_emails")  # the table that records them
        .select("message_id", count="exact")  # we only need the count
        .eq("from_email", sender)  # this sender
        .eq("replied", True)  # only mails we really answered
        .gte("created_at", since)  # within 24 hours
        .limit(1)  # no need to download rows
        .execute()  # run it
    )
    if (per_sender.count or 0) >= 1:  # one reply per sender per day
        return False  # stay quiet
    total = (  # replies sent to everyone in the last day
        db.table("unrouted_emails")  # same table
        .select("message_id", count="exact")  # count only
        .eq("replied", True)  # answered mails
        .gte("created_at", since)  # within 24 hours
        .limit(1)  # no rows needed
        .execute()  # run it
    )
    return (total.count or 0) < settings.unknown_reply_daily_cap  # global daily cap


# DECISION PROBLEM: when do we write the database row relative to sending the reply?
# Options: (1) row first, then send (at most one reply), (2) send first, then row (at least one reply).
# Chosen: option 1. Reason: a crash can never cause a second reply to a spammer, and the primary key blocks races.
# Cost: after a crash between the two steps, a real customer may get no reply. Acceptable for a demo.
def record_unrouted(mid: str, msg, sender: str, reason: str) -> None:  # store a mail that belongs to no restaurant, maybe answer it
    reply = bool(sender) and not is_automated(msg, sender) and within_reply_limits(sender)  # all guards must pass
    try:  # insert first
        db.table("unrouted_emails").insert(  # new row
            {"message_id": mid, "from_email": sender, "subject": str(msg.get("Subject", ""))[:200], "reason": reason, "replied": reply}  # what we know
        ).execute()  # run it
    except APIError as e:  # database refused
        if e.code == "23505":  # same message id already stored by a parallel run
            return  # someone else handled it, send nothing
        raise  # real error, let the poll loop log it
    log.info("unrouted mail %s reason=%s reply=%s", mid, reason, reply)  # no private text in the log
    if not reply:  # guards said no
        return  # done
    subject = str(msg.get("Subject", "")).strip() or "Your order"  # reuse their subject
    if not re.match(r"(?i)re:", subject):  # avoid "Re: Re: ..."
        subject = f"Re: {subject}"  # standard reply prefix
    try:  # sending can fail
        send_mail(sender, subject, UNKNOWN_REPLY, in_reply_to=str(msg.get("Message-ID", "")) or None)  # answer in their thread
    except Exception:  # SMTP problem
        log.exception("could not send unknown-address reply for %s", mid)  # log with traceback
        db.table("unrouted_emails").update({"replied": False}).eq("message_id", mid).execute()  # keep the count honest


def store_routed(owner_id: str, mid: str, msg, to_addr: str, sender: str) -> None:  # save a mail that belongs to a restaurant
    try:  # insert and handle duplicates
        db.table("emails").insert(  # the shared mail table
            {
                "owner_id": owner_id,  # restaurant that owns this mail, taken from the slug only
                "gmail_message_id": mid,  # Message-ID header, the dedup key
                "direction": "inbound",  # customer to restaurant
                "from_email": sender,  # who wrote
                "to_email": to_addr,  # which order address they used
                "subject": str(msg.get("Subject", ""))[:200],  # trimmed subject
                "body": body_text(msg),  # trimmed readable body, untrusted
                "status": "received",  # the agent step will pick it up later
            }
        ).execute()  # run it
    except APIError as e:  # database refused
        if e.code == "23505":  # unique (owner_id, gmail_message_id) already holds it
            return  # duplicate, safe to ignore
        raise  # real error
    log.info("stored mail %s for owner %s", mid, owner_id)  # no private text in the log


def handle_message(mid: str, msg) -> None:  # decide where one new mail goes
    sender = sender_of(msg)  # plain From address
    if sender and same_inbox(sender):  # mail from our own address
        record_unrouted(mid, msg, "", "own_address")  # remember it, empty sender means no reply is ever sent
        return  # done
    headers = [str(h) for h in msg.get_all("Delivered-To", []) + msg.get_all("To", [])]  # Delivered-To also covers BCC
    found = extract_slug(headers)  # look for mealdesk.orders+slug@gmail.com
    if found is None:  # no plus address used
        record_unrouted(mid, msg, sender, "no_slug")  # answer "unknown address"
        return  # done
    slug, to_addr = found  # the slug and the address that carried it
    owner_id = find_owner(slug)  # which restaurant uses this slug
    if owner_id is None:  # slug well formed but nobody owns it
        record_unrouted(mid, msg, sender, "unknown_slug")  # answer "unknown address"
        return  # done
    store_routed(owner_id, mid, msg, to_addr, sender)  # normal case


def poll_once() -> None:  # one full check of the inbox
    conn = open_imap()  # fresh connection every poll
    try:  # always log out, even on errors
        uids = list_recent_uids(conn, settings.lookback_days)  # mail from the lookback window
        id_by_uid: dict[bytes, str] = {}  # uid -> Message-ID
        for uid in uids:  # cheap header-only fetch for each
            mid = fetch_message_id(conn, uid)  # may be None for broken mail
            if mid:  # mail without Message-ID is skipped, we cannot dedup it safely
                id_by_uid[uid] = mid  # remember it
        known = known_ids(list(id_by_uid.values()))  # which of them we already stored
        for uid, mid in id_by_uid.items():  # only new mail from here on
            if mid in known:  # already handled earlier
                continue  # skip
            try:  # one bad mail must not block the others
                msg = fetch_message(conn, uid)  # download the full mail
                if msg is not None:  # fetch worked
                    handle_message(mid, msg)  # route it
            except Exception:  # anything unexpected
                log.exception("failed to handle mail %s", mid)  # it is retried next poll, fine at demo scale
    finally:  # cleanup block
        try:  # logout can fail on a dead connection
            conn.logout()  # close politely
        except Exception:  # ignore, we are leaving anyway
            pass  # nothing to do


def main() -> None:  # entry point: python -m app.worker
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")  # readable log lines
    if not settings.inbox_app_password:  # worker cannot work without it
        log.error("INBOX_APP_PASSWORD is missing in backend/.env")  # tell the human what to fix
        raise SystemExit(1)  # stop with an error code
    log.info("worker started, inbox=%s, every %ss", settings.shared_inbox, settings.poll_interval_seconds)  # startup banner
    
    last_sweep = None  # None means never swept, so the first round sweeps at once
    while True:  # run until you press Ctrl+C
        try:  # a failed poll must not kill the worker
            poll_once()  # check the inbox
        except Exception:  # network down, Gmail error, DB error
            log.exception("poll failed")  # log it and keep going
        if last_sweep is None or time.monotonic() - last_sweep >= SWEEP_INTERVAL_SECONDS:  # time for the sweep
            try:  # a failed sweep must not kill the worker
                expire_unpaid_orders()  # mark unpaid orders with a dead link as EXPIRED
            except Exception:  # database or network error
                log.exception("expiry sweep failed")  # log it and keep going
            last_sweep = time.monotonic()  # remember when we swept
        time.sleep(settings.poll_interval_seconds)  # wait for the next round

if __name__ == "__main__":  # true when started with python -m app.worker
    main()  # start the loop
import email  # parse raw mail bytes into message objects
import imaplib  # read mail over IMAP
import re  # small regex cleanups
import smtplib  # send mail over SMTP
from datetime import date, timedelta  # compute the first day of the lookback window
from email.message import EmailMessage  # build outgoing mail
from email.policy import default  # modern policy: decodes headers and bodies for us
from email.utils import parseaddr  # split 'Name <a@b.c>' into name and address

from app.config import settings  # host names, credentials, limits

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]  # IMAP needs English month names
AUTO_LOCALS = {"noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster"}  # robot sender names


def _imap_date(d: date) -> str:  # format a date the way IMAP SEARCH expects
    return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"  # strftime would follow the PC language, this will not


# DECISION PROBLEM: keep one IMAP connection open, or connect on every poll?
# Options: (1) connect per poll, (2) keep alive and reconnect on error.
# Chosen: option 1. Reason: a dropped connection can never leave the worker stuck.
# Cost: one login every 30 seconds, which is far below Gmail's limits.
# We open the folder read-only so reading a mail never marks it read (you will also open this inbox by hand).
def open_imap() -> imaplib.IMAP4_SSL:  # returns a logged-in connection with INBOX selected
    conn = imaplib.IMAP4_SSL(settings.imap_host, timeout=30)  # timeout stops a hung network from freezing the worker
    conn.login(settings.shared_inbox, settings.inbox_app_password.replace(" ", ""))  # Google shows the password with spaces
    conn.select("INBOX", readonly=True)  # readonly: never change flags on the server
    return conn  # caller must call logout


def list_recent_uids(conn: imaplib.IMAP4_SSL, days: int) -> list[bytes]:  # UIDs of mail from the last few days
    since = date.today() - timedelta(days=days)  # first day of the window
    typ, data = conn.uid("SEARCH", "SINCE", _imap_date(since))  # UID search stays valid even if mail is deleted
    if typ != "OK" or not data or not data[0]:  # search failed or nothing found
        return []  # no mail to look at
    return data[0].split()  # b"11 12 13" -> [b"11", b"12", b"13"]


def fetch_message_id(conn: imaplib.IMAP4_SSL, uid: bytes) -> str | None:  # download only the Message-ID header
    typ, data = conn.uid("FETCH", uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")  # PEEK reads without side effects
    if typ != "OK" or not data or not isinstance(data[0], tuple):  # mail vanished or odd reply
        return None  # skip it
    header = email.message_from_bytes(data[0][1])  # parse the tiny header block
    mid = header["Message-ID"]  # unique id the sender's mail server gave this mail
    return " ".join(str(mid).split()) if mid else None  # tidy folded lines; None when missing (such mail is skipped)


def fetch_message(conn: imaplib.IMAP4_SSL, uid: bytes) -> EmailMessage | None:  # download one full mail
    typ, data = conn.uid("FETCH", uid, "(BODY.PEEK[])")  # PEEK keeps the mail unread in Gmail
    if typ != "OK" or not data or not isinstance(data[0], tuple):  # mail vanished or odd reply
        return None  # nothing to parse
    return email.message_from_bytes(data[0][1], policy=default)  # parse into an EmailMessage


def sender_of(msg: EmailMessage) -> str:  # the plain address in the From header, lowercase
    return parseaddr(str(msg.get("From", "")))[1].lower()  # "Ravi <r@x.com>" -> "r@x.com"


# DECISION PROBLEM: which part of the mail do we keep as the order text?
# Options: (1) plain text only, (2) plain with HTML as fallback, (3) store both.
# Chosen: option 2. Reason: phone mail apps sometimes send HTML only.
# The text is untrusted input. We cut it to max_body_chars, and the agent must never treat it as instructions.
def body_text(msg: EmailMessage) -> str:  # readable text of a mail
    part = msg.get_body(preferencelist=("plain", "html"))  # prefer plain text, fall back to HTML
    if part is None:  # mail has no text body
        return ""  # store an empty body
    try:  # decoding can fail on broken encodings
        text = part.get_content()  # decoded text
    except Exception:  # unreadable body
        return ""  # store an empty body
    if part.get_content_type() == "text/html":  # fallback case
        text = re.sub(r"<[^>]+>", " ", text)  # crude tag removal, fine for short order mails
    text = re.sub(r"[ \t]+", " ", text).strip()  # squeeze repeated spaces, keep line breaks
    return text[: settings.max_body_chars]  # hard length cap


def is_automated(msg: EmailMessage, sender: str) -> bool:  # true for robots, newsletters, bounces
    if str(msg.get("Auto-Submitted", "no")).lower() != "no":  # standard "a robot sent this" header
        return True  # never answer robots, it can start a mail loop
    if str(msg.get("Precedence", "")).lower() in {"bulk", "list", "junk"}:  # old-style bulk mail marker
        return True  # newsletters and lists
    if msg.get("List-Id") or msg.get("List-Unsubscribe"):  # mailing list headers
        return True  # not a person
    local = sender.split("@")[0]  # the part before the @
    return local in AUTO_LOCALS or local.startswith("noreply")  # typical robot sender names


def send_mail(to: str, subject: str, body: str, in_reply_to: str | None = None) -> None:  # send one mail from the shared inbox
    msg = EmailMessage()  # empty outgoing mail
    msg["From"] = settings.shared_inbox  # Gmail only allows our own address here
    msg["To"] = to  # recipient
    msg["Subject"] = subject  # subject line
    if in_reply_to:  # keep the reply inside the customer's thread
        msg["In-Reply-To"] = in_reply_to  # points at the mail we answer
        msg["References"] = in_reply_to  # same, for mail clients that group by References
    msg["Auto-Submitted"] = "auto-replied"  # tells other robots not to answer us, stops loops
    msg.set_content(body)  # plain text body
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:  # encrypted SMTP connection
        smtp.login(settings.shared_inbox, settings.inbox_app_password.replace(" ", ""))  # same app password as IMAP
        smtp.send_message(msg)  # hand the mail to Gmail
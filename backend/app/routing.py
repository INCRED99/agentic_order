import re  # used to check that a slug has the exact expected shape
from email.utils import getaddresses, parseaddr  # getaddresses reads many addresses from headers, parseaddr reads one

from app.config import settings  # gives us the shared inbox address
from app.db import db  # Supabase client, used to look up the owner of a slug

SLUG_RE = re.compile(r"[a-z0-9]{8}")  # same shape as the DB check on profiles.restaurant_slug


def _inbox_parts() -> tuple[str, str]:  # split the shared inbox into a comparable local part and domain
    local, domain = settings.shared_inbox.lower().split("@")  # "mealdesk.orders@gmail.com" -> two pieces
    return local.replace(".", ""), domain  # Gmail ignores dots, so remove them before comparing


# DECISION PROBLEM: a mail can carry several recipient addresses (two restaurants at once).
# Options: (1) first matching address wins, (2) process every match, (3) reject ambiguous mail.
# Chosen: option 1. Reason: simplest, and one customer mail naming two restaurants is rare.
# Cost: the second restaurant never sees that mail. Revisit if testers do this on purpose.
def extract_slug(header_values: list[str]) -> tuple[str, str] | None:  # returns (slug, matched address) or None
    inbox_local, inbox_domain = _inbox_parts()  # what a valid address must look like
    for _, addr in getaddresses(header_values):  # walk every address in the given headers, in order
        addr = addr.strip().lower()  # normalize case and spaces
        if "@" not in addr:  # not an address at all
            continue  # try the next one
        local, domain = addr.split("@", 1)  # separate "mealdesk.orders+k7x2p9ab" from "gmail.com"
        base, plus, slug = local.partition("+")  # split at the plus sign into base, "+", and slug
        if not plus:  # no plus part, so no slug here
            continue  # try the next address
        if domain != inbox_domain or base.replace(".", "") != inbox_local:  # must be our inbox, dots ignored
            continue  # address belongs to someone else
        if SLUG_RE.fullmatch(slug):  # slug must be exactly 8 lowercase letters or digits
            return slug, addr  # first valid match wins
    return None  # nothing matched


def same_inbox(address: str) -> bool:  # true when an address is our own inbox, with or without a +tag
    inbox_local, inbox_domain = _inbox_parts()  # our own parts
    _, addr = parseaddr(address)  # tolerate "Name <a@b.c>" input
    if "@" not in addr:  # not an address
        return False  # cannot be ours
    local, domain = addr.lower().split("@", 1)  # split the candidate
    return domain == inbox_domain and local.split("+")[0].replace(".", "") == inbox_local  # compare ignoring tag and dots


def find_owner(slug: str) -> str | None:  # slug -> owner_id, or None when no restaurant uses it
    res = db.table("profiles").select("id").eq("restaurant_slug", slug).execute()  # slug is unique, so 0 or 1 row
    return res.data[0]["id"] if res.data else None  # profiles.id is the owner_id used everywhere else
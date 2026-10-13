import logging  # write sweep results to the server log

from app.db import db  # shared Supabase client (service role)

log = logging.getLogger(__name__)  # logger named after this file


def expire_unpaid_orders() -> int:  # D42 option a: the worker calls this on a timer
    res = db.rpc("expire_unpaid_orders", {}).execute()  # call the SQL function from 010, it takes no parameters
    count = int(res.data or 0)  # the function returns an integer, None becomes 0
    if count:  # only log when something happened, keeps the log quiet
        log.info("expired %s unpaid order(s)", count)  # one line per sweep that did work
    return count  # the caller can print or test it
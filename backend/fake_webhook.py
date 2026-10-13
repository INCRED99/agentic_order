import hmac  # build the HMAC signature exactly like Razorpay does
import hashlib  # SHA256 hash function used by the signature
import json  # build the webhook body
import sys  # read the test mode from the command line

import httpx  # send the HTTP request to our own backend

from app.config import settings  # holds razorpay_webhook_secret
from app.db import db  # read the real order and link id from the database

# USAGE (PowerShell, from backend, venv on):
#   python fake_webhook.py <ORDER_ID> ok        -> normal paid event
#   python fake_webhook.py <ORDER_ID> badsig    -> wrong signature, expect 401
#   python fake_webhook.py <ORDER_ID> amount    -> wrong amount, expect refund_approval
order_id = sys.argv[1]  # first argument: the order to "pay"
mode = sys.argv[2] if len(sys.argv) > 2 else "ok"  # second argument: which case to test

order = db.table("orders").select("total_paise").eq("id", order_id).limit(1).execute().data[0]  # stored total of the order
pay = db.table("payments").select("razorpay_payment_link_id").eq("order_id", order_id).limit(1).execute().data[0]  # stored link id

amount = order["total_paise"] + (100 if mode == "amount" else 0)  # amount case adds 1 rupee on purpose
body = {  # shape written from memory of the docs, UNVERIFIED (D35 real test checks it)
    "event": "payment_link.paid",  # the only event the handler acts on
    "payload": {  # event data
        "payment_link": {"entity": {"id": pay["razorpay_payment_link_id"], "reference_id": order_id}},  # link id and our order id
        "payment": {"entity": {"id": "pay_FAKE0000000001", "amount": amount}},  # fixed fake payment id, so a 2nd run tests idempotency
    },
}
raw = json.dumps(body).encode()  # the exact bytes that get signed AND sent
sig = hmac.new(settings.razorpay_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()  # correct signature
if mode == "badsig":  # wrong signature case
    sig = "0" * 64  # garbage signature

r = httpx.post(  # send to the local backend
    "http://127.0.0.1:8000/webhooks/razorpay",  # change the port if uvicorn runs elsewhere
    content=raw,  # raw bytes, not json=, so the signed bytes are the sent bytes
    headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},  # signature header
    timeout=20,  # do not hang forever
)
print(r.status_code, r.text)  # show the answer
from fastapi import APIRouter, Depends, Query  # APIRouter groups routes, Depends injects deps.py, Query validates URL parameters

from app.db import db  # the shared Supabase client (service role, bypasses RLS)
from app.deps import current_user_id  # verifies the token and returns the owner_id
from app.schemas import OrderOut  # response shape, defined in schemas.py

router = APIRouter(prefix="/orders", tags=["orders"])  # every route below starts with /orders
COLS = (  # one request fetches the order and everything the UI shows
    "id,status,total_paise,created_at,updated_at,"  # the order itself
    "customers(email,name),"  # who ordered, joined through customer_id
    "order_items(id,menu_item_id,quantity,unit_price_paise,menu_items(name)),"  # lines, with the dish name joined
    "payments(status,created_at,payment_link_url),"  # payment rows, used for payment status and link (needs migration 004)
    "approvals(status)"  # approval rows, used for AWAITING_APPROVAL (needs migration 004)
)

# DECISION PROBLEM (D1, chosen by the user): the UI and the database use different status words.
# Options: (1) change the database CHECK, (2) map in the API.
# Chosen: option 2. Reason: each fact stays stored once, and no migration touches live data.
# Cost: this mapping code must stay in sync with the database values.
PAYMENT_STATUS_MAP = {  # database payment status -> UI payment status
    "CREATED": "LINK_SENT",  # a payment row exists but nothing is paid yet, so the link went out
    "PAID": "PAID",  # same word
    "FAILED": "FAILED",  # same word
    "REFUNDED": "REFUNDED",  # same word
}


def _one(value):  # PostgREST returns an object for many-to-one joins, but be safe and accept a list too
    if isinstance(value, list):  # list shape
        return value[0] if value else None  # first element or nothing
    return value  # object shape or None


def _latest_payment(payments) -> dict | None:  # the payment row of an order, accepts an object or a list
    if not payments:  # no payment row yet
        return None  # nothing was created for this order
    if isinstance(payments, dict):  # since 008 (unique order_id) PostgREST sends ONE object, not a list
        return payments  # that object is the payment
    return max(payments, key=lambda p: p["created_at"])  # list shape: ISO strings sort correctly, so max is the newest


def _order_status(db_status: str, approvals: list[dict]) -> str:  # compute the UI order status
    if db_status == "PENDING" and any(a["status"] == "pending" for a in approvals):  # waiting for the owner
        return "AWAITING_APPROVAL"  # computed, never stored, so it cannot disagree with the approvals table
    return db_status  # otherwise the database value is already what the UI expects

def _payment_status(order_status: str, payment: dict | None) -> str:  # compute the UI payment status
    if payment is None:  # no payment row yet
        return "UNPAID"  # nothing was created for this order
    if payment["status"] == "CREATED" and order_status == "EXPIRED":  # D42: the sweep changes only orders.status, so the payment row stays CREATED
        return "EXPIRED"  # without this line an expired order would show "Link sent"
    return PAYMENT_STATUS_MAP.get(payment["status"], "UNPAID")  # normal mapping
def _to_order(row: dict) -> dict:  # turn one joined database row into the OrderOut shape
    customer = _one(row.get("customers")) or {}  # customer data, empty dict if the join is missing
    payment = _latest_payment(row.get("payments") or [])  # newest payment or None
    items = [  # one entry per order line
        {  # one line
            "id": i["id"],  # line id
            "menu_item_id": i["menu_item_id"],  # dish id
            "name": (_one(i.get("menu_items")) or {}).get("name", "Unknown dish"),  # dish name, see the weak spot note below
            "quantity": i["quantity"],  # how many
            "unit_price_paise": i["unit_price_paise"],  # price snapshot taken at order time
        }
        for i in row.get("order_items") or []  # loop over the joined lines
    ]
    return {  # the flat shape the UI expects
        "id": row["id"],  # order id
        "customer_name": customer.get("name"),  # may be None
        "customer_email": customer.get("email", ""),  # always set for real orders
        "items": items,  # lines built above
        "total_paise": row["total_paise"],  # total stored in the database
        "status": _order_status(row["status"], row.get("approvals") or []),  # PENDING, AWAITING_APPROVAL, PAID, CANCELLED or REFUNDED
        "payment_status": _payment_status(row["status"], payment),  # computed, never stored
        "payment_link_url": payment.get("payment_link_url") if payment else None,  # None until a link is created
        "created_at": row["created_at"],  # ISO timestamp string
        "updated_at": row["updated_at"],  # ISO timestamp string
    }


# NOTE: weak spot. The dish name comes from menu_items, so renaming a dish later changes old orders.
# The price is a snapshot but the name is not. Fix later: add order_items.name_snapshot.
@router.get("", response_model=list[OrderOut])  # GET /orders
def list_orders(  # newest orders first
    owner_id: str = Depends(current_user_id),  # owner_id comes from the verified token only
    limit: int = Query(50, ge=1, le=100),  # page size, default 50, max 100 so one request stays small
):
    res = (  # build the query step by step
        db.table("orders")  # read from the orders table
        .select(COLS)  # order plus joined customer, lines, payments and approvals
        .eq("owner_id", owner_id)  # THE guard: without this line every restaurant's orders would leak
        .order("created_at", desc=True)  # newest first, what a dashboard shows
        .limit(limit)  # cap the result size
        .execute()  # send the query to Supabase
    )
    return [_to_order(r) for r in res.data]  # convert each row, FastAPI turns the list into JSON
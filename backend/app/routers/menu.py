import logging  # Python's built-in logger, used to record rare failures
from fastapi import APIRouter, Depends, HTTPException  # APIRouter groups routes, Depends injects deps.py, HTTPException returns errors
from postgrest.exceptions import APIError  # error raised when Postgres rejects a query, has a .code

from app.db import db  # the shared Supabase client (service role, bypasses RLS)
from app.deps import current_user_id  # verifies the token and returns the owner_id
from app.schemas import MenuItemCreate, MenuItemOut, MenuItemUpdate  # request and response shapes

log = logging.getLogger(__name__)  # logger named after this file, so log lines show where they came from
router = APIRouter(prefix="/menu", tags=["menu"])  # every route below starts with /menu; tags only groups them in /docs
COLS = "id,name,description,category,price_paise,is_available,inventory(quantity)"  # inventory(quantity) joins the stock row in the same request
DEFAULT_STOCK = 5  # your decision: a new menu item starts with 5 in stock


def _raise_db_error(e: APIError):  # turns a Postgres error code into a clear HTTP error
    if e.code == "23505":  # 23505 = unique violation
        raise HTTPException(409, "Item name already exists")  # caused by unique (owner_id, name)
    if e.code == "23503":  # 23503 = foreign key violation
        raise HTTPException(409, "Item is used in orders. Disable it instead")  # order_items points at this item
    raise HTTPException(500, "Database error")  # anything else is unexpected


# DECISION PROBLEM: the join returns inventory in a nested shape, but the UI wants a flat "stock" number.
# Options: (1) flatten here in Python, (2) make the UI read the nested shape, (3) a database view.
# Chosen: option 1. Reason: the API contract stays simple, and the UI never learns about table layout.
# PostgREST returns one object for a one-to-one link and a list otherwise, so we accept both shapes.
def _flatten(row: dict) -> dict:  # turns {"inventory": {"quantity": 5}} into {"stock": 5}
    row = dict(row)  # copy so we never change the caller's data
    inv = row.pop("inventory", None)  # take the nested part out
    if isinstance(inv, list):  # list shape
        inv = inv[0] if inv else None  # first element, or nothing
    row["stock"] = inv["quantity"] if inv else None  # None means "no inventory row"
    return row  # flat dict that matches MenuItemOut


def _get_item(owner_id: str, item_id: str) -> dict | None:  # one dish with its stock, only if it belongs to this owner
    res = (  # build the query
        db.table("menu_items")  # read from the menu_items table
        .select(COLS)  # dish fields plus stock
        .eq("id", item_id)  # which dish
        .eq("owner_id", owner_id)  # and it must belong to this owner
        .limit(1)  # at most one row
        .execute()  # send the query
    )
    return _flatten(res.data[0]) if res.data else None  # None when there is no match


@router.get("", response_model=list[MenuItemOut])  # GET /menu, output filtered to MenuItemOut fields
def list_menu(owner_id: str = Depends(current_user_id)):  # owner_id comes from the verified token only
    res = (  # build the query step by step
        db.table("menu_items")  # read from the menu_items table
        .select(COLS)  # dish fields plus stock
        .eq("owner_id", owner_id)  # THE guard: without this line every restaurant's menu would leak
        .order("created_at")  # stable order, oldest first, so the UI does not shuffle
        .execute()  # send the query to Supabase
    )
    return [_flatten(r) for r in res.data]  # flatten each row, FastAPI turns the list into JSON


# DECISION PROBLEM: one new dish needs rows in TWO tables (menu_items and inventory).
# Problem: two separate calls can half-succeed, leaving a dish with no stock row.
# Options: (1) two inserts in Python + cleanup, (2) SQL function via rpc, (3) DB trigger.
# Chosen: option 1. Reason: low stakes, easiest to read and debug.
# Cost: cleanup delete can also fail (very rare), so we log it for manual repair.
# Revisit: payment + stock deduction will use option 2 because money needs all-or-nothing.
@router.post("", response_model=MenuItemOut, status_code=201)  # POST /menu, 201 = created
def create_item(body: MenuItemCreate, owner_id: str = Depends(current_user_id)):  # body is already validated by schemas.py
    try:  # step 1: create the dish
        res = (  # build the insert
            db.table("menu_items")  # target table
            .insert({**body.model_dump(), "owner_id": owner_id})  # client fields plus owner_id taken from the token
            .execute()  # send it
        )
    except APIError as e:  # for example a duplicate name
        _raise_db_error(e)  # always raises, so code below never runs after a failure
    item = res.data[0]  # insert returns the new row inside a list
    try:  # step 2: create its stock row
        db.table("inventory").insert(  # target table
            {"owner_id": owner_id, "menu_item_id": item["id"], "quantity": DEFAULT_STOCK}  # link to the dish, starting stock 5
        ).execute()  # send it
    except Exception:  # step 2 failed, so the dish is half-saved
        try:  # compensating action: undo step 1
            db.table("menu_items").delete().eq("id", item["id"]).eq("owner_id", owner_id).execute()  # remove the dish we just made
        except Exception:  # cleanup failed too
            log.exception("Orphan menu item %s: inventory insert and cleanup both failed", item["id"])  # record it so you can fix by hand
        raise HTTPException(500, "Could not create item, please try again")  # tell the client it failed
    return {**item, "stock": DEFAULT_STOCK}  # the insert result has no join, so add the stock we just wrote


@router.patch("/{item_id}", response_model=MenuItemOut)  # PATCH /menu/<id>, partial update
def update_item(item_id: str, body: MenuItemUpdate, owner_id: str = Depends(current_user_id)):  # item_id comes from the URL
    changes = {  # build only the fields the client really sent
        k: v  # keep this key and value
        for k, v in body.model_dump(exclude_unset=True).items()  # exclude_unset skips fields the client did not send
        if v is not None or k == "description"  # drop nulls, except description which may be cleared
    }  # end of the dict
    if not changes:  # nothing to update
        raise HTTPException(400, "Nothing to update")  # 400 = bad request
    try:  # run the update
        res = (  # build the update
            db.table("menu_items")  # target table
            .update(changes)  # new values
            .eq("id", item_id)  # which dish
            .eq("owner_id", owner_id)  # and it must belong to this owner, an id alone is not enough
            .execute()  # send it
        )
    except APIError as e:  # for example a rename to an existing name
        _raise_db_error(e)  # converts to a clear HTTP error
    if not res.data:  # no row matched
        raise HTTPException(404, "Item not found")  # same answer for "no such id" and "not yours", so ids cannot be probed
    fresh = _get_item(owner_id, item_id)  # read again so the answer includes stock, one extra query
    if fresh is None:  # deleted between the two calls
        raise HTTPException(404, "Item not found")  # treat like any missing item
    return fresh  # the updated dish with its stock


# DECISION PROBLEM: what happens when an owner deletes a dish that old orders used?
# Options: (1) hard delete, blocked by the DB if used in orders, (2) soft delete flag, (3) cascade delete orders.
# Chosen: option 1 with a clear 409 telling the owner to disable the dish instead.
# Reason: order history must never change, and is_available already works as a soft hide.
@router.delete("/{item_id}", status_code=204)  # DELETE /menu/<id>, 204 = success with no body
def delete_item(item_id: str, owner_id: str = Depends(current_user_id)):  # item_id from the URL
    try:  # run the delete
        res = (  # build the delete
            db.table("menu_items")  # target table
            .delete()  # remove rows
            .eq("id", item_id)  # which dish
            .eq("owner_id", owner_id)  # only if it is this owner's dish
            .execute()  # send it, the inventory row goes too (on delete cascade)
        )
    except APIError as e:  # foreign key block if an order used it
        _raise_db_error(e)  # converts to a 409 message
    if not res.data:  # delete returns deleted rows, empty means nothing was deleted
        raise HTTPException(404, "Item not found")  # no such id or not yours
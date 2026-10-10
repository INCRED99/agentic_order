from typing import Annotated  # lets us attach rules to a plain type

from pydantic import BaseModel, Field, StringConstraints  # BaseModel validates JSON, Field and StringConstraints add rules

MAX_PAISE = 10_000_000  # 1 lakh rupees in paise, a sanity cap against typos like an extra zero

# DECISION PROBLEM: what is a category?
# Options: (1) free text with a length limit, (2) a fixed list (enum), (3) a separate categories table.
# Chosen: option 1. Reason: owners can invent labels, and it needs no extra table or migration.
# Cost: typos create near-duplicates like "Drinks" and "drinks". The dashboard groups by exact text.
# We trim spaces so " Drinks" and "Drinks" are the same label.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]  # trimmed, 1 to 80 characters
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]  # trimmed, 1 to 40 characters


class MenuItemCreate(BaseModel):  # body of POST /menu
    name: Name  # required dish name
    description: str | None = Field(default=None, max_length=300)  # optional text, at most 300 characters
    category: Category = "Mains"  # optional, defaults to Mains
    price_paise: int = Field(ge=0, le=MAX_PAISE)  # integer paise: no float bugs, not negative, capped
    is_available: bool = True  # new dishes start available


class MenuItemUpdate(BaseModel):  # body of PATCH /menu/{id}
    name: Name | None = None  # every field is optional so a client can send only what changed
    description: str | None = Field(default=None, max_length=300)  # null clears the description
    category: Category | None = None  # new label
    price_paise: int | None = Field(default=None, ge=0, le=MAX_PAISE)  # new price in paise
    is_available: bool | None = None  # show or hide the dish


class MenuItemOut(BaseModel):  # what the API sends back
    id: str  # dish id
    name: str  # dish name
    description: str | None = None  # may be empty
    category: str  # label
    price_paise: int  # price in paise, the UI divides by 100
    is_available: bool  # visible to the agent or not
    stock: int | None = None  # units left from inventory; None when the dish has no inventory row


    # Paste everything below at the bottom of app/schemas.py. No new imports needed.


class OrderItemOut(BaseModel):  # one line of an order, as sent to the UI
    id: str  # line id
    menu_item_id: str  # dish id
    name: str  # dish name
    quantity: int  # how many units
    unit_price_paise: int  # price per unit in paise, snapshot from order time


class OrderOut(BaseModel):  # one order, as sent to the UI
    id: str  # order id
    customer_name: str | None = None  # None when the mail had no sender name
    customer_email: str  # sender address
    items: list[OrderItemOut]  # order lines
    total_paise: int  # order total in paise
    status: str  # PENDING, PAID, CANCELLED or REFUNDED
    payment_status: str  # UNPAID, LINK_SENT, PAID, FAILED or REFUNDED, computed from payments
    payment_link_url: str | None = None  # None until decision D4 is made
    created_at: str  # ISO timestamp
    updated_at: str  # ISO timestamp
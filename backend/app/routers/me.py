from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.db import db
from app.deps import current_user_id

router = APIRouter(tags=["me"])


def order_address(slug: str) -> str:
    user, domain = settings.shared_inbox.split("@")
    return f"{user}+{slug}@{domain}"


@router.get("/me")
def me(owner_id: str = Depends(current_user_id)):
    res = (
        db.table("profiles")
        .select("login_email,customer_email,restaurant_name,restaurant_slug")
        .eq("id", owner_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(404, "Profile not found")
    p = res.data[0]
    return {**p, "order_address": order_address(p["restaurant_slug"])}
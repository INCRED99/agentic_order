import json
import os

import redis
from dotenv import load_dotenv

load_dotenv()

_client = None

MENU_CACHE_TTL = 60  # seconds


def require_client() -> redis.Redis:
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL")
        if not url:
            raise RuntimeError("REDIS_URL not set in .env")
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        _client = client  # set only after ping succeed
    return _client


def _menu_key(owner_id: str) -> str:
    return f"menu:dishes:{owner_id}"


def menu_cache_get(owner_id: str):
    try:
        raw = require_client().get(_menu_key(owner_id))
        return json.loads(raw) if raw else None
    except Exception:
        return None  # cache fail = fall back to DB


def menu_cache_set(owner_id: str, data, ttl: int = MENU_CACHE_TTL):
    try:
        require_client().set(_menu_key(owner_id), json.dumps(data, default=str), ex=ttl)
    except Exception:
        pass


def menu_cache_delete(owner_id: str):
    try:
        require_client().delete(_menu_key(owner_id))
    except Exception:
        pass
from app.redis_client import require_client  # the shared client, reads REDIS_URL from .env

r = require_client()  # raises RedisUnavailable when REDIS_URL is empty
print("ping:", r.ping())  # True means connected over TLS
r.set("check:key", "hello", ex=30)  # write a value that deletes itself after 30 seconds
print("get:", r.get("check:key"))  # expect hello
print("incr:", r.incr("check:counter"))  # expect 1 on the first run
r.expire("check:counter", 30)  # the counter deletes itself too
print("ttl:", r.ttl("check:counter"))  # expect a number up to 30
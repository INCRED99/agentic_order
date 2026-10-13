# Import hashlib so we can use SHA-256 for the webhook signature.
import hashlib
# Import hmac so we can compute and safely compare the webhook signature.
import hmac
# Import time so we can turn "24 hours from now" into a Unix timestamp.
import time

# Import httpx, the HTTP client that already comes with supabase-py (D24).
import httpx

# Import the settings object that holds the Razorpay keys from backend/.env.
from app.config import settings

# Base URL of the Razorpay REST API, kept in one place so it is easy to change.
RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"
# Timeouts from architecture.md: 15 s for read/write/pool, 10 s to connect.
TIMEOUT = httpx.Timeout(15.0, connect=10.0)


# Error type for every Razorpay failure, so callers catch one thing.
class RazorpayError(Exception):
    # Store a message and a flag that says whether a retry could help.
    def __init__(self, message: str, retryable: bool) -> None:
        # Pass the message to the base Exception class.
        super().__init__(message)
        # ToolRetry (D28) reads this flag: True = retry, False = give up.
        self.retryable = retryable


# Guard that stops the code from ever running with live keys.
def _assert_test_mode() -> None:
    # Reuse the check from config.py: True only for keys starting with "rzp_test_".
    if not settings.razorpay_is_test:
        # Stop immediately; this is a config bug, not something to retry.
        raise RuntimeError("Refusing to run: Razorpay key is not a test key.")


# Create one payment link for one order.
def create_payment_link(
    # Keyword-only arguments, so a caller cannot mix up the order of values.
    *,
    # Our order id; also sent as reference_id (D25).
    order_id: str,
    # Amount in paise (rupees x 100). Comes from orders.total_amount (D29).
    amount_paise: int,
    # Customer email, shown on the Razorpay payment page.
    customer_email: str,
    # Short text shown to the customer on the payment page.
    description: str,
    # Link lifetime in minutes; 1440 = 24 h (D26).
    expire_minutes: int = 1440,
# Returns a small dict with only the fields we store.
) -> dict:
    # Refuse to continue if the key is not a test key.
    _assert_test_mode()
    # Razorpay wants the expiry as a Unix timestamp in seconds.
    expire_by = int(time.time()) + expire_minutes * 60
    # Build the JSON body for the Razorpay Payment Links API.
    body = {
        # Amount in paise, as an integer.
        "amount": amount_paise,
        # Currency; this project only uses Indian rupees.
        "currency": "INR",
        # One link must be paid in full; no partial payments.
        "accept_partial": False,
        # Text on the payment page.
        "description": description,
        # Customer details block.
        "customer": {"email": customer_email},
        # Razorpay sends no email or SMS; we send our own mail (D27).
        "notify": {"sms": False, "email": False},
        # No Razorpay reminders; reminder mail is a V2 item (D26).
        "reminder_enable": False,
        # Our order id, so the webhook can find the order (D25).
        "reference_id": order_id,
        # Link expiry time (D26).
        "expire_by": expire_by,
        # Extra data that comes back unchanged in the webhook.
        "notes": {"order_id": order_id},
    }
    # Catch network problems around the HTTP call.
    try:
        # Open a client with our timeouts and basic auth (key id + secret).
        with httpx.Client(
            timeout=TIMEOUT,
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
        ) as client:
            # Send the create request.
            response = client.post(f"{RAZORPAY_BASE_URL}/payment_links", json=body)
    # A timeout is worth retrying.
    except httpx.TimeoutException as exc:
        # Wrap it so the caller sees one error type.
        raise RazorpayError("Razorpay request timed out", retryable=True) from exc
    # Any other network error (DNS, connection reset) is also worth retrying.
    except httpx.TransportError as exc:
        # Wrap it so the caller sees one error type.
        raise RazorpayError("Razorpay network error", retryable=True) from exc
    # 429 (rate limit) and 5xx (Razorpay problem) may work on a later try.
    if response.status_code == 429 or response.status_code >= 500:
        # Mark as retryable.
        raise RazorpayError(
            f"Razorpay server error {response.status_code}", retryable=True
        )
    # Other 4xx errors mean our request is wrong; a retry gives the same result.
    if response.status_code >= 400:
        # Try to read Razorpay's error text; fall back to a generic message.
        try:
            # Razorpay puts the reason in error.description.
            detail = response.json().get("error", {}).get("description", "unknown")
        # The body was not JSON.
        except ValueError:
            # Use a generic message.
            detail = "unknown"
        # Mark as not retryable.
        raise RazorpayError(
            f"Razorpay rejected request ({response.status_code}): {detail}",
            retryable=False,
        )
    # Read the success body; a broken body is treated as a retryable glitch.
    try:
        # Parse the JSON response.
        data = response.json()
    # The body was not valid JSON.
    except ValueError as exc:
        # Mark as retryable.
        raise RazorpayError("Razorpay returned invalid JSON", retryable=True) from exc
    # Return only what the order row needs.
    return {
        # Razorpay's link id, stored in the unique column (D25).
        "id": data["id"],
        # The URL we put in the customer email (D27).
        "short_url": data["short_url"],
        # Expiry as Unix seconds, as Razorpay stored it.
        "expire_by": data["expire_by"],
        # Link status, normally "created" at this point.
        "status": data["status"],
    }


# Check that a webhook call really came from Razorpay.
def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    # Compute HMAC-SHA256 of the raw body with the webhook secret.
    expected = hmac.new(
        # The webhook secret is different from the API key secret.
        settings.razorpay_webhook_secret.encode(),
        # Use the exact raw bytes; re-serialised JSON would not match.
        raw_body,
        # Razorpay signs with SHA-256.
        hashlib.sha256,
    # Hex string, same format as the X-Razorpay-Signature header.
    ).hexdigest()
    # compare_digest takes the same time for every input; no timing leak.
    return hmac.compare_digest(expected, signature_header)
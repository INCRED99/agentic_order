# Import datetime tools to turn Razorpay's Unix expiry into a real timestamp.
from datetime import datetime, timezone

# Import the error type that Supabase raises when a query fails.
from postgrest.exceptions import APIError

# Import the shared Supabase client (service role, bypasses RLS, so we filter by owner_id).
from app.db import db
# Import the Razorpay helper built in D24.
from app.razorpay_client import create_payment_link


# Error type for business problems (wrong order state, expired link), not network problems.
class PaymentError(Exception):
    # Keep a short machine code next to the human message.
    def __init__(self, code: str, message: str) -> None:
        # Pass the message to the base Exception class.
        super().__init__(message)
        # The agent tool maps this code to a clear reply for the customer.
        self.code = code


# Return the first row of a Supabase result, or None when there are no rows.
def _first(result) -> dict | None:
    # result.data is a list of rows; it can be empty or None.
    rows = result.data or []
    # Give back the first row if there is one.
    return rows[0] if rows else None


# Turn a payments row into the small dict that callers use.
def _result(payment: dict) -> dict:
    # Only expose what the email and the dashboard need.
    return {
        # Id of our payments row.
        "payment_id": payment["id"],
        # The link we put in the customer email (D27).
        "payment_link_url": payment["payment_link_url"],
        # When the link stops working (D26).
        "expires_at": payment["payment_link_expires_at"],
        # Amount in paise, as stored.
        "amount_paise": payment["amount_paise"],
    }


# Main entry point. Takes ids only; the agent never passes an amount (D29).
# owner_id must come from the mail slug routing, never from mail text.
def get_or_create_payment_link(owner_id: str, order_id: str) -> dict:
    # Load the order, but only if it belongs to this restaurant.
    order = _first(
        # Start a query on the orders table.
        db.table("orders")
        # Fetch only the columns we need.
        .select("id, status, total_paise, customer_id")
        # Match the order id.
        .eq("id", order_id)
        # Match the owner, because the service role bypasses RLS.
        .eq("owner_id", owner_id)
        # We expect one row at most.
        .limit(1)
        # Run the query.
        .execute()
    )
    # No row means a wrong id or another restaurant's order.
    if order is None:
        # Same message for both cases, so ids of other restaurants cannot be probed.
        raise PaymentError("order_not_found", "Order not found")
    # Only a PENDING order can get a payment link.
    if order["status"] != "PENDING":
        # PAID, CANCELLED, REFUNDED and EXPIRED orders must not get a new link (D30).
        raise PaymentError("order_not_pending", f"Order is {order['status']}, not PENDING")
    # A zero total would create a useless link.
    if order["total_paise"] <= 0:
        # Stop before we call Razorpay.
        raise PaymentError("invalid_total", "Order total must be above zero")

    # Load the customer's email for the Razorpay payment page.
    customer = _first(
        # Start a query on the customers table.
        db.table("customers")
        # We only need the email.
        .select("email")
        # Match the customer id from the order.
        .eq("id", order["customer_id"])
        # Match the owner again.
        .eq("owner_id", owner_id)
        # We expect one row at most.
        .limit(1)
        # Run the query.
        .execute()
    )
    # An order without a customer should not exist, but check anyway.
    if customer is None:
        # Stop before we call Razorpay.
        raise PaymentError("customer_not_found", "Customer not found")

    # DECISION PROBLEM (D32, chosen by the user): which comes first, our row or the Razorpay call?
    # Options: (a) call Razorpay first, then insert, (b) insert a claim row first, then call Razorpay.
    # Chosen: (b). Reason: unique(order_id) from migration 008 lets only one caller claim the order.
    # Cost: a crash after the claim leaves a row without a link; the next call resumes from it.
    try:
        # Try to claim the order by inserting a payments row with no link yet.
        claim = db.table("payments").insert(
            {
                # Restaurant that owns the row.
                "owner_id": owner_id,
                # Order this payment is for; unique, so a second claim fails.
                "order_id": order_id,
                # Amount comes from the stored order total, never from the agent (D29).
                "amount_paise": order["total_paise"],
                # New rows start as CREATED.
                "status": "CREATED",
            }
        # Run the insert.
        ).execute()
        # Keep the row we just created.
        payment = claim.data[0]
    # The insert failed; check why.
    except APIError as exc:
        # 23505 is Postgres "unique violation": a row for this order already exists.
        if exc.code != "23505":
            # Any other database error is a real problem; let it go up.
            raise
        # Read the existing row; this is the retry or race case.
        payment = _first(
            # Start a query on the payments table.
            db.table("payments")
            # Fetch every column.
            .select("*")
            # Match the order.
            .eq("order_id", order_id)
            # Match the owner.
            .eq("owner_id", owner_id)
            # We expect one row at most.
            .limit(1)
            # Run the query.
            .execute()
        )
        # The conflict said a row exists, so None here is unexpected.
        if payment is None:
            # Let the original database error go up.
            raise

    # A row that is not CREATED was already paid, failed or refunded.
    if payment["status"] != "CREATED":
        # Do not create or return a link for it.
        raise PaymentError("payment_not_open", f"Payment is {payment['status']}")

    # DECISION PROBLEM (D25, chosen by the user): what happens on a repeat call for the same order?
    # Options: (a) raise an error, (b) return the link that already exists.
    # Chosen: (b). Reason: ToolRetry and a re-run of the same mail must not fail or double-charge.
    # Cost: the caller cannot tell "new" from "reused" unless we add a flag later.
    # The row already has a link, so reuse it.
    if payment["payment_link_url"]:
        # Check that the stored link has not expired yet (D26).
        expires_at = datetime.fromisoformat(payment["payment_link_expires_at"])
        # An expired link must not be sent again; a later sweep sets the order to EXPIRED (D30).
        if expires_at <= datetime.now(timezone.utc):
            # Tell the caller clearly.
            raise PaymentError("link_expired", "Payment link has expired")
        # Return the existing link.
        return _result(payment)

    # No link yet: call Razorpay. RazorpayError goes up with its retryable flag (D28).
    link = create_payment_link(
        # Our order id, sent as reference_id (D25).
        order_id=order_id,
        # Amount from the stored order total (D29).
        amount_paise=order["total_paise"],
        # Customer email for the payment page.
        customer_email=customer["email"],
        # Short text on the payment page; first 8 characters of the id are enough to match.
        description=f"Order {order_id[:8]}",
    )
    # Convert Razorpay's Unix expiry to an ISO timestamp for the timestamptz column.
    expires_iso = datetime.fromtimestamp(link["expire_by"], tz=timezone.utc).isoformat()

    # Save the link on the claim row.
    updated = _first(
        # Start an update on the payments table.
        db.table("payments")
        # Set the three new values.
        .update(
            {
                # Razorpay link id, unique (migration 008).
                "razorpay_payment_link_id": link["id"],
                # URL for the customer email.
                "payment_link_url": link["short_url"],
                # Expiry as a timestamp.
                "payment_link_expires_at": expires_iso,
            }
        )
        # Update only our claim row.
        .eq("id", payment["id"])
        # Match the owner.
        .eq("owner_id", owner_id)
        # Only if no link was saved yet, so we never overwrite a link another caller saved.
        .is_("razorpay_payment_link_id", "null")
        # Run the update.
        .execute()
    )
    # No row updated means another caller saved a link first.
    if updated is None:
        # Read the winner's row.
        updated = _first(
            # Start a query on the payments table.
            db.table("payments")
            # Fetch every column.
            .select("*")
            # Match our claim row.
            .eq("id", payment["id"])
            # Match the owner.
            .eq("owner_id", owner_id)
            # We expect one row at most.
            .limit(1)
            # Run the query.
            .execute()
        )
        # Still nothing: the row vanished, which should not happen.
        if updated is None:
            # Stop with a clear error.
            raise PaymentError("payment_row_missing", "Payment row disappeared")
    # Return the saved link.
    return _result(updated)
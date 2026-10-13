import Card from "../components/ui/Card"; // shared panel box
import { useOrders } from "../hooks/useOrders"; // real orders from GET /orders (D44: reuse, no new route)
import { formatMoney, formatTimeAgo } from "../lib/format"; // paise and time formatting
import type { Order, PaymentStatus } from "../types"; // UI shapes

const STATUS_LABEL: Record<PaymentStatus, string> = { // text shown in the badge
    UNPAID: "Unpaid", // no payment row yet
    LINK_SENT: "Link sent", // link exists, nothing paid
    PAID: "Paid", // webhook confirmed the money
    FAILED: "Failed", // payment failed
    REFUNDED: "Refunded", // money returned
    EXPIRED: "Expired", // D30: link died unpaid, the sweep expired the order
};

const STATUS_STYLE: Record<PaymentStatus, string> = { // color classes per status
    UNPAID: "bg-latte/30 text-espresso", // neutral
    LINK_SENT: "bg-saffron/25 text-espresso", // waiting
    PAID: "bg-basil/20 text-basil", // good
    FAILED: "bg-chili/15 text-chili", // bad
    REFUNDED: "bg-latte/30 text-espresso", // neutral
    EXPIRED: "bg-latte/30 text-espresso", // neutral, nothing to do anymore
};

function PaymentBadge({ status }: { status: PaymentStatus }) { // small colored pill
    return ( // the pill
        <span
            className={`inline-block whitespace-nowrap rounded-full px-3 py-1 text-sm font-medium ${STATUS_STYLE[status]}`} // look from the record above
        >
            {STATUS_LABEL[status]} {/* label from the record above */}
        </span>
    );
}

function customerLabel(order: Order): string { // name when known, otherwise the email
    return order.customerName ?? order.customerEmail; // ?? uses the right side when the left is null
}

// DECISION PROBLEM (D44, assumed): where do the payment rows come from?
// Options: (1) reuse GET /orders, (2) a new GET /payments route.
// Chosen: option 1. Reason: payments are one row per order, and /orders already joins them with the right status words.
// Cost: only the newest 50 orders are loaded, so "Collected" counts only those. Move to option 2 when 50 is too few.
export function Payments() { // the Payments page component
    const { orders, loading, error, reload } = useOrders(); // data and state come from the hook

    if (loading) { // first load still running
        return <p className="text-latte">Loading payments...</p>; // simple loading text
    }

    if (error) { // the list could not be loaded
        return ( // error screen with a retry button
            <div> {/* wrapper */}
                <p className="text-chili">{error}</p> {/* show the reason */}
                <button // retry button
                    type="button" // not a submit button
                    onClick={reload} // load the list again
                    className="mt-3 rounded-lg bg-tomato px-4 py-2 text-white" // button look
                >
                    Try again {/* button text */}
                </button>
            </div>
        );
    }

    const collected = orders // money that really arrived
        .filter((o) => o.paymentStatus === "PAID") // only paid orders
        .reduce((sum, o) => sum + o.totalPaise, 0); // add the totals in paise
    const waiting = orders.filter((o) => o.paymentStatus === "LINK_SENT").length; // links out, nothing paid yet
    const failed = orders.filter((o) => o.paymentStatus === "FAILED").length; // failed payments

    const stats = [ // the three summary boxes
        { label: "Collected", value: formatMoney(collected) }, // paise to display text
        { label: "Waiting for payment", value: String(waiting) }, // count as text
        { label: "Failed", value: String(failed) }, // count as text
    ];

    return ( // normal screen
        <div> {/* page wrapper */}
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Payments</h1> {/* page title */}
            <p className="mt-1 text-espresso/70"> {/* header line */}
                Only the verified Razorpay webhook marks an order paid. {/* kept from the old page */}
            </p>

            <div className="mt-4 grid gap-3 sm:grid-cols-3"> {/* summary boxes */}
                {stats.map((s) => ( // one box per stat
                    <Card key={s.label}> {/* key helps React track the box */}
                        <p className="text-sm text-espresso/70">{s.label}</p> {/* box title */}
                        <p className="mt-1 font-heading text-2xl text-espresso">{s.value}</p> {/* box number */}
                    </Card>
                ))}
            </div>

            {orders.length === 0 ? ( // no orders yet
                <Card className="mt-4"> {/* empty state panel */}
                    <p className="text-espresso/70">No payments yet. They appear when an order gets a payment link.</p> {/* tells the owner what to expect */}
                </Card>
            ) : ( // at least one order
                <> {/* fragment, groups the table and the cards without an extra element */}
                    {/* Desktop table */}
                    <Card className="mt-4 hidden overflow-x-auto md:block"> {/* hidden on phones */}
                        <table className="w-full text-left"> {/* the table */}
                            <thead> {/* header row group */}
                                <tr className="border-b border-latte/40 text-sm text-espresso/70"> {/* header row */}
                                    <th className="py-2 pr-4 font-medium">Order</th> {/* column title */}
                                    <th className="py-2 pr-4 font-medium">Customer</th> {/* column title */}
                                    <th className="py-2 pr-4 font-medium">Amount</th> {/* column title */}
                                    <th className="py-2 pr-4 font-medium">Payment</th> {/* column title */}
                                    <th className="py-2 font-medium">Created</th> {/* column title */}
                                </tr>
                            </thead>
                            <tbody> {/* body row group */}
                                {orders.map((o) => ( // one row per order, the API already sorts newest first
                                    <tr key={o.id} className="border-b border-latte/20 last:border-0"> {/* key helps React track the row */}
                                        <td className="py-3 pr-4 font-mono text-xs text-espresso">{o.id.slice(0, 8)}</td> {/* short id, same as the Orders page */}
                                        <td className="py-3 pr-4 text-espresso">{customerLabel(o)}</td> {/* name or email */}
                                        <td className="py-3 pr-4 text-espresso">{formatMoney(o.totalPaise)}</td> {/* amount */}
                                        <td className="py-3 pr-4"><PaymentBadge status={o.paymentStatus} /></td> {/* payment pill */}
                                        <td className="py-3 text-espresso/70">{formatTimeAgo(o.createdAt)}</td> {/* relative time */}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </Card>

                    {/* Phone cards */}
                    <ul className="mt-4 grid gap-3 md:hidden"> {/* hidden from md up */}
                        {orders.map((o) => ( // one card per order
                            <li key={o.id}> {/* key helps React track the card */}
                                <Card className="flex flex-col gap-2"> {/* card with spacing */}
                                    <div className="flex items-start justify-between gap-2"> {/* top row */}
                                        <div className="min-w-0"> {/* min-w-0 lets long names truncate */}
                                            <p className="truncate font-medium text-espresso">{customerLabel(o)}</p> {/* name or email */}
                                            <p className="font-mono text-xs text-espresso/60">Order {o.id.slice(0, 8)}</p> {/* short id */}
                                        </div>
                                        <PaymentBadge status={o.paymentStatus} /> {/* payment pill */}
                                    </div>
                                    <div className="flex items-center justify-between text-sm"> {/* bottom row */}
                                        <span className="font-medium text-espresso">{formatMoney(o.totalPaise)}</span> {/* amount */}
                                        <span className="text-espresso/60">{formatTimeAgo(o.createdAt)}</span> {/* relative time */}
                                    </div>
                                </Card>
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    );
}
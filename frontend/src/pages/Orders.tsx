// Orders page on real data from GET /orders.
// Desktop (md+): table. Phone: stack of cards.
// Both are in the markup; Tailwind hides one (hidden md:block / md:hidden).

import Card from '../components/ui/Card' // shared panel box
import { StatusBadge } from '../components/ui/Badge' // colored status pill
import { useOrders } from '../hooks/useOrders' // real orders from the backend
import { formatMoney, formatTimeAgo } from '../lib/format' // paise and time formatting
import type { Order } from '../types' // UI order shape

// "2x Butter Chicken, 4x Garlic Naan"
function summarizeItems(order: Order): string { // one line that lists the order lines
    return order.items.map((i) => `${i.quantity}x ${i.name}`).join(', ') // join the lines with commas
}

function customerLabel(order: Order): string { // name when known, otherwise the email
    return order.customerName ?? order.customerEmail // ?? uses the right side when the left is null
}

// DECISION PROBLEM: order ids are long UUIDs. How does the screen show them?
// Options: (1) show the full id, (2) show the first 8 characters.
// Chosen: option 2. Reason: 8 characters are enough to tell orders apart on screen and keep the table narrow.
// Cost: the short id is not the full id. A support lookup should use the full id from the API.
function shortId(order: Order): string { // first 8 characters of the id
    return order.id.slice(0, 8) // slice keeps characters 0 to 7
}

export default function Orders() { // the Orders page component
    const { orders, loading, error, reload } = useOrders() // data and state come from the hook

    if (loading) { // first load still running
        return <p className="text-latte">Loading orders...</p> // simple loading text
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
        )
    }

    return ( // normal screen
        <div> {/* page wrapper */}
            <h1 className="mb-4 text-2xl font-bold sm:mb-6 sm:text-3xl">Orders</h1> {/* page title */}

            {orders.length === 0 ? ( // no orders yet
                <Card> {/* empty state panel */}
                    <p className="text-espresso/70"> {/* explanation text */}
                        No orders yet. Orders appear here when a customer emails your order address. {/* tells the owner what to do */}
                    </p>
                </Card>
            ) : ( // at least one order
                <> {/* fragment, groups the table and the cards without an extra element */}
                    {/* Desktop table */}
                    <Card className="hidden overflow-x-auto p-0 sm:p-0 md:block"> {/* hidden on phones */}
                        <table className="w-full text-left text-sm"> {/* the table */}
                            <thead className="border-b border-latte/40 text-espresso/70"> {/* header row group */}
                                <tr> {/* header row */}
                                    <th className="px-4 py-3 font-semibold">Order</th> {/* column title */}
                                    <th className="px-4 py-3 font-semibold">Customer</th> {/* column title */}
                                    <th className="px-4 py-3 font-semibold">Items</th> {/* column title */}
                                    <th className="px-4 py-3 text-right font-semibold">Total</th> {/* column title, right aligned */}
                                    <th className="px-4 py-3 font-semibold">Status</th> {/* column title */}
                                    <th className="px-4 py-3 font-semibold">Payment</th> {/* column title */}
                                    <th className="px-4 py-3 font-semibold">Placed</th> {/* column title */}
                                </tr>
                            </thead>
                            <tbody> {/* body row group */}
                                {orders.map((order) => ( // one row per order
                                    <tr key={order.id} className="border-b border-latte/20 last:border-0"> {/* key helps React track the row */}
                                        <td className="px-4 py-3 font-mono text-xs">{shortId(order)}</td> {/* short order id */}
                                        <td className="px-4 py-3"> {/* customer cell */}
                                            <div className="font-semibold">{customerLabel(order)}</div> {/* name or email */}
                                            {order.customerName && ( // show the email under the name only when a name exists
                                                <div className="text-xs text-espresso/70">{order.customerEmail}</div> // email line
                                            )}
                                        </td>
                                        <td className="max-w-xs px-4 py-3 text-espresso/80">{summarizeItems(order)}</td> {/* order lines as text */}
                                        <td className="tabular px-4 py-3 text-right font-semibold">{formatMoney(order.totalPaise)}</td> {/* total, tabular keeps digits aligned */}
                                        <td className="px-4 py-3"><StatusBadge status={order.status} /></td> {/* order status pill */}
                                        <td className="px-4 py-3"><StatusBadge status={order.paymentStatus} /></td> {/* payment status pill */}
                                        <td className="whitespace-nowrap px-4 py-3 text-espresso/70">{formatTimeAgo(order.createdAt)}</td> {/* relative time */}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </Card>

                    {/* Phone cards */}
                    <div className="flex flex-col gap-3 md:hidden"> {/* hidden from md up */}
                        {orders.map((order) => ( // one card per order
                            <Card key={order.id}> {/* key helps React track the card */}
                                <div className="flex items-start justify-between gap-3"> {/* top row */}
                                    <div className="min-w-0"> {/* min-w-0 lets long names truncate */}
                                        <div className="truncate font-semibold">{customerLabel(order)}</div> {/* name or email */}
                                        <div className="font-mono text-xs text-espresso/70">{shortId(order)}</div> {/* short order id */}
                                    </div>
                                    <div className="tabular font-bold">{formatMoney(order.totalPaise)}</div> {/* total */}
                                </div>

                                <p className="mt-2 text-sm text-espresso/80">{summarizeItems(order)}</p> {/* order lines as text */}

                                <div className="mt-3 flex flex-wrap items-center gap-2"> {/* badge row */}
                                    <StatusBadge status={order.status} /> {/* order status pill */}
                                    <StatusBadge status={order.paymentStatus} /> {/* payment status pill */}
                                    <span className="ml-auto text-xs text-espresso/70">{formatTimeAgo(order.createdAt)}</span> {/* relative time */}
                                </div>
                            </Card>
                        ))}
                    </div>
                </>
            )}
        </div>
    )
}
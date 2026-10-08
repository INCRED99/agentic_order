// Orders page, running on mock data for now.
// Desktop (md+): table. Phone: stack of cards.
// Both are in the markup; Tailwind hides one (hidden md:block / md:hidden).

import Card from '../components/ui/Card'
import { StatusBadge } from '../components/ui/Badge'
import { mockOrders } from '../data/mock'
import { formatMoney, formatTimeAgo } from '../lib/format'
import type { Order } from '../types'

// Newest first. Sorted once; mock list never changes.
const orders = [...mockOrders].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
)

// "2x Butter Chicken, 4x Garlic Naan"
function summarizeItems(order: Order): string {
    return order.items.map((i) => `${i.quantity}x ${i.name}`).join(', ')
}

function customerLabel(order: Order): string {
    return order.customerName ?? order.customerEmail
}

export default function Orders() {
    return (
        <div>
            <h1 className="mb-4 text-2xl font-bold sm:mb-6 sm:text-3xl">Orders</h1>

            {/* Desktop table */}
            <Card className="hidden overflow-x-auto p-0 sm:p-0 md:block">
                <table className="w-full text-left text-sm">
                    <thead className="border-b border-latte/40 text-espresso/70">
                        <tr>
                            <th className="px-4 py-3 font-semibold">Order</th>
                            <th className="px-4 py-3 font-semibold">Customer</th>
                            <th className="px-4 py-3 font-semibold">Items</th>
                            <th className="px-4 py-3 text-right font-semibold">Total</th>
                            <th className="px-4 py-3 font-semibold">Status</th>
                            <th className="px-4 py-3 font-semibold">Payment</th>
                            <th className="px-4 py-3 font-semibold">Placed</th>
                        </tr>
                    </thead>
                    <tbody>
                        {orders.map((order) => (
                            <tr key={order.id} className="border-b border-latte/20 last:border-0">
                                <td className="px-4 py-3 font-mono text-xs">{order.id}</td>
                                <td className="px-4 py-3">
                                    <div className="font-semibold">{customerLabel(order)}</div>
                                    {order.customerName && (
                                        <div className="text-xs text-espresso/70">{order.customerEmail}</div>
                                    )}
                                </td>
                                <td className="max-w-xs px-4 py-3 text-espresso/80">
                                    {summarizeItems(order)}
                                </td>
                                <td className="px-4 py-3 text-right font-semibold">
                                    {formatMoney(order.totalPaise)}
                                </td>
                                <td className="px-4 py-3">
                                    <StatusBadge status={order.status} />
                                </td>
                                <td className="px-4 py-3">
                                    <StatusBadge status={order.paymentStatus} />
                                </td>
                                <td className="whitespace-nowrap px-4 py-3 text-espresso/70">
                                    {formatTimeAgo(order.createdAt)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </Card>

            {/* Phone cards */}
            <div className="flex flex-col gap-3 md:hidden">
                {orders.map((order) => (
                    <Card key={order.id}>
                        <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                                <div className="truncate font-semibold">{customerLabel(order)}</div>
                                <div className="font-mono text-xs text-espresso/70">{order.id}</div>
                            </div>
                            <div className="font-bold">{formatMoney(order.totalPaise)}</div>
                        </div>

                        <p className="mt-2 text-sm text-espresso/80">{summarizeItems(order)}</p>

                        <div className="mt-3 flex flex-wrap items-center gap-2">
                            <StatusBadge status={order.status} />
                            <StatusBadge status={order.paymentStatus} />
                            <span className="ml-auto text-xs text-espresso/70">
                                {formatTimeAgo(order.createdAt)}
                            </span>
                        </div>
                    </Card>
                ))}
            </div>
        </div>
    )
}
import Card from "../components/ui/Card";
import { mockOrders } from "../data/mock";
import { formatMoney, formatTimeAgo } from "../lib/format";
import type { PaymentStatus } from "../types";

const STATUS_LABEL: Record<PaymentStatus, string> = {
    UNPAID: "Unpaid",
    LINK_SENT: "Link sent",
    PAID: "Paid",
    FAILED: "Failed",
    REFUNDED: "Refunded",
};

const STATUS_STYLE: Record<PaymentStatus, string> = {
    UNPAID: "bg-latte/30 text-espresso",
    LINK_SENT: "bg-saffron/25 text-espresso",
    PAID: "bg-basil/20 text-basil",
    FAILED: "bg-chili/15 text-chili",
    REFUNDED: "bg-latte/30 text-espresso",
};

function PaymentBadge({ status }: { status: PaymentStatus }) {
    return (
        <span
            className={`inline-block whitespace-nowrap rounded-full px-3 py-1 text-sm font-medium ${STATUS_STYLE[status]}`}
        >
            {STATUS_LABEL[status]}
        </span>
    );
}

export function Payments() {
    const rows = [...mockOrders].sort(
        (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );

    const collected = rows
        .filter((o) => o.paymentStatus === "PAID")
        .reduce((sum, o) => sum + o.totalPaise, 0);
    const waiting = rows.filter((o) => o.paymentStatus === "LINK_SENT").length;
    const failed = rows.filter((o) => o.paymentStatus === "FAILED").length;

    const stats = [
        { label: "Collected", value: formatMoney(collected) },
        { label: "Waiting for payment", value: String(waiting) },
        { label: "Failed", value: String(failed) },
    ];

    return (
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Payments</h1>
            <p className="mt-1 text-espresso/70">
                Only the verified Razorpay webhook marks an order paid.
            </p>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {stats.map((s) => (
                    <Card key={s.label}>
                        <p className="text-sm text-espresso/70">{s.label}</p>
                        <p className="mt-1 font-heading text-2xl text-espresso">{s.value}</p>
                    </Card>
                ))}
            </div>

            {/* Desktop table */}
            <Card className="mt-4 hidden overflow-x-auto md:block">
                <table className="w-full text-left">
                    <thead>
                        <tr className="border-b border-latte/40 text-sm text-espresso/70">
                            <th className="py-2 pr-4 font-medium">Order</th>
                            <th className="py-2 pr-4 font-medium">Customer</th>
                            <th className="py-2 pr-4 font-medium">Amount</th>
                            <th className="py-2 pr-4 font-medium">Payment</th>
                            <th className="py-2 font-medium">Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((o) => (
                            <tr key={o.id} className="border-b border-latte/20 last:border-0">
                                <td className="py-3 pr-4 text-espresso">{o.id}</td>
                                <td className="py-3 pr-4 text-espresso">
                                    {o.customerName ?? o.customerEmail}
                                </td>
                                <td className="py-3 pr-4 text-espresso">{formatMoney(o.totalPaise)}</td>
                                <td className="py-3 pr-4">
                                    <PaymentBadge status={o.paymentStatus} />
                                </td>
                                <td className="py-3 text-espresso/70">{formatTimeAgo(o.createdAt)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </Card>

            {/* Phone cards */}
            <ul className="mt-4 grid gap-3 md:hidden">
                {rows.map((o) => (
                    <li key={o.id}>
                        <Card className="flex flex-col gap-2">
                            <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                    <p className="truncate font-medium text-espresso">
                                        {o.customerName ?? o.customerEmail}
                                    </p>
                                    <p className="text-sm text-espresso/60">Order {o.id}</p>
                                </div>
                                <PaymentBadge status={o.paymentStatus} />
                            </div>
                            <div className="flex items-center justify-between text-sm">
                                <span className="font-medium text-espresso">{formatMoney(o.totalPaise)}</span>
                                <span className="text-espresso/60">{formatTimeAgo(o.createdAt)}</span>
                            </div>
                        </Card>
                    </li>
                ))}
            </ul>
        </div>
    );
}
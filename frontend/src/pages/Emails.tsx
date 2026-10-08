import { useState } from "react";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import Card from "../components/ui/Card";
import { mockEmails } from "../data/mock";
import { formatTimeAgo } from "../lib/format";
import type { EmailDirection } from "../types";

type Filter = "ALL" | EmailDirection;

const FILTERS: { value: Filter; label: string }[] = [
    { value: "ALL", label: "All" },
    { value: "INBOUND", label: "Received" },
    { value: "OUTBOUND", label: "Sent" },
];

export function Emails() {
    const [filter, setFilter] = useState<Filter>("ALL");

    const emails = [...mockEmails]
        .filter((e) => filter === "ALL" || e.direction === filter)
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

    return (
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Emails</h1>
            <p className="mt-1 text-espresso/70">Mail the agent received and sent.</p>

            <div className="mt-4 flex gap-2" role="group" aria-label="Filter emails">
                {FILTERS.map((f) => (
                    <button
                        key={f.value}
                        type="button"
                        aria-pressed={filter === f.value}
                        onClick={() => setFilter(f.value)}
                        className={`min-h-11 rounded-full px-4 text-sm font-medium transition-colors ${filter === f.value
                            ? "bg-tomato text-paper"
                            : "bg-latte/25 text-espresso hover:bg-latte/40"
                            }`}
                    >
                        {f.label}
                    </button>
                ))}
            </div>

            {emails.length === 0 ? (
                <Card className="mt-4 text-center text-espresso/70">No emails here yet.</Card>
            ) : (
                <ul className="mt-4 grid gap-3">
                    {emails.map((e) => {
                        const inbound = e.direction === "INBOUND";
                        const Icon = inbound ? ArrowDownLeft : ArrowUpRight;
                        return (
                            <li key={e.id}>
                                <Card className="flex items-start gap-3">
                                    <span
                                        className={`mt-0.5 shrink-0 rounded-full p-2 ${inbound ? "bg-saffron/25" : "bg-basil/20"
                                            }`}
                                    >
                                        <Icon
                                            className="h-4 w-4 text-espresso"
                                            aria-label={inbound ? "Received" : "Sent"}
                                        />
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-start justify-between gap-2">
                                            <p className="truncate font-medium text-espresso">{e.subject}</p>
                                            <span className="shrink-0 text-sm text-espresso/60">
                                                {formatTimeAgo(e.createdAt)}
                                            </span>
                                        </div>
                                        <p className="truncate text-sm text-espresso/60">
                                            {inbound ? "From" : "To"} {e.address}
                                        </p>
                                        <p className="mt-1 line-clamp-2 text-sm text-espresso/80">{e.preview}</p>
                                        {e.orderId && (
                                            <p className="mt-2 text-sm text-espresso/60">Order {e.orderId}</p>
                                        )}
                                    </div>
                                </Card>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}
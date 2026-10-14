import { useState } from "react"; // filter state
import { ArrowDownLeft, ArrowUpRight } from "lucide-react"; // direction icons
import Card from "../components/ui/Card"; // shared panel box
import { useEmails } from "../hooks/useEmails"; // real mails from GET /emails
import { formatTimeAgo } from "../lib/format"; // "5 min ago" formatting
import type { EmailDirection, EmailStatus } from "../types"; // shared words

type Filter = "ALL" | EmailDirection; // which mails to show

const FILTERS: { value: Filter; label: string }[] = [ // filter buttons
    { value: "ALL", label: "All" },
    { value: "INBOUND", label: "Received" },
    { value: "OUTBOUND", label: "Sent" },
];

const STATUS_LABEL: Record<EmailStatus, string> = { // A23: text on the pill
    received: "Waiting", // stored, agent not started
    processing: "Processing", // agent running
    processed: "Handled", // agent finished
    failed: "Failed", // agent crashed
};

const STATUS_STYLE: Record<EmailStatus, string> = { // colors of the pill
    received: "bg-saffron/25 text-espresso", // yellow
    processing: "bg-espresso/10 text-espresso", // neutral
    processed: "bg-basil/20 text-basil", // green
    failed: "bg-chili/15 text-chili", // red
};

export function Emails() { // the Emails page
    const [filter, setFilter] = useState<Filter>("ALL"); // current filter
    const { emails: all, loading, error } = useEmails(); // data, first-load flag and error text

    const emails = all.filter((e) => filter === "ALL" || e.direction === filter); // the API already sorts newest first

    return ( // page markup
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Emails</h1>
            <p className="mt-1 text-espresso/70">Mail the agent received. Sent mails will appear here later.</p>

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

            {error && ( // plain text error, React escapes it
                <p className="mt-3 rounded-lg bg-chili/15 px-3 py-2 text-sm text-chili">{error}</p>
            )}

            {loading ? ( // first load still running
                <p className="mt-4 text-espresso/70">Loading emails...</p>
            ) : emails.length === 0 && !error ? ( // nothing to show
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
                                            <p className="truncate font-medium text-espresso">{e.subject || "(no subject)"}</p>
                                            <span className="shrink-0 text-sm text-espresso/60">
                                                {formatTimeAgo(e.createdAt)}
                                            </span>
                                        </div>
                                        <p className="truncate text-sm text-espresso/60">
                                            {inbound ? "From" : "To"} {e.address}
                                        </p>
                                        <p className="mt-1 line-clamp-2 text-sm text-espresso/80">{e.preview}</p>
                                        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-espresso/60">
                                            {inbound && e.status && ( // A23: only inbound mail has an agent status
                                                <span className={`rounded-full px-3 py-0.5 font-medium ${STATUS_STYLE[e.status]}`}>
                                                    {STATUS_LABEL[e.status]}
                                                </span>
                                            )}
                                            {e.orderId && <span>Order {e.orderId.slice(0, 8)}</span>}
                                        </div>
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
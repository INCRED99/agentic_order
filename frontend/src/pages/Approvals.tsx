import { useState } from "react";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import { mockApprovals } from "../data/mock";
import { formatTimeAgo } from "../lib/format";
import type { Approval, ApprovalAction } from "../types";

const ACTION_LABELS: Record<ApprovalAction, string> = {
    apply_discount: "Apply discount",
    cancel_order: "Cancel order",
    refund_order: "Refund order",
    accept_large_order: "Accept large order",
    substitute_item: "Substitute item",
};

type Decision = "APPROVED" | "REJECTED";

export function Approvals() {
    const [approvals, setApprovals] = useState<Approval[]>(mockApprovals);
    const [busy, setBusy] = useState<{ id: string; decision: Decision } | null>(null);

    const pending = approvals.filter((a) => a.status === "PENDING");
    const resolved = approvals.filter((a) => a.status !== "PENDING");

    // Fake network call. Replace with real API call later.
    function decide(id: string, decision: Decision) {
        setBusy({ id, decision });
        setTimeout(() => {
            setApprovals((prev) =>
                prev.map((a) => (a.id === id ? { ...a, status: decision } : a)),
            );
            setBusy(null);
        }, 700);
    }

    return (
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Approvals</h1>
            <p className="mt-1 text-espresso/70">
                Risky agent actions wait here until staff decide.
            </p>

            <h2 className="mt-6 font-heading text-lg text-espresso">
                Waiting ({pending.length})
            </h2>
            {pending.length === 0 ? (
                <Card className="mt-3 text-center text-espresso/70">Nothing waiting. All clear.</Card>
            ) : (
                <ul className="mt-3 grid gap-3 md:grid-cols-2">
                    {pending.map((a) => {
                        const isBusy = busy?.id === a.id;
                        return (
                            <li key={a.id}>
                                <Card className="flex h-full flex-col gap-3">
                                    <div className="flex items-start justify-between gap-2">
                                        <span className="rounded-full bg-saffron/20 px-3 py-1 text-sm font-medium text-espresso">
                                            {ACTION_LABELS[a.action]}
                                        </span>
                                        <span className="text-sm text-espresso/60">
                                            {formatTimeAgo(a.createdAt)}
                                        </span>
                                    </div>
                                    <p className="text-espresso">{a.reason}</p>
                                    <p className="text-sm text-espresso/60">Order {a.orderId}</p>
                                    <div className="mt-auto flex gap-2">
                                        <Button
                                            variant="success"
                                            className="flex-1"
                                            loading={isBusy && busy?.decision === "APPROVED"}
                                            disabled={isBusy}
                                            onClick={() => decide(a.id, "APPROVED")}
                                        >
                                            Approve
                                        </Button>
                                        <Button
                                            variant="danger"
                                            className="flex-1"
                                            loading={isBusy && busy?.decision === "REJECTED"}
                                            disabled={isBusy}
                                            onClick={() => decide(a.id, "REJECTED")}
                                        >
                                            Reject
                                        </Button>
                                    </div>
                                </Card>
                            </li>
                        );
                    })}
                </ul>
            )}

            {resolved.length > 0 && (
                <>
                    <h2 className="mt-8 font-heading text-lg text-espresso">
                        Decided ({resolved.length})
                    </h2>
                    <ul className="mt-3 grid gap-3 md:grid-cols-2">
                        {resolved.map((a) => (
                            <li key={a.id}>
                                <Card className="opacity-70">
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="font-medium text-espresso">
                                            {ACTION_LABELS[a.action]}
                                        </span>
                                        <span
                                            className={
                                                a.status === "APPROVED"
                                                    ? "text-sm font-medium text-basil"
                                                    : "text-sm font-medium text-chili"
                                            }
                                        >
                                            {a.status === "APPROVED" ? "Approved" : "Rejected"}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-sm text-espresso/70">{a.reason}</p>
                                </Card>
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    );
}
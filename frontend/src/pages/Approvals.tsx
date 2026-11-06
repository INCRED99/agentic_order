import { useState } from "react";
import Card from "../components/ui/Card"; // shared panel box
import Button from "../components/ui/Button"; // shared button with variant and loading props
import { useApprovals } from "../hooks/useApprovals"; // real approvals from the backend
import { formatTimeAgo } from "../lib/format"; // relative time text
import type { Approval, ApprovalAction } from "../types"; // the known action names
import type { Decision } from "../lib/approvalsApi";

const ACTION_LABELS: Record<ApprovalAction, string> = { // readable names for the known actions
    apply_discount: "Apply discount", // label
    cancel_order: "Cancel order", // label
    refund_order: "Refund order", // label
    accept_large_order: "Accept large order", // label
    substitute_item: "Substitute item", // label
};

// The database stores action as free text, so a new action can arrive that the UI does not know yet.
function actionLabel(action: string): string { // readable name, or the raw text as a fallback
    return ACTION_LABELS[action as ApprovalAction] ?? action; // unknown action shows its raw name instead of a blank
}

function PendingApprovalCard({
    a,
    busy,
    onDecide,
}: {
    a: Approval;
    busy: { id: string; decision: Decision } | null;
    onDecide: (id: string, decision: Decision, payload?: { approved_items?: string[] }) => void;
}) {
    const isThis = busy?.id === a.id;
    const anyBusy = busy !== null;
    const items = a.items || [];

    // Track selected items for discount permissions (default all selected)
    const [selectedItems, setSelectedItems] = useState<Record<string, boolean>>(() => {
        const init: Record<string, boolean> = {};
        for (const item of items) {
            init[item.menuItemId] = true;
        }
        return init;
    });

    const hasItems = items.length > 0;
    const isDiscount = a.action === "apply_discount";

    // Calculate dynamic totals
    const calculatedDiscountedTotal = items.reduce((acc, it) => {
        const isSelected = selectedItems[it.menuItemId] ?? true;
        const disc = isDiscount && isSelected ? (it.discountPercent ?? a.discountPercent ?? 10) : 0;
        const itemTotal = it.quantity * it.unitPricePaise;
        return acc + Math.floor((itemTotal * (100 - disc)) / 100);
    }, 0);

    const toggleItem = (menuItemId: string) => {
        setSelectedItems((prev) => ({ ...prev, [menuItemId]: !prev[menuItemId] }));
    };

    const toggleAll = (select: boolean) => {
        const next: Record<string, boolean> = {};
        for (const it of items) {
            next[it.menuItemId] = select;
        }
        setSelectedItems(next);
    };

    return (
        <Card className="flex h-full flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
                <span className="rounded-full bg-saffron/20 px-3 py-1 text-sm font-medium text-espresso">
                    {actionLabel(a.action)}
                </span>
                <span className="text-sm text-espresso/60">{formatTimeAgo(a.createdAt)}</span>
            </div>

            <p className="text-espresso font-medium">{a.reason || "No reason given."}</p>

            {a.orderId && <p className="text-xs text-espresso/60">Order #{a.orderId.slice(0, 8)}</p>}

            {/* Item-level discount permissions */}
            {hasItems && isDiscount && (
                <div className="mt-1 rounded-lg border border-espresso/10 bg-latte/10 p-3 text-sm">
                    <div className="flex items-center justify-between mb-2 pb-1 border-b border-espresso/10">
                        <span className="text-xs font-semibold uppercase tracking-wider text-espresso/70">
                            Items Asked for Discount ({items.length})
                        </span>
                        <div className="flex gap-2 text-xs">
                            <button
                                type="button"
                                onClick={() => toggleAll(true)}
                                className="text-basil hover:underline font-medium"
                            >
                                Allow all
                            </button>
                            <span className="text-espresso/30">|</span>
                            <button
                                type="button"
                                onClick={() => toggleAll(false)}
                                className="text-chili hover:underline font-medium"
                            >
                                Disallow all
                            </button>
                        </div>
                    </div>
                    <ul className="space-y-2">
                        {items.map((item) => {
                            const isChecked = selectedItems[item.menuItemId] ?? true;
                            const itemDisc = item.discountPercent ?? a.discountPercent ?? 10;
                            const regularPrice = (item.quantity * item.unitPricePaise) / 100;
                            const discPrice = (regularPrice * (100 - itemDisc)) / 100;

                            return (
                                <li key={item.menuItemId} className="flex items-center justify-between gap-2">
                                    <label className="flex items-center gap-2 cursor-pointer flex-1">
                                        <input
                                            type="checkbox"
                                            checked={isChecked}
                                            onChange={() => toggleItem(item.menuItemId)}
                                            className="h-4 w-4 rounded border-espresso/30 text-basil focus:ring-basil cursor-pointer"
                                        />
                                        <span className="text-espresso font-medium">
                                            {item.quantity}x {item.name}
                                        </span>
                                    </label>
                                    <div className="text-right text-xs">
                                        {isChecked ? (
                                            <div>
                                                <span className="font-semibold text-basil">Rs {discPrice.toFixed(2)}</span>
                                                <span className="ml-1 text-espresso/50 line-through">
                                                    Rs {regularPrice.toFixed(2)}
                                                </span>
                                                <span className="ml-1 font-medium text-basil bg-basil/10 px-1.5 py-0.5 rounded">
                                                    -{itemDisc}%
                                                </span>
                                            </div>
                                        ) : (
                                            <div>
                                                <span className="font-semibold text-espresso">
                                                    Rs {regularPrice.toFixed(2)}
                                                </span>
                                                <span className="ml-1 text-xs text-espresso/50">(regular price)</span>
                                            </div>
                                        )}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>

                    <div className="mt-3 pt-2 border-t border-espresso/10 flex items-center justify-between text-xs font-semibold text-espresso">
                        <span>Projected Total:</span>
                        <span className="text-sm font-bold text-basil">
                            Rs {(calculatedDiscountedTotal / 100).toFixed(2)}
                        </span>
                    </div>
                </div>
            )}

            <div className="mt-auto flex gap-2 pt-2">
                <Button
                    variant="success"
                    className="flex-1"
                    loading={isThis && busy?.decision === "APPROVED"}
                    disabled={anyBusy}
                    onClick={() => {
                        const approvedIds = hasItems
                            ? Object.keys(selectedItems).filter((k) => selectedItems[k])
                            : undefined;
                        onDecide(a.id, "APPROVED", { approved_items: approvedIds });
                    }}
                >
                    Approve
                </Button>
                <Button
                    variant="danger"
                    className="flex-1"
                    loading={isThis && busy?.decision === "REJECTED"}
                    disabled={anyBusy}
                    onClick={() => onDecide(a.id, "REJECTED")}
                >
                    Reject
                </Button>
            </div>
        </Card>
    );
}

export function Approvals() { // the Approvals page component
    const { approvals, loading, error, actionError, busy, reload, decide } = useApprovals(); // data and actions come from the hook

    if (loading) { // first load still running
        return <p className="text-latte">Loading approvals...</p>; // simple loading text
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

    const pending = approvals.filter((a) => a.status === "PENDING"); // waiting for a decision
    const resolved = approvals.filter((a) => a.status !== "PENDING"); // already decided

    return ( // normal screen
        <div> {/* page wrapper */}
            <h1 className="font-display text-2xl text-espresso md:text-3xl">Approvals</h1> {/* page title, font-display is the theme font */}
            <p className="mt-1 text-espresso/70"> {/* header line */}
                Risky agent actions wait here until staff decide. {/* explanation */}
            </p>

            {actionError && ( // show only when approve or reject failed
                <p role="alert" className="mt-3 rounded-lg border border-chili/40 bg-chili/10 px-3 py-2 text-chili"> {/* alert box */}
                    {actionError} {/* server message, for example "Approval was already decided" */}
                </p>
            )}

            <h2 className="mt-6 font-display text-lg text-espresso"> {/* section title */}
                Waiting ({pending.length}) {/* real count */}
            </h2>
            {pending.length === 0 ? ( // nothing to decide
                <Card className="mt-3 text-center text-espresso/70">Nothing waiting. All clear.</Card> // empty state
            ) : ( // at least one pending approval
                <ul className="mt-3 grid gap-3 md:grid-cols-2"> {/* two columns on wider screens */}
                    {pending.map((a) => (
                        <li key={a.id}>
                            <PendingApprovalCard a={a} busy={busy} onDecide={decide} />
                        </li>
                    ))}
                </ul>
            )}

            {resolved.length > 0 && ( // history section, only when something was decided
                <> {/* fragment, groups the title and the list */}
                    <h2 className="mt-8 font-display text-lg text-espresso"> {/* section title */}
                        Decided ({resolved.length}) {/* real count */}
                    </h2>
                    <ul className="mt-3 grid gap-3 md:grid-cols-2"> {/* two columns on wider screens */}
                        {resolved.map((a) => ( // one card per decided approval
                            <li key={a.id}> {/* key helps React track the card */}
                                <Card className="opacity-70"> {/* dimmed, because it is history */}
                                    <div className="flex items-center justify-between gap-2"> {/* top row */}
                                        <span className="font-medium text-espresso"> {/* action name */}
                                            {actionLabel(a.action)} {/* readable action name */}
                                        </span>
                                        <span // decision text
                                            className={ // color follows the decision
                                                a.status === "APPROVED"
                                                    ? "text-sm font-medium text-basil" // green for approved
                                                    : "text-sm font-medium text-chili" // red for rejected
                                            }
                                        >
                                            {a.status === "APPROVED" ? "Approved" : "Rejected"} {/* readable decision */}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-sm text-espresso/70">{a.reason || "No reason given."}</p> {/* why the agent asked */}
                                    {a.decidedAt && ( // show when it was decided, if the time is known
                                        <p className="mt-1 text-xs text-espresso/60">Decided {formatTimeAgo(a.decidedAt)}</p> // relative time
                                    )}
                                </Card>
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    );
}
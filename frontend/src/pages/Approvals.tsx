import Card from "../components/ui/Card"; // shared panel box
import Button from "../components/ui/Button"; // shared button with variant and loading props
import { useApprovals } from "../hooks/useApprovals"; // real approvals from the backend
import { formatTimeAgo } from "../lib/format"; // relative time text
import type { ApprovalAction } from "../types"; // the known action names

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
                    {pending.map((a) => { // one card per pending approval
                        const isThis = busy?.id === a.id; // true when this card's request is running
                        const anyBusy = busy !== null; // true when any request is running, all buttons stay locked
                        return ( // the card
                            <li key={a.id}> {/* key helps React track the card */}
                                <Card className="flex h-full flex-col gap-3"> {/* card fills the grid cell */}
                                    <div className="flex items-start justify-between gap-2"> {/* top row */}
                                        <span className="rounded-full bg-saffron/20 px-3 py-1 text-sm font-medium text-espresso"> {/* action pill */}
                                            {actionLabel(a.action)} {/* readable action name */}
                                        </span>
                                        <span className="text-sm text-espresso/60"> {/* time text */}
                                            {formatTimeAgo(a.createdAt)} {/* relative time */}
                                        </span>
                                    </div>
                                    <p className="text-espresso">{a.reason || "No reason given."}</p> {/* why the agent asked, with a fallback */}
                                    {a.orderId && ( // show the order only when the approval is about one
                                        <p className="text-sm text-espresso/60">Order {a.orderId.slice(0, 8)}</p> // short order id, same as the Orders page
                                    )}
                                    <div className="mt-auto flex gap-2"> {/* button row sits at the bottom of the card */}
                                        <Button // approve button
                                            variant="success" // green look
                                            className="flex-1" // share the row equally
                                            loading={isThis && busy?.decision === "APPROVED"} // spinner only on the pressed button
                                            disabled={anyBusy} // locked while any decision runs
                                            onClick={() => decide(a.id, "APPROVED")} // hook sends the request and waits
                                        >
                                            Approve {/* button text */}
                                        </Button>
                                        <Button // reject button
                                            variant="danger" // red look
                                            className="flex-1" // share the row equally
                                            loading={isThis && busy?.decision === "REJECTED"} // spinner only on the pressed button
                                            disabled={anyBusy} // locked while any decision runs
                                            onClick={() => decide(a.id, "REJECTED")} // hook sends the request and waits
                                        >
                                            Reject {/* button text */}
                                        </Button>
                                    </div>
                                </Card>
                            </li>
                        );
                    })}
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
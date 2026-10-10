import { useEffect, useState } from "react"; // React state and side-effect helpers
import type { Approval } from "../types"; // UI approval shape
import { ApiError } from "../lib/api"; // error type that carries a status and a readable message
import { decideApproval, listApprovals } from "../lib/approvalsApi"; // backend calls
import type { Decision } from "../lib/approvalsApi"; // "APPROVED" or "REJECTED"

function errorText(e: unknown): string { // turn any thrown value into text for the screen
    return e instanceof ApiError ? e.message : "Something went wrong"; // ApiError messages are already readable
}

// DECISION PROBLEM: should a decision update the screen before the server answers?
// Options: (1) wait for the server, then update, (2) update first and undo on failure (optimistic).
// Chosen: option 1, the same rule as the Menu toggle. Reason: a decision on a risky action must never look saved when it is not.
// Cost: the buttons show a spinner for the length of one request.
// While one decision is running, all buttons stay disabled, so two decisions can never run at once.
export function useApprovals() { // everything the Approvals page needs, in one place
    const [approvals, setApprovals] = useState<Approval[]>([]); // approvals shown on screen, newest first from the server
    const [loading, setLoading] = useState(true); // true until the first answer arrives
    const [error, setError] = useState<string | null>(null); // problem while loading the list
    const [actionError, setActionError] = useState<string | null>(null); // problem from approve or reject
    const [busy, setBusy] = useState<{ id: string; decision: Decision } | null>(null); // the decision in flight, or null
    const [attempt, setAttempt] = useState(0); // bump it to load again

    useEffect(() => { // runs on mount and whenever attempt changes
        let cancelled = false; // set to true if the component goes away before the answer arrives
        listApprovals() // ask the backend for the approvals
            .then((rows) => { // success
                if (cancelled) return; // ignore answers nobody waits for
                setApprovals(rows); // show the approvals
                setError(null); // clear any older error
            })
            .catch((e) => { // failure
                if (!cancelled) setError(errorText(e)); // show the reason
            })
            .finally(() => { // always
                if (!cancelled) setLoading(false); // stop the loading state
            });
        return () => { // cleanup runs when the effect re-runs or the page unmounts
            cancelled = true; // block late state updates
        };
    }, [attempt]); // reload when attempt changes

    function reload() { // used by a "Try again" button
        setLoading(true); // show the loading state again
        setError(null); // clear the old error
        setAttempt((a) => a + 1); // triggers the effect above
    }

    async function decide(id: string, decision: Decision) { // approve or reject one approval
        setBusy({ id, decision }); // mark it busy so its button shows a spinner
        setActionError(null); // clear the old action error
        try { // run the request
            const updated = await decideApproval(id, decision); // wait for the server
            setApprovals((prev) => prev.map((a) => (a.id === updated.id ? updated : a))); // swap in the server's version
        } catch (e) { // failure
            setActionError(errorText(e)); // show the reason, for example "Approval was already decided"
            if (e instanceof ApiError && e.status === 409) { // another tab decided it first, so our list is stale
                listApprovals() // quietly fetch the fresh list, no loading screen
                    .then(setApprovals) // show it
                    .catch(() => undefined); // ignore a failure here, the error message above already explains the problem
            }
        } finally { // always
            setBusy(null); // unlock the buttons
        }
    }

    return { approvals, loading, error, actionError, busy, reload, decide }; // the page uses these
}
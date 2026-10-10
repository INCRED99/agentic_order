import { useEffect, useState } from "react"; // React state and side-effect helpers
import type { Order } from "../types"; // UI order shape
import { ApiError } from "../lib/api"; // error type that carries a readable message
import { listOrders } from "../lib/ordersApi"; // backend call

function errorText(e: unknown): string { // turn any thrown value into text for the screen
    return e instanceof ApiError ? e.message : "Something went wrong"; // ApiError messages are already readable
}

// DECISION PROBLEM: should the Orders page refresh itself?
// Options: (1) load once and offer a manual reload, (2) poll every few seconds, (3) Supabase realtime.
// Chosen: option 1. Reason: simplest, and no order-creating code exists yet.
// Cost: a new order does not appear until the page is opened again or reload is called.
// Revisit: once the agent creates orders, polling every 10 to 15 seconds is the likely next step.
export function useOrders() { // everything the Orders page needs, in one place
    const [orders, setOrders] = useState<Order[]>([]); // orders shown on screen, newest first from the server
    const [loading, setLoading] = useState(true); // true until the first answer arrives
    const [error, setError] = useState<string | null>(null); // problem while loading the list
    const [attempt, setAttempt] = useState(0); // bump it to load again

    useEffect(() => { // runs on mount and whenever attempt changes
        let cancelled = false; // set to true if the component goes away before the answer arrives
        listOrders() // ask the backend for the orders
            .then((rows) => { // success
                if (cancelled) return; // ignore answers nobody waits for
                setOrders(rows); // show the orders
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

    return { orders, loading, error, reload }; // the page uses these
}
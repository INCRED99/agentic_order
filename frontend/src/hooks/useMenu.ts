import { useEffect, useState } from "react"; // React state and side-effect helpers
import type { MenuItem } from "../types"; // UI menu item shape
import { ApiError } from "../lib/api"; // error type that carries a readable message
import { createMenuItem, deleteMenuItem, listMenu, updateMenuItem } from "../lib/menuApi"; // backend calls
import type { NewMenuItem } from "../lib/menuApi"; // input shape for adding a dish

function errorText(e: unknown): string { // turn any thrown value into text for the screen
    return e instanceof ApiError ? e.message : "Something went wrong"; // ApiError messages are already readable
}

// DECISION PROBLEM: how does the page fetch and hold server data?
// Options: (1) a plain hook with useState and useEffect, (2) add React Query.
// Chosen: option 1. Reason: no new dependency, and every step is visible while you learn.
// Cost: no automatic caching or background refresh. Revisit if several pages share the same data.
// Your decision for the toggle: wait for the server, then update the screen (no optimistic update).
export function useMenu() { // everything the Menu page needs, in one place
    const [items, setItems] = useState<MenuItem[]>([]); // dishes shown on screen
    const [loading, setLoading] = useState(true); // true until the first answer arrives
    const [error, setError] = useState<string | null>(null); // problem while loading the list
    const [actionError, setActionError] = useState<string | null>(null); // problem from toggle, add or delete
    const [busyIds, setBusyIds] = useState<ReadonlySet<string>>(new Set()); // ids with a request in flight; "new" is the add form
    const [attempt, setAttempt] = useState(0); // bump it to load again

    useEffect(() => { // runs on mount and whenever attempt changes
        let cancelled = false; // set to true if the component goes away before the answer arrives
        listMenu() // ask the backend for the menu
            .then((rows) => { // success
                if (cancelled) return; // ignore answers nobody waits for
                setItems(rows); // show the dishes
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

    async function run<T>(id: string, task: () => Promise<T>): Promise<T | undefined> { // runs a request and tracks it as busy
        setBusyIds((prev) => new Set(prev).add(id)); // mark this id busy so its button can be disabled
        setActionError(null); // clear the old action error
        try { // run the request
            return await task(); // success: hand the result back
        } catch (e) { // failure
            setActionError(errorText(e)); // show the reason, for example "Item name already exists"
            return undefined; // signal failure to the caller
        } finally { // always
            setBusyIds((prev) => { // unmark busy
                const next = new Set(prev); // copy, never change state in place
                next.delete(id); // remove this id
                return next; // new set
            });
        }
    }

    async function toggleAvailable(item: MenuItem) { // flip a dish between available and hidden
        const updated = await run(item.id, () => updateMenuItem(item.id, { available: !item.available })); // wait for the server
        if (updated) setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i))); // swap in the server's version
    }

    async function addItem(input: NewMenuItem): Promise<boolean> { // add a dish, true on success so the form can reset
        const created = await run("new", () => createMenuItem(input)); // "new" is the busy key for the add form
        if (!created) return false; // failed, keep the form as it is
        setItems((prev) => [...prev, created]); // new dishes go to the end, same as the server order
        return true; // success
    }

    async function removeItem(id: string) { // delete a dish
        const done = await run(id, async () => { // wrap in a function that returns a value
            await deleteMenuItem(id); // 204 on success, 409 when used in orders
            return true; // marks success
        });
        if (done) setItems((prev) => prev.filter((i) => i.id !== id)); // drop it from the screen only after the server agreed
    }

    return { items, loading, error, actionError, busyIds, reload, toggleAvailable, addItem, removeItem }; // the page uses these
}
import { useEffect, useState } from "react"; // React state and side-effect helpers
import { ApiError } from "../lib/api"; // error type that carries a readable message
import { getMe } from "../lib/meApi"; // backend call
import type { Me } from "../lib/meApi"; // UI profile shape

function errorText(e: unknown): string { // turn any thrown value into text for the screen
    return e instanceof ApiError ? e.message : "Something went wrong"; // ApiError messages are already readable
}

// Same plain-hook pattern as useMenu, useOrders and useApprovals. No caching library.
export function useMe() { // the owner's profile for any screen that needs it
    const [me, setMe] = useState<Me | null>(null); // profile, null until the first answer arrives
    const [loading, setLoading] = useState(true); // true until the first answer arrives
    const [error, setError] = useState<string | null>(null); // problem while loading
    const [attempt, setAttempt] = useState(0); // bump it to load again

    useEffect(() => { // runs on mount and whenever attempt changes
        let cancelled = false; // set to true if the component goes away before the answer arrives
        getMe() // ask the backend for the profile
            .then((row) => { // success
                if (cancelled) return; // ignore answers nobody waits for
                setMe(row); // keep the profile
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

    return { me, loading, error, reload }; // the screens use these
}
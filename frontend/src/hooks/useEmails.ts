import { useCallback, useEffect, useState } from "react"; // React hooks for state, effects and a stable function
import { ApiError, apiFetch } from "../lib/api"; // the shared backend caller (same path as useAgentRuns)
import type { EmailDirection, EmailMessage, EmailStatus } from "../types"; // UI shapes

interface ApiEmail { // one mail as GET /emails sends it (snake_case)
    id: string; // mail id
    direction: EmailDirection; // INBOUND or OUTBOUND
    address: string; // customer address
    subject: string; // plain text
    preview: string; // plain text, at most 160 characters
    created_at: string; // ISO timestamp string
    order_id: string | null; // order made from this mail, or null
    status: EmailStatus; // agent progress
}

const POLL_MS = 15000; // A22: refresh every 15 seconds

function toEmail(m: ApiEmail): EmailMessage { // backend shape to UI shape
    return { // build the UI object
        id: m.id, // same id
        direction: m.direction, // same word
        address: m.address, // same text
        subject: m.subject, // same text
        preview: m.preview, // same text
        createdAt: m.created_at, // camelCase name
        orderId: m.order_id, // camelCase name
        status: m.status, // same word
    };
}

// DECISION PROBLEM: same as useAgentRuns, how does the page learn about new mail?
// Chosen: polling every 15 s (A22). Cost: up to 15 s delay. V2: Supabase Realtime.
export function useEmails() { // hook used by the Emails page
    const [emails, setEmails] = useState<EmailMessage[]>([]); // loaded mails, newest first (the API sorts them)
    const [loading, setLoading] = useState(true); // true until the first answer arrives
    const [error, setError] = useState<string | null>(null); // readable error text or null

    const load = useCallback(async () => { // one fetch, stable between renders
        try { // network or server errors throw
            const rows = await apiFetch<ApiEmail[]>("/emails"); // call the backend with the login token
            setEmails(rows.map(toEmail)); // convert and store
            setError(null); // clear an old error after a good answer
        } catch (e) { // anything went wrong
            setError(e instanceof ApiError ? e.message : "Could not load emails"); // friendly text
        } finally { // runs in both cases
            setLoading(false); // first load is over
        }
    }, []); // no dependencies, the function never changes

    useEffect(() => { // start loading when the page opens
        void load(); // first load at once
        const timer = window.setInterval(() => void load(), POLL_MS); // then every 15 seconds
        return () => window.clearInterval(timer); // stop the timer when the page closes
    }, [load]); // runs once because load is stable

    return { emails, loading, error }; // data for the page
}
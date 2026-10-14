import { useCallback, useEffect, useState } from "react"; // React hooks for state, effects and a stable function
import { ApiError, apiFetch } from "../lib/api"; // the shared backend caller (change the path if your api file has another name)
import type { AgentRun, AgentRunStatus, AgentStep } from "../types"; // UI shapes

// The shape GET /agent-runs sends (snake_case, same as the FastAPI model AgentRunOut).
interface ApiAgentRun { // one run as the backend sends it
    id: string; // run id
    email_from: string; // sender of the mail
    email_subject: string; // subject of the mail
    started_at: string; // ISO timestamp string
    status: AgentRunStatus; // RUNNING, SUCCESS, WAITING_APPROVAL or FAILED
    model_calls: number; // LLM calls used
    tokens: number; // tokens used
    steps: AgentStep[]; // tool calls, already in the UI shape (tool, summary, ok)
    error: string | null; // exception type name or null
}

const POLL_MS = 15000; // A16: refresh every 15 seconds

function toAgentRun(r: ApiAgentRun): AgentRun { // A15: backend shape to UI shape
    return { // build the UI object
        id: r.id, // same id
        emailFrom: r.email_from, // camelCase name
        emailSubject: r.email_subject, // camelCase name
        startedAt: r.started_at, // camelCase name
        status: r.status, // same status word
        modelCalls: r.model_calls, // camelCase name
        tokens: r.tokens, // same number
        steps: r.steps, // same list
        error: r.error, // same text or null
    };
}

// DECISION PROBLEM: how does the page learn about new runs?
// Options: (1) load once, (2) poll every few seconds, (3) Supabase Realtime subscription.
// Chosen: option 2 (A16). Reason: the worker writes runs without any browser open, and polling is 10 lines with no new moving parts.
// Cost: up to 15 s delay and one request per tick per open tab. V2: Realtime when many users watch at once.
export function useAgentRuns() { // hook used by the Agent Activity page
    const [runs, setRuns] = useState<AgentRun[]>([]); // the loaded runs, newest first (the API sorts them)
    const [loading, setLoading] = useState(true); // true until the first answer arrives
    const [error, setError] = useState<string | null>(null); // readable error text or null

    const load = useCallback(async () => { // one fetch, stable between renders
        try { // network or server errors throw
            const rows = await apiFetch<ApiAgentRun[]>("/agent-runs"); // call the backend with the login token
            setRuns(rows.map(toAgentRun)); // convert and store
            setError(null); // clear an old error after a good answer
        } catch (e) { // anything went wrong
            setError(e instanceof ApiError ? e.message : "Could not load agent runs"); // friendly text
        } finally { // runs in both cases
            setLoading(false); // first load is over
        }
    }, []); // no dependencies, the function never changes

    useEffect(() => { // start loading when the page opens
        void load(); // first load at once
        const timer = window.setInterval(() => void load(), POLL_MS); // then every 15 seconds
        return () => window.clearInterval(timer); // stop the timer when the page closes
    }, [load]); // runs once because load is stable

    return { runs, loading, error, reload: load }; // reload lets a button refresh by hand
}
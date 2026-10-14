import { supabase } from "./supabase"; // the shared Supabase client, used here only to read the login token (adjust the path if your file is elsewhere)

// Base URL of the FastAPI backend. Set VITE_API_URL in .env.local or Vercel environment variables.
const rawApiUrl = import.meta.env.VITE_API_URL;
const API_URL: string = rawApiUrl && rawApiUrl.trim() !== "" ? rawApiUrl.trim().replace(/\/+$/, "") : "http://localhost:8000";


// Error that carries the HTTP status, so screens can react differently to 401, 404, 409.
export class ApiError extends Error { // extends the built-in Error so it works with try/catch
    status: number; // declared as a normal field, because your TypeScript setup forbids constructor parameter shortcuts
    constructor(status: number, message: string) { // build it from a status code and a readable message
        super(message); // fills Error.message
        this.name = "ApiError"; // shows up in the console instead of plain "Error"
        this.status = status; // keep the status for callers; 0 means the server was unreachable
    }
}

// FastAPI sends {"detail": "text"} for our own errors and {"detail": [{"msg": ...}]} for validation errors.
function messageFrom(body: unknown, fallback: string): string { // pull a human message out of an error body
    if (typeof body === "object" && body !== null && "detail" in body) { // body looks like {detail: ...}
        const detail = (body as { detail: unknown }).detail; // read the detail field
        if (typeof detail === "string") return detail; // simple text message
        if (Array.isArray(detail)) { // validation errors come as a list
            return detail.map((d) => (typeof d?.msg === "string" ? d.msg : "Invalid input")).join(", "); // join their messages
        }
    }
    return fallback; // nothing readable, use the generic text
}

// DECISION PROBLEM: where does the login token come from on each call?
// Options: (1) read it from supabase.auth.getSession() on every call, (2) copy it into our own variable once.
// Chosen: option 1. Reason: supabase-js refreshes the token before it expires, so we always send a valid one.
// Cost: one cheap local read per request, no network call.
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> { // call the backend, return parsed JSON typed as T
    const { data } = await supabase.auth.getSession(); // current session from supabase-js storage
    const token = data.session?.access_token; // the JWT the backend will verify, undefined when signed out
    if (!token) throw new ApiError(401, "Not signed in"); // stop early, the backend would answer 401 anyway
    const headers = new Headers(init.headers); // copy any headers the caller set
    headers.set("Authorization", `Bearer ${token}`); // the Bearer scheme that deps.py expects
    if (init.body) headers.set("Content-Type", "application/json"); // tell the server the body is JSON
    let res: Response; // will hold the server answer
    try { // network errors throw before any answer exists
        res = await fetch(`${API_URL}${path}`, { ...init, headers }); // the actual HTTP call
    } catch { // server down, wrong port, or CORS blocked at network level
        throw new ApiError(0, "Cannot reach the server. Is the backend running?"); // friendly text for the screen
    }
    if (res.status === 204) return undefined as T; // 204 means success with no body, for example after DELETE
    let body: unknown = null; // parsed JSON, if any
    try { // some error answers have no JSON
        body = await res.json(); // read the body as JSON
    } catch { // empty or non-JSON body
        body = null; // keep null and fall back to a generic message below
    }
    if (!res.ok) throw new ApiError(res.status, messageFrom(body, `Request failed (${res.status})`)); // 4xx or 5xx
    return body as T; // success: hand back the data
}
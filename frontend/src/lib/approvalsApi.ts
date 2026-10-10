import type { Approval, ApprovalAction, ApprovalStatus } from "../types"; // the shapes the UI already uses
import { apiFetch } from "./api"; // authenticated fetch helper

// The two decisions an owner can make. Uppercase, same style as the UI status values.
export type Decision = "APPROVED" | "REJECTED"; // used by the hook and the page

// The exact JSON the backend sends for one approval: snake_case names.
interface ApiApproval { // one approval as sent by GET /approvals
    id: string; // approval id
    order_id: string | null; // null when the approval is not about an order
    action: string; // for example accept_large_order
    reason: string; // why the agent asked, empty text when unknown
    status: string; // PENDING, APPROVED or REJECTED, already uppercase from the API
    created_at: string; // ISO timestamp
    decided_at: string | null; // null while pending
}

// DECISION PROBLEM: the backend sends action and status as plain strings. How does the UI treat them?
// Options: (1) cast them to the UI union types, (2) check each value at runtime.
// Chosen: option 1, same as ordersApi.ts. Reason: the backend is ours and its values are fixed.
// Cost: an action the UI does not know shows its raw name, because the page falls back to the plain text.
function toApproval(row: ApiApproval): Approval { // backend shape -> UI shape
    return { // build the UI object field by field
        id: row.id, // same id
        orderId: row.order_id, // renamed field, null stays null
        action: row.action as ApprovalAction, // see the note above
        reason: row.reason, // same text
        status: row.status as ApprovalStatus, // see the note above
        createdAt: row.created_at, // renamed field
        decidedAt: row.decided_at, // renamed field, null stays null
    };
}

export async function listApprovals(): Promise<Approval[]> { // GET /approvals, newest first
    const rows = await apiFetch<ApiApproval[]>("/approvals"); // list of approvals from the backend
    return rows.map(toApproval); // convert each one
}

export async function decideApproval(id: string, decision: Decision): Promise<Approval> { // POST /approvals/{id}/approve or /reject
    const verb = decision === "APPROVED" ? "approve" : "reject"; // the backend route name for this decision
    const row = await apiFetch<ApiApproval>(`/approvals/${encodeURIComponent(id)}/${verb}`, { method: "POST" }); // id goes in the URL, encoded for safety
    return toApproval(row); // the updated approval including decided_at
}
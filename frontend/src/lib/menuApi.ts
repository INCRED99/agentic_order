import type { MenuItem } from "../types"; // the shape the UI already uses for menu items
import { apiFetch } from "./api"; // authenticated fetch helper

// The exact JSON the backend sends: snake_case names, same as database columns.
interface ApiMenuItem { // one dish as sent by GET /menu
    id: string; // dish id
    name: string; // dish name
    description: string | null; // may be missing
    category: string; // label like Mains
    price_paise: number; // price in paise
    is_available: boolean; // shown to the agent or not
    stock: number | null; // units left, null when no inventory row
}

// What the UI sends when it creates a dish. Price is in paise so the UI converts rupees first.
export interface NewMenuItem { // input for createMenuItem
    name: string; // required
    description?: string; // optional
    category: string; // required, the form supplies a default
    pricePaise: number; // integer paise
    available: boolean; // starts visible or hidden
}

// Only the fields that changed. Every key is optional, like the backend's PATCH.
export interface MenuItemPatch { // input for updateMenuItem
    name?: string; // new name
    description?: string | null; // null clears it
    category?: string; // new label
    pricePaise?: number; // new price in paise
    available?: boolean; // new visibility
}

// DECISION PROBLEM: who converts snake_case to camelCase and paise names?
// Options: (1) one mapping function here, (2) rename the backend fields, (3) rename the UI type.
// Chosen: option 1. Reason: each side keeps its own naming habit, and the mapping lives in exactly one place.
// The cast on category keeps this compiling even if your MenuItem type uses a fixed list of labels.
// If your list is fixed, free-text categories from the database can fall outside it. Loosen the type to string.
function toMenuItem(row: ApiMenuItem): MenuItem { // backend shape -> UI shape
    return { // build the UI object field by field
        id: row.id, // same id
        name: row.name, // same name
        description: row.description ?? "", // UI expects text, so empty string replaces null
        pricePaise: row.price_paise, // renamed field
        category: row.category as MenuItem["category"], // see the note above
        available: row.is_available, // renamed field
        stock: row.stock, // number or null, same meaning as in your mock data
    };
}

export async function listMenu(): Promise<MenuItem[]> { // GET /menu
    const rows = await apiFetch<ApiMenuItem[]>("/menu"); // list of dishes from the backend
    return rows.map(toMenuItem); // convert each one
}

export async function createMenuItem(input: NewMenuItem): Promise<MenuItem> { // POST /menu
    const row = await apiFetch<ApiMenuItem>("/menu", { // send the new dish
        method: "POST", // create
        body: JSON.stringify({ // backend field names
            name: input.name, // dish name
            description: input.description ?? null, // null when not given
            category: input.category, // label
            price_paise: input.pricePaise, // paise
            is_available: input.available, // visibility
        }),
    });
    return toMenuItem(row); // the created dish including stock
}

export async function updateMenuItem(id: string, patch: MenuItemPatch): Promise<MenuItem> { // PATCH /menu/{id}
    const body: Record<string, unknown> = {}; // build the body from only the keys that were provided
    if (patch.name !== undefined) body.name = patch.name; // include name when given
    if (patch.description !== undefined) body.description = patch.description; // include description, null allowed
    if (patch.category !== undefined) body.category = patch.category; // include category when given
    if (patch.pricePaise !== undefined) body.price_paise = patch.pricePaise; // include price when given
    if (patch.available !== undefined) body.is_available = patch.available; // include visibility when given
    const row = await apiFetch<ApiMenuItem>(`/menu/${encodeURIComponent(id)}`, { // id goes in the URL, encoded for safety
        method: "PATCH", // partial update
        body: JSON.stringify(body), // only the changed fields
    });
    return toMenuItem(row); // the updated dish including stock
}

export async function deleteMenuItem(id: string): Promise<void> { // DELETE /menu/{id}
    await apiFetch<void>(`/menu/${encodeURIComponent(id)}`, { method: "DELETE" }); // 204 means done, 409 means used in orders
}
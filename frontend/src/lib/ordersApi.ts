import type { Order, OrderStatus, PaymentStatus } from "../types"; // the shapes the UI already uses
import { apiFetch } from "./api"; // authenticated fetch helper

// The exact JSON the backend sends for one order line: snake_case names.
interface ApiOrderItem { // one line of an order as sent by GET /orders
    id: string; // line id
    menu_item_id: string; // dish id
    name: string; // dish name
    quantity: number; // how many units
    unit_price_paise: number; // price per unit in paise, snapshot from order time
}

// The exact JSON the backend sends for one order.
interface ApiOrder { // one order as sent by GET /orders
    id: string; // order id
    customer_name: string | null; // null when the mail had no sender name
    customer_email: string; // sender address
    items: ApiOrderItem[]; // order lines
    total_paise: number; // order total in paise
    status: string; // PENDING, AWAITING_APPROVAL, PAID, CANCELLED or REFUNDED
    payment_status: string; // UNPAID, LINK_SENT, PAID, FAILED or REFUNDED
    payment_link_url: string | null; // null until a payment link exists
    created_at: string; // ISO timestamp
    updated_at: string; // ISO timestamp
}

// DECISION PROBLEM: the backend sends status as a plain string. How does the UI treat it?
// Options: (1) cast it to the UI union type, (2) check each value at runtime and fall back to a safe default.
// Chosen: option 1, the same approach as menuApi.ts. Reason: the backend is ours and its values are fixed.
// Cost: if the backend ever sends a new status, the UI shows it without crashing but without a matching badge color.
function toOrder(row: ApiOrder): Order { // backend shape -> UI shape
    return { // build the UI object field by field
        id: row.id, // same id
        customerName: row.customer_name, // renamed field, null stays null
        customerEmail: row.customer_email, // renamed field
        items: row.items.map((i) => ({ // convert each line
            id: i.id, // same id
            menuItemId: i.menu_item_id, // renamed field
            name: i.name, // same name
            quantity: i.quantity, // same quantity
            unitPricePaise: i.unit_price_paise, // renamed field
        })),
        totalPaise: row.total_paise, // renamed field
        status: row.status as OrderStatus, // see the note above
        paymentStatus: row.payment_status as PaymentStatus, // see the note above
        paymentLinkUrl: row.payment_link_url, // renamed field, null stays null
        createdAt: row.created_at, // renamed field
        updatedAt: row.updated_at, // renamed field
    };
}

export async function listOrders(): Promise<Order[]> { // GET /orders, newest first
    const rows = await apiFetch<ApiOrder[]>("/orders"); // list of orders from the backend
    return rows.map(toOrder); // convert each one
}
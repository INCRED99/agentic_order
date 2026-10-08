// Shared frontend types. Money is always stored in paise (integer).
// 1 rupee = 100 paise. Format only at display time.
// Union types, not enums. Import with `import type { ... }`.

export type OrderStatus =
    | 'PENDING'
    | 'AWAITING_APPROVAL'
    | 'PAID'
    | 'PREPARING'
    | 'COMPLETED'
    | 'CANCELLED'

export type PaymentStatus =
    | 'UNPAID'
    | 'LINK_SENT'
    | 'PAID'
    | 'FAILED'
    | 'REFUNDED'

export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

// Risky agent actions that need a human decision.
export type ApprovalAction =
    | 'apply_discount'
    | 'cancel_order'
    | 'refund_order'
    | 'accept_large_order'
    | 'substitute_item'

export interface OrderItem {
    id: string
    menuItemId: string
    name: string // snapshot of name at order time
    quantity: number
    unitPricePaise: number // snapshot of price at order time
}

export interface Order {
    id: string
    customerName: string | null
    customerEmail: string
    items: OrderItem[]
    totalPaise: number // calculated by backend from DB prices
    status: OrderStatus
    paymentStatus: PaymentStatus
    paymentLinkUrl: string | null
    createdAt: string // ISO 8601
    updatedAt: string // ISO 8601
}

export interface Approval {
    id: string
    orderId: string
    action: ApprovalAction
    reason: string // agent explanation shown to staff
    status: ApprovalStatus
    createdAt: string // ISO 8601
    decidedAt: string | null // ISO 8601
}

export interface MenuItem {
    id: string
    name: string
    description: string
    pricePaise: number
    category: string
    available: boolean
    stock: number | null // null = not tracked
}


export type AgentRunStatus = "SUCCESS" | "WAITING_APPROVAL" | "FAILED";

export interface AgentStep {
    tool: string;
    summary: string;
    ok: boolean;
}

export interface AgentRun {
    id: string;
    emailFrom: string;
    emailSubject: string;
    startedAt: string; // ISO string
    status: AgentRunStatus;
    modelCalls: number;
    tokens: number;
    steps: AgentStep[];
}

export type EmailDirection = "INBOUND" | "OUTBOUND";

export interface EmailMessage {
    id: string;
    direction: EmailDirection;
    address: string; // sender if INBOUND, recipient if OUTBOUND
    subject: string;
    preview: string;
    createdAt: string; // ISO string
    orderId: string | null; // null when email did not become an order
}
// Fake data so we can build the UI before the backend exists.
// Delete this file once pages read from the real API.
// Totals are consistent with items (quantity * unitPricePaise).

import type { Approval, MenuItem, Order } from '../types'
import type { AgentRun } from "../types"
import type { EmailMessage } from '../types'
// Timestamps relative to now, so the dashboard always looks fresh.
const ago = (minutes: number): string =>
    new Date(Date.now() - minutes * 60_000).toISOString()

export const mockMenu: MenuItem[] = [
    { id: 'm1', name: 'Butter Chicken', description: 'Creamy tomato gravy, slow cooked', pricePaise: 32000, category: 'Mains', available: true, stock: 20 },
    { id: 'm2', name: 'Paneer Tikka', description: 'Charred cottage cheese, mint chutney', pricePaise: 15000, category: 'Starters', available: true, stock: 15 },
    { id: 'm3', name: 'Garlic Naan', description: 'Tandoor baked, brushed with butter', pricePaise: 6000, category: 'Breads', available: true, stock: null },
    { id: 'm4', name: 'Veg Biryani', description: 'Fragrant basmati, seasonal vegetables', pricePaise: 22000, category: 'Mains', available: true, stock: 12 },
    { id: 'm5', name: 'Masala Chai', description: 'Ginger and cardamom', pricePaise: 8000, category: 'Drinks', available: true, stock: null },
    { id: 'm6', name: 'Gulab Jamun', description: 'Warm milk dumplings in rose syrup', pricePaise: 12000, category: 'Desserts', available: false, stock: 0 },
    { id: 'm7', name: 'Mango Lassi', description: 'Thick yogurt drink, Alphonso mango', pricePaise: 11000, category: 'Drinks', available: true, stock: 30 },
]

export const mockOrders: Order[] = [
    {
        id: 'ord_1001',
        customerName: 'Aarav Sharma',
        customerEmail: 'aarav.sharma@example.com',
        items: [
            { id: 'oi_1', menuItemId: 'm1', name: 'Butter Chicken', quantity: 2, unitPricePaise: 32000 },
            { id: 'oi_2', menuItemId: 'm3', name: 'Garlic Naan', quantity: 4, unitPricePaise: 6000 },
        ],
        totalPaise: 88000,
        status: 'PAID',
        paymentStatus: 'PAID',
        paymentLinkUrl: 'https://rzp.io/l/test-aarav',
        createdAt: ago(25),
        updatedAt: ago(12),
    },
    {
        id: 'ord_1002',
        customerName: 'Priya Nair',
        customerEmail: 'priya.nair@example.com',
        items: [
            { id: 'oi_3', menuItemId: 'm2', name: 'Paneer Tikka', quantity: 1, unitPricePaise: 24000 },
            { id: 'oi_4', menuItemId: 'm4', name: 'Veg Biryani', quantity: 2, unitPricePaise: 22000 },
        ],
        totalPaise: 68000,
        status: 'PENDING',
        paymentStatus: 'LINK_SENT',
        paymentLinkUrl: 'https://rzp.io/l/test-priya',
        createdAt: ago(8),
        updatedAt: ago(7),
    },
    {
        id: 'ord_1003',
        customerName: null, // sender name not in email
        customerEmail: 'rohan.m@example.com',
        items: [
            { id: 'oi_5', menuItemId: 'm7', name: 'Mango Lassi', quantity: 3, unitPricePaise: 11000 },
        ],
        totalPaise: 33000,
        status: 'PENDING',
        paymentStatus: 'UNPAID',
        paymentLinkUrl: null,
        createdAt: ago(2),
        updatedAt: ago(2),
    },
    {
        id: 'ord_1004',
        customerName: 'Dev Pathak',
        customerEmail: 'dev@example.com',
        items: [
            { id: 'oi_6', menuItemId: 'm4', name: 'Veg Biryani', quantity: 10, unitPricePaise: 22000 },
            { id: 'oi_7', menuItemId: 'm3', name: 'Garlic Naan', quantity: 10, unitPricePaise: 6000 },
        ],
        totalPaise: 280000,
        status: 'AWAITING_APPROVAL', // large order, agent paused
        paymentStatus: 'UNPAID',
        paymentLinkUrl: null,
        createdAt: ago(15),
        updatedAt: ago(14),
    },
    {
        id: 'ord_1005',
        customerName: 'Kabir Singh',
        customerEmail: 'kabir.singh@example.com',
        items: [
            { id: 'oi_8', menuItemId: 'm1', name: 'Butter Chicken', quantity: 1, unitPricePaise: 32000 },
            { id: 'oi_9', menuItemId: 'm5', name: 'Masala Chai', quantity: 2, unitPricePaise: 8000 },
        ],
        totalPaise: 48000,
        status: 'COMPLETED',
        paymentStatus: 'PAID',
        paymentLinkUrl: 'https://rzp.io/l/test-kabir',
        createdAt: ago(180),
        updatedAt: ago(120),
    },
    {
        id: 'ord_1006',
        customerName: 'Sana Khan',
        customerEmail: 'sana.khan@example.com',
        items: [
            { id: 'oi_10', menuItemId: 'm2', name: 'Paneer Tikka', quantity: 2, unitPricePaise: 24000 },
        ],
        totalPaise: 48000,
        status: 'CANCELLED',
        paymentStatus: 'FAILED',
        paymentLinkUrl: 'https://rzp.io/l/test-sana',
        createdAt: ago(300),
        updatedAt: ago(240),
    },
]

export const mockApprovals: Approval[] = [
    {
        id: 'apr_1',
        orderId: 'ord_1004',
        action: 'accept_large_order',
        reason: 'Order total is Rs 2,800, above the Rs 1,500 auto-accept limit. Customer asked for delivery in 3 hours.',
        status: 'PENDING',
        createdAt: ago(14),
        decidedAt: null,
    },
    {
        id: 'apr_2',
        orderId: 'ord_1002',
        action: 'apply_discount',
        reason: 'Customer wrote that she is a regular and asked for 10% off. Agent cannot grant discounts alone.',
        status: 'PENDING',
        createdAt: ago(6),
        decidedAt: null,
    },
    {
        id: 'apr_3',
        orderId: 'ord_1006',
        action: 'cancel_order',
        reason: 'Payment failed twice and customer asked to cancel by email.',
        status: 'APPROVED',
        createdAt: ago(250),
        decidedAt: ago(240),
    },
]


export const mockAgentRuns: AgentRun[] = [
    {
        id: "run_1",
        emailFrom: "asha@example.com",
        emailSubject: "Order for 2 paneer wraps",
        startedAt: ago(5),
        status: "SUCCESS",
        modelCalls: 3,
        tokens: 6420,
        steps: [
            { tool: "extract_order", summary: "2 x Paneer Wrap", ok: true },
            { tool: "check_menu", summary: "All items available", ok: true },
            { tool: "create_order", summary: "Order created, total from DB prices", ok: true },
            { tool: "create_payment_link", summary: "Razorpay link emailed", ok: true },
        ],
    },
    {
        id: "run_2",
        emailFrom: "rohan@example.com",
        emailSubject: "Party of 40, need big order",
        startedAt: ago(32),
        status: "WAITING_APPROVAL",
        modelCalls: 3,
        tokens: 7100,
        steps: [
            { tool: "extract_order", summary: "40 x Veg Thali", ok: true },
            { tool: "check_menu", summary: "All items available", ok: true },
            { tool: "request_approval", summary: "accept_large_order, staff must decide", ok: true },
        ],
    },
    {
        id: "run_3",
        emailFrom: "meera@example.com",
        emailSubject: "Hi, what time do you open?",
        startedAt: ago(90),
        status: "FAILED",
        modelCalls: 1,
        tokens: 1800,
        steps: [
            { tool: "extract_order", summary: "No order found in email", ok: false },
        ],
    },
];


export const mockEmails: EmailMessage[] = [
    {
        id: "em_1",
        direction: "INBOUND",
        address: "asha@example.com",
        subject: "Order for 2 paneer wraps",
        preview: "Hi, can I get 2 paneer wraps for pickup at 7pm?",
        createdAt: ago(5),
        orderId: "ord_1",
    },
    {
        id: "em_2",
        direction: "OUTBOUND",
        address: "asha@example.com",
        subject: "Your order: pay to confirm",
        preview: "Thanks Asha! Your total is shown below. Pay with this link to confirm.",
        createdAt: ago(4),
        orderId: "ord_1",
    },
    {
        id: "em_3",
        direction: "INBOUND",
        address: "rohan@example.com",
        subject: "Party of 40, need big order",
        preview: "We need 40 veg thalis for Saturday lunch. Possible?",
        createdAt: ago(32),
        orderId: "ord_2",
    },
    {
        id: "em_4",
        direction: "INBOUND",
        address: "meera@example.com",
        subject: "Hi, what time do you open?",
        preview: "Just wondering about your opening hours on Sundays.",
        createdAt: ago(90),
        orderId: null,
    },
];
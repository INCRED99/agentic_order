// Small colored pill. Two parts:
//  - Badge: generic pill, you pick the tone.
//  - StatusBadge: takes any status string from types, picks tone + label itself.
// Same status in one place means a status never has two different colors.

import type { ReactNode } from 'react'
import type { ApprovalStatus, OrderStatus, PaymentStatus } from '../../types'

type Tone = 'neutral' | 'warning' | 'success' | 'danger' | 'brand'

const toneClasses: Record<Tone, string> = {
    neutral: 'bg-latte/25 text-espresso',
    warning: 'bg-saffron/30 text-espresso',
    success: 'bg-basil/15 text-basil',
    danger: 'bg-chili/15 text-chili',
    brand: 'bg-tomato/15 text-tomato',
}

interface BadgeProps {
    tone?: Tone
    children: ReactNode
}

export function Badge({ tone = 'neutral', children }: BadgeProps) {
    return (
        <span
            className={[
                'inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5',
                'text-xs font-semibold',
                toneClasses[tone],
            ].join(' ')}
        >
            {children}
        </span>
    )
}

type Status = OrderStatus | PaymentStatus | ApprovalStatus

// Record<Status, Tone> makes TypeScript error if a status is missing here.
// PENDING and PAID appear in more than one type; same word, same color.
const statusTone: Record<Status, Tone> = {
    // order
    PENDING: 'warning',
    AWAITING_APPROVAL: 'brand', // needs staff attention
    PAID: 'success',

    CANCELLED: 'neutral',
    EXPIRED: 'neutral', // NEW: link died unpaid (D30), nothing left to do, same grey as CANCELLED
    // payment
    UNPAID: 'neutral',
    LINK_SENT: 'warning',
    FAILED: 'danger',
    REFUNDED: 'neutral',
    // approval
    APPROVED: 'success',
    REJECTED: 'danger',
}

// "AWAITING_APPROVAL" -> "Awaiting approval"
function formatStatus(status: string): string {
    const text = status.toLowerCase().replace(/_/g, ' ')
    return text.charAt(0).toUpperCase() + text.slice(1)
}

export function StatusBadge({ status }: { status: Status }) {
    return <Badge tone={statusTone[status]}>{formatStatus(status)}</Badge>
}
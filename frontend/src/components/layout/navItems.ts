// Single list of pages. Sidebar (desktop) and BottomNav (phone) both read it,
// so a route or label is never edited in two places.
// showOnMobile: true = appears in bottom nav (max 5 fit on a phone).

import type { LucideIcon } from 'lucide-react'
import {
    Bot,
    ClipboardList,
    CreditCard,
    Mail,
    Settings,
    ShieldCheck,
    UtensilsCrossed,
} from 'lucide-react'

export interface NavItem {
    to: string
    label: string
    icon: LucideIcon
    showOnMobile: boolean
}

export const navItems: NavItem[] = [
    { to: '/orders', label: 'Orders', icon: ClipboardList, showOnMobile: true },
    { to: '/approvals', label: 'Approvals', icon: ShieldCheck, showOnMobile: true },
    { to: '/menu', label: 'Menu', icon: UtensilsCrossed, showOnMobile: true },
    { to: '/payments', label: 'Payments', icon: CreditCard, showOnMobile: true },
    { to: '/agent-activity', label: 'Activity', icon: Bot, showOnMobile: true },
    { to: '/emails', label: 'Emails', icon: Mail, showOnMobile: false },
    { to: '/settings', label: 'Settings', icon: Settings, showOnMobile: false },
]
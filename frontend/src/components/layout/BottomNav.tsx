// Phone navigation. Fixed to bottom, hidden from md (768px) up;
// Sidebar takes over on desktop. Shows only items with showOnMobile.
// AppLayout must add bottom padding so content is not hidden behind this bar.

import { NavLink } from 'react-router-dom'
import { navItems } from './navItems'

const mobileItems = navItems.filter((item) => item.showOnMobile)

export default function BottomNav() {
    return (
        <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t border-latte/40 bg-paper pb-[env(safe-area-inset-bottom)] md:hidden">
            {mobileItems.map(({ to, label, icon: Icon }) => (
                <NavLink
                    key={to}
                    to={to}
                    className={({ isActive }) =>
                        [
                            'flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-xs font-semibold transition-colors',
                            isActive ? 'text-tomato' : 'text-espresso/70',
                        ].join(' ')
                    }
                >
                    <Icon className="h-5 w-5" />
                    {label}
                </NavLink>
            ))}
        </nav>
    )
}
// Desktop navigation. Hidden below the md breakpoint (768px);
// BottomNav takes over on phones. Shows ALL pages from navItems.
// Log out button sits at the bottom (mt-auto inside a flex-col aside).

import { NavLink } from 'react-router-dom'
import { ChefHat, LogOut } from 'lucide-react'
import { navItems } from './navItems'
import { useAuth } from '../../auth/AuthContext'

export default function Sidebar() {
    const { signOut } = useAuth()

    return (
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-latte/40 bg-paper p-4 md:flex">
            <div className="mb-6 flex items-center gap-2 px-2 py-1">
                <ChefHat className="h-7 w-7 text-tomato" />
                <span className="text-xl font-bold text-espresso">Order Desk</span>
            </div>

            <nav className="flex flex-col gap-1">
                {navItems.map(({ to, label, icon: Icon }) => (
                    <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) =>
                            [
                                'flex min-h-11 items-center gap-3 rounded-xl px-3 font-semibold transition-colors',
                                isActive
                                    ? 'bg-tomato text-white'
                                    : 'text-espresso hover:bg-latte/20',
                            ].join(' ')
                        }
                    >
                        <Icon className="h-5 w-5" />
                        {label}
                    </NavLink>
                ))}
            </nav>

            <button
                type="button"
                onClick={signOut}
                className="mt-auto flex min-h-11 items-center gap-3 rounded-xl px-3 font-semibold text-espresso transition-colors hover:bg-latte/20"
            >
                <LogOut className="h-5 w-5" />
                Log out
            </button>
        </aside>
    )
}
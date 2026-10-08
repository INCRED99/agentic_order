// Page frame shared by every dashboard page.
// Desktop: Sidebar on the left, page on the right.
// Phone: page full width, BottomNav fixed under it.
// Used as a layout route in App.tsx; <Outlet /> is where the current page renders.
// arrages the navbar, bottomnav and main content area.
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import BottomNav from './BottomNav'

export default function AppLayout() {
    return (
        <div className="flex min-h-screen bg-cream text-espresso">
            <Sidebar />

            {/* min-w-0 lets wide content shrink instead of stretching the page.
          pb-24 on phone keeps the last item clear of the fixed BottomNav. */}
            <main className="min-w-0 flex-1 p-4 pb-24 sm:p-6 sm:pb-24 md:pb-8 lg:p-8">
                <div className="mx-auto max-w-6xl">
                    <Outlet />
                </div>
            </main>

            <BottomNav />
        </div>
    )
}


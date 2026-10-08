// Container box. Gives every panel the same look: paper background,
// soft border, rounded corners, light shadow, padding.
// Used for stat tiles, approval items, and order rows on phones
// (tables become stacks of cards on small screens).

import type { HTMLAttributes } from 'react'

export default function Card({
    className = '',
    children,
    ...rest
}: HTMLAttributes<HTMLDivElement>) {
    return (
        <div
            className={[
                'rounded-2xl border border-latte/40 bg-paper p-4 shadow-sm sm:p-5',
                className,
            ].join(' ')}
            {...rest}
        >
            {children}
        </div>
    )
}
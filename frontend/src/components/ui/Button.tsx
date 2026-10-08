// Plain Tailwind button. No component library.
// Assumes palette tokens from index.css are exposed as Tailwind colors
// (bg-tomato, text-espresso, ...). If classes do nothing, check @theme names.

import type { ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'secondary' | 'success' | 'danger' | 'ghost'
type Size = 'sm' | 'md'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: Variant
    size?: Size
    loading?: boolean // disables button and shows spinner during API calls
}

const variantClasses: Record<Variant, string> = {
    primary: 'bg-tomato text-white hover:bg-tomato/90',
    secondary: 'bg-paper text-espresso border border-latte hover:bg-latte/20',
    success: 'bg-basil text-white hover:bg-basil/90',
    danger: 'bg-chili text-white hover:bg-chili/90',
    ghost: 'bg-transparent text-espresso hover:bg-latte/20',
}

// md has 44px min height: comfortable tap target on phones.
const sizeClasses: Record<Size, string> = {
    sm: 'px-3 py-1.5 text-sm min-h-9',
    md: 'px-5 py-2.5 text-base min-h-11',
}

export default function Button({
    variant = 'primary',
    size = 'md',
    loading = false,
    disabled,
    className = '',
    children,
    ...rest
}: ButtonProps) {
    return (
        <button
            disabled={disabled || loading}
            className={[
                'inline-flex items-center justify-center gap-2 rounded-xl font-semibold',
                'transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-saffron',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                variantClasses[variant],
                sizeClasses[size],
                className,
            ].join(' ')}
            {...rest}
        >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {children}
        </button>
    )
}
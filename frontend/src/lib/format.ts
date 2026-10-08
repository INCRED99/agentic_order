// Display helpers. Data stays in paise and ISO strings everywhere;
// convert to human text only here, at the last moment.

const wholeRupees = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
})

const withPaise = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
})

// 88000 -> "₹880", 33050 -> "₹330.50"
export function formatMoney(paise: number): string {
    const rupees = paise / 100
    return paise % 100 === 0 ? wholeRupees.format(rupees) : withPaise.format(rupees)
}

// "2025-01-01T10:00:00Z" -> "5 min ago" / "3 h ago" / "1 Jan"
// Not live: text updates only when the page re-renders.
export function formatTimeAgo(iso: string): string {
    const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000)
    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes} min ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours} h ago`
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
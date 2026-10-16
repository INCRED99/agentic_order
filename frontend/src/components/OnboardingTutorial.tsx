import { useEffect, useState } from "react";
import {
    Bot,
    Check,
    ChevronLeft,
    ChevronRight,
    ClipboardList,
    Copy,
    CreditCard,
    Mail,
    ShieldCheck,
    UtensilsCrossed,
    X,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useMe } from "../hooks/useMe";

export default function OnboardingTutorial() {
    const { session, loading: authLoading } = useAuth();
    const { me } = useMe();
    const [isOpen, setIsOpen] = useState(false);
    const [step, setStep] = useState(0);
    const [copied, setCopied] = useState(false);

    const userId = session?.user?.id || session?.user?.email || "anonymous";
    const storageKey = `tutorial_dismissed_${userId}`;
    const address = me?.orderAddress || "mealdesk.orders+yourtag@gmail.com";

    useEffect(() => {
        if (authLoading) return;
        if (!session) {
            setIsOpen(false);
            return;
        }

        const dismissed = localStorage.getItem(storageKey);
        if (!dismissed) {
            // First time after login: open tutorial automatically
            setIsOpen(true);
        }
    }, [session, authLoading, storageKey]);

    // Allow opening tutorial programmatically via custom event
    useEffect(() => {
        function handleOpen() {
            setStep(0);
            setIsOpen(true);
        }
        window.addEventListener("open-tutorial", handleOpen);
        return () => window.removeEventListener("open-tutorial", handleOpen);
    }, []);

    const dismiss = () => {
        localStorage.setItem(storageKey, "true");
        setIsOpen(false);
    };

    const copyAddress = async () => {
        try {
            await navigator.clipboard.writeText(address);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            /* clipboard blocked */
        }
    };

    if (!isOpen) return null;

    const steps = [
        {
            title: "How orders reach you",
            subtitle: "Customers order by email. The AI assistant builds the order and sends a payment link.",
            icon: Mail,
            content: (
                <div className="space-y-4">
                    <p className="text-sm text-espresso/80 leading-relaxed">
                        Every restaurant has a dedicated email address. When an email arrives, your assistant automatically matches menu items, checks stock, and replies.
                    </p>
                    <div className="rounded-xl border border-latte/30 bg-cream/70 p-3.5">
                        <span className="block text-xs font-semibold uppercase tracking-wider text-latte mb-1.5">
                            Your Unique Order Address
                        </span>
                        <div className="flex items-center gap-2">
                            <code className="min-w-0 flex-1 truncate select-all rounded-lg border border-latte/40 bg-paper px-2.5 py-1.5 font-mono text-sm text-espresso">
                                {address}
                            </code>
                            <button
                                type="button"
                                onClick={copyAddress}
                                className="flex shrink-0 items-center gap-1.5 rounded-lg bg-tomato px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-tomato/90"
                            >
                                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                                {copied ? "Copied" : "Copy"}
                            </button>
                        </div>
                    </div>
                    <p className="text-xs text-latte">
                        Share this on your physical menu, website, or Instagram bio. Keep the tag after the plus sign intact so orders reach your dashboard.
                    </p>
                </div>
            ),
        },
        {
            title: "The customer sends an email",
            subtitle: "Customers write orders in regular, everyday language.",
            icon: UtensilsCrossed,
            content: (
                <div className="space-y-3.5">
                    <p className="text-sm text-espresso/80 leading-relaxed">
                        No app download or sign-up needed for your customers. They simply email what they want:
                    </p>
                    <div className="rounded-xl border-l-4 border-tomato border border-latte/30 bg-cream/60 p-3.5 text-xs space-y-1">
                        <div className="flex gap-2 text-latte">
                            <span className="w-12 font-medium">To:</span>
                            <span className="text-espresso font-mono truncate">{address}</span>
                        </div>
                        <div className="flex gap-2 text-latte">
                            <span className="w-12 font-medium">Subject:</span>
                            <span className="text-espresso font-medium">Order for dinner</span>
                        </div>
                        <div className="pt-2 text-espresso text-sm font-sans border-t border-latte/20 mt-2">
                            “2 Veg Biryani and 1 Cold Coffee please. Thanks, Asha”
                        </div>
                    </div>
                    <p className="text-xs text-latte">
                        The assistant automatically maps dish names against your live Menu page.
                    </p>
                </div>
            ),
        },
        {
            title: "Assistant replies with payment link",
            subtitle: "Instant confirmation and automated payment collection.",
            icon: CreditCard,
            content: (
                <div className="space-y-3.5">
                    <p className="text-sm text-espresso/80 leading-relaxed">
                        The assistant immediately calculates item prices and replies in the same email thread with a direct payment link.
                    </p>
                    <div className="grid grid-cols-2 gap-2.5">
                        <div className="rounded-xl border border-latte/30 bg-cream/70 p-3">
                            <span className="text-xs text-latte block">Order state</span>
                            <span className="text-sm font-bold text-saffron mt-0.5 inline-block">Pending</span>
                        </div>
                        <div className="rounded-xl border border-latte/30 bg-cream/70 p-3">
                            <span className="text-xs text-latte block">Payment state</span>
                            <span className="text-sm font-bold text-tomato mt-0.5 inline-block">Link sent</span>
                        </div>
                    </div>
                    <p className="text-xs text-latte">
                        Customers pay using UPI or cards. Once paid, the order turns to Paid and inventory is deducted.
                    </p>
                </div>
            ),
        },
        {
            title: "You follow along in real time",
            subtitle: "Everything is organized into dedicated dashboard tabs.",
            icon: ShieldCheck,
            content: (
                <div className="space-y-3 text-xs text-espresso/80">
                    <div className="flex items-start gap-2.5 rounded-xl border border-latte/20 bg-cream/50 p-2.5">
                        <ClipboardList className="h-4 w-4 text-tomato shrink-0 mt-0.5" />
                        <div>
                            <span className="font-semibold text-espresso block">Orders</span>
                            Live view of incoming, paid, and completed customer orders.
                        </div>
                    </div>
                    <div className="flex items-start gap-2.5 rounded-xl border border-latte/20 bg-cream/50 p-2.5">
                        <ShieldCheck className="h-4 w-4 text-basil shrink-0 mt-0.5" />
                        <div>
                            <span className="font-semibold text-espresso block">Approvals</span>
                            Flags unusually large orders, refunds, or discounts for your approval.
                        </div>
                    </div>
                    <div className="flex items-start gap-2.5 rounded-xl border border-latte/20 bg-cream/50 p-2.5">
                        <Bot className="h-4 w-4 text-saffron shrink-0 mt-0.5" />
                        <div>
                            <span className="font-semibold text-espresso block">Activity & Emails</span>
                            Transparent audit logs showing every email received and action taken.
                        </div>
                    </div>
                </div>
            ),
        },
        {
            title: "Before you share your address",
            subtitle: "A quick 3-point checklist to ensure smooth operations.",
            icon: ClipboardList,
            content: (
                <ul className="space-y-2.5 text-xs text-espresso/80">
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-basil/20 text-basil font-bold text-[11px]">
                            1
                        </span>
                        <span>
                            <strong className="text-espresso">Add all dishes on Menu:</strong> Customers can only order items listed on your Menu page.
                        </span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-basil/20 text-basil font-bold text-[11px]">
                            2
                        </span>
                        <span>
                            <strong className="text-espresso">Keep stock updated:</strong> Out of stock items are politely flagged back to the customer.
                        </span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-basil/20 text-basil font-bold text-[11px]">
                            3
                        </span>
                        <span>
                            <strong className="text-espresso">Send a test order:</strong> Send an email from your personal inbox to your order address and test the flow!
                        </span>
                    </li>
                </ul>
            ),
        },
    ];

    const currentStep = steps[step];
    const Icon = currentStep.icon;
    const isLast = step === steps.length - 1;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-espresso/60 p-4 backdrop-blur-xs">
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="tutorial-title"
                className="flex w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-latte/40 bg-paper shadow-2xl transition-all"
            >
                {/* Progress bar */}
                <div className="h-1.5 w-full bg-cream">
                    <div
                        className="h-full bg-tomato transition-all duration-300"
                        style={{ width: `${((step + 1) / steps.length) * 100}%` }}
                    />
                </div>

                {/* Header */}
                <div className="flex items-center justify-between border-b border-latte/20 px-6 py-4">
                    <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-tomato/15 text-tomato">
                            <Icon className="h-4 w-4" />
                        </div>
                        <div>
                            <span className="text-[11px] font-bold uppercase tracking-wider text-latte">
                                Tutorial • Step {step + 1} of {steps.length}
                            </span>
                            <h2 id="tutorial-title" className="text-base font-bold text-espresso">
                                {currentStep.title}
                            </h2>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={dismiss}
                        className="rounded-lg p-1.5 text-latte transition hover:bg-latte/15 hover:text-espresso"
                        aria-label="Skip tutorial"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                {/* Body */}
                <div className="px-6 py-5">
                    <p className="mb-4 text-xs text-latte">{currentStep.subtitle}</p>
                    {currentStep.content}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between border-t border-latte/20 bg-cream/40 px-6 py-3.5">
                    <div className="flex items-center gap-1.5">
                        {steps.map((_, i) => (
                            <button
                                key={i}
                                type="button"
                                onClick={() => setStep(i)}
                                aria-label={`Go to step ${i + 1}`}
                                className={`h-2 rounded-full transition-all ${
                                    i === step ? "w-5 bg-tomato" : "w-2 bg-latte/30 hover:bg-latte/50"
                                }`}
                            />
                        ))}
                    </div>

                    <div className="flex items-center gap-2">
                        {step > 0 ? (
                            <button
                                type="button"
                                onClick={() => setStep((s) => Math.max(0, s - 1))}
                                className="flex items-center gap-1 rounded-xl px-3 py-2 text-xs font-semibold text-espresso hover:bg-latte/15"
                            >
                                <ChevronLeft className="h-3.5 w-3.5" />
                                Back
                            </button>
                        ) : (
                            <button
                                type="button"
                                onClick={dismiss}
                                className="rounded-xl px-3 py-2 text-xs font-semibold text-latte hover:text-espresso hover:bg-latte/15"
                            >
                                Skip
                            </button>
                        )}

                        <button
                            type="button"
                            onClick={() => {
                                if (isLast) {
                                    dismiss();
                                } else {
                                    setStep((s) => Math.min(steps.length - 1, s + 1));
                                }
                            }}
                            className="flex items-center gap-1 rounded-xl bg-tomato px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-tomato/90"
                        >
                            {isLast ? "Get Started" : "Next"}
                            {!isLast && <ChevronRight className="h-3.5 w-3.5" />}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

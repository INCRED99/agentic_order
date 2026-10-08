import { useState } from "react";
import type { FormEvent } from "react";
import { CheckCircle2, CircleAlert } from "lucide-react";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { formatMoney } from "../lib/format";

// Mock values. Real ones come from the API later.
const gmail = { connected: true, address: "orders@restaurant.example" };
const razorpay = { mode: "Test" };

interface PolicySettings {
    restaurantName: string;
    largeOrderPaise: number;
    maxDiscountPercent: number;
}

const initial: PolicySettings = {
    restaurantName: "Order Desk Kitchen",
    largeOrderPaise: 500000,
    maxDiscountPercent: 10,
};

export function Settings() {
    const [saved, setSaved] = useState<PolicySettings>(initial);
    const [name, setName] = useState(initial.restaurantName);
    const [largeRupees, setLargeRupees] = useState(String(initial.largeOrderPaise / 100));
    const [discount, setDiscount] = useState(String(initial.maxDiscountPercent));
    const [error, setError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [justSaved, setJustSaved] = useState(false);

    function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setJustSaved(false);

        const rupees = Number(largeRupees);
        const percent = Number(discount);

        if (!name.trim()) return setError("Restaurant name is required.");
        if (!Number.isInteger(rupees) || rupees < 1)
            return setError("Large order limit must be a whole number of rupees, at least 1.");
        if (!Number.isInteger(percent) || percent < 0 || percent > 100)
            return setError("Max discount must be a whole number from 0 to 100.");

        setError(null);
        setSaving(true);
        // Fake network call. Replace with real API call later.
        setTimeout(() => {
            setSaved({
                restaurantName: name.trim(),
                largeOrderPaise: rupees * 100,
                maxDiscountPercent: percent,
            });
            setSaving(false);
            setJustSaved(true);
        }, 700);
    }

    const inputClass =
        "mt-1 w-full rounded-xl border border-latte bg-paper px-3 py-2.5 text-espresso " +
        "placeholder:text-espresso/40 focus:border-tomato focus:outline-none focus:ring-2 focus:ring-tomato/30";

    return (
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Settings</h1>
            <p className="mt-1 text-espresso/70">Rules the agent follows. Backend enforces them.</p>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <Card>
                    <h2 className="font-heading text-lg text-espresso">Agent rules</h2>
                    <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
                        <label className="block text-sm font-medium text-espresso">
                            Restaurant name
                            <input
                                type="text"
                                required
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                className={inputClass}
                            />
                        </label>

                        <label className="block text-sm font-medium text-espresso">
                            Large order needs approval above (Rs)
                            <input
                                type="number"
                                inputMode="numeric"
                                min={1}
                                step={1}
                                required
                                value={largeRupees}
                                onChange={(e) => setLargeRupees(e.target.value)}
                                className={inputClass}
                            />
                            <span className="mt-1 block text-xs font-normal text-espresso/60">
                                Now: {formatMoney(saved.largeOrderPaise)}
                            </span>
                        </label>

                        <label className="block text-sm font-medium text-espresso">
                            Max discount agent may request (%)
                            <input
                                type="number"
                                inputMode="numeric"
                                min={0}
                                max={100}
                                step={1}
                                required
                                value={discount}
                                onChange={(e) => setDiscount(e.target.value)}
                                className={inputClass}
                            />
                            <span className="mt-1 block text-xs font-normal text-espresso/60">
                                Now: {saved.maxDiscountPercent}%. Every discount still needs staff approval.
                            </span>
                        </label>

                        {error && (
                            <p role="alert" className="text-sm text-chili">
                                {error}
                            </p>
                        )}
                        {justSaved && (
                            <p role="status" className="text-sm text-basil">
                                Saved.
                            </p>
                        )}

                        <Button type="submit" loading={saving} disabled={saving}>
                            Save
                        </Button>
                    </form>
                </Card>

                <Card>
                    <h2 className="font-heading text-lg text-espresso">Connections</h2>
                    <ul className="mt-4 flex flex-col gap-4">
                        <li className="flex items-start gap-3">
                            {gmail.connected ? (
                                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-basil" aria-label="connected" />
                            ) : (
                                <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-chili" aria-label="not connected" />
                            )}
                            <div className="min-w-0">
                                <p className="font-medium text-espresso">Gmail</p>
                                <p className="truncate text-sm text-espresso/70">
                                    {gmail.connected ? gmail.address : "Not connected"}
                                </p>
                            </div>
                        </li>
                        <li className="flex items-start gap-3">
                            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-basil" aria-label="active" />
                            <div>
                                <p className="font-medium text-espresso">Razorpay</p>
                                <p className="text-sm text-espresso/70">{razorpay.mode} mode. No real money moves.</p>
                            </div>
                        </li>
                    </ul>
                </Card>
            </div>
        </div>
    );
}
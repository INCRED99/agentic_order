import { useState } from "react";
import Card from "../components/ui/Card";
import { mockMenu } from "../data/mock";
import { formatMoney } from "../lib/format";
import type { MenuItem } from "../types";

export function Menu() {
    const [items, setItems] = useState<MenuItem[]>(mockMenu);

    // Local only. Real version calls API, backend stays source of truth.
    function toggleAvailable(id: string) {
        setItems((prev) =>
            prev.map((item) =>
                item.id === id ? { ...item, available: !item.available } : item,
            ),
        );
    }

    const availableCount = items.filter((i) => i.available).length;

    return (
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Menu</h1>
            <p className="mt-1 text-espresso/70">
                {availableCount} of {items.length} items available. Agent only sells available items.
            </p>

            <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((item) => (
                    <li key={item.id}>
                        <Card
                            className={`flex h-full items-center justify-between gap-3 ${item.available ? "" : "opacity-60"
                                }`}
                        >
                            <div className="min-w-0">
                                <p className="truncate font-medium text-espresso">{item.name}</p>
                                <p className="text-sm text-espresso/70">{formatMoney(item.pricePaise)}</p>
                            </div>

                            <button
                                type="button"
                                role="switch"
                                aria-checked={item.available}
                                aria-label={`${item.name} available`}
                                onClick={() => toggleAvailable(item.id)}
                                className={`relative h-8 w-14 shrink-0 rounded-full transition-colors ${item.available ? "bg-basil" : "bg-latte"
                                    }`}
                            >
                                <span
                                    className={`absolute top-1 left-1 h-6 w-6 rounded-full bg-paper shadow transition-transform ${item.available ? "translate-x-6" : ""
                                        }`}
                                />
                            </button>
                        </Card>
                    </li>
                ))}
            </ul>
        </div>
    );
}
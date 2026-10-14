import { useEffect, useState } from "react"; // load /me once
import Card from "../components/ui/Card"; // shared panel box
import OrderAddressCard from "../components/OrderAddressCard"; // already real, shows the order address
import { ApiError, apiFetch } from "../lib/api"; // the shared backend caller

interface Me { // the part of GET /me this page uses
    restaurant_name: string; // from profiles
    login_email: string; // the owner's login address
}

// DECISION PROBLEM: the agent rules shown here are written twice, in the agent code and in this text.
// Options: (1) hardcode the text here, (2) let GET /me send the rules.
// Chosen: option 1 (D66). Reason: V1 rules are fixed constants, no editing yet.
// Cost: if D64 or D55 change, this text must be edited too. V2: store rules per restaurant and send them.
const RULES: string[] = [ // fixed V1 rules, same as the agent code
    "An order with more than 10 portions of one dish, or more than 25 portions in total, needs staff approval.", // D64
    "Discounts, cancellations and refunds always need staff approval.", // D62 and D49
    "Unclear orders (missing quantity, unknown or sold-out dish) get a question by mail, no order is made.", // D50, D63
    "Each restaurant has a limit on agent runs per minute and per day.", // D55, no number shown because it changes
];

export function Settings() { // the Settings page
    const [me, setMe] = useState<Me | null>(null); // loaded profile
    const [error, setError] = useState<string | null>(null); // readable error text

    useEffect(() => { // load once when the page opens
        apiFetch<Me>("/me") // backend call with the login token
            .then(setMe) // store the profile
            .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load settings")); // friendly text
    }, []); // empty list: run once

    return ( // page markup
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Settings</h1>
            <p className="mt-1 text-espresso/70">Your restaurant and the rules the agent follows.</p>
            <OrderAddressCard />

            {error && ( // plain text error, React escapes it
                <p className="mt-3 rounded-lg bg-chili/15 px-3 py-2 text-sm text-chili">{error}</p>
            )}

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <Card>
                    <h2 className="font-heading text-lg text-espresso">Restaurant</h2>
                    <dl className="mt-4 flex flex-col gap-3 text-sm">
                        <div>
                            <dt className="text-espresso/60">Name</dt>
                            <dd className="font-medium text-espresso">{me ? me.restaurant_name : "Loading..."}</dd>
                        </div>
                        <div>
                            <dt className="text-espresso/60">Login email</dt>
                            <dd className="truncate font-medium text-espresso">{me ? me.login_email : "Loading..."}</dd>
                        </div>
                        <div>
                            <dt className="text-espresso/60">Payments</dt>
                            <dd className="font-medium text-espresso">Razorpay test mode. No real money moves.</dd>
                        </div>
                    </dl>
                </Card>

                <Card>
                    <h2 className="font-heading text-lg text-espresso">Agent rules</h2>
                    <p className="mt-1 text-sm text-espresso/60">Fixed for now. Editing comes later.</p>
                    <ul className="mt-3 flex list-disc flex-col gap-2 pl-5 text-sm text-espresso">
                        {RULES.map((rule) => ( // one bullet per rule
                            <li key={rule}>{rule}</li>
                        ))}
                    </ul>
                </Card>
            </div>
        </div>
    );
}
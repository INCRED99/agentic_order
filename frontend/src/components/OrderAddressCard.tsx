import { useState } from "react"; // local state for the "Copied" message
import Card from "./ui/Card"; // shared panel box
import Button from "./ui/Button"; // shared button
import { useMe } from "../hooks/useMe"; // the owner's profile from the backend

// DECISION PROBLEM: how does the card get its data?
// Options: (1) the Settings page loads it and passes it down, (2) the card loads it by itself.
// Chosen: option 2. Reason: Settings.tsx needs only two small edits, and other pages can reuse this card.
// Cost: if two components both call useMe, the profile is fetched twice. Fine at this size.
export default function OrderAddressCard() { // shows the address customers email their orders to
    const { me, loading, error, reload } = useMe(); // profile and state from the hook
    const [copied, setCopied] = useState(false); // true for two seconds after a successful copy
    const [copyFailed, setCopyFailed] = useState(false); // true when the browser blocked clipboard access

    async function copy(address: string) { // copy the address to the clipboard
        try { // clipboard access can be refused
            await navigator.clipboard.writeText(address); // works on localhost and on https pages
            setCopyFailed(false); // clear an older failure
            setCopied(true); // show "Copied"
            setTimeout(() => setCopied(false), 2000); // hide it again after two seconds
        } catch { // blocked by the browser
            setCopyFailed(true); // ask the owner to copy by hand
        }
    }

    return ( // the card
        <Card className="mt-4"> {/* panel with space above it */}
            <h2 className="font-display text-lg text-espresso">Your order address</h2> {/* card title, font-display is the theme font */}
            <p className="mt-1 text-sm text-espresso/70"> {/* explanation text */}
                Customers email their order to this address. Each restaurant has its own. {/* tells the owner what the address is for */}
            </p>

            {loading && <p className="mt-3 text-latte">Loading...</p>} {/* first load still running */}

            {error && ( // the profile could not be loaded
                <div className="mt-3"> {/* wrapper */}
                    <p className="text-chili">{error}</p> {/* show the reason */}
                    <button // retry button
                        type="button" // not a submit button
                        onClick={reload} // load the profile again
                        className="mt-2 rounded-lg bg-tomato px-4 py-2 text-white" // button look
                    >
                        Try again {/* button text */}
                    </button>
                </div>
            )}

            {me && ( // the profile arrived
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center"> {/* column on phones, row on wider screens */}
                    <span className="min-w-0 flex-1 select-all break-all rounded-xl border border-latte/40 bg-cream px-3 py-2.5 font-mono text-sm text-espresso"> {/* select-all picks the whole address with one click */}
                        {me.orderAddress} {/* the address built by the backend */}
                    </span>
                    <Button onClick={() => copy(me.orderAddress)}> {/* copy button */}
                        {copied ? "Copied" : "Copy"} {/* text changes after a successful copy */}
                    </Button>
                </div>
            )}

            {copyFailed && ( // clipboard blocked
                <p role="alert" className="mt-2 text-sm text-chili"> {/* alert text */}
                    Could not copy automatically. Click the address and press Ctrl+C. {/* manual fallback */}
                </p>
            )}
        </Card>
    );
}
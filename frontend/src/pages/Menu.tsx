import { useState } from "react"; // local state for the add form and the delete confirm step
import type { FormEvent } from "react"; // type of the form submit event
import { Trash2 } from "lucide-react"; // delete icon
import Card from "../components/ui/Card"; // shared panel box
import { formatMoney } from "../lib/format"; // paise to display text
import { useMenu } from "../hooks/useMenu"; // server data and actions
import type { MenuItem } from "../types"; // UI menu item shape

// Text under each dish that tells the owner how much stock is left.
function stockLabel(stock: number | null): { text: string; className: string } { // returns text and a color class
    if (stock === null) return { text: "Stock not tracked", className: "text-latte" }; // no inventory row exists
    if (stock === 0) return { text: "Out of stock", className: "text-chili" }; // nothing left, show a warning color
    return { text: `${stock} in stock`, className: "text-latte" }; // normal case
}

// DECISION PROBLEM: where does the delete control live?
// Options: (1) trash icon on the card with an inline confirm step, (2) delete button inside a separate edit view.
// Chosen: option 1 (assumed, the user did not answer). Reason: fewer clicks and no extra screen to build yet.
// Cost: a misclick is possible, so the confirm step is required. Moving to option 2 later only changes this file.
export function Menu() { // the Menu page component
    const { items, loading, error, actionError, busyIds, reload, toggleAvailable, addItem, removeItem } = useMenu(); // all data and actions come from the hook
    const [confirmId, setConfirmId] = useState<string | null>(null); // id of the dish waiting for delete confirmation
    const [name, setName] = useState(""); // add form: dish name
    const [priceRupees, setPriceRupees] = useState(""); // add form: price typed in rupees
    const [category, setCategory] = useState("Mains"); // add form: category, same default as the backend
    const [description, setDescription] = useState(""); // add form: optional description
    const [formError, setFormError] = useState<string | null>(null); // add form: problem found before calling the server

    const availableCount = items.filter((i) => i.available).length; // real count for the header line
    const adding = busyIds.has("new"); // true while the add request is in flight

    async function handleAdd(e: FormEvent<HTMLFormElement>) { // runs when the add form is submitted
        e.preventDefault(); // stop the browser from reloading the page
        const trimmedName = name.trim(); // remove spaces around the name
        const trimmedCategory = category.trim(); // remove spaces around the category
        const rupees = Number(priceRupees); // the input is text, convert to a number
        if (trimmedName === "") { // name is required
            setFormError("Enter a dish name"); // tell the owner what is wrong
            return; // stop here
        }
        if (trimmedCategory === "" || trimmedCategory.length > 40) { // backend allows 1 to 40 characters
            setFormError("Category must be 1 to 40 characters"); // tell the owner what is wrong
            return; // stop here
        }
        if (!Number.isFinite(rupees) || rupees <= 0) { // price must be a positive number
            setFormError("Enter a price above 0"); // tell the owner what is wrong
            return; // stop here
        }
        setFormError(null); // input looks fine, clear the old message
        const ok = await addItem({ // call the hook, which calls the backend
            name: trimmedName, // dish name
            description: description.trim() === "" ? undefined : description.trim(), // empty text means no description
            category: trimmedCategory, // label
            pricePaise: Math.round(rupees * 100), // rupees to integer paise, round away float noise
            available: true, // new dishes start visible
        });
        if (ok) { // the server accepted the dish
            setName(""); // reset the name field
            setPriceRupees(""); // reset the price field
            setDescription(""); // reset the description field
            setCategory("Mains"); // reset the category to the default
        }
    }

    async function handleDelete(item: MenuItem) { // runs when the owner confirms a delete
        setConfirmId(null); // close the confirm step first
        await removeItem(item.id); // ask the server, a 409 message lands in actionError
    }

    if (loading) { // first load still running
        return <p className="text-latte">Loading menu...</p>; // simple loading text
    }

    if (error) { // the list could not be loaded
        return ( // error screen with a retry button
            <div> {/* wrapper */}
                <p className="text-chili">{error}</p> {/* show the reason */}
                <button // retry button
                    type="button" // not a submit button
                    onClick={reload} // load the list again
                    className="mt-3 rounded-lg bg-tomato px-4 py-2 text-white" // button look
                >
                    Try again {/* button text */}
                </button>
            </div>
        );
    }

    return ( // normal screen
        <div> {/* page wrapper */}
            <h1 className="font-display text-2xl text-espresso md:text-3xl">Menu</h1> {/* page title, font-display is the theme font */}
            <p className="mt-1 text-espresso/70"> {/* header line */}
                {availableCount} of {items.length} items available. Agent only sells available items. {/* real numbers from the server data */}
            </p>

            {actionError && ( // show only when a toggle, add or delete failed
                <p role="alert" className="mt-3 rounded-lg border border-chili/40 bg-chili/10 px-3 py-2 text-chili"> {/* alert box */}
                    {actionError} {/* server message, for example the 409 text */}
                </p>
            )}

            <Card className="mt-4"> {/* add form panel */}
                <form onSubmit={handleAdd} className="grid gap-3 sm:grid-cols-2"> {/* two columns on wider screens */}
                    <input // dish name field
                        value={name} // controlled by state
                        onChange={(e) => setName(e.target.value)} // update state while typing
                        placeholder="Dish name" // hint text
                        aria-label="Dish name" // screen reader label
                        className="rounded-lg border border-latte/40 px-3 py-2" // field look
                    />
                    <input // price field in rupees
                        value={priceRupees} // controlled by state
                        onChange={(e) => setPriceRupees(e.target.value)} // update state while typing
                        placeholder="Price in rupees" // hint text
                        inputMode="decimal" // numeric keyboard on phones
                        aria-label="Price in rupees" // screen reader label
                        className="rounded-lg border border-latte/40 px-3 py-2" // field look
                    />
                    <input // category field, free text
                        value={category} // controlled by state
                        onChange={(e) => setCategory(e.target.value)} // update state while typing
                        placeholder="Category" // hint text
                        aria-label="Category" // screen reader label
                        className="rounded-lg border border-latte/40 px-3 py-2" // field look
                    />
                    <input // optional description field
                        value={description} // controlled by state
                        onChange={(e) => setDescription(e.target.value)} // update state while typing
                        placeholder="Description (optional)" // hint text
                        aria-label="Description" // screen reader label
                        className="rounded-lg border border-latte/40 px-3 py-2" // field look
                    />
                    <div className="flex items-center gap-3 sm:col-span-2"> {/* button row spans both columns */}
                        <button // submit button
                            type="submit" // submits the form
                            disabled={adding} // block double clicks while the request runs
                            className="rounded-lg bg-tomato px-4 py-2 text-white disabled:opacity-50" // button look
                        >
                            {adding ? "Adding..." : "Add dish"} {/* text changes while busy */}
                        </button>
                        {formError && <span className="text-sm text-chili">{formError}</span>} {/* local validation message */}
                    </div>
                </form>
            </Card>

            <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"> {/* dish grid */}
                {items.map((item) => { // one card per dish
                    const busy = busyIds.has(item.id); // true while a request for this dish runs
                    const stock = stockLabel(item.stock); // stock text and color
                    return ( // the card
                        <li key={item.id}> {/* key helps React track the row */}
                            <Card className={`flex h-full flex-col gap-3 ${item.available ? "" : "opacity-60"}`}> {/* dim hidden dishes */}
                                <div className="flex items-center justify-between gap-3"> {/* top row: info left, switch right */}
                                    <div className="min-w-0"> {/* min-w-0 lets long names truncate */}
                                        <p className="truncate font-medium text-espresso">{item.name}</p> {/* dish name */}
                                        <p className="tabular text-sm text-espresso/70">{formatMoney(item.pricePaise)}</p> {/* price, tabular keeps digits aligned */}
                                        <p className="text-xs text-latte">{item.category}</p> {/* category label */}
                                        <p className={`text-xs ${stock.className}`}>{stock.text}</p> {/* stock line */}
                                    </div>
                                    <button // availability switch
                                        type="button" // not a submit button
                                        role="switch" // announces as a switch
                                        aria-checked={item.available} // current state for screen readers
                                        aria-label={`${item.name} available`} // screen reader label
                                        disabled={busy} // wait for the server, no double clicks
                                        onClick={() => toggleAvailable(item)} // hook sends the PATCH and swaps in the server answer
                                        className={`relative h-8 w-14 shrink-0 rounded-full transition-colors disabled:opacity-50 ${item.available ? "bg-basil" : "bg-latte"}`} // track color follows state
                                    >
                                        <span // the moving knob
                                            className={`absolute top-1 left-1 h-6 w-6 rounded-full bg-paper shadow transition-transform ${item.available ? "translate-x-6" : ""}`} // slides right when on
                                        />
                                    </button>
                                </div>

                                {confirmId === item.id ? ( // confirm step is open for this dish
                                    <div className="flex items-center gap-2 text-sm"> {/* confirm row */}
                                        <span className="text-chili">Delete this dish?</span> {/* question */}
                                        <button // confirm button
                                            type="button" // not a submit button
                                            disabled={busy} // block double clicks
                                            onClick={() => handleDelete(item)} // run the delete
                                            className="rounded-lg bg-chili px-3 py-1 text-white disabled:opacity-50" // button look
                                        >
                                            Yes, delete {/* button text */}
                                        </button>
                                        <button // cancel button
                                            type="button" // not a submit button
                                            onClick={() => setConfirmId(null)} // close the confirm step
                                            className="rounded-lg border border-latte/40 px-3 py-1" // button look
                                        >
                                            Cancel {/* button text */}
                                        </button>
                                    </div>
                                ) : ( // confirm step closed, show the trash icon
                                    <button // trash icon button
                                        type="button" // not a submit button
                                        aria-label={`Delete ${item.name}`} // screen reader label
                                        disabled={busy} // block clicks while a request runs
                                        onClick={() => setConfirmId(item.id)} // open the confirm step
                                        className="self-start text-latte hover:text-chili disabled:opacity-50" // icon look
                                    >
                                        <Trash2 size={18} /> {/* the icon */}
                                    </button>
                                )}
                            </Card>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}
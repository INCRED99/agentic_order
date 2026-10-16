import { useState } from "react";
import { useMe } from "../hooks/useMe";

type Props = {
    /** Full inbox address for this restaurant, e.g. mealdesk.orders+abc123@gmail.com */
    inboxAddress?: string;
};

export default function TutorialPage({ inboxAddress }: Props = {}) {
    const { me } = useMe();
    const address = inboxAddress || me?.orderAddress || "mealdesk.orders+yourtag@gmail.com";
    const [copied, setCopied] = useState(false);

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(address);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            /* clipboard blocked: address stays selectable */
        }
    };

    return (
        <main className="otp-page">
            <style>{css}</style>

            <header>
                <h1>How orders reach you</h1>
                <p className="otp-lead">
                    Customers order by email. The assistant reads each email, builds the
                    order and sends a payment link. You follow everything from this
                    dashboard.
                </p>
            </header>

            <section className="otp-address-block" aria-labelledby="otp-addr">
                <h2 id="otp-addr">Your order email address</h2>
                <div className="otp-address">
                    <code>{address}</code>
                    <button type="button" className="otp-copy" onClick={copy}>
                        {copied ? "Copied" : "Copy address"}
                    </button>
                </div>
                <p className="otp-note">
                    Share this address on your menu, website and social pages. The part
                    after the plus sign is unique to your restaurant. Keep it exactly as
                    shown, or orders will not reach your dashboard.
                </p>
            </section>

            <ol className="otp-steps">
                <li>
                    <h2>The customer sends an email</h2>
                    <p>
                        Plain language works. The assistant matches dish names against your
                        menu.
                    </p>
                    <div className="otp-mail" aria-label="Example order email">
                        <div>
                            <span>To</span>
                            {address}
                        </div>
                        <div>
                            <span>Subject</span>Order for tonight
                        </div>
                        <p>2 Veg Biryani and 1 Cold Coffee please. Thanks, Asha</p>
                    </div>
                </li>

                <li>
                    <h2>The assistant replies with a payment link</h2>
                    <p>
                        It reads the email, builds the order and replies in the same email
                        thread with the total and a payment link. The order appears on the
                        Orders page as Pending, with payment marked Link sent.
                    </p>
                </li>

                <li>
                    <h2>The customer pays</h2>
                    <p>
                        When payment goes through, the order changes to Paid and stock is
                        deducted. Unpaid orders expire after a while.
                    </p>
                </li>

                <li>
                    <h2>You follow along</h2>
                    <p>
                        Orders shows every order and its payment state. Approvals lists
                        anything the assistant could not decide on its own. Emails shows each
                        message received.
                    </p>
                </li>
            </ol>

            <section className="otp-tips" aria-labelledby="otp-tips">
                <h2 id="otp-tips">Before you share the address</h2>
                <ul>
                    <li>Add every dish on the Menu page. Dishes missing there cannot be ordered.</li>
                    <li>Keep stock numbers current. Out of stock dishes are not sold.</li>
                    <li>Send one test order from your own email and pay it once.</li>
                    <li>Check spam if a customer says the payment link did not arrive.</li>
                    <li>
                        Limit: your restaurant can process up to 50 customer emails per day,
                        at most one per minute. The daily count resets at 5:30 AM India time.
                    </li>
                </ul>
            </section>
        </main>
    );
}

const css = `
.otp-page{max-width:760px;margin:0 auto;padding:32px 20px 64px;color:#2b1d16;font-family:inherit}
.otp-page h1{margin:0 0 10px;font-size:34px;line-height:1.15;font-weight:700}
.otp-page h2{margin:0 0 8px;font-size:20px;line-height:1.3;font-weight:700}
.otp-page p{margin:0 0 12px;font-size:16px;line-height:1.6}
.otp-lead{max-width:60ch;font-size:18px!important;color:#5c4637}
.otp-note{font-size:14px!important;color:#7a6455}
.otp-address-block{margin:28px 0;padding:20px;background:#fff;border:1px solid #f1e3d3;border-radius:16px}
.otp-address{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:10px 0 12px;padding:12px 14px;background:#fdf6ec;border:1px solid #f1e3d3;border-radius:12px}
.otp-address code{flex:1 1 240px;min-width:0;overflow-wrap:anywhere;font-size:15px;user-select:all}
.otp-copy{font:inherit;font-weight:600;border:0;border-radius:8px;padding:8px 14px;background:#e8452c;color:#fff;cursor:pointer}
.otp-copy:focus-visible{outline:3px solid #2b1d16;outline-offset:2px}
.otp-steps{list-style:none;margin:0 0 32px;padding:0;counter-reset:s}
.otp-steps>li{position:relative;margin:0;padding:0 0 28px 52px;counter-increment:s}
.otp-steps>li::before{content:counter(s);position:absolute;left:0;top:0;width:34px;height:34px;display:flex;align-items:center;justify-content:center;border-radius:50%;background:#e8452c;color:#fff;font-weight:700}
.otp-steps>li::after{content:"";position:absolute;left:16px;top:40px;bottom:6px;width:2px;background:#f1e3d3}
.otp-steps>li:last-child::after{display:none}
.otp-mail{margin:6px 0 4px;padding:14px;background:#fdf6ec;border-left:4px solid #e8452c;border-radius:8px;font-size:14px;line-height:1.5}
.otp-mail div{overflow-wrap:anywhere}
.otp-mail span{display:inline-block;width:64px;color:#7a6455}
.otp-mail p{margin:10px 0 0;font-size:15px}
.otp-tips{padding:20px;background:#fdf6ec;border-radius:16px}
.otp-tips ul{margin:0;padding-left:20px}
.otp-tips li{margin:0 0 8px;font-size:16px;line-height:1.55}
@media (max-width:480px){.otp-page h1{font-size:28px}.otp-steps>li{padding-left:46px}}
`;
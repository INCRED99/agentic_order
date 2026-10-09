import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import GoogleIcon from "../components/ui/GoogleIcon";

interface LocationState {
    from?: { pathname: string };
}

export function Login() {
    const { session, loading, signIn, signInWithGoogle } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const redirectTo = (location.state as LocationState | null)?.from?.pathname ?? "/orders";

    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);

    // Already logged in: skip login page.
    if (!loading && session) {
        return <Navigate to={redirectTo} replace />;
    }

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setError(null);
        setSubmitting(true);
        const message = await signIn(email.trim(), password);
        setSubmitting(false);
        if (message) {
            setError(message);
            return;
        }
        navigate(redirectTo, { replace: true });
    }
    async function handleGoogle() {
        setError(null);
        const message = await signInWithGoogle();
        if (message) setError(message);
    }

    const inputClass =
        "mt-1 w-full rounded-xl border border-latte bg-paper px-3 py-2.5 text-espresso " +
        "placeholder:text-espresso/40 focus:border-tomato focus:outline-none focus:ring-2 focus:ring-tomato/30";

    return (
        <div className="flex min-h-screen items-center justify-center bg-cream p-4">
            <Card className="w-full max-w-sm">
                <h1 className="font-heading text-2xl text-espresso">Order Desk</h1>
                <p className="mt-1 text-espresso/70">Staff sign in.</p>

                <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-4">
                    <label className="block text-sm font-medium text-espresso">
                        Email
                        <input
                            type="email"
                            autoComplete="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className={inputClass}
                            placeholder="staff@restaurant.com"
                        />
                    </label>

                    <label className="block text-sm font-medium text-espresso">
                        Password
                        <input
                            type="password"
                            autoComplete="current-password"
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className={inputClass}
                        />
                    </label>

                    {error && (
                        <p role="alert" className="text-sm text-chili">
                            {error}
                        </p>
                    )}

                    <Button type="submit" loading={submitting} disabled={submitting}>
                        Sign in
                    </Button>
                </form>
                <div className="my-4 flex items-center gap-3 text-sm text-espresso/50">
                    <span className="h-px flex-1 bg-latte/50" />
                    or
                    <span className="h-px flex-1 bg-latte/50" />
                </div>

                <Button
                    type="button"
                    variant="secondary"
                    className="flex w-full items-center justify-center gap-3"
                    onClick={handleGoogle}
                >
                    <GoogleIcon />
                    Continue with Google
                </Button>

            </Card>
        </div>
    );
}
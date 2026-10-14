import { Check, X } from "lucide-react"; // tick and cross icons for steps
import Card from "../components/ui/Card"; // shared panel box
import { useAgentRuns } from "../hooks/useAgentRuns"; // real runs from GET /agent-runs
import { formatTimeAgo } from "../lib/format"; // "5 min ago" formatting
import type { AgentRunStatus } from "../types"; // status words

const STATUS_LABEL: Record<AgentRunStatus, string> = { // text on the status pill
    RUNNING: "Running", // A12: run in progress
    SUCCESS: "Done", // finished fine
    WAITING_APPROVAL: "Waiting for staff", // owner must decide
    FAILED: "Failed", // run crashed
};

const STATUS_STYLE: Record<AgentRunStatus, string> = { // colors of the pill
    RUNNING: "bg-espresso/10 text-espresso", // neutral for in progress
    SUCCESS: "bg-basil/20 text-basil", // green
    WAITING_APPROVAL: "bg-saffron/25 text-espresso", // yellow
    FAILED: "bg-chili/15 text-chili", // red
};

export function AgentActivity() { // the Agent Activity page
    const { runs, loading, error } = useAgentRuns(); // data, first-load flag and error text
    const totalTokens = runs.reduce((sum, r) => sum + r.tokens, 0); // tokens of the runs on screen

    return ( // page markup
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Agent Activity</h1>
            {loading ? ( // first load still running
                <p className="mt-1 text-espresso/70">Loading runs...</p>
            ) : (
                <p className="mt-1 text-espresso/70">
                    {runs.length} runs, {totalTokens.toLocaleString("en-IN")} tokens used.
                </p>
            )}

            {error && ( // plain text error, React escapes it
                <p className="mt-3 rounded-lg bg-chili/15 px-3 py-2 text-sm text-chili">{error}</p>
            )}

            {!loading && !error && runs.length === 0 && ( // nothing yet
                <p className="mt-4 text-espresso/60">
                    No agent runs yet. Runs appear when the worker processes a customer mail.
                </p>
            )}

            <ul className="mt-4 grid gap-3">
                {runs.map((run) => ( // one card per run
                    <li key={run.id}>
                        <Card>
                            <details>
                                <summary className="flex cursor-pointer list-none flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                    <div className="min-w-0">
                                        <p className="truncate font-medium text-espresso">{run.emailSubject || "(no subject)"}</p>
                                        <p className="truncate text-sm text-espresso/60">
                                            {run.emailFrom} · {formatTimeAgo(run.startedAt)}
                                        </p>
                                    </div>
                                    <span
                                        className={`inline-block w-fit whitespace-nowrap rounded-full px-3 py-1 text-sm font-medium ${STATUS_STYLE[run.status]}`}
                                    >
                                        {STATUS_LABEL[run.status]}
                                    </span>
                                </summary>

                                <p className="mt-3 text-sm text-espresso/60">
                                    {run.modelCalls} model calls · {run.tokens.toLocaleString("en-IN")} tokens
                                </p>
                                {run.error && ( // A17: only failed runs have it
                                    <p className="mt-1 text-sm text-chili">Error: {run.error}</p>
                                )}
                                <ol className="mt-2 flex flex-col gap-2">
                                    {run.steps.map((step, i) => ( // tool calls in order
                                        <li key={i} className="flex items-start gap-2 text-sm">
                                            {step.ok ? (
                                                <Check className="mt-0.5 h-4 w-4 shrink-0 text-basil" aria-label="ok" />
                                            ) : (
                                                <X className="mt-0.5 h-4 w-4 shrink-0 text-chili" aria-label="failed" />
                                            )}
                                            <span className="min-w-0 text-espresso">
                                                <code className="font-mono text-espresso/80">{step.tool}</code>
                                                {": "}
                                                {step.summary}
                                            </span>
                                        </li>
                                    ))}
                                </ol>
                            </details>
                        </Card>
                    </li>
                ))}
            </ul>
        </div>
    );
}
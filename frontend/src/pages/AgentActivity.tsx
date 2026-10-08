import { Check, X } from "lucide-react";
import Card from "../components/ui/Card";
import { mockAgentRuns } from "../data/mock";
import { formatTimeAgo } from "../lib/format";
import type { AgentRunStatus } from "../types";

const STATUS_LABEL: Record<AgentRunStatus, string> = {
    SUCCESS: "Done",
    WAITING_APPROVAL: "Waiting for staff",
    FAILED: "Failed",
};

const STATUS_STYLE: Record<AgentRunStatus, string> = {
    SUCCESS: "bg-basil/20 text-basil",
    WAITING_APPROVAL: "bg-saffron/25 text-espresso",
    FAILED: "bg-chili/15 text-chili",
};

export function AgentActivity() {
    const runs = [...mockAgentRuns].sort(
        (a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime(),
    );
    const totalTokens = runs.reduce((sum, r) => sum + r.tokens, 0);

    return (
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">Agent Activity</h1>
            <p className="mt-1 text-espresso/70">
                {runs.length} runs, {totalTokens.toLocaleString("en-IN")} tokens used.
            </p>

            <ul className="mt-4 grid gap-3">
                {runs.map((run) => (
                    <li key={run.id}>
                        <Card>
                            <details>
                                <summary className="flex cursor-pointer list-none flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                    <div className="min-w-0">
                                        <p className="truncate font-medium text-espresso">{run.emailSubject}</p>
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
                                <ol className="mt-2 flex flex-col gap-2">
                                    {run.steps.map((step, i) => (
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
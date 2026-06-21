import { AlertTriangle, CheckCircle2, ExternalLink, Play, RotateCcw, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { runTestLabSmokeTest } from "../../api";
import type { SmokeTestCheck, SmokeTestOptions, SmokeTestReport, SmokeTestStatus } from "../../types/testLab";

const STATUS_STYLES: Record<SmokeTestStatus, { label: string; icon: typeof CheckCircle2; className: string }> = {
  pass: {
    label: "Pass",
    icon: CheckCircle2,
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  },
  warn: {
    label: "Warn",
    icon: AlertTriangle,
    className: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  },
  fail: {
    label: "Fail",
    icon: XCircle,
    className: "border-rose-500/30 bg-rose-500/10 text-rose-200",
  },
};

export default function SmokeTestLab() {
  const [options, setOptions] = useState<SmokeTestOptions>({
    render_heavy: true,
    external_api: false,
  });
  const [report, setReport] = useState<SmokeTestReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  async function handleRun() {
    if (running) return;
    setRunning(true);
    setError("");
    try {
      const nextReport = await runTestLabSmokeTest(options);
      if (!nextReport) {
        setError("Smoke Test could not start. Check the backend logs and try again.");
        return;
      }
      setReport(nextReport);
    } finally {
      setRunning(false);
    }
  }

  const groupedChecks = useMemo(() => groupChecks(report?.checks ?? []), [report]);

  return (
    <div className="grid h-full min-h-0 grid-cols-[minmax(320px,380px)_minmax(0,1fr)] gap-4">
      <aside className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        <div>
          <p className="text-xs font-semibold uppercase text-neutral-500">Smoke Test</p>
          <h2 className="mt-2 text-lg font-semibold text-neutral-100">Project readiness checks</h2>
          <p className="mt-2 text-sm leading-6 text-neutral-400">
            Runs the highest-risk Test Lab diagnostics for visual modes, settings, style character continuity,
            and representative renders.
          </p>
        </div>

        <div className="mt-5 space-y-3">
          <ToggleRow
            label="Render-heavy probes"
            description="Render representative Test Lab scenes so Remotion and manifests are exercised."
            checked={options.render_heavy}
            onChange={(render_heavy) => setOptions((current) => ({ ...current, render_heavy }))}
          />
          <ToggleRow
            label="External API asset generation"
            description="Allow probes to spend provider calls for audio, image, or cutout assets."
            checked={options.external_api}
            onChange={(external_api) => setOptions((current) => ({ ...current, external_api }))}
          />
        </div>

        <button
          onClick={handleRun}
          disabled={running}
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
        >
          {running ? <RotateCcw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          {running ? "Running Smoke Test" : "Run Smoke Test"}
        </button>

        {error && (
          <div className="mt-4 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
            {error}
          </div>
        )}
      </aside>

      <section className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        {report ? (
          <div className="space-y-4">
            <header className="flex flex-wrap items-start justify-between gap-3 border-b border-neutral-800 pb-4">
              <div>
                <p className="text-xs font-semibold uppercase text-neutral-500">Latest report</p>
                <h3 className="mt-2 text-base font-semibold text-neutral-100">{report.id}</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                <SummaryPill status="pass" count={report.summary.pass ?? 0} />
                <SummaryPill status="warn" count={report.summary.warn ?? 0} />
                <SummaryPill status="fail" count={report.summary.fail ?? 0} />
              </div>
            </header>

            {groupedChecks.map(([group, checks]) => (
              <div key={group} className="space-y-2">
                <p className="text-xs font-semibold uppercase text-neutral-500">{group}</p>
                <div className="divide-y divide-neutral-800 overflow-hidden rounded-lg border border-neutral-800">
                  {checks.map((check) => (
                    <CheckRow key={check.id} check={check} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex h-full min-h-[320px] items-center justify-center text-center">
            <div>
              <p className="text-sm font-medium text-neutral-200">No smoke test run yet</p>
              <p className="mt-2 max-w-md text-sm leading-6 text-neutral-500">
                Start with the default options for a broad local readiness check before creating a new project.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-md border border-neutral-800 bg-neutral-950/50 p-3 transition-colors hover:border-neutral-700">
      <input
        type="checkbox"
        aria-label={label}
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-4 w-4 accent-violet-500"
      />
      <span>
        <span className="block text-sm font-medium text-neutral-100">{label}</span>
        <span className="mt-1 block text-xs leading-5 text-neutral-500">{description}</span>
      </span>
    </label>
  );
}

function SummaryPill({ status, count }: { status: SmokeTestStatus; count: number }) {
  const style = STATUS_STYLES[status];
  const Icon = style.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium ${style.className}`}>
      <Icon className="h-3.5 w-3.5" />
      {count} {status === "pass" ? "passed" : status === "warn" ? "warnings" : "failed"}
    </span>
  );
}

function CheckRow({ check }: { check: SmokeTestCheck }) {
  const style = STATUS_STYLES[check.status];
  const Icon = style.icon;
  return (
    <article className="bg-neutral-950/40 p-3">
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 inline-flex rounded-md border p-1 ${style.className}`}>
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-neutral-100">{check.label}</h4>
            <span className="rounded bg-neutral-800 px-1.5 py-0.5 text-[11px] font-medium uppercase text-neutral-400">
              {style.label}
            </span>
          </div>
          <p className="mt-1 text-sm leading-6 text-neutral-300">{check.detail}</p>
          {check.next_action && (
            <p className="mt-2 text-xs leading-5 text-sky-200">{check.next_action}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-neutral-500">
            {check.run_id && <span className="rounded bg-neutral-900 px-2 py-1">{check.run_id}</span>}
            {check.evidence && <span className="rounded bg-neutral-900 px-2 py-1">{check.evidence}</span>}
            {check.render_url && (
              <a
                href={check.render_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded bg-neutral-900 px-2 py-1 text-violet-200 transition-colors hover:bg-neutral-800"
              >
                Render <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

function groupChecks(checks: SmokeTestCheck[]): Array<[string, SmokeTestCheck[]]> {
  const grouped = new Map<string, SmokeTestCheck[]>();
  for (const check of checks) {
    const group = grouped.get(check.group) ?? [];
    group.push(check);
    grouped.set(check.group, group);
  }
  return Array.from(grouped.entries());
}

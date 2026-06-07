import {
  AlertTriangle,
  Cloud,
  FileJson2,
  KeyRound,
  ListFilter,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

const FLOW_STEPS = [
  "Refresh profile in Inspire -> For You.",
  "The backend writes a sanitized seed to discovery/content-profile-seed.json.",
  "The app uploads that seed to GitHub when GITHUB_CONTENTS_TOKEN is configured.",
  "GitHub Actions runs the YouTube analyzer with the YOUTUBE_API_KEY repo secret.",
  "The workflow commits frontend/public/discovery/youtube-whitespace.json.",
  "The local app shows the updated feed after the repo/static assets are refreshed.",
];

const REQUIRED_KEYS = [
  {
    icon: Cloud,
    name: "GITHUB_CONTENTS_TOKEN",
    location: "Settings -> API Keys -> Discovery",
    purpose: "Lets the local app upload the sanitized seed JSON to GitHub.",
  },
  {
    icon: KeyRound,
    name: "YOUTUBE_API_KEY",
    location: "GitHub repo -> Actions secrets",
    purpose: "Lets GitHub Actions call the YouTube Data API during feed refresh.",
  },
];

const QUALIFIERS = [
  "10 videos or fewer",
  "At least 200K total demand",
  "At least one 100K-view video",
  "Found through a profile-derived query",
];

const TROUBLESHOOTING = [
  {
    symptom: "Whitespace still shows old results",
    fix: "Pull main locally, then restart the app or refresh the built static feed.",
  },
  {
    symptom: "GitHub Actions succeeds but feed stays old",
    fix: "Check that the repo secret YOUTUBE_API_KEY exists and is not empty.",
  },
  {
    symptom: "Profile refresh skips seed upload",
    fix: "Add GITHUB_CONTENTS_TOKEN in Settings -> API Keys -> Discovery.",
  },
  {
    symptom: "Only a few results appear",
    fix: "That is expected for V1. The analyzer is intentionally strict and favors high-confidence opportunities.",
  },
];

export default function WhitespaceDiscoveryDocSection() {
  return (
    <div className="space-y-6 px-6 py-6">
      <section className="space-y-2">
        <h2 className="text-base font-semibold text-neutral-100">Whitespace Discovery</h2>
        <p className="max-w-4xl text-sm leading-6 text-neutral-400">
          Whitespace discovery looks for YouTube channels with unusually strong demand relative to
          visible supply. It is meant to surface small channels and topic pockets where a Headless
          Hero-style video might have room to compete.
        </p>
      </section>

      <section className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <ListFilter className="h-4 w-4 text-violet-300" />
            Strict By Design
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            V1 prefers a short list of stronger signals over a broad list of weak leads. A small
            result count can mean the filters are doing their job.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <FileJson2 className="h-4 w-4 text-sky-300" />
            Static Feed
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            The tab reads a committed JSON file. It does not call YouTube live from the desktop app
            or automatically fetch the latest GitHub commit.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <ShieldCheck className="h-4 w-4 text-emerald-300" />
            Sanitized Seed
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            The uploaded seed contains profile summaries and search queries only. It must not
            include scripts, local database rows, generated paths, OAuth data, or API keys.
          </p>
        </div>
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-900/35 p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
          <RefreshCw className="h-4 w-4 text-sky-300" />
          Refresh Flow
        </div>
        <ol className="mt-4 grid gap-2 lg:grid-cols-2">
          {FLOW_STEPS.map((step, index) => (
            <li key={step} className="flex gap-3 rounded-md border border-neutral-800 bg-neutral-950/35 px-3 py-2">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-500/15 text-[11px] font-semibold text-violet-200">
                {index + 1}
              </span>
              <span className="text-xs leading-5 text-neutral-400">{step}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        {REQUIRED_KEYS.map((keyInfo) => {
          const Icon = keyInfo.icon;
          return (
            <article key={keyInfo.name} className="rounded-lg border border-neutral-800 bg-neutral-900/35 p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
                <Icon className="h-4 w-4 text-violet-300" />
                {keyInfo.name}
              </div>
              <div className="mt-3 space-y-2 text-xs leading-5 text-neutral-400">
                <p>
                  <span className="font-medium text-neutral-300">Lives in: </span>
                  {keyInfo.location}
                </p>
                <p>{keyInfo.purpose}</p>
              </div>
            </article>
          );
        })}
      </section>

      <section className="grid gap-3 lg:grid-cols-[1fr_1.2fr]">
        <article className="rounded-lg border border-neutral-800 bg-neutral-900/35 p-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <KeyRound className="h-4 w-4 text-emerald-300" />
            Qualification Rules
          </div>
          <ul className="mt-4 space-y-2">
            {QUALIFIERS.map((qualifier) => (
              <li key={qualifier} className="relative pl-4 text-xs leading-5 text-neutral-400 before:absolute before:left-0 before:top-2 before:h-1 before:w-1 before:rounded-full before:bg-neutral-600">
                {qualifier}
              </li>
            ))}
          </ul>
          <div className="mt-4 rounded-md border border-neutral-800 bg-neutral-950/40 px-3 py-2 text-xs leading-5 text-neutral-400">
            Score: <span className="font-mono text-neutral-200">log10(total_views + 1) * 100 / videos</span>
          </div>
        </article>

        <article className="rounded-lg border border-neutral-800 bg-neutral-900/35 p-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <AlertTriangle className="h-4 w-4 text-amber-300" />
            Common States
          </div>
          <div className="mt-4 space-y-2">
            {TROUBLESHOOTING.map((item) => (
              <div key={item.symptom} className="rounded-md border border-neutral-800 bg-neutral-950/35 px-3 py-2">
                <div className="text-xs font-medium text-neutral-200">{item.symptom}</div>
                <div className="mt-1 text-xs leading-5 text-neutral-400">{item.fix}</div>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}

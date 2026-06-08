import { AlertTriangle, Archive, CheckCircle2, FileText, HardDrive, Image, Layers, Mic, RefreshCw, Video } from "lucide-react";

const CACHE_AREAS = [
  {
    icon: FileText,
    title: "Script & Project Metadata",
    cached: "Script JSON, canonical project title, segment titles, script rating, short-form hook metadata, and generated SEO.",
    invalidatedBy: "Story text edits, title edits, segment title changes, hook detection changes, and SEO refreshes.",
    note: "Title-only edits update names and SEO without clearing the full-script rating. Script/story edits should invalidate ratings because the rubric no longer describes the same script.",
  },
  {
    icon: Mic,
    title: "Voiceover & Timing",
    cached: "Scene audio files, audio duration, word timestamps, and timing data used by visual validation.",
    invalidatedBy: "Narration edits, voice model/settings changes, explicit revoice actions, or manual recording replacement.",
    note: "Once real audio exists, scene duration comes from audio. The app should not silently rewrite narration or revoice scenes just to fix pacing.",
  },
  {
    icon: Image,
    title: "Normal Scene Media",
    cached: "Full-frame images plus multi-frame and continuous frame sequences.",
    invalidatedBy: "Visual prompt edits, style/reference changes, scene mode changes, frame prompt changes, and cache fingerprint changes.",
    note: "Generated scene images and frames should be full-bleed. Continuous continuation frames use the previous generated frame as their reference after the first frame.",
  },
  {
    icon: Layers,
    title: "Layered Mode Assets",
    cached: "Popup cutouts, flip-flop shared A/B state sheets and state cutouts, renderer_context staging, comparison cutouts, stat icons, caption fields, layer timing, and canvas-oriented assets.",
    invalidatedBy: "Visual-mode validation, word timing changes, layer prompt changes, renderer_context or context-stage version changes, mode changes, and mode-specific sidecar metadata changes.",
    note: "Layered modes skip or clear normal scene image paths. Their renderers own layout and readable text instead of asking generated images to contain labels.",
  },
  {
    icon: Video,
    title: "AI Video & Renders",
    cached: "AI video clips, long-form MP4 renders, short-form MP4 renders, and render sidecar metadata.",
    invalidatedBy: "Voice timing changes, visual assets, subtitle settings, hook metadata, part labels, render settings, and stale sidecar fingerprints.",
    note: "An MP4 existing on disk does not always mean it is reusable. The sidecar metadata decides whether it still matches the current project state.",
  },
  {
    icon: Archive,
    title: "Exports & Thumbnails",
    cached: "Project export folders, title-based filenames, active thumbnail, thumbnail variants, short thumbnails, and SEO markdown.",
    invalidatedBy: "Project title edits, thumbnail regeneration, thumbnail prompt fingerprints, short-form segment counts, part labels, and SEO title changes.",
    note: "Exports live under the single configured Exports root. Thumbnail regeneration preserves previous active versions instead of overwriting history.",
  },
];

const RULES = [
  "If a cache fingerprint changes, treat the old asset as stale even when the file still exists.",
  "If hook metadata is missing for short #1, older short renders are stale because they may include scenes that should now be skipped.",
  "If life-as-a part indicators do not match the current segment count and index, cached short renders and thumbnails are stale.",
  "If split-thumbnail prompt wording changes, cached Gemini-enhanced thumbnails are stale even when the source image and labels look unchanged.",
  "If a project title changes, export folders, title-based filenames, SEO markdown, and deterministic short titles must be repaired to the new title.",
  "If standard subtitle settings change, render cache fingerprints must change because the same media now renders differently.",
];

const OWNERSHIP = [
  {
    label: "Script JSON",
    body: "Stores narration, scene intent, selected visual_mode, title-card fields, segment metadata, ratings, and editor-facing project state.",
  },
  {
    label: "Voiceover",
    body: "Owns final timing. Visual validation and Remotion should use actual audio duration and word timestamps after voiceover exists.",
  },
  {
    label: "Image Generation",
    body: "Creates media assets and cutouts. It should not create readable UI text for renderer-owned modes such as captions, stat cards, or title cards.",
  },
  {
    label: "Remotion",
    body: "Owns final composition: subtitles, captions, stat typography, title cards, comparison layout, timing, and video frame output.",
  },
  {
    label: "Export Pipeline",
    body: "Owns the user-facing project folder under the configured Exports root and dedupes rendered MP4 copies where hardlinks are possible.",
  },
];

export default function RenderCacheDocSection() {
  return (
    <div className="px-6 py-6 space-y-6">
      <section className="space-y-2">
        <h2 className="text-base font-semibold text-neutral-100">Render & Cache Behavior</h2>
        <p className="max-w-4xl text-sm leading-6 text-neutral-400">
          Headless Hero reuses generated work whenever it can, but reuse depends on whether the
          saved file still matches the current script, timing, visual settings, subtitle settings,
          thumbnail metadata, and export names. This page explains the non-obvious rules behind
          why something regenerates, stays cached, or gets marked stale.
        </p>
      </section>

      <section className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <HardDrive className="h-4 w-4 text-sky-300" />
            Files Are Not Enough
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            The app often checks sidecar metadata and fingerprints before trusting an existing file.
            A stale file can stay on disk while the project correctly asks for a new render.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <RefreshCw className="h-4 w-4 text-violet-300" />
            Regenerate By Ownership
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Script changes, voice changes, visual changes, subtitle changes, and export title
            changes invalidate different layers. Reusing one layer does not guarantee the next layer
            can be reused.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <AlertTriangle className="h-4 w-4 text-amber-300" />
            Validation Can Downgrade
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Post-voiceover validation can prepare layers, time assets, and downgrade unsafe visual
            modes. It should not rewrite narration or discover every specialized mode after audio.
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-100">What Gets Cached</h3>
        <div className="grid gap-3 xl:grid-cols-2">
          {CACHE_AREAS.map((area) => {
            const Icon = area.icon;
            return (
              <article key={area.title} className="rounded-lg border border-neutral-800 bg-neutral-900/35 p-4">
                <div className="flex gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-neutral-800 text-violet-300">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 space-y-3">
                    <div>
                      <h4 className="text-sm font-semibold text-neutral-100">{area.title}</h4>
                      <p className="mt-1 text-xs leading-5 text-neutral-400">{area.cached}</p>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950/35 px-3 py-2">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-600">
                        Common invalidators
                      </div>
                      <p className="mt-1 text-xs leading-5 text-neutral-300">{area.invalidatedBy}</p>
                    </div>
                    <p className="text-xs leading-5 text-neutral-500">{area.note}</p>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-100">Stale Render Rules</h3>
        <div className="grid gap-2 md:grid-cols-2">
          {RULES.map((rule) => (
            <div key={rule} className="flex items-start gap-2 rounded-md border border-neutral-800 bg-neutral-900/40 px-3 py-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300" />
              <span className="text-xs leading-5 text-neutral-400">{rule}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-100">Ownership Map</h3>
        <div className="grid gap-3 lg:grid-cols-5">
          {OWNERSHIP.map((item) => (
            <div key={item.label} className="rounded-lg border border-neutral-800 bg-neutral-900/45 p-4">
              <div className="text-sm font-semibold text-neutral-100">{item.label}</div>
              <p className="mt-2 text-xs leading-5 text-neutral-400">{item.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

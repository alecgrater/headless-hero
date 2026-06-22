import { BadgeCheck, Captions, Clapperboard, FileJson, Image, Layers3, Palette, Scissors, Subtitles, Video } from "lucide-react";

const OWNERS = [
  {
    icon: FileJson,
    title: "Script JSON Owns Intent",
    owns: "Scene narration, visual_prompt, visual_mode, segment metadata, title-card fields, caption/stat fields, and editor-visible choices.",
    doesNotOwn: "Final image pixels, final typography layout, exact render timing, exported filenames, or platform upload state.",
    reason: "The script is the durable plan. It should describe what the scene means and which renderer path it wants, then let later stages produce concrete assets.",
  },
  {
    icon: Palette,
    title: "Style & Character References Own Continuity",
    owns: "Global style preset influence, recurring character reference, thumbnail style references, and project-level style toggles.",
    doesNotOwn: "Scene layout, subtitles, labels, comparison columns, or generated image text.",
    reason: "References guide the look of generated assets without becoming another renderer or another source of readable copy.",
  },
  {
    icon: Image,
    title: "Image Generation Owns Raw Visual Assets",
    owns: "Full-frame images, multi-frame images, continuous frames, AI-video anchor images, transparent cutouts, icon cutouts, and full-frame blink detection metadata.",
    doesNotOwn: "Readable captions, stat numbers, title-card copy, subtitle text, export wrappers, or UI labels.",
    reason: "Generated images should supply visual material. Remotion owns final composition and readable text so outputs stay editable, consistent, and cacheable.",
  },
  {
    icon: Layers3,
    title: "Layered Mode Analysis Owns Layer Plans",
    owns: "Popup item timing, comparison subject layers, stat icon layers, cutout placement hints, and mode-specific visual_layers data.",
    doesNotOwn: "Narration rewrites, voiceover duration changes, final Remotion typography, or normal scene image paths.",
    reason: "Layer planning happens after voice timing exists. It prepares renderer-ready pieces without changing the story after audio is locked.",
  },
  {
    icon: Video,
    title: "AI Video Owns Motion Clips",
    owns: "Provider-generated video_url assets derived from anchor images, plus eligibility governed by timing, spacing, and caps.",
    doesNotOwn: "Scene mode selection by quota, adjacent video overrides, narration pacing fixes, or generated still-image replacement.",
    reason: "Motion is an enhancement when it clearly helps a scene. The static anchor remains important for fallback and visual continuity.",
  },
  {
    icon: Clapperboard,
    title: "Remotion Owns Final Composition",
    owns: "Canvas layout, subtitles, title cards, caption typography, stat-card text, comparison board columns, full-frame blink overlays, animation timing, and MP4 frames.",
    doesNotOwn: "LLM prompt decisions, source narration, raw asset generation, API credentials, or export folder policy.",
    reason: "Renderer-owned text and layout keep visual modes deterministic and prevent generated images from baking in copy that cannot be corrected later.",
  },
  {
    icon: Subtitles,
    title: "Subtitle Settings Own Standard Subtitle Behavior",
    owns: "Coverage mode, enabled subtitle styles, scene-level subtitle routing, hyphen hiding, and render cache fingerprints for subtitle output.",
    doesNotOwn: "Captions visual mode text, title cards, stat-card values, or image-generated text.",
    reason: "Standard subtitles are a separate layer. Renderer-owned visual modes can suppress them when their own text would conflict.",
  },
  {
    icon: Scissors,
    title: "Export Pipeline Owns User-Facing Files",
    owns: "Project export folder, long-form MP4 destination, short-form files, SEO markdown, title-based filenames, and hardlink dedupe.",
    doesNotOwn: "Internal render cache names, script generation, visual-mode choice, or platform-side final appearance.",
    reason: "Exports are the handoff package. Internal render paths can be technical, but user-facing files need stable naming and one configured root.",
  },
];

const MODE_OWNERSHIP = [
  {
    mode: "full_frame",
    asset: "One normal scene image",
    renderer: "Static image scene fills the canvas and may layer subtitles, Eli, transitions, and scene FX.",
  },
  {
    mode: "multi_frame",
    asset: "A set of independent generated frames",
    renderer: "Frame timing and transitions decide how examples or quick beats advance.",
  },
  {
    mode: "continuous",
    asset: "A generated progression frame sequence",
    renderer: "Displays a same-scene transformation while preserving subtitle and FX layers.",
  },
  {
    mode: "video",
    asset: "Anchor image plus AI-generated motion clip",
    renderer: "Uses the clip when timing is valid and falls back to still media when needed.",
  },
  {
    mode: "popup_sequence",
    asset: "Anchor cutout plus popup item cutouts",
    renderer: "Stages orbiting popup items over the global canvas at voice-timed moments; scene-level camera drift and zoom punch are suppressed so the canvas stays stable.",
  },
  {
    mode: "comparison_board",
    asset: "Transparent comparison subject cutouts",
    renderer: "Owns columns, dividers, VS markers, arrows, badges, labels, and layout; scene-level camera drift and zoom punch are suppressed so the board stays readable.",
  },
  {
    mode: "stat_card",
    asset: "Optional supporting icon cutout",
    renderer: "Owns the giant stat_value, optional stat_label, typography, and text timing.",
  },
  {
    mode: "captions",
    asset: "Optional supporting side image",
    renderer: "Owns caption_text, caption_emphasis, editorial layout, and subtitle suppression.",
  },
];

const HANDOFF_RULES = [
  "Readable text belongs to the renderer unless the user is editing script/story copy.",
  "Normal scene images are for full_frame, multi_frame, and continuous; layered modes use their own asset paths and visual_layers.",
  "A visual_mode value chooses a renderer path. Do not reintroduce separate media_source or visual_treatment fields for normal project data.",
  "Blink is not a selectable visual_mode. Full-frame blink uses reviewed visual_source_metadata on normal generated images, while legacy/Test Lab debug blink remains a compatibility path only.",
  "Generated images should be full-bleed unless the mode is intentionally producing transparent cutouts or contact-sheet crops.",
  "Comparison board and popup sequence modes own their internal motion; do not apply whole-scene camera drift, Ken Burns movement, zoom punch, or non-cut FX transitions to them.",
  "Post-voiceover validation may prepare assets and timing, but script generation owns the main visual rhythm before voiceover.",
  "Exported files are user-facing deliverables; internal render cache files are implementation details.",
];

export default function VisualAssetOwnershipDocSection() {
  return (
    <div className="px-6 py-6 space-y-6">
      <section className="space-y-2">
        <h2 className="text-base font-semibold text-neutral-100">Visual Asset Ownership</h2>
        <p className="max-w-4xl text-sm leading-6 text-neutral-400">
          The app has several visual systems working together: script planning, style references,
          image generation, layered analysis, AI video, Remotion, subtitles, and exports. This page
          explains who owns each decision so changes land in the right layer and do not create
          hidden conflicts.
        </p>
      </section>

      <section className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <BadgeCheck className="h-4 w-4 text-emerald-300" />
            Intent Before Pixels
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Script data should describe intent and mode. Concrete image pixels, layer timings, and
            final typography are produced later by specialized stages.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <Captions className="h-4 w-4 text-violet-300" />
            Text Stays Editable
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Title cards, captions, stat cards, subtitles, and comparison labels are renderer-owned
            text layers. Do not bake them into generated images.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <Layers3 className="h-4 w-4 text-sky-300" />
            Modes Decide Asset Shape
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            A scene's visual_mode decides whether the app needs normal images, frame sequences,
            cutouts, panel assets, an AI video clip, or only renderer-owned text.
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-100">Ownership By System</h3>
        <div className="grid gap-3 xl:grid-cols-2">
          {OWNERS.map((owner) => {
            const Icon = owner.icon;
            return (
              <article key={owner.title} className="rounded-lg border border-neutral-800 bg-neutral-900/35 p-4">
                <div className="flex gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-neutral-800 text-violet-300">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 space-y-3">
                    <h4 className="text-sm font-semibold text-neutral-100">{owner.title}</h4>
                    <div className="grid gap-2 md:grid-cols-2">
                      <div className="rounded-md border border-neutral-800 bg-neutral-950/35 px-3 py-2">
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-600">
                          Owns
                        </div>
                        <p className="mt-1 text-xs leading-5 text-neutral-300">{owner.owns}</p>
                      </div>
                      <div className="rounded-md border border-neutral-800 bg-neutral-950/35 px-3 py-2">
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-600">
                          Does not own
                        </div>
                        <p className="mt-1 text-xs leading-5 text-neutral-400">{owner.doesNotOwn}</p>
                      </div>
                    </div>
                    <p className="text-xs leading-5 text-neutral-500">{owner.reason}</p>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-100">Visual Mode Asset Map</h3>
        <div className="overflow-hidden rounded-lg border border-neutral-800">
          <div className="grid grid-cols-[160px_minmax(0,1fr)_minmax(0,1fr)] border-b border-neutral-800 bg-neutral-900/80 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
            <div>Mode</div>
            <div>Generated asset</div>
            <div>Renderer responsibility</div>
          </div>
          <div className="divide-y divide-neutral-900">
            {MODE_OWNERSHIP.map((item) => (
              <div key={item.mode} className="grid grid-cols-[160px_minmax(0,1fr)_minmax(0,1fr)] gap-3 bg-neutral-950/20 px-3 py-2 text-xs leading-5">
                <div className="font-mono text-neutral-300">{item.mode}</div>
                <div className="text-neutral-400">{item.asset}</div>
                <div className="text-neutral-400">{item.renderer}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-100">Handoff Rules</h3>
        <div className="grid gap-2 md:grid-cols-2">
          {HANDOFF_RULES.map((rule) => (
            <div key={rule} className="rounded-md border border-neutral-800 bg-neutral-900/40 px-3 py-2 text-xs leading-5 text-neutral-400">
              {rule}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

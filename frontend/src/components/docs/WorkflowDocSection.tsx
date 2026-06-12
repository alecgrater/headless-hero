import {
  CheckCircle2,
  Clapperboard,
  Compass,
  FileText,
  Image,
  Lightbulb,
  Megaphone,
  Mic,
  RefreshCw,
  Scissors,
  Upload,
} from "lucide-react";

const WORKFLOW_STAGES = [
  {
    icon: Compass,
    title: "1. Set up the workspace",
    goal: "Make sure the app has everything it needs before a project starts moving.",
    details: [
      "Open Settings, confirm the export directory, and make sure API keys are present for text generation, image generation, voice, and publishing.",
      "Choose the default narrator in Voices. Headless Hero Narrator is the preferred voice, with Liam and Adam Greene as fallback options.",
      "Pick any global style or character defaults that should apply to new projects. These defaults seed projects at creation time, but each project keeps its own configuration after that.",
      "Connect YouTube, TikTok, or Instagram in Publishing when uploads should happen directly from the finished project.",
    ],
    done: "A new project can be generated without stopping for missing credentials, storage choices, or publishing setup.",
  },
  {
    icon: Lightbulb,
    title: "2. Find or write the idea",
    goal: "Start from a topic that has a clear promise and enough visual potential to carry a video.",
    details: [
      "Use Inspire when you want the app to surface trending topics, whitespace opportunities, or saved ideas from a niche.",
      "Use the idea screen directly when you already know the topic. Creator guidance can add constraints such as audience, tone, angle, or things to avoid.",
      "Choose the script type before generation. The format determines structure, title-card style, narration guardrails, and how scenes are expected to stand alone as shorts.",
      "If a cold open is available, select it only when it strengthens the opening promise instead of duplicating the first segment.",
    ],
    done: "The selected idea has a title, format, optional creator guidance, and enough specificity for the scriptwriter to produce a coherent visual story.",
  },
  {
    icon: FileText,
    title: "3. Generate and review the script",
    goal: "Create a script whose scenes work as narration, visuals, and standalone short-form segments.",
    details: [
      "Generate the script and review the outline, segment titles, title cards, narration, and visual prompts before creating expensive media assets.",
      "During outline generation, the app plans visual opportunities for each segment before scenes are cut, so modes like captions, flip-flop, stat cards, popup sequences, and comparison boards can get scenes shaped to the right length.",
      "For long scripts, outline planning uses soft candidate discovery expectations for captions, popup sequences, comparison boards, and stat cards. Final mode usage remains contextual instead of quota-driven.",
      "Caption beats use normal short-scene timing as editorial punches. Before voiceover, a metadata-only audit can fill caption and stat-card fields from existing narration without rewriting the script.",
      "Check the script rating and category breakdown. Treat low ratings as a signal to regenerate or edit the script while changes are still cheap.",
      "Confirm each segment ends cleanly on its own topic. Do not rely on a whole-video recap, subscribe request, or later scene to make a short make sense.",
      "Use timeline title editing for project title changes. The project title is canonical and is used later for export folders and deterministic short-form SEO titles.",
    ],
    done: "The script is approved, the project title is correct, and every scene has narration and visual intent that can be produced without rewriting after voiceover.",
  },
  {
    icon: Mic,
    title: "4. Generate or record voiceover",
    goal: "Lock real scene durations so visual validation and rendering use actual audio timing.",
    details: [
      "Generate voiceover with the saved ElevenLabs settings or record manually in the recording view.",
      "Scene duration comes from the generated or recorded audio file. The app should not estimate final timing once real audio exists.",
      "Post-voiceover diagnostics may flag pacing problems, but they should not rewrite narration or silently revoice scenes.",
      "If a scene is too long, fix the script or use explicit editor actions. Automatic scene-length protection should happen before voiceover.",
    ],
    done: "Every scene has audio and a positive audio duration, which unlocks visual-mode validation and asset timing.",
  },
  {
    icon: Image,
    title: "5. Validate visual modes and generate assets",
    goal: "Turn planned visual intent into render-ready images, layers, frames, and optional AI video clips.",
    details: [
      "Visual modes are planned during script generation from the segment opportunity plan. After voiceover, validation uses real timing and word timestamps to prepare mode-specific assets or downgrade unsafe choices.",
      "Full-frame scenes generate one full-bleed image. Multi-frame and continuous scenes generate frame sequences. Layered modes generate cutouts, panels, stats, captions, or comparison assets instead of normal scene images.",
      "AI video scenes start from a generated anchor image, then produce motion through the configured video provider when timing, spacing, and caps allow it.",
      "Use Test Lab for risky visual behavior before spending a full project render. Test Lab should mirror production settings where the workflow depends on shared behavior.",
      "For flip-flop iteration, use Test Lab -> Flip-flop to generate a reusable fixture once, then rerun detector or Remotion previews locally against the same saved cutout while renderer logic changes.",
    ],
    done: "The timeline has all required image, frame, layer, thumbnail, and optional video assets with no stale or missing media warnings.",
  },
  {
    icon: Clapperboard,
    title: "6. Render long-form video and shorts",
    goal: "Create final media outputs using the same assets, timing, subtitle settings, and export conventions the app will publish.",
    details: [
      "Render the long-form video when scene media, audio, subtitles, title cards, and thumbnail choices are ready.",
      "For short-form exports, hook detection runs before render/status/export/SEO so the first short can skip hook scenes when appropriate.",
      "Short-form subtitles are positioned above app chrome, and standard subtitles route per scene without extra LLM calls.",
      "Rendered MP4 exports should land in the project export folder under the single configured Exports root, with hardlink dedupe when possible.",
    ],
    done: "The long-form render and desired shorts exist in the export folder and are playable outside the app.",
  },
  {
    icon: Scissors,
    title: "7. Finalize thumbnails, titles, and metadata",
    goal: "Make the exported package upload-ready and keep titles deterministic.",
    details: [
      "Review the active long-form thumbnail and saved variants before export. Regeneration should preserve older versions for comparison.",
      "Confirm short-form thumbnails display visible part labels for life-as-a projects when needed, while upload titles remain deterministic.",
      "Generate or refresh SEO metadata after final title edits. Short-form upload titles must be project title plus segment title.",
      "If the project title changes late, existing export folders, title-based filenames, SEO markdown, and short-form SEO titles should be repaired to match.",
    ],
    done: "The exported package has final thumbnails, titles, descriptions, SEO markdown, and stable filenames.",
  },
  {
    icon: Upload,
    title: "8. Upload and verify",
    goal: "Publish the finished media and confirm the platform-facing result is correct.",
    details: [
      "Use Publishing controls to upload rendered shorts to connected platforms, or upload manually from the export folder when direct publishing is not configured.",
      "Check platform title, description, visibility, thumbnail, and video playback after upload. Platform UI is the final source of truth.",
      "Keep exported files in the project folder as the local archive. Avoid creating parallel download roots or ad hoc copies outside the configured export structure.",
      "If upload state, credentials, or platform responses change, refresh status in the app before deciding whether a retry is needed.",
    ],
    done: "The project has published videos or a verified upload-ready export folder, with local files and metadata still matching the app state.",
  },
];

const REVIEW_CHECKS = [
  "Can the first 10 seconds sell the promise without extra context?",
  "Does each short-form segment work as a standalone video?",
  "Are project title, export folder, thumbnail text, and SEO titles consistent?",
  "Do visual modes match the scene intent instead of showing variety for its own sake?",
  "Are generated images full-bleed and free of unwanted text, borders, cards, and frames?",
  "Do captions, subtitles, stat cards, and title cards avoid duplicating or fighting each other?",
  "Are all platform uploads using final rendered media rather than stale cache outputs?",
];

export default function WorkflowDocSection() {
  return (
    <div className="px-6 py-6 space-y-6">
      <section className="space-y-2">
        <h2 className="text-base font-semibold text-neutral-100">End-to-End Workflow</h2>
        <p className="max-w-4xl text-sm leading-6 text-neutral-400">
          A Headless Hero project moves from idea selection to published videos through a sequence of
          locks. The script locks story and visual intent, voiceover locks timing, visual validation locks
          assets, rendering locks final media, and publishing locks the platform-facing result.
        </p>
      </section>

      <section className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <RefreshCw className="h-4 w-4 text-sky-300" />
            Iterate Early
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Change ideas, scripts, and titles before voice and images. Later stages are still editable,
            but every change can invalidate generated media, exports, or SEO.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
            Validate Before Render
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Voice timing, visual modes, generated assets, subtitle settings, and thumbnails should all be
            ready before a long-form or shorts render is treated as final.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-neutral-100">
            <Megaphone className="h-4 w-4 text-violet-300" />
            Publish From Exports
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Finished assets live under the configured Exports directory. That folder is the handoff point
            for manual uploads and the source of truth for archived deliverables.
          </p>
        </div>
      </section>

      <section className="space-y-3">
        {WORKFLOW_STAGES.map((stage) => {
          const Icon = stage.icon;
          return (
            <article key={stage.title} className="rounded-lg border border-neutral-800 bg-neutral-900/35 p-5">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-neutral-800 text-violet-300">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1 space-y-3">
                  <div>
                    <h3 className="text-sm font-semibold text-neutral-100">{stage.title}</h3>
                    <p className="mt-1 text-xs leading-5 text-neutral-400">{stage.goal}</p>
                  </div>
                  <ul className="grid gap-2 lg:grid-cols-2">
                    {stage.details.map((detail) => (
                      <li key={detail} className="relative pl-4 text-xs leading-5 text-neutral-400 before:absolute before:left-0 before:top-2 before:h-1 before:w-1 before:rounded-full before:bg-neutral-600">
                        {detail}
                      </li>
                    ))}
                  </ul>
                  <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs leading-5 text-emerald-200">
                    Done when: {stage.done}
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-neutral-100">Final Review Checklist</h3>
        <div className="grid gap-2 md:grid-cols-2">
          {REVIEW_CHECKS.map((check) => (
            <div key={check} className="flex items-start gap-2 rounded-md border border-neutral-800 bg-neutral-900/40 px-3 py-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300" />
              <span className="text-xs leading-5 text-neutral-400">{check}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

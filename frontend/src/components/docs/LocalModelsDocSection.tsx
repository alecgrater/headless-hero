import { AlertTriangle, Cpu, Gauge, Image, Mic, ScrollText, Video } from "lucide-react";

const MODALITIES = [
  {
    icon: ScrollText,
    title: "Text",
    cloud: "Claude and OpenAI, routed per task in Settings → AI Models.",
    local: "Qwen3.8 27B through Ollama, serving every LLM task at once.",
    note: "Script quality is the most visible difference. If local scripts feel thin, set Text back to Cloud and leave images and voice local — the overrides are independent.",
  },
  {
    icon: Image,
    title: "Images",
    cloud: "Google Gemini, including thumbnails, character references, and cutouts.",
    local: "FLUX.2 klein 4B through ComfyUI, about 33 seconds per scene image.",
    note: "Character references still work: a scene generated from your style-preset character keeps their face, hair, and clothing. Qwen-Image-Edit is selectable for higher fidelity but runs roughly 24× slower.",
  },
  {
    icon: Mic,
    title: "Voice",
    cloud: "ElevenLabs, using the saved narration voice from Settings → Narration.",
    local: "Higgs TTS 3 through mlx-audio, about 3 seconds per scene once warm.",
    note: "Word timings come from local Whisper alignment rather than the TTS engine, so subtitles, highlighting, and scene durations behave exactly as before.",
  },
  {
    icon: Video,
    title: "AI Video",
    cloud: "Runway or fal, whichever is set in Settings → Visuals.",
    local: "Stays on the cloud, by design.",
    note: "Local image-to-video models are impractically slow on this hardware. Video scenes still generate their anchor image locally, then send it to the cloud provider for motion.",
  },
];

export default function LocalModelsDocSection() {
  return (
    <div className="space-y-8">
      <div className="-ml-4 rounded-2xl border border-violet-500/40 bg-violet-500/5 px-4 py-3">
        <h2 className="text-xl font-semibold tracking-tight text-neutral-100">Local Models Mode</h2>
        <p className="text-xs leading-relaxed text-neutral-500">
          Run generation on models installed on this machine instead of cloud APIs. Turn it on in
          Settings → Local Models.
        </p>
      </div>

      <div className="space-y-4">
        {MODALITIES.map((m) => (
          <div key={m.title} className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
            <div className="flex items-center gap-2">
              <m.icon className="h-4 w-4 text-violet-400" />
              <h3 className="text-sm font-semibold text-neutral-100">{m.title}</h3>
            </div>
            <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
              <div>
                <dt className="text-neutral-500">Cloud</dt>
                <dd className="text-neutral-300">{m.cloud}</dd>
              </div>
              <div>
                <dt className="text-neutral-500">Local</dt>
                <dd className="text-neutral-300">{m.local}</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs leading-relaxed text-neutral-400">{m.note}</p>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4">
        <div className="flex items-center gap-2">
          <Gauge className="h-4 w-4 text-amber-400" />
          <h3 className="text-sm font-semibold text-amber-200">One model at a time</h3>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-amber-200/90">
          The three local models plus the app and the renderer do not fit in this machine's memory
          together, so Local Mode loads one at a time and unloads it before the next stage. Scripting,
          image generation, and voiceover queue rather than overlap, which makes a fully local video
          slower end to end than a cloud one even though each individual call is free.
        </p>
      </div>

      <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          <h3 className="text-sm font-semibold text-amber-200">The default voice requires a credit</h3>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-amber-200/90">
          Higgs TTS 3 is free for monetized video only if the work credits Boson AI. When it produces
          a project's narration, “Voice: Boson AI Higgs Audio” is appended to the generated SEO
          description automatically — there is no switch to turn that off, because it is a licence
          term rather than a preference. Selecting Kokoro or Chatterbox removes the requirement and
          the credit.
        </p>
      </div>

      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-neutral-400" />
          <h3 className="text-sm font-semibold text-neutral-100">Setup and troubleshooting</h3>
        </div>
        <ul className="mt-2 space-y-1 text-xs leading-relaxed text-neutral-400">
          <li>
            Install everything with{" "}
            <code className="text-neutral-300">scripts/install-local-models.sh</code>; verify an
            existing install with <code className="text-neutral-300">--check</code>.
          </li>
          <li>
            Settings → Local Models shows live health for the three services. A modality set to
            Local while its service is down fails with a message naming the service, rather than
            silently falling back to the cloud.
          </li>
          <li>
            Switching a modality between cloud and local invalidates that modality's cached assets,
            so a “local” video never reuses cloud-generated images or a cloud narrator.
          </li>
        </ul>
      </div>
    </div>
  );
}

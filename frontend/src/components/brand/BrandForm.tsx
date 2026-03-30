import { useEffect, useState } from "react";
import type { BrandProfileCreate, ContentModifierMeta } from "../../types/brand";
import { fetchModifiers } from "../../api";

const EMPTY_FORM: BrandProfileCreate = {
  name: "",
  content_modifiers: "",
  style_string: "",
};

interface Props {
  onSave: (brand: BrandProfileCreate) => Promise<void>;
  onCancel: () => void;
  initial?: BrandProfileCreate;
  saving?: boolean;
  brandId?: string;
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function BrandForm({ onSave, onCancel, initial, saving, brandId }: Props) {
  const [form, setForm] = useState<BrandProfileCreate>(initial ?? EMPTY_FORM);
  const [modifiers, setModifiers] = useState<ContentModifierMeta[]>([]);

  useEffect(() => {
    fetchModifiers().then((res) => {
      if (res.ok && Array.isArray(res.data)) {
        setModifiers(res.data as ContentModifierMeta[]);
      }
    });
  }, []);

  // Parse active modifier IDs from the JSON string
  const activeModifierIds: string[] = (() => {
    try {
      const parsed = JSON.parse(form.content_modifiers || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  })();

  const toggleModifier = (id: string) => {
    const next = activeModifierIds.includes(id)
      ? activeModifierIds.filter((m) => m !== id)
      : [...activeModifierIds, id];
    setForm((prev) => ({ ...prev, content_modifiers: JSON.stringify(next) }));
  };

  const set = (field: keyof BrandProfileCreate, value: string) =>
    setForm((prev: BrandProfileCreate) => ({ ...prev, [field]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(form);
  };

  const isEditing = !!brandId;

  const inputCls =
    "w-full h-[44px] rounded-lg bg-[#1a1a24] border border-white/[0.08] px-3 text-[13px] text-white/90 placeholder:text-white/40 placeholder:font-['JetBrains_Mono'] outline-none transition-all duration-200 focus:border-[rgba(124,58,237,0.6)] focus:shadow-[0_0_0_3px_rgba(124,58,237,0.15)]";

  const labelCls =
    "block text-[11px] font-medium tracking-[0.08em] uppercase text-white/40 mb-1.5 font-['Sora']";

  return (
    <form
      onSubmit={handleSubmit}
      className="min-h-screen"
      style={{ background: "#0a0a0f" }}
    >
      {/* ===== Sticky Header ===== */}
      <div
        className="sticky top-0 z-50 border-b border-white/[0.06] backdrop-blur-md"
        style={{ background: "rgba(10, 10, 15, 0.85)" }}
      >
        <div className="max-w-[600px] mx-auto px-10 py-4 flex items-center justify-between">
          <h1
            className="text-[22px] font-semibold text-white/95"
            style={{ fontFamily: "Sora, sans-serif" }}
          >
            {isEditing ? "Edit Brand Profile" : "Create Brand Profile"}
          </h1>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="px-5 py-2 rounded-lg text-[13px] font-medium text-white/50 hover:text-white/80 border border-white/[0.08] hover:border-white/[0.15] bg-transparent transition-all duration-200"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !form.name.trim()}
              className="px-5 py-2 rounded-lg text-[13px] font-semibold text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(124,58,237,0.3)]"
              style={{
                fontFamily: "Sora, sans-serif",
                background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              }}
            >
              {saving ? "Saving..." : "Save Brand"}
            </button>
          </div>
        </div>
      </div>

      {/* ===== Radial glow ===== */}
      <div className="relative">
        <div
          className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] rounded-full pointer-events-none"
          style={{
            background: "radial-gradient(ellipse, rgba(124,58,237,0.06) 0%, transparent 70%)",
          }}
        />

        {/* ===== Single-column centered layout ===== */}
        <div className="max-w-[600px] mx-auto px-10 py-10 relative">
          <div
            className="rounded-xl p-6 space-y-6 transition-all duration-250 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
            style={{
              background: "#111118",
              border: "1px solid rgba(255,255,255,0.06)",
              animation: "fadeUp 400ms ease both",
            }}
          >
            <h2
              className="text-[15px] font-semibold text-white/80 mb-1"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              Brand Identity
            </h2>

            {/* Name */}
            <div>
              <label className={labelCls}>
                Brand / Channel Name <span className="text-red-400/80">*</span>
              </label>
              <input
                required
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                className={inputCls}
                placeholder="Everything Professor"
              />
            </div>

            {/* Style Prompt */}
            <div>
              <label className={labelCls}>
                Visual Style Prompt
              </label>
              <textarea
                value={form.style_string ?? ""}
                onChange={(e) => set("style_string", e.target.value)}
                className="w-full min-h-[100px] rounded-lg bg-[#1a1a24] border border-white/[0.08] px-3 py-2.5 text-[13px] text-white/90 placeholder:text-white/40 placeholder:font-['JetBrains_Mono'] outline-none transition-all duration-200 focus:border-[rgba(124,58,237,0.6)] focus:shadow-[0_0_0_3px_rgba(124,58,237,0.15)] resize-y"
                placeholder="e.g. flat vector illustration, dark background, bold outlines, minimal detail, neon accents on deep purple..."
                rows={4}
              />
              <p className="text-[11px] text-white/25 mt-1.5 leading-relaxed">
                This exact text is prepended verbatim to every image generation prompt.
                Describe your desired art style, color palette, typography, and visual feel here.
              </p>
            </div>
          </div>

          {/* ===== Content Modifiers Card ===== */}
          {modifiers.length > 0 && (
            <div
              className="rounded-xl p-6 space-y-4 transition-all duration-250 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
              style={{
                background: "#111118",
                border: "1px solid rgba(255,255,255,0.06)",
                animation: "fadeUp 400ms ease both",
                animationDelay: "100ms",
              }}
            >
              <h2
                className="text-[15px] font-semibold text-white/80 mb-1"
                style={{ fontFamily: "Sora, sans-serif" }}
              >
                Content Modifiers
              </h2>
              <p className="text-[12px] text-white/35 leading-relaxed">
                Enable plugins that change how scripts are generated and videos are rendered.
              </p>
              <div className="grid gap-3">
                {modifiers.map((mod) => {
                  const active = activeModifierIds.includes(mod.id);
                  return (
                    <button
                      key={mod.id}
                      type="button"
                      onClick={() => toggleModifier(mod.id)}
                      className={`flex items-start gap-3 p-3.5 rounded-lg border text-left transition-all duration-200 ${
                        active
                          ? "border-violet-500/40 bg-violet-500/[0.08]"
                          : "border-white/[0.06] bg-[#1a1a24] hover:border-white/[0.12]"
                      }`}
                    >
                      <span className="text-xl leading-none mt-0.5">{mod.icon}</span>
                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-[13px] font-semibold ${
                            active ? "text-violet-300" : "text-white/80"
                          }`}
                          style={{ fontFamily: "Sora, sans-serif" }}
                        >
                          {mod.name}
                        </p>
                        <p className="text-[11px] text-white/35 mt-0.5 leading-relaxed">
                          {mod.description}
                        </p>
                      </div>
                      <div
                        className={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 mt-0.5 transition-all duration-200 ${
                          active
                            ? "border-violet-500 bg-violet-500"
                            : "border-white/20 bg-transparent"
                        }`}
                      >
                        {active && (
                          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </form>
  );
}

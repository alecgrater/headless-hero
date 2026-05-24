import { useEffect, useState } from "react";
import api from "../../api";
import { useStylePreset } from "../../contexts/StylePresetContext";
import { showToast } from "../ToastContainer";
import { StylePresetToggle } from "../shared/StylePresetToggle";

const DISABLED_SETTING_VALUES = new Set(["", "0", "false", "no", "off"]);

function settingEnabled(val: string): boolean {
  return !DISABLED_SETTING_VALUES.has(val.trim().toLowerCase());
}

export default function MiscSection() {
  const [hookRefinementEnabled, setHookRefinementEnabled] = useState("true");
  const [showSpeedRenderButton, setShowSpeedRenderButton] = useState("true");
  const [rateLimitEnabled, setRateLimitEnabled] = useState("true");
  const [scraperFallbackEnabled, setScraperFallbackEnabled] = useState("false");
  const [eliEnabledDefault, setEliEnabledDefault] = useState("true");
  const [stylePresetEnabledDefault, setStylePresetEnabledDefault] = useState("true");

  const [originalHookRefinement, setOriginalHookRefinement] = useState("true");
  const [originalShowSpeedRenderButton, setOriginalShowSpeedRenderButton] = useState("true");
  const [originalRateLimit, setOriginalRateLimit] = useState("true");
  const [originalScraperFallback, setOriginalScraperFallback] = useState("false");
  const [originalEliEnabledDefault, setOriginalEliEnabledDefault] = useState("true");
  const [originalStylePresetEnabledDefault, setOriginalStylePresetEnabledDefault] = useState("true");

  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const { activePreset } = useStylePreset();

  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, { masked: string; configured: boolean; source: string }>;
        const hrVal = data.HOOK_REFINEMENT_ENABLED?.masked || "true";
        setHookRefinementEnabled(settingEnabled(hrVal) ? "true" : "false");
        setOriginalHookRefinement(settingEnabled(hrVal) ? "true" : "false");
        const srVal = data.SHOW_SPEED_RENDER_BUTTON?.masked || "true";
        setShowSpeedRenderButton(settingEnabled(srVal) ? "true" : "false");
        setOriginalShowSpeedRenderButton(settingEnabled(srVal) ? "true" : "false");
        const rlVal = data.IMAGE_RATE_LIMIT_MS?.masked || "true";
        setRateLimitEnabled(settingEnabled(rlVal) ? "true" : "false");
        setOriginalRateLimit(settingEnabled(rlVal) ? "true" : "false");
        const sfVal = data.IMAGE_SCRAPER_FALLBACK_ENABLED?.masked || "false";
        setScraperFallbackEnabled(settingEnabled(sfVal) ? "true" : "false");
        setOriginalScraperFallback(settingEnabled(sfVal) ? "true" : "false");
        const eliVal = data.ELI_ENABLED_DEFAULT?.masked || "true";
        setEliEnabledDefault(settingEnabled(eliVal) ? "true" : "false");
        setOriginalEliEnabledDefault(settingEnabled(eliVal) ? "true" : "false");
        const styleVal = data.STYLE_PRESET_ENABLED_DEFAULT?.masked || "true";
        setStylePresetEnabledDefault(settingEnabled(styleVal) ? "true" : "false");
        setOriginalStylePresetEnabledDefault(settingEnabled(styleVal) ? "true" : "false");
      }
      setLoading(false);
    });
  }, []);

  const hasChanges =
    hookRefinementEnabled !== originalHookRefinement ||
    showSpeedRenderButton !== originalShowSpeedRenderButton ||
    rateLimitEnabled !== originalRateLimit ||
    scraperFallbackEnabled !== originalScraperFallback ||
    eliEnabledDefault !== originalEliEnabledDefault ||
    stylePresetEnabledDefault !== originalStylePresetEnabledDefault;

  const handleSave = async () => {
    setSaving(true);
    const res = await api.put("/api/settings/keys", {
      HOOK_REFINEMENT_ENABLED: hookRefinementEnabled,
      SHOW_SPEED_RENDER_BUTTON: showSpeedRenderButton,
      IMAGE_RATE_LIMIT_MS: rateLimitEnabled === "true" ? "10000" : "0",
      IMAGE_SCRAPER_FALLBACK_ENABLED: scraperFallbackEnabled,
      ELI_ENABLED_DEFAULT: eliEnabledDefault,
      STYLE_PRESET_ENABLED_DEFAULT: stylePresetEnabledDefault,
    });
    setSaving(false);
    if (res.ok) {
      showToast("Settings saved", "success");
      setOriginalHookRefinement(hookRefinementEnabled);
      setOriginalShowSpeedRenderButton(showSpeedRenderButton);
      setOriginalRateLimit(rateLimitEnabled);
      setOriginalScraperFallback(scraperFallbackEnabled);
      setOriginalEliEnabledDefault(eliEnabledDefault);
      setOriginalStylePresetEnabledDefault(stylePresetEnabledDefault);
    }
  };

  if (loading) {
    return (
      <div className="px-8 py-8">
        <p className="text-sm text-neutral-500">Loading…</p>
      </div>
    );
  }

  return (
    <div className="px-8 py-8 max-w-2xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Miscellaneous</h2>
        <p className="text-neutral-400 text-sm mt-1">
          One-off toggles that don't fit neatly elsewhere.
        </p>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
        {/* Eli Host Overlay Default */}
        <div className="p-5">
          <div className="flex items-start justify-between gap-5">
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-neutral-100">Enable Eli host overlay by default for new projects</h3>
              <p className="text-xs text-neutral-500 leading-relaxed">
                When off, new projects start with Eli disabled and use a project-specific main character integrated into scene images instead. Existing projects are unaffected.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={eliEnabledDefault === "true"}
              aria-label="Enable Eli host overlay by default for new projects"
              onClick={() =>
                setEliEnabledDefault(eliEnabledDefault === "true" ? "false" : "true")
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                eliEnabledDefault === "true" ? "bg-violet-600 shadow-sm shadow-violet-500/30" : "bg-neutral-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  eliEnabledDefault === "true" ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>

        {/* Style Preset Default */}
        <div className="p-5">
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">Default style preset for new projects</h3>
              <p className="text-xs text-neutral-500 leading-relaxed">
                When on, new projects with Eli disabled will automatically use the active global style preset. Greyed out when Eli is enabled by default.
              </p>
            </div>
            <StylePresetToggle
              eliEnabled={eliEnabledDefault === "true"}
              enabled={stylePresetEnabledDefault === "true"}
              onChange={(next) => setStylePresetEnabledDefault(next ? "true" : "false")}
              activePresetName={activePreset?.name ?? null}
            />
          </div>
        </div>

        {/* Hook Refinement */}
        <div className="p-5">
          <div className="flex items-center justify-between gap-5">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">Hook Refinement</h3>
              <p className="text-xs text-neutral-500">
                After you pick from the three scored cold opens, rewrite the selected hook before using it.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={hookRefinementEnabled === "true"}
              onClick={() =>
                setHookRefinementEnabled(hookRefinementEnabled === "true" ? "false" : "true")
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                hookRefinementEnabled === "true" ? "bg-violet-600 shadow-sm shadow-violet-500/30" : "bg-neutral-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  hookRefinementEnabled === "true" ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>

        {/* 1.25x Render Button */}
        <div className="p-5">
          <div className="flex items-center justify-between gap-5">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">1.25x Render Button</h3>
              <p className="text-xs text-neutral-500">
                Shows or hides the "Render YouTube Video (1.25x Speed)" button in the Export window. The regular "Render YouTube Video" button always stays visible.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={showSpeedRenderButton === "true"}
              onClick={() =>
                setShowSpeedRenderButton(showSpeedRenderButton === "true" ? "false" : "true")
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                showSpeedRenderButton === "true" ? "bg-violet-600 shadow-sm shadow-violet-500/30" : "bg-neutral-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  showSpeedRenderButton === "true" ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>

        {/* Image Rate Limit */}
        <div className="p-5">
          <div className="flex items-center justify-between gap-5">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">Image Rate Limit</h3>
              <p className="text-xs text-neutral-500">
                Throttle batch image generation to ~6 requests/min to stay under free-tier API limits.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={rateLimitEnabled === "true"}
              onClick={() =>
                setRateLimitEnabled(rateLimitEnabled === "true" ? "false" : "true")
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                rateLimitEnabled === "true" ? "bg-violet-600 shadow-sm shadow-violet-500/30" : "bg-neutral-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  rateLimitEnabled === "true" ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>

        {/* Scraped Web Image Fallback */}
        <div className="p-5">
          <div className="flex items-start justify-between gap-5">
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-neutral-100">Scraped Web Image Fallback</h3>
              <p className="text-xs text-neutral-400 leading-relaxed">
                Off by default. When Gemini fails after its normal retries, Headless Hero will create a placeholder image so the scene stays visibly marked for regeneration. Turning this on allows the app to scrape Google Images as a last-resort fallback, which can break the project&apos;s AI visual style and may pull images with unclear rights or attribution expectations. Enable this only for rough drafts or when you plan to manually verify every fallback image before export.
              </p>
              {scraperFallbackEnabled === "true" && (
                <p className="text-xs text-amber-300 leading-relaxed">
                  Scraped fallback images are labeled in the scene properties with their provider, query, reason, and a rights-verification note.
                </p>
              )}
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={scraperFallbackEnabled === "true"}
              onClick={() =>
                setScraperFallbackEnabled(scraperFallbackEnabled === "true" ? "false" : "true")
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                scraperFallbackEnabled === "true" ? "bg-amber-500 shadow-sm shadow-amber-500/30" : "bg-neutral-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  scraperFallbackEnabled === "true" ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Sticky save bar */}
      {hasChanges && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-neutral-800 bg-neutral-900/95 backdrop-blur-sm px-8 py-3">
          <div className="max-w-2xl mx-auto flex items-center justify-between">
            <span className="text-sm text-neutral-400">You have unsaved changes</span>
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn-primary px-5 py-2 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

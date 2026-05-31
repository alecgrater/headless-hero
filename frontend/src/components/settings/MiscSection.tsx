import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import api from "../../api";
import { showToast } from "../ToastContainer";

const DISABLED_SETTING_VALUES = new Set(["", "0", "false", "no", "off"]);

function settingEnabled(val: string): boolean {
  return !DISABLED_SETTING_VALUES.has(val.trim().toLowerCase());
}

function SettingsSwitch({
  checked,
  onChange,
  label,
  warning = false,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
  warning?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
        checked
          ? warning
            ? "bg-amber-500 shadow-sm shadow-amber-500/30"
            : "bg-violet-600 shadow-sm shadow-violet-500/30"
          : "bg-neutral-700"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function SettingsRow({
  title,
  description,
  children,
  risky = false,
}: {
  title: string;
  description: string;
  children: ReactNode;
  risky?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-5 ${
        risky
          ? "border-amber-500/20 bg-amber-500/[0.03]"
          : "border-neutral-800 bg-neutral-900"
      }`}
    >
      <div className="flex items-start justify-between gap-5">
        <div className="space-y-1">
          <h3 className="text-sm font-medium text-neutral-100">{title}</h3>
          <p className="text-xs text-neutral-500 leading-relaxed">{description}</p>
        </div>
        {children}
      </div>
    </div>
  );
}

interface MiscSectionProps {
  showHeader?: boolean;
}

export default function MiscSection({ showHeader = true }: MiscSectionProps) {
  const [hookRefinementEnabled, setHookRefinementEnabled] = useState("true");
  const [showSpeedRenderButton, setShowSpeedRenderButton] = useState("true");
  const [rateLimitEnabled, setRateLimitEnabled] = useState("true");
  const [scraperFallbackEnabled, setScraperFallbackEnabled] = useState("false");

  const [originalHookRefinement, setOriginalHookRefinement] = useState("true");
  const [originalShowSpeedRenderButton, setOriginalShowSpeedRenderButton] = useState("true");
  const [originalRateLimit, setOriginalRateLimit] = useState("true");
  const [originalScraperFallback, setOriginalScraperFallback] = useState("false");

  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, { masked: string }>;
        const hrVal = settingEnabled(data.HOOK_REFINEMENT_ENABLED?.masked || "true") ? "true" : "false";
        const srVal = settingEnabled(data.SHOW_SPEED_RENDER_BUTTON?.masked || "true") ? "true" : "false";
        const rlVal = settingEnabled(data.IMAGE_RATE_LIMIT_MS?.masked || "true") ? "true" : "false";
        const sfVal = settingEnabled(data.IMAGE_SCRAPER_FALLBACK_ENABLED?.masked || "false") ? "true" : "false";
        setHookRefinementEnabled(hrVal);
        setOriginalHookRefinement(hrVal);
        setShowSpeedRenderButton(srVal);
        setOriginalShowSpeedRenderButton(srVal);
        setRateLimitEnabled(rlVal);
        setOriginalRateLimit(rlVal);
        setScraperFallbackEnabled(sfVal);
        setOriginalScraperFallback(sfVal);
      }
      setLoading(false);
    });
  }, []);

  const hasChanges =
    hookRefinementEnabled !== originalHookRefinement ||
    showSpeedRenderButton !== originalShowSpeedRenderButton ||
    rateLimitEnabled !== originalRateLimit ||
    scraperFallbackEnabled !== originalScraperFallback;

  const handleSave = async () => {
    setSaving(true);
    const res = await api.put("/api/settings/keys", {
      HOOK_REFINEMENT_ENABLED: hookRefinementEnabled,
      SHOW_SPEED_RENDER_BUTTON: showSpeedRenderButton,
      IMAGE_RATE_LIMIT_MS: rateLimitEnabled === "true" ? "10000" : "0",
      IMAGE_SCRAPER_FALLBACK_ENABLED: scraperFallbackEnabled,
    });
    setSaving(false);
    if (res.ok) {
      showToast("Settings saved", "success");
      setOriginalHookRefinement(hookRefinementEnabled);
      setOriginalShowSpeedRenderButton(showSpeedRenderButton);
      setOriginalRateLimit(rateLimitEnabled);
      setOriginalScraperFallback(scraperFallbackEnabled);
    }
  };

  if (loading) {
    return (
      <div className="px-8 py-8">
        <p className="text-sm text-neutral-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="px-8 py-8 max-w-2xl space-y-6 pb-24">
      {showHeader && (
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Advanced</h2>
        <p className="text-neutral-400 text-sm mt-1">
          Edge-case controls for workflow, rendering, and image fallback behavior.
        </p>
      </div>
      )}

      <section className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-neutral-100">Workflow</h3>
          <p className="text-xs leading-relaxed text-neutral-500">Controls that change ideation and script-prep flow.</p>
        </div>
        <SettingsRow
          title="Hook Refinement"
          description="After you pick from the three scored cold opens, rewrite the selected hook before using it."
        >
          <SettingsSwitch
            checked={hookRefinementEnabled === "true"}
            label="Toggle hook refinement"
            onChange={() => setHookRefinementEnabled(hookRefinementEnabled === "true" ? "false" : "true")}
          />
        </SettingsRow>
      </section>

      <section className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-neutral-100">Rendering</h3>
          <p className="text-xs leading-relaxed text-neutral-500">Controls that affect export UI and generation pacing.</p>
        </div>
        <div className="space-y-3">
          <SettingsRow
            title="1.25x Render Button"
            description='Shows or hides the "Render YouTube Video (1.25x Speed)" button in the Export window. The regular render button always stays visible.'
          >
            <SettingsSwitch
              checked={showSpeedRenderButton === "true"}
              label="Toggle 1.25x render button"
              onChange={() => setShowSpeedRenderButton(showSpeedRenderButton === "true" ? "false" : "true")}
            />
          </SettingsRow>
          <SettingsRow
            title="Image Rate Limit"
            description="Throttle batch image generation to about 6 requests per minute to stay under free-tier API limits."
          >
            <SettingsSwitch
              checked={rateLimitEnabled === "true"}
              label="Toggle image rate limit"
              onChange={() => setRateLimitEnabled(rateLimitEnabled === "true" ? "false" : "true")}
            />
          </SettingsRow>
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-neutral-100">Image Generation Safety</h3>
          <p className="text-xs leading-relaxed text-neutral-500">Riskier fallback behavior for rough drafts only.</p>
        </div>
        <SettingsRow
          title="Scraped Web Image Fallback"
          description="Off by default. When Gemini fails after its normal retries, Headless Hero creates a placeholder image. Turning this on allows Google Images scraping as a last resort, which can break visual style and may pull images with unclear rights."
          risky
        >
          <SettingsSwitch
            checked={scraperFallbackEnabled === "true"}
            label="Toggle scraped web image fallback"
            warning
            onChange={() => setScraperFallbackEnabled(scraperFallbackEnabled === "true" ? "false" : "true")}
          />
        </SettingsRow>
        {scraperFallbackEnabled === "true" && (
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-5 py-3 text-xs leading-relaxed text-amber-300">
            Scraped fallback images are labeled in scene properties with provider, query, reason, and a rights-verification note.
          </div>
        )}
      </section>

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

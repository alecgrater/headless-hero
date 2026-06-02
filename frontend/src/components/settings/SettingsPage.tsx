import { useEffect, useState } from "react";
import {
  Archive,
  Brain,
  Captions,
  Folder,
  Image,
  Key,
  Mic,
  Palette,
  SlidersHorizontal,
  Sparkles,
  Upload,
  type LucideIcon,
} from "lucide-react";
import ApiKeysSection from "./ApiKeysSection";
import AssetVaultSection from "./AssetVaultSection";
import GeneralSection from "./GeneralSection";
import MiscSection from "./MiscSection";
import PublishingSection from "./PublishingSection";
import { StylePresetsSection } from "./StylePresetsSection";
import SubtitlesSection from "./SubtitlesSection";
import VoiceSection from "./VoiceSection";

// eslint-disable-next-line react-refresh/only-export-components -- co-located with the SettingsPage component that owns these section IDs
export const SECTIONS = [
  { id: "storage", label: "Storage", description: "Choose where finished files and export bundles are saved.", icon: Folder, group: "Setup" },
  { id: "api-keys", label: "API Keys", description: "Manage local credentials for generation, voice, publishing, and discovery.", icon: Key, group: "Setup" },
  { id: "ai-models", label: "AI Models", description: "Route scriptwriting, ideation, metadata, scoring, and animation tasks.", icon: Brain, group: "Generation" },
  { id: "visuals", label: "Visuals", description: "Configure image generation, AI video, and scene structure defaults.", icon: Image, group: "Generation" },
  { id: "subtitles", label: "Subtitles", description: "Control subtitle coverage and which visual treatments can be routed.", icon: Captions, group: "Generation" },
  { id: "voice", label: "Voices", description: "Choose the saved narration voice and delivery settings.", icon: Mic, group: "Generation" },
  { id: "audio", label: "Audio", description: "Tune recording export filters for manually recorded voiceover.", icon: SlidersHorizontal, group: "Generation" },
  { id: "brand-style", label: "Brand & Style", description: "Set the visual style, recurring character, and defaults for new projects.", icon: Palette, group: "Brand & Style" },
  { id: "asset-vault", label: "Assets", description: "Browse and generate reusable character and item cutouts.", icon: Archive, group: "Brand & Style" },
  { id: "publishing", label: "Publishing", description: "Connect platforms that should receive one-click short-form uploads.", icon: Upload, group: "Publishing" },
  { id: "advanced", label: "Advanced", description: "Edge-case controls for workflow, rendering, and image fallback behavior.", icon: Sparkles, group: "Advanced" },
] as const;

export type SectionId = (typeof SECTIONS)[number]["id"];
export type LegacySectionId = SectionId | "style-presets" | "misc" | "script-types" | "visual-modes";

// eslint-disable-next-line react-refresh/only-export-components -- used by App to normalize legacy Settings deep links
export function normalizeSectionId(sectionId: LegacySectionId | null | undefined): SectionId {
  if (sectionId === "style-presets") return "brand-style";
  if (sectionId === "misc") return "advanced";
  if (sectionId === "script-types" || sectionId === "visual-modes") return "storage";
  return sectionId ?? "storage";
}

export function SectionIcon({ icon, className }: { icon: LucideIcon; className?: string }) {
  const Icon = icon;
  return <Icon className={className} />;
}

// eslint-disable-next-line react-refresh/only-export-components -- grouped nav metadata is shared with the top Settings dropdown
export const SECTION_GROUPS = [
  "Setup",
  "Generation",
  "Brand & Style",
  "Publishing",
  "Advanced",
] as const;

interface Props {
  onBack: () => void;
  defaultSection?: LegacySectionId | null;
  onConsumeDefaultSection?: () => void;
}

export default function SettingsPage({ onBack, defaultSection, onConsumeDefaultSection }: Props) {
  const [activeSection, setActiveSection] = useState<SectionId>(normalizeSectionId(defaultSection));
  const activeSectionMeta = SECTIONS.find((section) => section.id === activeSection) ?? SECTIONS[0];

  useEffect(() => {
    if (defaultSection) {
      setActiveSection(normalizeSectionId(defaultSection));
      onConsumeDefaultSection?.();
    }
  }, [defaultSection, onConsumeDefaultSection]);

  return (
    <div className="flex flex-col h-full">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 flex border-b border-neutral-800 bg-neutral-950">
        <div className="flex w-60 shrink-0 items-center px-6 py-5">
          <button
            onClick={onBack}
            aria-label="Back"
            className="text-neutral-400 hover:text-neutral-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 rounded-md"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <h1 className="text-xl font-semibold tracking-tight ml-4">Settings</h1>
        </div>
        <div className="flex flex-1 flex-col justify-center px-8 py-5">
          <h2 className="text-xl font-semibold tracking-tight text-neutral-100">{activeSectionMeta.label}</h2>
          <p className="mt-1 text-sm text-neutral-400">{activeSectionMeta.description}</p>
        </div>
      </div>

      {/* Sidebar + content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <nav className="w-60 shrink-0 border-r border-neutral-800 py-4 px-3 overflow-y-auto">
          <div className="space-y-5">
            {SECTION_GROUPS.map((group) => (
              <div key={group} className="space-y-1">
                <div className="px-3 text-[11px] font-semibold uppercase tracking-wide text-neutral-600">
                  {group}
                </div>
                {SECTIONS.filter((section) => section.group === group).map((section) => (
                  <button
                    key={section.id}
                    onClick={() => setActiveSection(section.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                      activeSection === section.id
                        ? "bg-neutral-800 text-neutral-100"
                        : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50"
                    }`}
                  >
                    <SectionIcon icon={section.icon} className="w-4 h-4 shrink-0" />
                    {section.label}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </nav>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto">
          {activeSection === "storage" && <GeneralSection panel="storage" showHeader={false} />}
          {activeSection === "ai-models" && <GeneralSection panel="ai-models" showHeader={false} />}
          {activeSection === "visuals" && <GeneralSection panel="visuals" showHeader={false} />}
          {activeSection === "subtitles" && <SubtitlesSection showHeader={false} />}
          {activeSection === "voice" && <VoiceSection panel="voice" showHeader={false} />}
          {activeSection === "audio" && <VoiceSection panel="audio" showHeader={false} />}
          {activeSection === "publishing" && <PublishingSection showHeader={false} />}
          {activeSection === "api-keys" && <ApiKeysSection showHeader={false} />}
          {activeSection === "advanced" && <MiscSection showHeader={false} />}
          {activeSection === "brand-style" && (
            <div className="max-w-7xl px-6 py-6">
              <StylePresetsSection showHeader={false} />
            </div>
          )}
          {activeSection === "asset-vault" && <AssetVaultSection />}
        </div>
      </div>
    </div>
  );
}

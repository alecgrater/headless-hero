import { useEffect, useState } from "react";
import {
  Brain,
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
import GeneralSection from "./GeneralSection";
import MiscSection from "./MiscSection";
import PublishingSection from "./PublishingSection";
import { StylePresetsSection } from "./StylePresetsSection";
import VoiceSection from "./VoiceSection";

// eslint-disable-next-line react-refresh/only-export-components -- co-located with the SettingsPage component that owns these section IDs
export const SECTIONS = [
  { id: "storage", label: "Storage", icon: Folder, group: "Setup" },
  { id: "api-keys", label: "API Keys", icon: Key, group: "Setup" },
  { id: "ai-models", label: "AI Models", icon: Brain, group: "Generation" },
  { id: "visuals", label: "Visuals", icon: Image, group: "Generation" },
  { id: "voice", label: "Voices", icon: Mic, group: "Generation" },
  { id: "audio", label: "Audio", icon: SlidersHorizontal, group: "Generation" },
  { id: "brand-style", label: "Brand & Style", icon: Palette, group: "Brand & Style" },
  { id: "publishing", label: "Publishing", icon: Upload, group: "Publishing" },
  { id: "advanced", label: "Advanced", icon: Sparkles, group: "Advanced" },
] as const;

export type SectionId = (typeof SECTIONS)[number]["id"];
export type LegacySectionId = SectionId | "style-presets" | "misc";

// eslint-disable-next-line react-refresh/only-export-components -- used by App to normalize legacy Settings deep links
export function normalizeSectionId(sectionId: LegacySectionId | null | undefined): SectionId {
  if (sectionId === "style-presets") return "brand-style";
  if (sectionId === "misc") return "advanced";
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

  useEffect(() => {
    if (defaultSection) {
      setActiveSection(normalizeSectionId(defaultSection));
      onConsumeDefaultSection?.();
    }
  }, [defaultSection, onConsumeDefaultSection]);

  return (
    <div className="flex flex-col h-full">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-neutral-950 border-b border-neutral-800 px-6 py-4 flex items-center">
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
          {activeSection === "storage" && <GeneralSection panel="storage" />}
          {activeSection === "ai-models" && <GeneralSection panel="ai-models" />}
          {activeSection === "visuals" && <GeneralSection panel="visuals" />}
          {activeSection === "voice" && <VoiceSection panel="voice" />}
          {activeSection === "audio" && <VoiceSection panel="audio" />}
          {activeSection === "publishing" && <PublishingSection />}
          {activeSection === "api-keys" && <ApiKeysSection />}
          {activeSection === "advanced" && <MiscSection />}
          {activeSection === "brand-style" && (
            <div className="max-w-6xl px-8 py-8">
              <StylePresetsSection />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

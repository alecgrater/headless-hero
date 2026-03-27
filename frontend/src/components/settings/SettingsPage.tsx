import { useState } from "react";
import ApiKeysSection from "./ApiKeysSection";

const SECTIONS = [
  { id: "api-keys", label: "API Keys", icon: "key" },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];

function SectionIcon({ icon, className }: { icon: string; className?: string }) {
  switch (icon) {
    case "key":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
        </svg>
      );
    default:
      return null;
  }
}

interface Props {
  onBack: () => void;
}

export default function SettingsPage({ onBack }: Props) {
  const [activeSection, setActiveSection] = useState<SectionId>("api-keys");

  return (
    <div className="flex flex-col h-full">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-neutral-950 border-b border-neutral-800 px-6 py-4 flex items-center">
        <button
          onClick={onBack}
          className="text-neutral-400 hover:text-neutral-200 transition-colors"
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
        <nav className="w-52 shrink-0 border-r border-neutral-800 py-4 px-3 space-y-1 overflow-y-auto">
          {SECTIONS.map((section) => (
            <button
              key={section.id}
              onClick={() => setActiveSection(section.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeSection === section.id
                  ? "bg-neutral-800 text-neutral-100"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50"
              }`}
            >
              <SectionIcon icon={section.icon} className="w-4 h-4 shrink-0" />
              {section.label}
            </button>
          ))}
        </nav>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto">
          {activeSection === "api-keys" && <ApiKeysSection />}
        </div>
      </div>
    </div>
  );
}

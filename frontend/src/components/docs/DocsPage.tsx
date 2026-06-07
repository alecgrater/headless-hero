import { useState } from "react";
import { DatabaseZap, FileText, GitCompare, LayoutGrid, Layers3, Radar, type LucideIcon } from "lucide-react";
import ScriptTypesSection from "../settings/script-types/ScriptTypesSection";
import VisualModesSection from "../settings/visual-modes/VisualModesSection";
import RenderCacheDocSection from "./RenderCacheDocSection";
import VisualAssetOwnershipDocSection from "./VisualAssetOwnershipDocSection";
import WhitespaceDiscoveryDocSection from "./WhitespaceDiscoveryDocSection";
import WorkflowDocSection from "./WorkflowDocSection";

const DOC_SECTIONS = [
  {
    id: "workflow",
    label: "Workflow",
    description: "Follow a project from idea selection through rendered exports and uploaded videos.",
    icon: FileText,
  },
  {
    id: "script-types",
    label: "Script Types",
    description: "Compare script formats, structure, narration rules, and visual-mode compatibility.",
    icon: GitCompare,
  },
  {
    id: "render-cache",
    label: "Render & Cache",
    description: "Understand when generated assets are reused, invalidated, regenerated, or exported.",
    icon: DatabaseZap,
  },
  {
    id: "whitespace",
    label: "Whitespace",
    description: "Understand how profile-seeded YouTube whitespace discovery refreshes and why results may be sparse.",
    icon: Radar,
  },
  {
    id: "visual-ownership",
    label: "Visual Ownership",
    description: "See which system owns script intent, generated assets, renderer text, timing, and exports.",
    icon: Layers3,
  },
  {
    id: "visual-modes",
    label: "Visual Modes",
    description: "Browse every scene visual mode, routing rule, duration profile, and renderer behavior.",
    icon: LayoutGrid,
  },
] as const;

type DocSectionId = (typeof DOC_SECTIONS)[number]["id"];

function DocIcon({ icon, className }: { icon: LucideIcon; className?: string }) {
  const Icon = icon;
  return <Icon className={className} />;
}

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState<DocSectionId>("workflow");
  const activeSectionMeta =
    DOC_SECTIONS.find((section) => section.id === activeSection) ?? DOC_SECTIONS[0];

  return (
    <div className="flex h-full flex-col">
      <div className="sticky top-0 z-10 flex border-b border-neutral-800 bg-neutral-950">
        <div className="flex w-60 shrink-0 items-center px-6 py-5">
          <h1 className="text-xl font-semibold tracking-tight">Docs</h1>
        </div>
        <div className="flex flex-1 flex-col justify-center px-8 py-5">
          <h2 className="text-xl font-semibold tracking-tight text-neutral-100">
            {activeSectionMeta.label}
          </h2>
          <p className="mt-1 text-sm text-neutral-400">{activeSectionMeta.description}</p>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <nav className="w-60 shrink-0 overflow-y-auto border-r border-neutral-800 px-3 py-4">
          <div className="space-y-1">
            {DOC_SECTIONS.map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  activeSection === section.id
                    ? "bg-neutral-800 text-neutral-100"
                    : "text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-200"
                }`}
              >
                <DocIcon icon={section.icon} className="h-4 w-4 shrink-0" />
                {section.label}
              </button>
            ))}
          </div>
        </nav>

        <div className="flex-1 overflow-y-auto">
          {activeSection === "workflow" && <WorkflowDocSection />}
          {activeSection === "script-types" && (
            <ScriptTypesSection onOpenVisualModes={() => setActiveSection("visual-modes")} />
          )}
          {activeSection === "render-cache" && <RenderCacheDocSection />}
          {activeSection === "whitespace" && <WhitespaceDiscoveryDocSection />}
          {activeSection === "visual-ownership" && <VisualAssetOwnershipDocSection />}
          {activeSection === "visual-modes" && <VisualModesSection />}
        </div>
      </div>
    </div>
  );
}

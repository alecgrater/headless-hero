import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Keyboard } from "lucide-react";
import { Tooltip } from "./components/ui/Tooltip";
import api, { assetUrl } from "./api";
import ProjectDashboard from "./components/dashboard/ProjectDashboard";
import IdeationPage from "./components/ideation/IdeationPage";
import ScriptGenerationPage from "./components/script/ScriptGenerationPage";
import SettingsPage, { SECTIONS, SectionIcon, type SectionId } from "./components/settings/SettingsPage";
import TimelinePage from "./components/timeline/TimelinePage";
import VoiceoverRecordingPage from "./components/recording/VoiceoverRecordingPage";
import { ShortcutHelpOverlay } from "./components/timeline/useKeyboardShortcuts";
import DiscoverPage from "./components/trending/DiscoverPage";
import IdeaPage from "./components/ideas/IdeaPage";
import CatalogPage from "./components/catalog/CatalogPage";
import useLongPress from "./hooks/useLongPress";
import type { Idea, VideoIdea } from "./types/idea";
import type { ScriptSummary } from "./types/script";

type View = "project-dashboard" | "ideation" | "script-generation" | "timeline" | "settings" | "discover" | "ideas" | "catalog" | "voiceover-recording";

function formatRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

export interface SaveState {
  isDirty: boolean;
  saveStatus: string;
  save: () => void;
  canUndo: boolean;
  undo: () => void;
}

function App() {
  const [backendStatus, setBackendStatus] = useState<string>("connecting...");
  const [view, setView] = useState<View>("project-dashboard");
  const [selectedIdea, setSelectedIdea] = useState<VideoIdea | null>(null);
  const [timelineScriptId, setTimelineScriptId] = useState<string | null>(null);
  const [defaultBrandId, setDefaultBrandId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState | null>(null);
  const [trendingNiche, setTrendingNiche] = useState<string | null>(null);
  const [trendingIdeas, setTrendingIdeas] = useState<VideoIdea[] | null>(null);
  const [autoGenerateNiche, setAutoGenerateNiche] = useState<string | null>(null);
  const [projectsDropdownOpen, setProjectsDropdownOpen] = useState(false);
  const [settingsDropdownOpen, setSettingsDropdownOpen] = useState(false);
  const [recentProjects, setRecentProjects] = useState<ScriptSummary[]>([]);
  const [settingsDefaultSection, setSettingsDefaultSection] = useState<SectionId | null>(null);
  const [showShortcutHelp, setShowShortcutHelp] = useState(false);

  const projectsDropdownRef = useRef<HTMLDivElement>(null);
  const settingsDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .get("/api/health")
      .then((res) => {
        if (res.ok) {
          const data = res.data as { version: string };
          setBackendStatus(`connected (v${data.version})`);
        } else {
          setBackendStatus("error");
        }
      })
      .catch(() => {
        setBackendStatus("offline");
      });
  }, []);

  // Fetch the default brand ID on startup
  const loadDefaultBrand = useCallback(async () => {
    const res = await api.get("/api/brand");
    if (res.ok) {
      const data = res.data as { id: string };
      setDefaultBrandId(data.id);
    }
  }, []);

  useEffect(() => {
    loadDefaultBrand();
  }, [loadDefaultBrand]);


  // Clear save state when leaving timeline
  const handleSetView = useCallback((v: View) => {
    if (v !== "timeline") setSaveState(null);
    if (v !== "ideation") {
      setTrendingNiche(null);
      setTrendingIdeas(null);
      setAutoGenerateNiche(null);
    }
    setView(v);
  }, []);

  // Stable callback for save state changes
  const handleSaveStateChange = useMemo(() => (s: SaveState) => setSaveState(s), []);

  // Long-press handlers for nav dropdowns
  const projectsLongPress = useLongPress({
    onClick: () => handleSetView("project-dashboard"),
    onLongPress: async () => {
      setSettingsDropdownOpen(false);
      const res = await api.get("/api/scripts");
      if (res.ok) {
        const all = res.data as ScriptSummary[];
        all.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setRecentProjects(all.slice(0, 5));
      }
      setProjectsDropdownOpen(true);
    },
  });

  const settingsLongPress = useLongPress({
    onClick: () => handleSetView("settings"),
    onLongPress: () => {
      setProjectsDropdownOpen(false);
      setSettingsDropdownOpen(true);
    },
  });

  // Dismiss dropdowns on outside click or Escape
  useEffect(() => {
    if (!projectsDropdownOpen && !settingsDropdownOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (projectsDropdownOpen && projectsDropdownRef.current && !projectsDropdownRef.current.contains(e.target as Node)) {
        setProjectsDropdownOpen(false);
      }
      if (settingsDropdownOpen && settingsDropdownRef.current && !settingsDropdownRef.current.contains(e.target as Node)) {
        setSettingsDropdownOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setProjectsDropdownOpen(false);
        setSettingsDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [projectsDropdownOpen, settingsDropdownOpen]);

  return (
    <div className="h-screen bg-app text-neutral-100 flex flex-col overflow-hidden">
      {/* Top bar */}
      <header className="relative z-50 border-b border-neutral-800/40 px-6 py-4 flex items-center justify-between bg-neutral-950/80 backdrop-blur-sm">
        <div className="flex items-center gap-6">
          <button
            onClick={() => handleSetView("project-dashboard")}
            className="text-xl font-semibold tracking-tight hover:text-violet-400 transition-colors flex items-center gap-2"
          >
            <svg className="w-6 h-6" viewBox="0 0 48 46" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z" fill="currentColor"/>
            </svg>
            Headless Hero
          </button>
          <nav className="flex items-center gap-1">
            <div className="relative" ref={projectsDropdownRef}>
              <button
                {...projectsLongPress}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                  view === "project-dashboard" || view === "ideation" || view === "script-generation" || view === "timeline"
                    ? "bg-violet-500/15 text-violet-300 font-semibold"
                    : "text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
                }`}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
                </svg>
                Projects
              </button>
              {projectsDropdownOpen && (
                <div className="absolute left-0 top-full mt-2 w-72 bg-neutral-800 border border-neutral-700 rounded-lg shadow-xl shadow-black/40 z-50 animate-[fadeUp_150ms_ease-out] overflow-hidden">
                  {recentProjects.length === 0 ? (
                    <div className="px-4 py-6 text-center text-sm text-neutral-500">No projects yet</div>
                  ) : (
                    <div className="py-1">
                      {recentProjects.map((project) => (
                        <button
                          key={project.id}
                          onClick={() => {
                            setProjectsDropdownOpen(false);
                            setTimelineScriptId(project.id);
                            handleSetView("timeline");
                          }}
                          className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-neutral-700 transition-colors text-left"
                        >
                          {project.thumbnail_url ? (
                            <img
                              src={assetUrl(project.thumbnail_url)}
                              alt=""
                              className="w-10 h-10 rounded object-cover shrink-0 bg-neutral-700"
                            />
                          ) : (
                            <div className="w-10 h-10 rounded bg-neutral-700 shrink-0 flex items-center justify-center">
                              <svg className="w-5 h-5 text-neutral-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z" />
                              </svg>
                            </div>
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-neutral-100 truncate">{project.topic_title}</div>
                            <div className="flex items-center gap-1.5 mt-0.5">
                              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                                project.status === "exported" ? "bg-emerald-400" :
                                project.status === "audio" ? "bg-amber-400" :
                                project.status === "images" ? "bg-blue-400" :
                                "bg-neutral-400"
                              }`} />
                              <span className="text-xs text-neutral-500">{formatRelativeTime(project.created_at)}</span>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => {
                      setProjectsDropdownOpen(false);
                      handleSetView("project-dashboard");
                    }}
                    className="w-full px-3 py-2.5 text-xs text-neutral-400 hover:text-neutral-200 hover:bg-neutral-700/50 transition-colors text-center border-t border-neutral-700"
                  >
                    View All Projects
                  </button>
                </div>
              )}
            </div>
            <button
              onClick={() => handleSetView("discover")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                view === "discover"
                  ? "bg-violet-500/15 text-violet-300 font-semibold"
                  : "text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
              </svg>
              Discover
            </button>
            <button
              onClick={() => handleSetView("ideas")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                view === "ideas"
                  ? "bg-violet-500/15 text-violet-300 font-semibold"
                  : "text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
              </svg>
              Ideas
            </button>
            <button
              onClick={() => handleSetView("catalog")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                view === "catalog"
                  ? "bg-violet-500/15 text-violet-300 font-semibold"
                  : "text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
              </svg>
              Catalog
            </button>
            <div className="relative" ref={settingsDropdownRef}>
              <button
                {...settingsLongPress}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                  view === "settings"
                    ? "bg-violet-500/15 text-violet-300 font-semibold"
                    : "text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
                }`}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Settings
              </button>
              {settingsDropdownOpen && (
                <div className="absolute right-0 top-full mt-2 w-52 bg-neutral-800 border border-neutral-700 rounded-lg shadow-xl shadow-black/40 z-50 animate-[fadeUp_150ms_ease-out] overflow-hidden py-1">
                  {SECTIONS.map((section) => (
                    <button
                      key={section.id}
                      onClick={() => {
                        setSettingsDropdownOpen(false);
                        setSettingsDefaultSection(section.id);
                        handleSetView("settings");
                      }}
                      className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-neutral-300 hover:bg-neutral-700 hover:text-neutral-100 transition-colors text-left"
                    >
                      <SectionIcon icon={section.icon} className="w-4 h-4 shrink-0 text-neutral-500" />
                      {section.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </nav>
        </div>
        <div className="flex items-center gap-4">
          {/* Save controls — only visible on timeline view */}
          {view === "timeline" && saveState && (
            <div className="flex items-center gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${
                saveState.saveStatus === "saved"
                  ? "bg-emerald-400"
                  : saveState.saveStatus === "saving"
                    ? "bg-yellow-400"
                    : "bg-red-400 animate-pulse"
              }`} />
              <span className="text-[11px] text-neutral-500">
                {saveState.saveStatus === "saved" ? "Saved" : saveState.saveStatus === "saving" ? "Saving..." : "Unsaved"}
              </span>
              {saveState.canUndo && (
                <button
                  onClick={saveState.undo}
                  className="text-[11px] px-2 py-1 text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800 rounded-md transition-colors"
                  title="Undo (Cmd+Z)"
                >
                  Undo
                </button>
              )}
              <button
                onClick={saveState.save}
                disabled={!saveState.isDirty}
                className={`text-sm px-3 py-1 rounded-lg font-medium transition-colors ${
                  saveState.isDirty
                    ? "bg-neutral-200 text-neutral-900 hover:bg-white"
                    : "bg-neutral-800 text-neutral-500 cursor-default"
                }`}
                title="Cmd+S"
              >
                Save
              </button>
            </div>
          )}
          {/* Keyboard shortcuts */}
          <Tooltip content="Keyboard shortcuts (?)">
            <button
              onClick={() => setShowShortcutHelp((prev) => !prev)}
              className="text-neutral-500 hover:text-neutral-300 transition-colors p-1 rounded-md hover:bg-neutral-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
              aria-label="Keyboard shortcuts"
            >
              <Keyboard size={16} />
            </button>
          </Tooltip>
          <div className="flex items-center gap-2 text-sm text-neutral-500">
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                backendStatus.startsWith("connected")
                  ? "bg-emerald-500"
                  : backendStatus === "connecting..."
                    ? "bg-yellow-500 animate-pulse"
                    : "bg-red-500"
              }`}
            />
            Backend: {backendStatus}
          </div>
        </div>
      </header>

      {/* Main content area */}
      <main className={`flex-1 min-h-0 w-full ${view === "timeline" || view === "project-dashboard" || view === "settings" || view === "discover" || view === "ideas" || view === "catalog" || view === "voiceover-recording" ? "overflow-hidden" : "overflow-y-auto px-6 py-8 max-w-4xl mx-auto"}`}>
        {view === "settings" && (
          <SettingsPage
            onBack={() => handleSetView("project-dashboard")}
            defaultSection={settingsDefaultSection}
            onConsumeDefaultSection={() => setSettingsDefaultSection(null)}
          />
        )}

        {view === "discover" && (
          <DiscoverPage
            onGenerateIdeas={(ideas, niche) => {
              setTrendingIdeas(ideas);
              setTrendingNiche(niche);
              handleSetView("ideation");
            }}
          />
        )}

        {view === "ideation" && (
          <IdeationPage
            initialIdeas={trendingIdeas}
            initialNiche={trendingNiche}
            autoGenerateNiche={autoGenerateNiche}
            onUseIdea={(idea) => {
              setSelectedIdea(idea);
              handleSetView("script-generation");
            }}
          />
        )}

        {view === "script-generation" && selectedIdea && defaultBrandId && (
          <ScriptGenerationPage
            brandId={defaultBrandId}
            idea={selectedIdea}
            onBack={() => handleSetView("ideation")}
            onContinue={(scriptId) => {
              setTimelineScriptId(scriptId);
              handleSetView("timeline");
            }}
          />
        )}

        {view === "timeline" && timelineScriptId && (
          <TimelinePage
            scriptId={timelineScriptId}
            onBack={() => handleSetView("project-dashboard")}
            onSaveStateChange={handleSaveStateChange}
            onNavigateToSettings={() => handleSetView("settings")}
            onRecordVoiceover={() => handleSetView("voiceover-recording")}
          />
        )}

        {view === "voiceover-recording" && timelineScriptId && (
          <VoiceoverRecordingPage
            scriptId={timelineScriptId}
            onClose={() => handleSetView("timeline")}
          />
        )}

        {view === "project-dashboard" && (
          <ProjectDashboard
            onNewVideo={() => handleSetView("ideation")}
            onOpenProject={(scriptId) => {
              setTimelineScriptId(scriptId);
              handleSetView("timeline");
            }}
          />
        )}

        {view === "ideas" && (
          <IdeaPage
            onGenerateIdeas={(niche) => {
              setAutoGenerateNiche(niche);
              handleSetView("ideation");
            }}
            onUseIdea={(idea: Idea) => {
              const hook = idea.selected_hook_json ? JSON.parse(idea.selected_hook_json) as { intro_hook: string; opening_narration: string } : null;
              setSelectedIdea({
                title: idea.text,
                segments_est: 8,
                description: idea.description,
                keywords: [],
                cold_open_text: hook ? `${hook.intro_hook}\n\n${hook.opening_narration}` : undefined,
              });
              handleSetView("script-generation");
            }}
          />
        )}

        {view === "catalog" && <CatalogPage onNavigateToSettings={() => handleSetView("settings")} />}
      </main>
      {showShortcutHelp && (
        <ShortcutHelpOverlay onClose={() => setShowShortcutHelp(false)} />
      )}
    </div>
  );
}

export default App;

import { useCallback, useEffect, useState } from "react";
import api from "./api";
import ProjectDashboard from "./components/dashboard/ProjectDashboard";
import IdeationPage from "./components/ideation/IdeationPage";
import ScriptGenerationPage from "./components/script/ScriptGenerationPage";
import SettingsPage from "./components/settings/SettingsPage";
import TimelinePage from "./components/timeline/TimelinePage";
import type { VideoIdea } from "./types/idea";

type View = "project-dashboard" | "ideation" | "script-generation" | "timeline" | "settings";

function App() {
  const [backendStatus, setBackendStatus] = useState<string>("connecting...");
  const [view, setView] = useState<View>("project-dashboard");
  const [selectedIdea, setSelectedIdea] = useState<VideoIdea | null>(null);
  const [timelineScriptId, setTimelineScriptId] = useState<string | null>(null);
  const [defaultBrandId, setDefaultBrandId] = useState<string | null>(null);

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

  return (
    <div className="min-h-screen bg-app text-neutral-100 flex flex-col">
      {/* Top bar */}
      <header className="border-b border-neutral-800/40 px-6 py-4 flex items-center justify-between bg-neutral-950/80 backdrop-blur-sm">
        <button
          onClick={() => setView("project-dashboard")}
          className="text-xl font-semibold tracking-tight hover:text-violet-400 transition-colors flex items-center gap-2"
        >
          <svg className="w-6 h-6" viewBox="0 0 48 46" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z" fill="currentColor"/>
          </svg>
          Headless Hero
        </button>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setView("settings")}
            className="text-neutral-400 hover:text-neutral-200 transition-colors"
            title="Settings"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
          <div className="flex items-center gap-2 text-sm text-neutral-500">
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                backendStatus.startsWith("connected")
                  ? "bg-emerald-500"
                  : backendStatus === "connecting..."
                    ? "bg-yellow-500"
                    : "bg-red-500"
              }`}
            />
            Backend: {backendStatus}
          </div>
        </div>
      </header>

      {/* Main content area */}
      <main className={`flex-1 w-full ${view === "timeline" || view === "project-dashboard" || view === "settings" ? "" : "px-6 py-8 max-w-4xl mx-auto"}`}>
        {view === "settings" && (
          <SettingsPage onBack={() => setView("project-dashboard")} />
        )}

        {view === "ideation" && (
          <IdeationPage
            onUseIdea={(idea) => {
              setSelectedIdea(idea);
              setView("script-generation");
            }}
          />
        )}

        {view === "script-generation" && selectedIdea && defaultBrandId && (
          <ScriptGenerationPage
            brandId={defaultBrandId}
            idea={selectedIdea}
            onBack={() => setView("ideation")}
            onContinue={(scriptId) => {
              setTimelineScriptId(scriptId);
              setView("timeline");
            }}
          />
        )}

        {view === "timeline" && timelineScriptId && (
          <TimelinePage
            scriptId={timelineScriptId}
            onBack={() => setView("project-dashboard")}
          />
        )}

        {view === "project-dashboard" && (
          <ProjectDashboard
            onNewVideo={() => setView("ideation")}
            onOpenProject={(scriptId) => {
              setTimelineScriptId(scriptId);
              setView("timeline");
            }}
          />
        )}
      </main>
    </div>
  );
}

export default App;

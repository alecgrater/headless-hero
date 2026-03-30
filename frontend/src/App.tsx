import { useCallback, useEffect, useState } from "react";
import api from "./api";
import BrandForm from "./components/brand/BrandForm";
import BrandList from "./components/brand/BrandList";
import ProjectDashboard from "./components/dashboard/ProjectDashboard";
import FormatSelection from "./components/ideation/FormatSelection";
import IdeationPage from "./components/ideation/IdeationPage";
import ScriptGenerationPage from "./components/script/ScriptGenerationPage";
import SettingsPage from "./components/settings/SettingsPage";
import StoryboardPage from "./components/storyboard/StoryboardPage";
import type { BrandProfile, BrandProfileCreate } from "./types/brand";
import type { VideoIdea } from "./types/idea";

type View = "home" | "brand-create" | "brand-edit" | "project-dashboard" | "ideation" | "format-selection" | "script-generation" | "storyboard" | "settings";

function App() {
  const [backendStatus, setBackendStatus] = useState<string>("connecting...");
  const [view, setView] = useState<View>("home");
  const [brands, setBrands] = useState<BrandProfile[]>([]);
  const [selectedBrand, setSelectedBrand] = useState<BrandProfile | null>(null);
  const [editingBrand, setEditingBrand] = useState<BrandProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [selectedIdea, setSelectedIdea] = useState<VideoIdea | null>(null);
  const [storyboardScriptId, setStoryboardScriptId] = useState<string | null>(null);
  const [contentFormat, setContentFormat] = useState<"youtube" | "shortform">("youtube");
  const [shortformPlatforms, setShortformPlatforms] = useState<string[]>(["youtube_shorts", "tiktok", "instagram_reels"]);

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

  const loadBrands = useCallback(async () => {
    const res = await api.get("/api/brands");
    if (res.ok) setBrands(res.data as BrandProfile[]);
  }, []);

  useEffect(() => {
    loadBrands();
  }, [loadBrands]);

  const handleCreate = async (data: BrandProfileCreate) => {
    setSaving(true);
    try {
      const res = await api.post("/api/brands", data);
      if (res.ok) {
        await loadBrands();
        setSelectedBrand(res.data as BrandProfile);
        setView("home");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (data: BrandProfileCreate) => {
    if (!editingBrand) return;
    setSaving(true);
    try {
      const res = await api.put(`/api/brands/${editingBrand.id}`, data);
      if (res.ok) {
        await loadBrands();
        setSelectedBrand(res.data as BrandProfile);
        setEditingBrand(null);
        setView("home");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (brand: BrandProfile) => {
    if (!confirm(`Delete brand "${brand.name}"?`)) return;
    await api.delete(`/api/brands/${brand.id}`);
    if (selectedBrand?.id === brand.id) setSelectedBrand(null);
    await loadBrands();
  };

  const startEdit = (brand: BrandProfile) => {
    setEditingBrand(brand);
    setView("brand-edit");
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col">
      {/* Top bar */}
      <header className="border-b border-neutral-800/40 px-6 py-4 flex items-center justify-between">
        <button
          onClick={() => {
            setView("home");
            setEditingBrand(null);
          }}
          className="text-xl font-semibold tracking-tight hover:text-violet-400 transition-colors flex items-center gap-2"
        >
          <svg className="w-6 h-6" viewBox="0 0 48 46" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z" fill="currentColor"/>
          </svg>
          Headless Hero
        </button>
        <div className="flex items-center gap-4">
          {selectedBrand && (
            <span className="text-sm text-neutral-400">
              Brand:{" "}
              <span className="text-violet-400 font-medium">
                {selectedBrand.name}
              </span>
            </span>
          )}
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
      <main className={`flex-1 w-full ${view === "storyboard" || view === "project-dashboard" || view === "brand-create" || view === "brand-edit" || view === "settings" || view === "format-selection" ? "" : "px-6 py-8 max-w-4xl mx-auto"}`}>
        {view === "settings" && (
          <SettingsPage onBack={() => setView("home")} />
        )}

        {view === "brand-create" && (
          <BrandForm
            onSave={handleCreate}
            onCancel={() => setView("home")}
            saving={saving}
          />
        )}

        {view === "brand-edit" && editingBrand && (
          <BrandForm
            onSave={handleUpdate}
            onCancel={() => {
              setEditingBrand(null);
              setView("home");
            }}
            initial={editingBrand}
            saving={saving}
            brandId={editingBrand.id}
          />
        )}

        {view === "ideation" && selectedBrand && (
          <IdeationPage
            brand={selectedBrand}
            onUseIdea={(idea) => {
              setSelectedIdea(idea);
              setView("format-selection");
            }}
          />
        )}

        {view === "format-selection" && selectedBrand && selectedIdea && (
          <FormatSelection
            onSelect={(format, platforms) => {
              setContentFormat(format);
              setShortformPlatforms(platforms);
              setView("script-generation");
            }}
            onBack={() => setView("ideation")}
          />
        )}

        {view === "script-generation" && selectedBrand && selectedIdea && (
          <ScriptGenerationPage
            brand={selectedBrand}
            idea={selectedIdea}
            contentFormat={contentFormat}
            shortformPlatforms={shortformPlatforms}
            onBack={() => setView("format-selection")}
            onContinue={(scriptId) => {
              setStoryboardScriptId(scriptId);
              setView("storyboard");
            }}
          />
        )}

        {view === "storyboard" && storyboardScriptId && (
          <StoryboardPage
            scriptId={storyboardScriptId}
            onBack={() => setView("project-dashboard")}
          />
        )}

        {view === "project-dashboard" && selectedBrand && (
          <ProjectDashboard
            brand={selectedBrand}
            onNewVideo={() => setView("ideation")}
            onOpenProject={(scriptId) => {
              setStoryboardScriptId(scriptId);
              setView("storyboard");
            }}
            onBack={() => setView("home")}
          />
        )}

        {view === "home" && (
          <div className="space-y-8">
            <BrandList
              brands={brands}
              selectedId={selectedBrand?.id}
              onSelect={(brand) => {
                setSelectedBrand(brand);
                setView("project-dashboard");
              }}
              onEdit={startEdit}
              onDelete={handleDelete}
              onCreate={() => setView("brand-create")}
            />

            {/* Empty state when no brands */}
            {brands.length === 0 && (
              <div className="text-center pt-8 space-y-4">
                <h2 className="text-4xl font-bold tracking-tight">Welcome</h2>
                <p className="text-neutral-400 text-lg max-w-md mx-auto">
                  Your AI-powered video production pipeline.
                  <br />
                  Start by creating a brand profile, then generate your first
                  video.
                </p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;

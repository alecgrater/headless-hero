import { useCallback, useEffect, useState } from "react";
import api from "./api";
import "./App.css";
import BrandForm from "./components/brand/BrandForm";
import BrandList from "./components/brand/BrandList";
import BrandSettings from "./components/brand/BrandSettings";
import IdeationPage from "./components/ideation/IdeationPage";
import ScriptGenerationPage from "./components/script/ScriptGenerationPage";
import StoryboardPage from "./components/storyboard/StoryboardPage";
import type { BrandProfile, BrandProfileCreate } from "./types/brand";
import type { VideoIdea } from "./types/idea";

type View = "home" | "brand-create" | "brand-edit" | "brand-settings" | "ideation" | "script-generation" | "storyboard";

function App() {
  const [backendStatus, setBackendStatus] = useState<string>("connecting...");
  const [view, setView] = useState<View>("home");
  const [brands, setBrands] = useState<BrandProfile[]>([]);
  const [selectedBrand, setSelectedBrand] = useState<BrandProfile | null>(null);
  const [editingBrand, setEditingBrand] = useState<BrandProfile | null>(null);
  const [settingsBrand, setSettingsBrand] = useState<BrandProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [selectedIdea, setSelectedIdea] = useState<VideoIdea | null>(null);
  const [storyboardScriptId, setStoryboardScriptId] = useState<string | null>(null);

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

  const openSettings = (brand: BrandProfile) => {
    setSettingsBrand(brand);
    setView("brand-settings");
  };

  const handleSettingsUpdate = async (data: BrandProfileCreate) => {
    if (!settingsBrand) return;
    const res = await api.put(`/api/brands/${settingsBrand.id}`, data);
    if (res.ok) {
      await loadBrands();
      const updated = res.data as BrandProfile;
      setSettingsBrand(updated);
      if (selectedBrand?.id === updated.id) setSelectedBrand(updated);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col">
      {/* Top bar */}
      <header className="border-b border-neutral-800 px-6 py-4 flex items-center justify-between">
        <button
          onClick={() => {
            setView("home");
            setEditingBrand(null);
          }}
          className="text-xl font-semibold tracking-tight hover:text-violet-400 transition-colors"
        >
          YouTube AI Machine
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
      <main className={`flex-1 w-full ${view === "storyboard" || view === "brand-create" || view === "brand-edit" || view === "brand-settings" ? "" : "px-6 py-8 max-w-4xl mx-auto"}`}>
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

        {view === "brand-settings" && settingsBrand && (
          <BrandSettings
            brand={settingsBrand}
            onUpdate={handleSettingsUpdate}
            onBack={() => {
              setSettingsBrand(null);
              setView("home");
            }}
          />
        )}

        {view === "ideation" && selectedBrand && (
          <IdeationPage
            brand={selectedBrand}
            onUseIdea={(idea) => {
              setSelectedIdea(idea);
              setView("script-generation");
            }}
          />
        )}

        {view === "script-generation" && selectedBrand && selectedIdea && (
          <ScriptGenerationPage
            brand={selectedBrand}
            idea={selectedIdea}
            onBack={() => setView("ideation")}
            onContinue={(scriptId) => {
              setStoryboardScriptId(scriptId);
              setView("storyboard");
            }}
          />
        )}

        {view === "storyboard" && storyboardScriptId && (
          <StoryboardPage
            scriptId={storyboardScriptId}
            onBack={() => setView("script-generation")}
          />
        )}

        {view === "home" && (
          <div className="space-y-8">
            <BrandList
              brands={brands}
              selectedId={selectedBrand?.id}
              onSelect={setSelectedBrand}
              onEdit={startEdit}
              onDelete={handleDelete}
              onSettings={openSettings}
              onCreate={() => setView("brand-create")}
            />

            {/* Prompt area when a brand is selected */}
            {selectedBrand && (
              <div className="border-t border-neutral-800 pt-8 text-center space-y-4">
                <h2 className="text-3xl font-bold tracking-tight">
                  Ready to create
                </h2>
                <p className="text-neutral-400 text-lg max-w-md mx-auto">
                  Brand <span className="text-violet-400">{selectedBrand.name}</span>{" "}
                  is selected. Start your next video.
                </p>
                <button
                  onClick={() => setView("ideation")}
                  className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
                >
                  New Video
                </button>
              </div>
            )}

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

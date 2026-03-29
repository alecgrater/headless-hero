import { useEffect, useState } from "react";
import api from "../../api";
import { showToast } from "../ToastContainer";

interface KeyInfo {
  configured: boolean;
  masked: string;
  source: "db" | "env" | "none";
}

const IMAGE_PROVIDERS = [
  { value: "google", label: "Google Gemini" },
  { value: "replicate", label: "Replicate (Flux)" },
] as const;

export default function GeneralSection() {
  const [downloadsDir, setDownloadsDir] = useState("");
  const [imageProvider, setImageProvider] = useState("google");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [originalDownloads, setOriginalDownloads] = useState("");
  const [originalProvider, setOriginalProvider] = useState("google");

  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, KeyInfo>;
        const dlVal = data.DOWNLOADS_DIR?.masked ?? "";
        setDownloadsDir(dlVal);
        setOriginalDownloads(dlVal);
        const provVal = data.IMAGE_PROVIDER?.masked || "google";
        setImageProvider(provVal);
        setOriginalProvider(provVal);
      }
      setLoading(false);
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const res = await api.put("/api/settings/keys", {
      DOWNLOADS_DIR: downloadsDir.trim(),
      IMAGE_PROVIDER: imageProvider,
    });
    setSaving(false);

    if (res.ok) {
      showToast("Settings saved", "success");
      setOriginalDownloads(downloadsDir.trim());
      setOriginalProvider(imageProvider);
    }
  };

  const hasChanges =
    downloadsDir.trim() !== originalDownloads ||
    imageProvider !== originalProvider;

  return (
    <div className="px-8 py-8 max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">General</h2>
          <p className="text-neutral-400 text-sm mt-1">
            App-wide preferences.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {loading ? (
        <div className="text-neutral-500 text-sm">Loading...</div>
      ) : (
        <div className="space-y-6">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-2">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">Downloads Directory</h3>
              <p className="text-xs text-neutral-500">
                Rendered videos, audio, and thumbnails are copied here for easy access.
              </p>
            </div>
            <input
              type="text"
              value={downloadsDir}
              onChange={(e) => setDownloadsDir(e.target.value)}
              placeholder="~/Downloads"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 transition-colors font-mono"
            />
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-2">
            <div>
              <h3 className="text-sm font-medium text-neutral-100">Image Provider</h3>
              <p className="text-xs text-neutral-500">
                Choose which AI service generates scene images and thumbnails.
              </p>
            </div>
            <select
              value={imageProvider}
              onChange={(e) => setImageProvider(e.target.value)}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
            >
              {IMAGE_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import api from "../../api";
import { showToast } from "../ToastContainer";

interface KeyInfo {
  configured: boolean;
  masked: string;
  source: "db" | "env" | "none";
}

export default function GeneralSection() {
  const [downloadsDir, setDownloadsDir] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [originalValue, setOriginalValue] = useState("");

  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, KeyInfo>;
        const val = data.DOWNLOADS_DIR?.masked ?? "";
        setDownloadsDir(val);
        setOriginalValue(val);
      }
      setLoading(false);
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const res = await api.put("/api/settings/keys", {
      DOWNLOADS_DIR: downloadsDir.trim(),
    });
    setSaving(false);

    if (res.ok) {
      showToast("Settings saved", "success");
      setOriginalValue(downloadsDir.trim());
    }
  };

  const hasChanges = downloadsDir.trim() !== originalValue;

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
      )}
    </div>
  );
}

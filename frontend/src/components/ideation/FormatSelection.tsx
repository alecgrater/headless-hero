import { useState } from "react";

interface FormatSelectionProps {
  onSelect: (format: "youtube" | "shortform", platforms: string[]) => void;
  onBack: () => void;
}

const ALL_PLATFORMS = ["YouTube Shorts", "TikTok", "Instagram Reels"];

export default function FormatSelection({
  onSelect,
  onBack,
}: FormatSelectionProps) {
  const [selected, setSelected] = useState<"youtube" | "shortform" | null>(
    null,
  );
  const [platforms, setPlatforms] = useState<string[]>([...ALL_PLATFORMS]);

  const togglePlatform = (platform: string) => {
    setPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform],
    );
  };

  const canContinue =
    selected === "youtube" ||
    (selected === "shortform" && platforms.length > 0);

  return (
    <div className="space-y-6">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-neutral-400 hover:text-neutral-200 transition-colors"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15.75 19.5L8.25 12l7.5-7.5"
          />
        </svg>
        Back
      </button>

      <div>
        <h2 className="text-2xl font-bold mb-1">Choose a Format</h2>
        <p className="text-neutral-400 text-sm">
          Select the type of video you want to create.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* YouTube Video Card */}
        <button
          onClick={() => setSelected("youtube")}
          className={`rounded-xl border p-6 text-left transition-all ${
            selected === "youtube"
              ? "border-violet-500 bg-violet-500/10 ring-1 ring-violet-500/50"
              : "border-neutral-800 bg-neutral-900 hover:border-neutral-700 hover:bg-neutral-800/60"
          }`}
        >
          <div className="flex flex-col items-center gap-4">
            {/* 16:9 icon */}
            <svg
              className={`w-20 h-14 ${selected === "youtube" ? "text-violet-500" : "text-neutral-500"}`}
              viewBox="0 0 80 56"
              fill="none"
            >
              <rect
                x="2"
                y="2"
                width="76"
                height="52"
                rx="6"
                stroke="currentColor"
                strokeWidth="3"
              />
              <text
                x="40"
                y="33"
                textAnchor="middle"
                fill="currentColor"
                fontSize="14"
                fontWeight="600"
              >
                16:9
              </text>
            </svg>
            <div className="text-center">
              <h3
                className={`text-lg font-semibold ${selected === "youtube" ? "text-violet-400" : "text-neutral-200"}`}
              >
                YouTube Video
              </h3>
              <p className="text-sm text-neutral-400 mt-1">
                Long-form educational content, 5–15 minutes
              </p>
            </div>
          </div>
        </button>

        {/* Short-Form Video Card */}
        <button
          onClick={() => setSelected("shortform")}
          className={`rounded-xl border p-6 text-left transition-all ${
            selected === "shortform"
              ? "border-emerald-500 bg-emerald-500/10 ring-1 ring-emerald-500/50"
              : "border-neutral-800 bg-neutral-900 hover:border-neutral-700 hover:bg-neutral-800/60"
          }`}
        >
          <div className="flex flex-col items-center gap-4">
            {/* 9:16 icon */}
            <svg
              className={`w-10 h-14 ${selected === "shortform" ? "text-emerald-500" : "text-neutral-500"}`}
              viewBox="0 0 40 56"
              fill="none"
            >
              <rect
                x="2"
                y="2"
                width="36"
                height="52"
                rx="6"
                stroke="currentColor"
                strokeWidth="3"
              />
              <text
                x="20"
                y="33"
                textAnchor="middle"
                fill="currentColor"
                fontSize="10"
                fontWeight="600"
              >
                9:16
              </text>
            </svg>
            <div className="text-center">
              <h3
                className={`text-lg font-semibold ${selected === "shortform" ? "text-emerald-400" : "text-neutral-200"}`}
              >
                Short-Form Video
              </h3>
              <p className="text-sm text-neutral-400 mt-1">
                Shorts, TikTok, Reels — under 60 seconds
              </p>
            </div>
          </div>
        </button>
      </div>

      {/* Platform checkboxes for short-form */}
      {selected === "shortform" && (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 space-y-3">
          <p className="text-sm font-medium text-neutral-300">
            Target platforms
          </p>
          <div className="flex gap-4">
            {ALL_PLATFORMS.map((platform) => (
              <label
                key={platform}
                className="flex items-center gap-2 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={platforms.includes(platform)}
                  onChange={() => togglePlatform(platform)}
                  className="w-4 h-4 rounded border-neutral-600 bg-neutral-800 text-emerald-500 focus:ring-emerald-500/50 focus:ring-offset-0"
                />
                <span className="text-sm text-neutral-300">{platform}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Continue button */}
      <div className="flex justify-end">
        <button
          disabled={!canContinue}
          onClick={() => {
            if (selected === "youtube") {
              onSelect("youtube", []);
            } else if (selected === "shortform") {
              onSelect("shortform", platforms);
            }
          }}
          className={`px-6 py-2.5 rounded-lg font-medium text-sm transition-all ${
            canContinue
              ? selected === "youtube"
                ? "bg-violet-600 hover:bg-violet-500 text-white"
                : "bg-emerald-600 hover:bg-emerald-500 text-white"
              : "bg-neutral-800 text-neutral-500 cursor-not-allowed"
          }`}
        >
          Continue
        </button>
      </div>
    </div>
  );
}

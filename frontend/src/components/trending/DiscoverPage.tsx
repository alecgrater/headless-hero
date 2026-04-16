import { useState } from "react";
import type { VideoIdea } from "../../types/idea";
import TrendingTab from "./TrendingTab";
import ForYouTab from "./ForYouTab";

interface Props {
  onGenerateIdeas: (ideas: VideoIdea[], niche: string) => void;
}

export default function DiscoverPage({ onGenerateIdeas }: Props) {
  const [activeTab, setActiveTab] = useState<"trending" | "for-you">("trending");

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      {/* Shared animation keyframes */}
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* Tab switcher */}
      <div className="inline-flex items-center p-1 mb-8 bg-neutral-800/60 rounded-xl border border-neutral-700/40">
        <button
          onClick={() => setActiveTab("trending")}
          className={`flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
            activeTab === "trending"
              ? "bg-neutral-700/80 text-white shadow-sm"
              : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
          </svg>
          Trending
        </button>
        <button
          onClick={() => setActiveTab("for-you")}
          className={`flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
            activeTab === "for-you"
              ? "bg-neutral-700/80 text-white shadow-sm"
              : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
          </svg>
          For You
        </button>
      </div>

      {/* Both tabs rendered, toggled via hidden class to preserve state */}
      <div className={activeTab === "trending" ? "block" : "hidden"}>
        <TrendingTab onGenerateIdeas={onGenerateIdeas} />
      </div>
      <div className={activeTab === "for-you" ? "block" : "hidden"}>
        <ForYouTab onGenerateIdeas={onGenerateIdeas} />
      </div>
    </div>
  );
}

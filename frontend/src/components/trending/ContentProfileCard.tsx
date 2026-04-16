import { useState } from "react";
import type { ContentProfile } from "../../types/trending";

interface Props {
  profile: ContentProfile;
  loading: boolean;
  onRefresh: () => void;
}

export default function ContentProfileCard({ profile, loading, onRefresh }: Props) {
  const [expanded, setExpanded] = useState(false);

  const analyzedAgo = (() => {
    const diff = Date.now() - new Date(profile.analyzed_at).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  })();

  return (
    <div className="rounded-xl border border-neutral-700/60 bg-neutral-800/40 overflow-hidden">
      {/* Header — always visible, clickable to expand */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between gap-4 px-5 py-3.5 text-left hover:bg-neutral-800/60 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-violet-500/15 border border-violet-500/20 flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-violet-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
          </div>
          <div className="min-w-0">
            <span className="text-sm font-medium text-neutral-200">Your Content Profile</span>
            <span className="text-xs text-neutral-500 ml-2">
              Based on {profile.script_count} script{profile.script_count !== 1 ? "s" : ""}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {profile.is_stale && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-400 border border-amber-500/20">
              Stale
            </span>
          )}
          <svg
            className={`w-4 h-4 text-neutral-500 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-5 pb-4 pt-1 space-y-4 border-t border-neutral-700/40">
          {/* Two-column grid */}
          <div className="grid grid-cols-2 gap-4">
            {/* Topics */}
            <div>
              <h4 className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-2">
                Common Topics
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {profile.common_topics.map((topic) => (
                  <span
                    key={topic}
                    className="text-xs px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-300 border border-violet-500/15"
                  >
                    {topic}
                  </span>
                ))}
              </div>
            </div>

            {/* Audience */}
            <div>
              <h4 className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-2">
                Audience
              </h4>
              <p className="text-xs text-neutral-300 leading-relaxed">
                {profile.audience_profile}
              </p>
            </div>

            {/* Narration style */}
            <div>
              <h4 className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-2">
                Narration Style
              </h4>
              <p className="text-xs text-neutral-300 leading-relaxed">
                {profile.narration_style}
              </p>
            </div>

            {/* Visual approach */}
            <div>
              <h4 className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-2">
                Visual Approach
              </h4>
              <p className="text-xs text-neutral-300 leading-relaxed">
                {profile.visual_approach}
              </p>
            </div>
          </div>

          {/* Keywords */}
          {profile.typical_keywords.length > 0 && (
            <div>
              <h4 className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-2">
                Keywords
              </h4>
              <div className="flex flex-wrap gap-1">
                {profile.typical_keywords.map((kw) => (
                  <span
                    key={kw}
                    className="text-[11px] px-1.5 py-0.5 rounded bg-neutral-700/50 text-neutral-400"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-neutral-500">
              Analyzed {analyzedAgo} · ~{profile.avg_segment_count} segments/video
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRefresh();
              }}
              disabled={loading}
              className="text-[11px] text-violet-400 hover:text-violet-300 disabled:opacity-50 transition-colors"
            >
              {loading ? "Refreshing..." : "Refresh profile"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

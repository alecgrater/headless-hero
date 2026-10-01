import { useState } from "react";
import type { ScriptRating, ScriptRatingProblemCategory, ScriptRatingScores } from "../../types/script";

interface Props {
  rating: ScriptRating | null | undefined;
}

const SCORES: { key: keyof ScriptRatingScores; label: string; hint: string }[] = [
  { key: "flow", label: "Flow", hint: "Does each line follow from the one before when heard as one voiceover?" },
  { key: "clarity", label: "Clarity", hint: "Is every person, term, and idea introduced before it is used?" },
  { key: "human_sounding", label: "Sounds human", hint: "Free of formula lines, reused sentence patterns, and empty aphorisms?" },
  { key: "continuity", label: "Continuity", hint: "Do names, ages, numbers, and timeline stay consistent?" },
  { key: "format_fit", label: "Format fit", hint: "Does it keep the format's voice and rules (standalone segments, second person)?" },
];

const CATEGORY_LABELS: Record<ScriptRatingProblemCategory, string> = {
  continuity_errors: "Continuity",
  unintroduced_references: "Never introduced",
  bumpy_transitions: "Bumpy transition",
  ai_tells: "Sounds machine-written",
  read_aloud_problems: "Hard to read aloud",
  standalone_violations: "Breaks standalone Short",
  voice_violations: "Off-voice",
};

const COLLAPSED_PROBLEM_COUNT = 6;

function scoreColor(score: number) {
  if (score >= 8) return "text-emerald-400";
  if (score >= 6) return "text-amber-400";
  return "text-red-400";
}

export default function ScriptRatingCard({ rating }: Props) {
  const [showAll, setShowAll] = useState(false);
  if (!rating) return null;

  const majors = rating.problems.filter((problem) => problem.severity === "major").length;
  const visible = showAll ? rating.problems : rating.problems.slice(0, COLLAPSED_PROBLEM_COUNT);

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-5 py-5">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-neutral-100">Script Rating</h3>
          <p className="mt-1 text-sm text-neutral-400">
            A strict editor's read of the narration as one continuous voiceover. 10 = a strong human writer would ship
            it, 5 = noticeably flawed.
          </p>
        </div>
        <div className="text-right">
          <span className={`block text-4xl font-bold tabular-nums leading-none ${scoreColor(rating.overall)}`}>
            {rating.overall.toFixed(1)}
          </span>
          <span className="mt-1 block text-sm text-neutral-500">/ 10</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {SCORES.map(({ key, label, hint }) => (
          <div
            key={key}
            title={hint}
            className="flex items-center justify-between gap-2 rounded-md border border-neutral-800 bg-neutral-950/50 px-3 py-2 text-sm transition-colors hover:border-neutral-700"
          >
            <span className="truncate text-neutral-400">{label}</span>
            <span className={`font-semibold tabular-nums ${scoreColor(rating.scores[key])}`}>{rating.scores[key]}</span>
          </div>
        ))}
      </div>

      {rating.worst_problem && (
        <p className="mt-4 text-sm leading-6 text-neutral-300">
          <span className="font-medium text-neutral-100">Biggest issue: </span>
          {rating.worst_problem}
        </p>
      )}

      <div className="mt-5">
        <h4 className="text-sm font-semibold text-neutral-100">
          {rating.problems.length === 0
            ? "No concrete problems found"
            : `${rating.problems.length} problem${rating.problems.length === 1 ? "" : "s"}${majors ? ` · ${majors} major` : ""}`}
        </h4>
        {rating.problems.length > 0 && (
          <ul className="mt-3 divide-y divide-neutral-800 rounded-lg border border-neutral-800 bg-neutral-950/50">
            {visible.map((problem, index) => (
              <li key={`${problem.scene}-${index}`} className="space-y-1 px-4 py-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span
                    className={`rounded px-1.5 py-0.5 font-semibold uppercase tracking-wide ${
                      problem.severity === "major" ? "bg-red-500/15 text-red-300" : "bg-neutral-800 text-neutral-400"
                    }`}
                  >
                    {problem.severity}
                  </span>
                  <span className="text-neutral-300">{CATEGORY_LABELS[problem.category] ?? problem.category}</span>
                  {problem.scene && <span className="font-mono text-neutral-500">{problem.scene}</span>}
                </div>
                <p className="text-sm italic text-neutral-200">“{problem.quote}”</p>
                {problem.problem && <p className="text-sm text-neutral-400">{problem.problem}</p>}
              </li>
            ))}
          </ul>
        )}
        {rating.problems.length > COLLAPSED_PROBLEM_COUNT && (
          <button
            type="button"
            onClick={() => setShowAll((value) => !value)}
            className="mt-3 text-sm font-medium text-violet-300 transition-colors hover:text-violet-200"
          >
            {showAll ? "Show fewer" : `Show all ${rating.problems.length}`}
          </button>
        )}
      </div>
    </div>
  );
}

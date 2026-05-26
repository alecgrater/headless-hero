import type { ScriptRating, ScriptRatingCategory } from "../../types/script";

interface Props {
  rating: ScriptRating | null | undefined;
}

const CATEGORIES: {
  key: keyof Pick<ScriptRating, "viewer_retention" | "narrative_quality" | "script_craft" | "audience_fit" | "seo_alignment">;
  label: string;
  weight: string;
  color: string;
  criteria: { key: string; label: string }[];
}[] = [
  {
    key: "viewer_retention",
    label: "Viewer Retention",
    weight: "30%",
    color: "bg-violet-500",
    criteria: [
      { key: "hook_strength", label: "hook" },
      { key: "curiosity_gaps", label: "curiosity" },
      { key: "pacing_variance", label: "pacing" },
    ],
  },
  {
    key: "narrative_quality",
    label: "Narrative Quality",
    weight: "15%",
    color: "bg-sky-500",
    criteria: [
      { key: "coherence", label: "coherence" },
      { key: "throughline", label: "throughline" },
    ],
  },
  {
    key: "script_craft",
    label: "Script Craft",
    weight: "25%",
    color: "bg-emerald-500",
    criteria: [
      { key: "sentence_variety", label: "variety" },
      { key: "specificity", label: "specificity" },
      { key: "redundancy", label: "redundancy" },
      { key: "word_economy", label: "economy" },
    ],
  },
  {
    key: "audience_fit",
    label: "Audience Fit",
    weight: "20%",
    color: "bg-amber-500",
    criteria: [
      { key: "assumed_knowledge_level", label: "knowledge" },
      { key: "relatability", label: "relatability" },
      { key: "tone_consistency", label: "tone" },
      { key: "emotional_range", label: "emotion" },
    ],
  },
  {
    key: "seo_alignment",
    label: "SEO Alignment",
    weight: "10%",
    color: "bg-rose-500",
    criteria: [
      { key: "title_hook_match", label: "title" },
      { key: "search_intent_match", label: "intent" },
      { key: "rewatch_value", label: "rewatch" },
    ],
  },
];

function scoreColor(score: number) {
  if (score >= 8) return "text-emerald-400";
  if (score >= 6) return "text-amber-400";
  return "text-red-400";
}

function CategoryRow({
  category,
  label,
  weight,
  color,
  criteria,
}: {
  category: ScriptRatingCategory;
  label: string;
  weight: string;
  color: string;
  criteria: { key: string; label: string }[];
}) {
  return (
    <div className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-950/50 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${color}`} />
            <h4 className="truncate text-sm font-medium text-neutral-200">{label}</h4>
          </div>
          <p className="mt-0.5 text-[11px] text-neutral-600">Weight {weight}</p>
        </div>
        <span className={`text-lg font-semibold tabular-nums ${scoreColor(category.average)}`}>
          {category.average.toFixed(1)}
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {criteria.map(({ key, label: criterionLabel }) => {
          const score = category.criteria[key]?.score;
          if (score == null) return null;
          return (
            <span
              key={key}
              className="rounded border border-neutral-800 bg-neutral-900 px-1.5 py-0.5 text-[11px] text-neutral-400"
            >
              {criterionLabel}: <span className="font-medium text-neutral-200">{score}</span>
            </span>
          );
        })}
      </div>

      {category.explanation && (
        <p className="text-xs leading-5 text-neutral-500">{category.explanation}</p>
      )}
    </div>
  );
}

export default function ScriptRatingCard({ rating }: Props) {
  if (!rating) return null;

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-5 py-4">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-neutral-200">
            Script Rating
          </h3>
          <p className="mt-1 text-xs text-neutral-500">
            Full-script score against top educational YouTube standards.
          </p>
        </div>
        <div className="text-right">
          <span className={`block text-3xl font-bold tabular-nums ${scoreColor(rating.overall)}`}>
            {rating.overall.toFixed(1)}
          </span>
          <span className="text-xs text-neutral-600">/ 10</span>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {CATEGORIES.map((item) => (
          <CategoryRow
            key={item.key}
            category={rating[item.key]}
            label={item.label}
            weight={item.weight}
            color={item.color}
            criteria={item.criteria}
          />
        ))}
      </div>
    </div>
  );
}

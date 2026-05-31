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
  const sortedCriteria = criteria
    .map(({ key, label: criterionLabel }) => ({
      key,
      label: criterionLabel,
      score: category.criteria[key]?.score,
    }))
    .filter((item) => item.score != null);

  return (
    <div className="space-y-3 rounded-lg border border-neutral-800 bg-neutral-950/50 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${color}`} />
            <h4 className="text-base font-semibold leading-snug text-neutral-100">{label}</h4>
          </div>
          <p className="mt-1 text-xs text-neutral-500">Weight {weight}</p>
        </div>
        <span className={`text-2xl font-bold tabular-nums leading-none ${scoreColor(category.average)}`}>
          {category.average.toFixed(1)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {sortedCriteria.map(({ key, label: criterionLabel, score }) => (
          <div
            key={key}
            className="flex items-center justify-between gap-2 rounded-md border border-neutral-800 bg-neutral-900/80 px-2.5 py-1.5 text-xs"
          >
            <span className="truncate text-neutral-400">{criterionLabel}</span>
            <span className="font-semibold tabular-nums text-neutral-100">{score}</span>
          </div>
        ))}
      </div>

      {category.explanation && (
        <p className="text-sm leading-6 text-neutral-300">{category.explanation}</p>
      )}
    </div>
  );
}

export default function ScriptRatingCard({ rating }: Props) {
  if (!rating) return null;

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-5 py-5">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-neutral-100">
            Script Rating
          </h3>
          <p className="mt-1 text-sm text-neutral-400">
            Full-script score against top educational YouTube standards.
          </p>
        </div>
        <div className="text-right">
          <span className={`block text-4xl font-bold tabular-nums leading-none ${scoreColor(rating.overall)}`}>
            {rating.overall.toFixed(1)}
          </span>
          <span className="mt-1 block text-sm text-neutral-500">/ 10</span>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
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

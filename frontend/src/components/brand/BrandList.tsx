import type { BrandProfile } from "../../types/brand";

interface Props {
  brands: BrandProfile[];
  selectedId?: string;
  onSelect: (brand: BrandProfile) => void;
  onEdit: (brand: BrandProfile) => void;
  onDelete: (brand: BrandProfile) => void;
  onSettings: (brand: BrandProfile) => void;
  onCreate: () => void;
}

export default function BrandList({
  brands,
  selectedId,
  onSelect,
  onEdit,
  onDelete,
  onSettings,
  onCreate,
}: Props) {
  if (brands.length === 0) {
    return (
      <div className="text-center py-12 space-y-3">
        <p className="text-neutral-400">No brand profiles yet.</p>
        <button
          onClick={onCreate}
          className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
        >
          Create Your First Brand
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-neutral-200">Your Brands</h3>
        <button
          onClick={onCreate}
          className="text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
        >
          + New Brand
        </button>
      </div>

      <ul className="space-y-2">
        {brands.map((brand) => (
          <li
            key={brand.id}
            onClick={() => onSelect(brand)}
            className={`rounded-lg border p-4 cursor-pointer transition-colors ${
              selectedId === brand.id
                ? "border-violet-500 bg-violet-500/10"
                : "border-neutral-700 bg-neutral-800/50 hover:border-neutral-600"
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-neutral-100 truncate">{brand.name}</p>
                {brand.art_style && (
                  <p className="text-sm text-neutral-400 mt-1 line-clamp-2">
                    {brand.art_style}
                  </p>
                )}
                {brand.color_palette && (
                  <div className="flex gap-1.5 mt-2">
                    {brand.color_palette.split(",").map((hex, i) => (
                      <span
                        key={i}
                        className="w-5 h-5 rounded-sm border border-neutral-600"
                        style={{ backgroundColor: hex.trim() }}
                        title={hex.trim()}
                      />
                    ))}
                  </div>
                )}
              </div>

              <div className="flex gap-1 ml-3 shrink-0">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onSettings(brand);
                  }}
                  className="text-xs px-2 py-1 rounded bg-neutral-700 hover:bg-neutral-600 text-neutral-300 transition-colors"
                  title="Voice & platform settings"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(brand);
                  }}
                  className="text-xs px-2 py-1 rounded bg-neutral-700 hover:bg-neutral-600 text-neutral-300 transition-colors"
                >
                  Edit
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(brand);
                  }}
                  className="text-xs px-2 py-1 rounded bg-neutral-700 hover:bg-red-600 text-neutral-300 transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
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

/** Parse comma-separated hex colors from the brand's color_palette field */
function parseColors(palette: string): string[] {
  if (!palette) return [];
  return palette
    .split(",")
    .map((c) => c.trim())
    .filter((c) => /^#?[0-9a-fA-F]{3,8}$/.test(c))
    .map((c) => (c.startsWith("#") ? c : `#${c}`));
}

/** Build a cinematic diagonal gradient from the brand's palette */
function buildGradient(colors: string[]): string {
  if (colors.length === 0) return "linear-gradient(135deg, #1a1a2e 0%, #0a0a14 100%)";
  if (colors.length === 1) return `linear-gradient(135deg, ${colors[0]}cc 0%, ${colors[0]}33 100%)`;
  const stops = colors.map((c, i) => `${c}bb ${Math.round((i / (colors.length - 1)) * 100)}%`);
  return `linear-gradient(135deg, ${stops.join(", ")})`;
}

/** Extract style keywords as tag pills from art_style text */
function extractTags(artStyle: string): string[] {
  if (!artStyle) return [];
  // Split on commas, semicolons, "and", or common separators, then clean up
  const raw = artStyle
    .split(/[,;·•|]|\band\b/i)
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && s.length < 30);
  // Take up to 4 tags, capitalize first letter
  return raw.slice(0, 4).map((t) => t.charAt(0).toUpperCase() + t.slice(1));
}

/** Format a relative time string from ISO date */
function timeAgo(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

/** Check if a brand is incomplete / in "draft" state */
function isDraft(brand: BrandProfile): boolean {
  return !brand.art_style && !brand.color_palette;
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
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    }
    if (menuOpenId) {
      document.addEventListener("mousedown", handleClick);
      return () => document.removeEventListener("mousedown", handleClick);
    }
  }, [menuOpenId]);

  if (brands.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center py-20 space-y-5"
        style={{ animation: "brandFadeUp 500ms ease both" }}
      >
        <div
          className="w-20 h-20 rounded-2xl flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, #7c3aed44 0%, #7c3aed11 100%)",
            border: "1px solid rgba(124, 58, 237, 0.2)",
          }}
        >
          <svg className="w-9 h-9 text-violet-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        </div>
        <div className="text-center space-y-2">
          <p className="text-neutral-300 text-[15px] font-medium" style={{ fontFamily: "'Sora', sans-serif" }}>
            No brands yet
          </p>
          <p className="text-neutral-500 text-[13px] max-w-[260px]">
            Create a brand profile to define your channel's visual identity, voice, and style.
          </p>
        </div>
        <button
          onClick={onCreate}
          className="group relative px-5 py-2.5 rounded-lg text-[13px] font-semibold text-violet-300 transition-all duration-300"
          style={{
            fontFamily: "'Sora', sans-serif",
            background: "rgba(124, 58, 237, 0.12)",
            border: "1px solid rgba(124, 58, 237, 0.3)",
            boxShadow: "0 0 0 0 rgba(124, 58, 237, 0)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = "0 0 20px 0 rgba(124, 58, 237, 0.25)";
            e.currentTarget.style.borderColor = "rgba(124, 58, 237, 0.6)";
            e.currentTarget.style.background = "rgba(124, 58, 237, 0.18)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = "0 0 0 0 rgba(124, 58, 237, 0)";
            e.currentTarget.style.borderColor = "rgba(124, 58, 237, 0.3)";
            e.currentTarget.style.background = "rgba(124, 58, 237, 0.12)";
          }}
        >
          Create Your First Brand
        </button>

        <style>{`
          @keyframes brandFadeUp {
            from { opacity: 0; transform: translateY(12px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3
          className="text-[15px] font-semibold text-neutral-300 tracking-wide uppercase"
          style={{ fontFamily: "'Sora', sans-serif", letterSpacing: "0.08em" }}
        >
          Your Brands
        </h3>
        <button
          onClick={onCreate}
          className="group relative flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[12px] font-semibold text-violet-300 transition-all duration-300"
          style={{
            fontFamily: "'Sora', sans-serif",
            background: "rgba(124, 58, 237, 0.10)",
            border: "1px solid rgba(124, 58, 237, 0.25)",
            boxShadow: "0 0 0 0 rgba(124, 58, 237, 0)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = "0 0 16px 0 rgba(124, 58, 237, 0.2)";
            e.currentTarget.style.borderColor = "rgba(124, 58, 237, 0.5)";
            e.currentTarget.style.background = "rgba(124, 58, 237, 0.16)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = "0 0 0 0 rgba(124, 58, 237, 0)";
            e.currentTarget.style.borderColor = "rgba(124, 58, 237, 0.25)";
            e.currentTarget.style.background = "rgba(124, 58, 237, 0.10)";
          }}
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Brand
        </button>
      </div>

      {/* Brand list */}
      <ul className="space-y-1.5">
        {brands.map((brand, index) => {
          const isSelected = selectedId === brand.id;
          const isHovered = hoveredId === brand.id;
          const draft = isDraft(brand);
          const colors = parseColors(brand.color_palette);
          const gradient = buildGradient(colors);
          const tags = extractTags(brand.art_style);
          const edited = timeAgo(brand.updated_at);

          return (
            <li
              key={brand.id}
              onClick={() => onSelect(brand)}
              onMouseEnter={() => setHoveredId(brand.id)}
              onMouseLeave={() => setHoveredId(null)}
              className="relative flex cursor-pointer rounded-lg transition-all duration-200"
              style={{
                height: "100px",
                background: isSelected
                  ? "rgba(124, 58, 237, 0.06)"
                  : isHovered
                    ? "rgba(255, 255, 255, 0.04)"
                    : "rgba(255, 255, 255, 0.02)",
                borderLeft: isSelected
                  ? `3px solid ${colors[0] || "#7c3aed"}`
                  : "3px solid transparent",
                animation: `brandFadeUp 400ms ease both`,
                animationDelay: `${index * 60}ms`,
              }}
            >
              {/* Left preview panel */}
              <div
                className="relative shrink-0 overflow-hidden rounded-l-lg transition-all duration-300"
                style={{
                  width: "120px",
                  background: draft
                    ? "repeating-linear-gradient(45deg, #1a1a2e, #1a1a2e 8px, #12121e 8px, #12121e 16px)"
                    : gradient,
                  filter: isHovered ? "brightness(1.2)" : "brightness(1)",
                }}
              >
                {/* Noise overlay for depth */}
                {!draft && (
                  <div
                    className="absolute inset-0"
                    style={{
                      background: "radial-gradient(ellipse at 30% 20%, rgba(255,255,255,0.08) 0%, transparent 60%)",
                    }}
                  />
                )}

                {/* Checkmark badge for selected */}
                {isSelected && (
                  <div
                    className="absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center"
                    style={{
                      background: colors[0] || "#7c3aed",
                      boxShadow: `0 0 8px ${colors[0] || "#7c3aed"}88`,
                    }}
                  >
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  </div>
                )}

                {/* Draft indicator */}
                {draft && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span
                      className="text-[10px] font-medium text-neutral-500 uppercase tracking-wider"
                      style={{ fontFamily: "'Sora', sans-serif" }}
                    >
                      Draft
                    </span>
                  </div>
                )}
              </div>

              {/* Content area */}
              <div className="flex-1 min-w-0 px-4 py-3 flex flex-col justify-center">
                {/* Brand name */}
                <p
                  className="text-[15px] font-bold text-neutral-100 truncate leading-tight"
                  style={{ fontFamily: "'Sora', sans-serif" }}
                >
                  {brand.name}
                </p>

                {/* Description or draft prompt */}
                {draft ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onEdit(brand);
                    }}
                    className="text-[12px] text-violet-400 hover:text-violet-300 mt-1 transition-colors inline-flex items-center gap-1"
                    style={{ fontFamily: "'Sora', sans-serif" }}
                  >
                    Finish Setup
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                    </svg>
                  </button>
                ) : (
                  <>
                    {brand.art_style && (
                      <p className="text-[12px] text-neutral-500 mt-0.5 truncate leading-snug">
                        {brand.art_style}
                      </p>
                    )}
                  </>
                )}

                {/* Tags + stats row */}
                <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                  {tags.map((tag, i) => (
                    <span
                      key={i}
                      className="px-1.5 py-0.5 rounded text-[10px] text-neutral-400"
                      style={{
                        background: "rgba(255, 255, 255, 0.06)",
                        fontFamily: "'Sora', sans-serif",
                        letterSpacing: "0.02em",
                      }}
                    >
                      {tag}
                    </span>
                  ))}
                  {tags.length > 0 && edited && (
                    <span className="text-neutral-700 text-[10px] mx-0.5">·</span>
                  )}
                  {edited && (
                    <span
                      className="text-[10px] text-neutral-600"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      edited {edited}
                    </span>
                  )}
                </div>
              </div>

              {/* Overflow menu (appears on hover) */}
              <div
                className="shrink-0 flex items-center pr-3 transition-opacity duration-200"
                style={{ opacity: isHovered || menuOpenId === brand.id ? 1 : 0 }}
              >
                <div className="relative" ref={menuOpenId === brand.id ? menuRef : undefined}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuOpenId(menuOpenId === brand.id ? null : brand.id);
                    }}
                    className="w-7 h-7 rounded-md flex items-center justify-center text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.06] transition-colors"
                  >
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                    </svg>
                  </button>

                  {/* Dropdown menu */}
                  {menuOpenId === brand.id && (
                    <div
                      className="absolute right-0 top-full mt-1 w-40 rounded-lg py-1 z-50"
                      style={{
                        background: "#1c1c28",
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.5)",
                      }}
                    >
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setMenuOpenId(null);
                          onEdit(brand);
                        }}
                        className="w-full text-left px-3 py-1.5 text-[12px] text-neutral-300 hover:bg-white/[0.06] transition-colors flex items-center gap-2"
                      >
                        <svg className="w-3.5 h-3.5 text-neutral-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487z" />
                        </svg>
                        Edit Brand
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setMenuOpenId(null);
                          onSettings(brand);
                        }}
                        className="w-full text-left px-3 py-1.5 text-[12px] text-neutral-300 hover:bg-white/[0.06] transition-colors flex items-center gap-2"
                      >
                        <svg className="w-3.5 h-3.5 text-neutral-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        Settings
                      </button>
                      <div className="my-1 border-t border-white/[0.06]" />
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setMenuOpenId(null);
                          onDelete(brand);
                        }}
                        className="w-full text-left px-3 py-1.5 text-[12px] text-red-400 hover:bg-red-500/10 transition-colors flex items-center gap-2"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                        </svg>
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <style>{`
        @keyframes brandFadeUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

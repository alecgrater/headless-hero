import type { VideoFormat } from "../../../types/format";
import { VISUAL_MODE_CATALOG } from "../visual-modes/catalog";

export interface ModeChip {
  id: string;
  label: string;
  hasDetail: boolean; // true if the Visual Modes reference page has an entry to link to
}

const CATALOG_BY_ID = new Map(VISUAL_MODE_CATALOG.map((e) => [e.id as string, e]));

function humanize(id: string): string {
  return id
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function toChip(id: string): ModeChip {
  const entry = CATALOG_BY_ID.get(id);
  return { id, label: entry ? entry.label : humanize(id), hasDetail: Boolean(entry) };
}

/** Ordered union of every format's supported modes (first-appearance order). */
export function allVisualModes(formats: VideoFormat[]): string[] {
  const seen: string[] = [];
  for (const fmt of formats) {
    for (const mode of fmt.supported_visual_modes) {
      if (!seen.includes(mode)) seen.push(mode);
    }
  }
  return seen;
}

export function modeChipsForFormat(
  format: VideoFormat,
  universe: string[],
): { supported: ModeChip[]; disabled: ModeChip[] } {
  const supportedSet = new Set(format.supported_visual_modes);
  const supported: ModeChip[] = [];
  const disabled: ModeChip[] = [];
  for (const id of universe) {
    (supportedSet.has(id) ? supported : disabled).push(toChip(id));
  }
  return { supported, disabled };
}

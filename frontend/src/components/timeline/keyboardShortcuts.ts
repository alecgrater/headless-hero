export interface ShortcutActions {
  selectPrevScene: () => void;
  selectNextScene: () => void;
  undo: () => void;
  save: () => void;
  generateImage: () => void;
  generateAllImages: () => void;
  openUpload: () => void;
  toggleAudioPreview: () => void;
  deleteScene: () => void;
  splitAtPlayhead: () => void;
  placeMarker: () => void;
  nudgeBack: (large: boolean) => void;
  nudgeForward: (large: boolean) => void;
  selectLane: (lane: number) => void;
  deselectMicroTimeline: () => void;
  deleteMarker: () => void;
}

export interface Shortcut {
  key: string;
  label: string;
  shortcutDisplay: string;
}

export interface ShortcutGroup {
  label: string;
  shortcuts: Shortcut[];
}

export const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    label: "Timeline Navigation",
    shortcuts: [
      { key: "ArrowUp", label: "Select previous scene", shortcutDisplay: "\u2191" },
      { key: "ArrowDown", label: "Select next scene", shortcutDisplay: "\u2193" },
      { key: "Space", label: "Play/pause audio", shortcutDisplay: "Space" },
    ],
  },
  {
    label: "Scene Editing",
    shortcuts: [
      { key: "s", label: "Split scene at playhead", shortcutDisplay: "S" },
      { key: "Delete", label: "Delete scene or marker", shortcutDisplay: "Delete" },
      { key: "g", label: "Generate image for scene", shortcutDisplay: "\u2318G" },
      { key: "G", label: "Generate all images", shortcutDisplay: "\u2318\u21E7G" },
      { key: "z", label: "Undo", shortcutDisplay: "\u2318Z" },
      { key: "s_save", label: "Save", shortcutDisplay: "\u2318S" },
    ],
  },
  {
    label: "Micro-Timeline",
    shortcuts: [
      { key: "m", label: "Place marker at playhead", shortcutDisplay: "M" },
      { key: "[", label: "Nudge -1 frame", shortcutDisplay: "[" },
      { key: "]", label: "Nudge +1 frame", shortcutDisplay: "]" },
      { key: "shift_[", label: "Nudge -10 frames", shortcutDisplay: "\u21E7[" },
      { key: "shift_]", label: "Nudge +10 frames", shortcutDisplay: "\u21E7]" },
      { key: "1-4", label: "Select lane (Images/FX/Eli/In\u00B7Out)", shortcutDisplay: "1-4" },
      { key: "Escape", label: "Deselect marker/lane", shortcutDisplay: "Esc" },
    ],
  },
  {
    label: "Global",
    shortcuts: [
      { key: "e", label: "Open upload suite", shortcutDisplay: "\u2318E" },
      { key: "?", label: "Toggle keyboard shortcuts", shortcutDisplay: "? / \u2318/" },
    ],
  },
];

export const SHORTCUTS: Shortcut[] = SHORTCUT_GROUPS.flatMap((group) => group.shortcuts);

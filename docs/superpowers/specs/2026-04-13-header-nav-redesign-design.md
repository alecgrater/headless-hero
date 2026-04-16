# Header Navigation Redesign

## Context

The current navigation between Projects, Discover, and Settings uses small icon-only buttons in the top-right corner of the header. There's no visual indication of which view is active, and the icons are easy to miss. This redesign replaces those buttons with a proper left-aligned tab bar with icons, labels, and active state styling.

## Design

### Layout

Left-aligned `<nav>` element placed after the "Headless Hero" logo in the header. The right side of the header retains save controls (timeline view only) and the backend status indicator.

```
[⚡ Headless Hero]  [📁 Projects] [🌐 Discover] [⚙️ Settings]        [Save controls] [● Connected]
```

### Nav Items

| Tab | Icon | Label | Maps to views |
|-----|------|-------|---------------|
| Projects | 2x2 grid squares icon (Heroicons `squares-2x2`, new SVG) | Projects | `project-dashboard`, `ideation`, `script-generation`, `timeline` |
| Discover | Globe icon (existing) | Discover | `discover` |
| Settings | Gear icon (existing) | Settings | `settings` |

Projects tab is active for all project sub-views (ideation, script gen, timeline) since those are part of the project workflow.

### Styling

- **Active tab:** `bg-violet-500/15 text-violet-300 font-semibold rounded-lg` — subtle violet fill
- **Inactive tab:** `text-neutral-500` — no background
- **Hover (inactive):** `hover:bg-neutral-800 hover:text-neutral-200 transition-colors`
- **Icons:** `w-4 h-4` inline with label text, `gap-2` between icon and label
- **Tab padding:** `px-3 py-1.5`
- **Gap between tabs:** `gap-1`
- **Gap between logo and nav:** `gap-6`

### What Changes

**File:** `frontend/src/App.tsx`

1. Remove the standalone Discover icon button (lines 123-131) and Settings icon button (lines 132-141) from the right-side `<div>`
2. Add a `<nav className="flex items-center gap-1">` element after the logo button, inside a flex container with `gap-6`
3. Each nav item is a `<button>` with icon SVG + text label
4. Active state computed by checking `view` against each tab's associated views
5. Save controls and backend status remain in the right-side div, unchanged

### No New Files

Everything fits in `App.tsx`. No new components, hooks, or utility files needed.

## Verification

1. Run `npm run dev:frontend` and open in browser
2. Confirm three tabs appear after the logo: Projects, Discover, Settings
3. Click each tab — verify the correct view renders and the active state (violet fill) moves to the clicked tab
4. Navigate into a project (ideation → script gen → timeline) — verify Projects tab stays active throughout
5. Verify save controls still appear on the timeline view
6. Verify backend status indicator remains on the far right
7. Verify hover states on inactive tabs (gray background, lighter text)

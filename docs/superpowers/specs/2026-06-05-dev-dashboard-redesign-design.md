# Dev Dashboard Visual Parity Redesign

## Context

The dev dashboard began as a standalone backend-served browser tool at `/dev/`, but it is now embedded inside the Electron app as the Dev Dashboard tab. Its current UI still reads like an external diagnostics page: standalone header, top tab bar, monospace body typography, CDN Tailwind defaults, and heavier utility styling. The app around it now uses a quieter dark neutral interface with sticky headers, left navigation, compact controls, and restrained bordered surfaces.

This redesign keeps the dashboard backend-served through the existing iframe and preserves its current functionality. The goal is visual parity with the rest of Headless Hero, not a React migration.

## Goals

- Make the dashboard feel like a native Headless Hero app tab while keeping `/dev/` as the source.
- Preserve every existing dashboard feature: logs, telemetry, jobs, API tester, database browser, usage tracker, and file/docs browser.
- Use the app's established visual language: `bg-neutral-950`, `border-neutral-800`, `text-neutral-100/400`, violet focus and active states, compact controls, and restrained cards.
- Reserve monospace typography for logs, JSON, SQL, code, paths, IDs, and tables where fixed-width alignment is useful.
- Improve scanability while preserving the dashboard's original horizontal tab workflow.

## Non-Goals

- Do not migrate the dashboard to React in this change.
- Do not change backend API behavior, database access rules, file editing behavior, log streaming semantics, job cancellation, or usage tracking logic.
- Do not add new dashboard capabilities beyond layout and visual consistency.
- Do not introduce a second app-wide design system or shared frontend dependency for the backend HTML page.

## Layout

The page will use a full-height app shell with a compact sticky header and full-width work surface.

The header will not repeat the app-level `Dev Dashboard` title, launch action, or live connection indicator because the dashboard now lives inside the app's Developer tab. Instead, it will show a small `Developer` kicker, the active section title, one short description, and the dashboard's original section tabs in a compact horizontal tab strip.

The original section model remains intact: Logs, Telemetry, Jobs, API, Database, Usage, and Files are reachable from top tabs. Tab styling should match the rest of the app through rounded selected states, neutral hover states, restrained borders, and violet accents only where they clarify focus or active context.

## Section Behavior

Logs remains the default section. Its main table/raw view, filters, pause/raw/clear controls, kill-all action, log detail modal, WebSocket status, and analytics rail remain functionally unchanged. The visual treatment changes to a compact app toolbar above the log surface, a dedicated right analytics rail, and table styling that matches the app's dense production surfaces.

Telemetry keeps the fallback visibility view and all existing filters, summaries, hot events, recent examples, and detail interactions. The nested telemetry sidebar can be removed while there is only one telemetry view. If more telemetry views are added later, they should use the same local subnavigation pattern as the main shell.

Jobs keeps active and completed job grouping, progress bars, errors, and two-second refresh while visible. Empty state, section headings, status badges, and job panels should match Project Dashboard and Settings density.

API keeps the endpoint list, filter, request builder, response viewer, method badges, schema-derived examples, and send flow. The endpoint list becomes a consistent split-pane sidebar with grouped headers and selected rows. Request and response panes keep their current proportions but use app-consistent controls and code blocks.

Database keeps the table list, SQL runner, table browser, row details, query execution, and error display. The SQL runner remains collapsible. Tables and row detail modals should use the same surface, border, and typography rules as the rest of the dashboard.

Usage keeps the date range selector, grand total, service cards, daily chart, operation table, API call filters, pagination, and recent calls table. The ASCII daily chart may remain monospace because it is data visualization, but the surrounding panel should match app cards.

Files keeps the docs sidebar, explorer, file viewer, Markdown rendering, edit/save/cancel flow, breadcrumbs, and file metadata. The three-pane layout remains because it is efficient for this workflow. Markdown content should keep readable prose styling while matching neutral colors and spacing.

## Visual System

The dashboard will define a small set of local CSS utility classes inside `dashboard.html` for repeated patterns that are hard to maintain as long Tailwind class strings in dynamic JavaScript-rendered markup. These classes are limited to the dashboard page and map to the existing app style:

- Shell: dark neutral background, full-height flex, overflow-safe panes.
- Navigation: compact tab base, selected, and hover states.
- Controls: inputs, selects, text buttons, primary buttons, danger buttons.
- Surfaces: section panels, metric cards, tables, modals, empty states.
- Badges: log levels, HTTP methods, job status, fallback severity.

These classes should not become a second design system. They are a maintenance layer for one backend-served page.

## Data Flow

No API contracts change. Existing JavaScript functions continue to call the same endpoints and mutate the same DOM targets. The main JavaScript update is renaming the tab navigation mental model to section navigation where helpful, while preserving IDs or updating all references together.

The iframe source in `frontend/src/App.tsx` remains `http://localhost:${BACKEND_PORT}/dev/`.

## Error Handling

Existing error handling remains in place. Visual updates should make errors easier to see without changing behavior:

- API schema load failures stay in the endpoint list.
- SQL errors stay next to the execute control.
- Job errors stay inside the job panel.
- Log tracebacks stay in the detail modal.
- File save/edit failures continue to use the existing display path.

Danger actions such as `Kill All` remain visually distinct and keep confirmation.

## Testing And Verification

Implementation should follow test-first where practical for structural behavior that can regress, especially selected section state, preserved panel IDs, and any helper functions introduced for class names or rendering.

Manual verification is required in the running app with the in-app browser/browser tooling:

- Open the Dev Dashboard tab through the Electron app.
- Confirm all seven sections are reachable from the compact top tabs.
- Confirm Logs receives live entries, filters work, raw/table toggle works, modals open/close, and analytics refresh.
- Confirm Jobs auto-refresh still happens only when visible.
- Confirm API endpoint selection, request rendering, and response display still work.
- Confirm Database table browsing, SQL runner, and row detail modal still work.
- Confirm Usage filters, load more, and tables render.
- Confirm Files explorer, Markdown viewer, edit/save/cancel controls, and breadcrumbs render.
- Check at desktop and narrower widths for overflow, clipped labels, and unusable panes.

## Documentation

Because this is a visual redesign of an existing in-app workflow rather than an end-to-end workflow change, no new user-facing docs page is required. If implementation changes dashboard workflow or adds/removes capabilities, update the relevant in-app docs in the same change.

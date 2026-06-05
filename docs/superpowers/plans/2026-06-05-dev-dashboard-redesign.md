# Dev Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the backend-served Dev Dashboard so it feels visually consistent with the rest of the Headless Hero app while preserving all current functionality.

**Architecture:** Keep `/dev/` as the iframe source and update the single backend-served `dashboard.html` page. Add focused backend tests that inspect the served HTML for the new app-shell structure and the existing panel/DOM hooks that the dashboard JavaScript depends on.

**Tech Stack:** FastAPI backend route, static HTML, Tailwind CDN classes, local CSS utility classes inside `dashboard.html`, vanilla JavaScript, pytest via `uv run --project backend pytest`.

---

## File Map

- Modify: `backend/dev/dashboard.html`
  - Owns all dashboard markup, local styles, and vanilla JavaScript.
  - Keep existing API calls, WebSocket path, panel IDs, and feature-specific DOM IDs unless every reference is updated in the same task.
- Create: `backend/tests/test_dev_dashboard_html.py`
  - Static route/HTML tests that verify the redesigned shell exists and existing dashboard hooks remain present.
- Read-only reference: `frontend/src/components/settings/SettingsPage.tsx`
  - Use as the layout reference for sticky header, left sidebar, selected navigation, section title, and helper text hierarchy.
- Read-only reference: `frontend/src/components/dashboard/ProjectDashboard.tsx`
  - Use as the density reference for production tables, small badges, compact filters, and empty states.
- Read-only reference: `docs/superpowers/specs/2026-06-05-dev-dashboard-redesign-design.md`
  - Approved design source.

## Task 1: Add Dashboard Shell Regression Tests

**Files:**
- Create: `backend/tests/test_dev_dashboard_html.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_dev_dashboard_html.py` with this content:

```python
from fastapi.testclient import TestClient


def _dashboard_html() -> str:
    from api import app

    response = TestClient(app).get("/dev/")
    assert response.status_code == 200
    return response.text


def test_dev_dashboard_uses_app_shell_sidebar_navigation():
    html = _dashboard_html()

    assert 'id="dashboardShell"' in html
    assert 'id="dashboardSidebar"' in html
    assert 'id="activeSectionTitle"' in html
    assert 'id="activeSectionDescription"' in html
    assert "Operations" in html
    assert "Inspection" in html
    assert "Assets" in html
    assert 'data-section="logs"' in html
    assert 'data-section="telemetry"' in html
    assert 'data-section="jobs"' in html
    assert 'data-section="api"' in html
    assert 'data-section="database"' in html
    assert 'data-section="usage"' in html
    assert 'data-section="files"' in html


def test_dev_dashboard_preserves_feature_panel_hooks():
    html = _dashboard_html()

    required_ids = [
        "panel-logs",
        "panel-telemetry",
        "panel-jobs",
        "panel-api",
        "panel-database",
        "panel-usage",
        "panel-files",
        "filterLevel",
        "filterModule",
        "filterSearch",
        "killAllBtn",
        "viewToggleBtn",
        "pauseBtn",
        "logBody",
        "logRawContainer",
        "statsByLevel",
        "fallbackSummaryCards",
        "jobsContainer",
        "apiEndpointList",
        "apiRequestBuilder",
        "apiResponseViewer",
        "dbTableList",
        "sqlInput",
        "usageServiceCards",
        "usageRecentTable",
        "mdSidebar",
        "fileTree",
        "fileViewerContent",
    ]

    for element_id in required_ids:
        assert f'id="{element_id}"' in html


def test_dev_dashboard_defines_local_app_style_classes():
    html = _dashboard_html()

    assert ".app-shell" in html
    assert ".section-nav-item" in html
    assert ".control-input" in html
    assert ".surface-panel" in html
    assert ".metric-card" in html
    assert ".status-badge" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_dev_dashboard_html.py -v
```

Expected: the first and third tests fail because the current HTML still uses the standalone header/top-tab structure and does not define the new shell/style classes. The second test should mostly pass unless an expected existing hook has drifted.

- [ ] **Step 3: Commit the failing test only**

Do not commit a permanently failing test to `main`. If executing tasks one by one on `main`, skip this commit and proceed directly to Task 2 in the same working tree. If executing in an isolated branch/worktree, commit with:

```bash
git add backend/tests/test_dev_dashboard_html.py
git commit -m "Add dev dashboard shell regression tests"
```

## Task 2: Add Local Dashboard Style Primitives

**Files:**
- Modify: `backend/dev/dashboard.html`

- [ ] **Step 1: Replace the current standalone dashboard CSS primitives**

In `backend/dev/dashboard.html`, update the `<style>` block so normal text uses the app sans-serif stack and repeated dashboard patterns have local classes. Preserve `.md-content` rules and scrollbar styling, but change the global font and add these classes:

```css
body { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.mono, code, pre, textarea, .tabular-data { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace; }
.app-shell { min-height: 100vh; background: #0a0a0a; color: #d4d4d4; }
.app-header { position: sticky; top: 0; z-index: 20; display: flex; border-bottom: 1px solid #262626; background: #0a0a0a; }
.app-header-brand { display: flex; width: 15rem; flex-shrink: 0; align-items: center; gap: 0.75rem; padding: 1.25rem 1.5rem; }
.app-header-section { display: flex; min-width: 0; flex: 1; align-items: center; justify-content: space-between; gap: 1rem; padding: 1.25rem 2rem; }
.app-sidebar { width: 15rem; flex-shrink: 0; border-right: 1px solid #262626; padding: 1rem 0.75rem; overflow-y: auto; }
.nav-group-label { padding: 0 0.75rem; font-size: 11px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: #525252; }
.section-nav-item { width: 100%; display: flex; align-items: flex-start; gap: 0.625rem; border-radius: 0.5rem; padding: 0.625rem 0.75rem; text-align: left; color: #a3a3a3; transition: color 150ms ease, background-color 150ms ease; }
.section-nav-item:hover { background: rgba(38, 38, 38, 0.55); color: #e5e5e5; }
.section-nav-item.is-active { background: #262626; color: #f5f5f5; }
.section-icon { width: 1rem; height: 1rem; margin-top: 0.125rem; flex-shrink: 0; color: currentColor; }
.control-input { border-radius: 0.5rem; border: 1px solid #404040; background: #171717; color: #d4d4d4; font-size: 0.8125rem; line-height: 1.25rem; padding: 0.375rem 0.625rem; outline: none; transition: border-color 150ms ease; }
.control-input:focus { border-color: #8b5cf6; }
.action-button { border-radius: 0.5rem; background: #262626; color: #d4d4d4; font-size: 0.75rem; font-weight: 500; padding: 0.375rem 0.75rem; transition: background-color 150ms ease, color 150ms ease; }
.action-button:hover { background: #404040; color: #f5f5f5; }
.primary-button { border-radius: 0.5rem; background: #7c3aed; color: white; font-size: 0.75rem; font-weight: 500; padding: 0.375rem 0.75rem; transition: background-color 150ms ease; }
.primary-button:hover { background: #8b5cf6; }
.danger-button { border-radius: 0.5rem; background: #991b1b; color: white; font-size: 0.75rem; font-weight: 600; padding: 0.375rem 0.75rem; transition: background-color 150ms ease; }
.danger-button:hover { background: #b91c1c; }
.surface-panel { border: 1px solid #404040; border-radius: 0.5rem; background: #171717; }
.metric-card { border: 1px solid #404040; border-radius: 0.5rem; background: #171717; padding: 1rem; }
.status-badge { display: inline-flex; align-items: center; border-radius: 0.375rem; padding: 0.125rem 0.375rem; font-size: 10px; font-weight: 500; }
.table-header { position: sticky; top: 0; z-index: 10; background: #0a0a0a; border-bottom: 1px solid #262626; color: #737373; }
.table-row { border-bottom: 1px solid rgba(38, 38, 38, 0.7); }
.table-row:hover { background: rgba(255, 255, 255, 0.04); }
```

- [ ] **Step 2: Keep Markdown content readable**

Confirm `.md-content` remains in the same `<style>` block and still defines headings, links, code blocks, blockquotes, lists, tables, and images. Update only its colors if needed to stay neutral/violet; do not remove Markdown styling.

- [ ] **Step 3: Run the dashboard HTML tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_dev_dashboard_html.py -v
```

Expected: the local style class test passes. The shell navigation test still fails until Task 3.

## Task 3: Replace Top Tabs With App Shell And Sidebar

**Files:**
- Modify: `backend/dev/dashboard.html`

- [ ] **Step 1: Replace the `<body>` opening and old header/nav markup**

Change:

```html
<body class="bg-surface-900 text-neutral-300 min-h-screen">
```

to:

```html
<body class="app-shell">
  <div id="dashboardShell" class="flex min-h-screen flex-col">
```

Replace the current standalone `<header>` and `<nav>` top tabs with:

```html
  <header class="app-header">
    <div class="app-header-brand">
      <button onclick="launchApp(this)" class="primary-button">Launch App</button>
      <div>
        <h1 class="text-xl font-semibold tracking-tight text-neutral-100">Dev Dashboard</h1>
        <div class="mt-1 flex items-center gap-2 text-xs text-neutral-500">
          <span class="w-2 h-2 rounded-full bg-emerald-500 live-dot" id="wsIndicator"></span>
          <span id="wsStatus">Connecting...</span>
        </div>
      </div>
    </div>
    <div class="app-header-section">
      <div class="min-w-0">
        <h2 id="activeSectionTitle" class="text-xl font-semibold tracking-tight text-neutral-100">Logs</h2>
        <p id="activeSectionDescription" class="mt-1 text-sm text-neutral-400">Live backend logs, filters, details, and 24-hour analytics.</p>
      </div>
      <div id="activeSectionMeta" class="text-xs text-neutral-500"></div>
    </div>
  </header>

  <div class="flex min-h-0 flex-1 overflow-hidden">
    <aside id="dashboardSidebar" class="app-sidebar scrollbar-thin">
      <div class="space-y-5">
        <div class="space-y-1">
          <div class="nav-group-label">Operations</div>
          <button type="button" onclick="switchTab('logs')" data-section="logs" id="tab-logs" class="section-nav-item is-active">
            <span class="section-icon">≡</span>
            <span class="min-w-0">
              <span class="block text-sm font-medium">Logs</span>
              <span class="block truncate text-xs text-neutral-500">Live stream and analytics</span>
            </span>
          </button>
          <button type="button" onclick="switchTab('jobs')" data-section="jobs" id="tab-jobs" class="section-nav-item">
            <span class="section-icon">◷</span>
            <span class="min-w-0">
              <span class="block text-sm font-medium">Jobs</span>
              <span class="block truncate text-xs text-neutral-500">Render progress and errors</span>
            </span>
          </button>
          <button type="button" onclick="switchTab('telemetry')" data-section="telemetry" id="tab-telemetry" class="section-nav-item">
            <span class="section-icon">◇</span>
            <span class="min-w-0">
              <span class="block text-sm font-medium">Telemetry</span>
              <span class="block truncate text-xs text-neutral-500">Fallback visibility</span>
            </span>
          </button>
        </div>
        <div class="space-y-1">
          <div class="nav-group-label">Inspection</div>
          <button type="button" onclick="switchTab('api')" data-section="api" id="tab-api" class="section-nav-item">
            <span class="section-icon">{ }</span>
            <span class="min-w-0">
              <span class="block text-sm font-medium">API</span>
              <span class="block truncate text-xs text-neutral-500">Endpoint tester</span>
            </span>
          </button>
          <button type="button" onclick="switchTab('database')" data-section="database" id="tab-database" class="section-nav-item">
            <span class="section-icon">▦</span>
            <span class="min-w-0">
              <span class="block text-sm font-medium">Database</span>
              <span class="block truncate text-xs text-neutral-500">Tables and SQL</span>
            </span>
          </button>
          <button type="button" onclick="switchTab('usage')" data-section="usage" id="tab-usage" class="section-nav-item">
            <span class="section-icon">$</span>
            <span class="min-w-0">
              <span class="block text-sm font-medium">Usage</span>
              <span class="block truncate text-xs text-neutral-500">API cost tracker</span>
            </span>
          </button>
        </div>
        <div class="space-y-1">
          <div class="nav-group-label">Assets</div>
          <button type="button" onclick="switchTab('files')" data-section="files" id="tab-files" class="section-nav-item">
            <span class="section-icon">□</span>
            <span class="min-w-0">
              <span class="block text-sm font-medium">Files</span>
              <span class="block truncate text-xs text-neutral-500">Docs and project files</span>
            </span>
          </button>
        </div>
      </div>
    </aside>
    <main class="min-w-0 flex-1 overflow-hidden">
```

- [ ] **Step 2: Close the new wrapper**

Before `<!-- DB Row Detail Modal -->`, keep all section panels inside `<main>`. After the Files tab panel and before the modal overlays, close the wrappers:

```html
    </main>
  </div>
```

Before `</body>`, close the shell:

```html
  </div>
</body>
```

If the closing `</body>` already exists, add only the missing `</div>`.

- [ ] **Step 3: Update section panel heights**

Replace section heights that depend on the old top header math:

```html
h-[calc(100vh-97px)]
```

with:

```html
h-full
```

Only do this for top-level `panel-*` containers.

- [ ] **Step 4: Update `switchTab` selected-state logic**

Replace the current `switchTab` class toggling block with:

```javascript
const SECTION_META = {
  logs: {
    title: 'Logs',
    description: 'Live backend logs, filters, details, and 24-hour analytics.',
  },
  telemetry: {
    title: 'Telemetry',
    description: 'Structured fallback events from generation, rendering, and recovery paths.',
  },
  jobs: {
    title: 'Jobs',
    description: 'Render jobs, active progress, completed work, and failure details.',
  },
  api: {
    title: 'API',
    description: 'Explore OpenAPI endpoints and test backend requests.',
  },
  database: {
    title: 'Database',
    description: 'Browse SQLite tables and run scoped diagnostic SQL queries.',
  },
  usage: {
    title: 'Usage',
    description: 'Track API call volume, operation costs, and recent usage.',
  },
  files: {
    title: 'Files',
    description: 'Browse docs and project files without leaving the app.',
  },
};

const ALL_TABS = ['logs', 'telemetry', 'jobs', 'api', 'database', 'usage', 'files'];
function switchTab(tab) {
  document.querySelectorAll('.section-nav-item').forEach((button) => {
    button.classList.toggle('is-active', button.dataset.section === tab);
  });

  for (const t of ALL_TABS) {
    document.getElementById('panel-' + t).classList.toggle('hidden', t !== tab);
  }

  const meta = SECTION_META[tab] || SECTION_META.logs;
  document.getElementById('activeSectionTitle').textContent = meta.title;
  document.getElementById('activeSectionDescription').textContent = meta.description;

  if (tab === 'jobs') fetchJobs();
  if (tab === 'telemetry') {
    switchTelemetryView('fallbacks');
    fetchFallbackStats();
  }
  if (tab === 'api') loadOpenApiSchema();
  if (tab === 'database') fetchDbTables();
  if (tab === 'usage') fetchUsageSummary();
  if (tab === 'files') initFilesTab();
}
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_dev_dashboard_html.py -v
```

Expected: all tests pass.

## Task 4: Restyle Static Section Markup

**Files:**
- Modify: `backend/dev/dashboard.html`

- [ ] **Step 1: Restyle Logs static controls**

In the Logs filter toolbar:

- Change select/input classes to `control-input`.
- Change neutral buttons to `action-button`.
- Change `Kill All` to `danger-button`.
- Keep `id="filterLevel"`, `id="filterModule"`, `id="filterSearch"`, `id="killAllBtn"`, `id="viewToggleBtn"`, and `id="pauseBtn"` unchanged.

Use this class pattern:

```html
<select id="filterLevel" onchange="fetchLogs()" class="control-input">
```

```html
<button onclick="fetchLogs()" class="action-button">Search</button>
```

```html
<button onclick="killAll()" id="killAllBtn" class="danger-button">Kill All</button>
```

- [ ] **Step 2: Restyle Telemetry static markup**

Remove the nested telemetry left sidebar markup because only `fallbacks` exists. Keep `id="telemetry-panel-fallbacks"` and the fallback filters. Convert fallback filter controls to `control-input` and refresh to `action-button`.

The top of the telemetry panel should begin:

```html
<div id="panel-telemetry" class="hidden h-full overflow-y-auto scrollbar-thin">
  <div id="telemetry-panel-fallbacks" class="p-6">
    <div class="max-w-7xl space-y-4">
```

Keep `switchTelemetryView('fallbacks')` callable, but it can become a no-op for now if the nested button no longer exists.

- [ ] **Step 3: Restyle Jobs, Usage, Database, API, and Files static containers**

Apply these class conversions without changing IDs:

```html
class="surface-panel p-4"
class="metric-card"
class="control-input"
class="action-button"
class="primary-button"
```

Use `surface-panel` for framed content panels and `metric-card` only for repeated metric summaries. Do not wrap page sections in cards.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_dev_dashboard_html.py -v
```

Expected: PASS.

## Task 5: Restyle JavaScript-Rendered Markup

**Files:**
- Modify: `backend/dev/dashboard.html`

- [ ] **Step 1: Update badge constants to use `status-badge`**

Change badge color constants so they include `status-badge`:

```javascript
const LEVEL_COLORS = {
  DEBUG: 'status-badge bg-neutral-600 text-neutral-300',
  INFO: 'status-badge bg-sky-600/30 text-sky-400',
  WARNING: 'status-badge bg-amber-600/30 text-amber-400',
  ERROR: 'status-badge bg-red-600/30 text-red-400',
  CRITICAL: 'status-badge bg-red-700/50 text-red-300 font-bold',
};
```

Do the same for `FALLBACK_SEVERITY_COLORS`, `METHOD_COLORS`, and job status colors. Remove duplicated `px-* py-* rounded text-[10px] font-medium` around badges where the constant now provides it.

- [ ] **Step 2: Update log rows and tables**

In `createLogRow`, set:

```javascript
tr.className = 'table-row cursor-pointer';
```

Use:

```html
<span class="${levelCls}">${log.level}</span>
```

instead of adding badge spacing in the template.

Apply `table-header` to table headers where JavaScript returns complete tables, including fallback recent, DB tables, usage operation tables, and usage recent calls.

- [ ] **Step 3: Update dynamic cards and panels**

Replace dynamic card strings such as:

```html
<div class="bg-surface-800 border border-neutral-700 rounded-lg p-4">
```

with:

```html
<div class="metric-card">
```

for summary cards, and:

```html
<div class="surface-panel p-4">
```

for larger detail panels.

- [ ] **Step 4: Preserve monospace only where useful**

Keep monospace classes on:

- Raw logs
- SQL textarea
- Job IDs
- JSON request and response bodies
- Code blocks
- File paths
- ASCII usage chart

Remove inherited monospace assumptions from normal labels, buttons, headings, and helper text.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_dev_dashboard_html.py -v
```

Expected: PASS.

## Task 6: Browser Verification And Iteration

**Files:**
- Modify if needed: `backend/dev/dashboard.html`

- [ ] **Step 1: Start the app stack**

Run:

```bash
npm run dev
```

Expected: backend starts on `8420`, frontend starts on `5173`, and Electron launches or is available.

- [ ] **Step 2: Open the running app in Browser tooling**

Use the in-app Browser plugin to open:

```text
http://localhost:5173
```

Navigate to the Dev Dashboard tab.

- [ ] **Step 3: Verify all sections**

Check:

- Logs is default and the sidebar selected state is visible.
- Logs filters, raw/table toggle, pause/resume, clear, detail modal, and analytics rail work.
- Telemetry fallback cards and recent examples render.
- Jobs page renders empty or populated state and keeps its refresh behavior.
- API endpoint filter, endpoint selection, request builder, and response viewer render.
- Database table list, SQL runner, browser table, and row modal render.
- Usage service cards, daily chart, operation table, filters, and load more render.
- Files docs sidebar, explorer, viewer, Markdown, edit/save/cancel controls, and breadcrumbs render.

- [ ] **Step 4: Check responsive widths**

In Browser tooling, inspect at:

```text
1440x900
1024x768
800x900
```

Fix any clipped header text, unusable panes, overlapping controls, or controls whose text overflows their own button/input.

- [ ] **Step 5: Stop the dev server**

Stop the `npm run dev` session with Ctrl-C after verification is complete.

## Task 7: Final Verification, Commit, Push, And Delegated Review Loop

**Files:**
- Modify if needed: `backend/dev/dashboard.html`
- Create: `backend/tests/test_dev_dashboard_html.py`

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_dev_dashboard_html.py backend/tests/test_dev_fallback_routes.py -v
```

Expected: PASS.

- [ ] **Step 2: Run the full backend test suite**

Run:

```bash
npm run test
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Stage relevant files**

Run:

```bash
git add backend/dev/dashboard.html backend/tests/test_dev_dashboard_html.py docs/superpowers/plans/2026-06-05-dev-dashboard-redesign.md
```

Do not stage unrelated untracked files under `docs/superpowers/plans/`.

- [ ] **Step 5: Commit**

Run:

```bash
git commit -m "Update dev dashboard app styling"
```

- [ ] **Step 6: Push to main**

Run:

```bash
git push origin main
```

- [ ] **Step 7: Dispatch delegated code review**

Use Codex agent delegation tooling with this exact prompt:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

- [ ] **Step 8: Apply review findings internally**

If the delegated review returns `NEEDS CHANGES`, immediately implement every FAIL and WARN finding, then run:

```bash
git add backend/dev/dashboard.html backend/tests/test_dev_dashboard_html.py docs/superpowers/plans/2026-06-05-dev-dashboard-redesign.md
git commit -m "fix: address review findings"
git push origin main
```

Dispatch the same delegated review prompt again. Repeat until the verdict is `LGTM`.

- [ ] **Step 9: Final user summary**

After `LGTM`, summarize:

- What changed visually.
- What verification passed.
- What the delegated review caught, if anything, and what was fixed.

Do not expose raw review findings before they are fixed.

## Self-Review Notes

- Spec coverage: The plan keeps `/dev/` backend-served, preserves all seven sections, changes top tabs to a Settings-like sidebar, adds local style primitives, reserves monospace for diagnostic content, keeps APIs unchanged, and requires browser verification.
- Placeholder scan: No unresolved markers or unspecified test-writing steps remain.
- Type/name consistency: The plan preserves the existing `panel-*` and feature DOM IDs and introduces only `dashboardShell`, `dashboardSidebar`, `activeSectionTitle`, `activeSectionDescription`, `SECTION_META`, and local CSS class names.

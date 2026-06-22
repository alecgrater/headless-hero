# Img Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a non-destructive Img Review tab that lets users correct project render-source images before rerender/export.

**Architecture:** Backend owns asset enumeration, safe edited-copy persistence, script JSON URL updates, and render-cache invalidation. Frontend owns a focused canvas editor and calls the backend to save or reset a selected render-source asset.

**Tech Stack:** FastAPI, SQLModel/Pydantic, Pillow, React 19, TypeScript, Tailwind 4, Vitest, pytest.

---

## File Structure

- Create `backend/api/image_review.py`: image-review API router, asset id parsing, PNG data URL validation, edited-copy saving, script JSON updates.
- Modify `backend/api/__init__.py`: include the new router.
- Create `backend/tests/test_image_review_api.py`: backend behavior tests.
- Create `frontend/src/types/imageReview.ts`: image-review API types.
- Modify `frontend/src/api.ts`: typed image-review API helpers.
- Create `frontend/src/components/timeline/image-review/ImageReviewEditor.tsx`: canvas editor for erase, select, copy, paste, delete, text, undo/redo, save.
- Create `frontend/src/components/timeline/image-review/ImageReviewTab.tsx`: asset list, loading/error states, save/reset orchestration.
- Create `frontend/src/components/timeline/image-review/ImageReviewTab.test.tsx`: UI behavior tests with mocked API.
- Modify `frontend/src/components/timeline/TimelinePage.tsx`: add `Img Review` nav option and render the tab.
- Modify `docs/SETUP.md` or `docs/formats/AUTHORING.md`: mention Img Review before render/export.
- Modify `AGENTS.md`: add the project convention that Img Review edits are non-destructive render-source replacements and thumbnails are out of scope.

## Task 1: Backend API

**Files:**
- Create: `backend/api/image_review.py`
- Modify: `backend/api/__init__.py`
- Test: `backend/tests/test_image_review_api.py`

- [ ] **Step 1: Write failing backend tests**

Create tests that:

```python
def test_list_image_review_assets_includes_scene_frames_and_layers(client, test_engine, tmp_path, monkeypatch):
    # Create a script with image_url, frame_urls, and visual_layers[].image_url.
    # Assert GET /api/image-review/{script_id} returns three asset ids and no thumbnail paths.
```

```python
def test_save_image_review_edit_updates_frame_url_non_destructively(client, test_engine, tmp_path, monkeypatch):
    # Save a 1x1 PNG data URL for scene:{scene_id}:frame:1.
    # Assert a file exists under projects/{script_id}/image_review/.
    # Assert script_json frame_urls[1] points at the edited copy.
    # Assert metadata preserves the original URL.
```

```python
def test_reset_image_review_asset_restores_original_url(client, test_engine, tmp_path, monkeypatch):
    # After saving an edit, call reset.
    # Assert script_json points back at the original URL.
```

```python
def test_save_image_review_rejects_unknown_asset_and_invalid_data_url(client, test_engine):
    # Assert 404 for an unknown asset id.
    # Assert 422 for a non-PNG/non-data-url payload.
```

- [ ] **Step 2: Run backend tests and verify RED**

Run:

```bash
uv run --project backend pytest backend/tests/test_image_review_api.py -q
```

Expected: tests fail because `/api/image-review/{script_id}` does not exist.

- [ ] **Step 3: Implement backend API**

Implement:

- `ImageReviewAsset`, `ImageReviewListResponse`, `ImageReviewEditRequest`, and `ImageReviewUpdateResponse`.
- `_collect_assets(content, script_id)` to enumerate scene images, frame URLs, and visual layer image URLs.
- `_apply_asset_url(content, asset_id, new_url, original_url, reviewed)` to mutate the matching field and store metadata.
- `_decode_png_data_url(data_url)` to accept only `data:image/png;base64,...`.
- `save_edit` to write `edit_{version}.png`.
- `reset_asset` to restore metadata original URL.

- [ ] **Step 4: Run backend tests and verify GREEN**

Run:

```bash
uv run --project backend pytest backend/tests/test_image_review_api.py -q
```

Expected: all image-review backend tests pass.

## Task 2: Frontend API Types

**Files:**
- Create: `frontend/src/types/imageReview.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add typed frontend API helpers**

Create the response/request types and add:

```ts
export async function getImageReviewAssets(scriptId: string): Promise<ImageReviewListResponse>
export async function saveImageReviewEdit(scriptId: string, assetId: string, dataUrl: string): Promise<ImageReviewUpdateResponse>
export async function resetImageReviewAsset(scriptId: string, assetId: string): Promise<ImageReviewUpdateResponse>
```

- [ ] **Step 2: Run TypeScript build**

Run:

```bash
cd frontend && npm run build
```

Expected: either build passes or fails only because Img Review components are not yet created/imported.

## Task 3: Img Review Tab and Editor

**Files:**
- Create: `frontend/src/components/timeline/image-review/ImageReviewEditor.tsx`
- Create: `frontend/src/components/timeline/image-review/ImageReviewTab.tsx`
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`
- Test: `frontend/src/components/timeline/image-review/ImageReviewTab.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

Create tests that:

```ts
it("lists image review assets and saves a deleted selection", async () => {
  // Mock getImageReviewAssets with one asset.
  // Render ImageReviewTab.
  // Select rectangle/delete/save through accessible controls.
  // Assert saveImageReviewEdit was called with a PNG data URL.
});
```

```ts
it("resets the selected asset and applies returned script content", async () => {
  // Mock resetImageReviewAsset.
  // Click Reset.
  // Assert onContentUpdated receives returned script.
});
```

- [ ] **Step 2: Run frontend tests and verify RED**

Run:

```bash
cd frontend && npm run test -- src/components/timeline/image-review/ImageReviewTab.test.tsx
```

Expected: tests fail because components do not exist.

- [ ] **Step 3: Implement tab and editor**

Implement the editor with:

- Image loading into `<canvas>`.
- Tool modes: erase, select, text, move pasted patch.
- Selection rectangle in canvas coordinates.
- Copy/delete/paste actions.
- Text color and size inputs.
- Undo/redo by storing PNG data URLs.
- Save button that exports `canvas.toDataURL("image/png")`.
- Reset button calling backend reset.

Implement the tab with:

- Asset loading on mount and when script id changes.
- Asset list grouped by segment/scene label.
- Selected asset editor.
- Save/reset loading states and toast feedback.
- `onContentUpdated(response.script)` after save/reset.

- [ ] **Step 4: Integrate into TimelinePage**

Add:

- `ViewerTab` key `image-review`.
- `VIEWER_NAV_OPTIONS` item `{ key: "image-review", label: "Img Review", Icon: Images }`.
- Render `ImageReviewTab` when the active tab is `image-review` and asset is `render`.

- [ ] **Step 5: Run frontend tests and build**

Run:

```bash
cd frontend && npm run test -- src/components/timeline/image-review/ImageReviewTab.test.tsx
cd frontend && npm run build
```

Expected: tests and build pass.

## Task 4: Docs and Project Convention

**Files:**
- Modify: `docs/SETUP.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update docs**

Add a short workflow note:

```markdown
Before render/export, use the project Img Review tab to inspect and non-destructively correct generated scene images, frame images, and layered image assets. Img Review does not manage thumbnails.
```

- [ ] **Step 2: Update AGENTS.md**

Add a convention:

```markdown
- **Img Review edits are non-destructive render-source replacements**: Project Img Review saves edited copies under the project `image_review` folder, updates the relevant scene image/frame/layer URL to the edited copy, preserves the original URL for reset, and marks renders stale. Img Review covers render-source scene assets only, not long-form or short-form thumbnails.
```

## Task 5: Full Verification and Auto-Commit Loop

**Files:**
- All changed files.

- [ ] **Step 1: Run targeted verification**

Run:

```bash
uv run --project backend pytest backend/tests/test_image_review_api.py -q
cd frontend && npm run test -- src/components/timeline/image-review/ImageReviewTab.test.tsx
cd frontend && npm run build
```

Expected: all commands pass.

- [ ] **Step 2: Run broader smoke verification**

Run:

```bash
npm run test -- backend/tests/test_image_review_api.py
```

Expected: backend test command passes.

- [ ] **Step 3: Commit and push**

Run:

```bash
git add backend/api/image_review.py backend/api/__init__.py backend/tests/test_image_review_api.py frontend/src/types/imageReview.ts frontend/src/api.ts frontend/src/components/timeline/image-review frontend/src/components/timeline/TimelinePage.tsx docs/SETUP.md AGENTS.md docs/superpowers/specs/2026-06-22-img-review-design.md docs/superpowers/plans/2026-06-22-img-review.md
git commit -m "Add Img Review editor for project images"
git push origin main
```

- [ ] **Step 4: Delegated code review loop**

Dispatch a code review agent with the project-required review prompt. If the verdict is `NEEDS CHANGES`, implement all FAIL and WARN findings, commit as `fix: address review findings`, push, and repeat review until `LGTM`.

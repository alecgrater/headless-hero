# Eli Vortex Thumbnail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Eli corner overlay (video + thumbnail) with a Gemini-powered thumbnail transformation that uses user-uploaded reference thumbnails to add glowing borders, insert Eli into a random circle, and optimize the title for CTR.

**Architecture:** The existing Pillow title card compositor produces a base image (circles, labels, title). A new Gemini transformation step takes that base + a reference thumbnail + an Eli character frame and returns a CTR-optimized final thumbnail. The video Eli overlay system (animation keyframes, Remotion component) is removed entirely.

**Tech Stack:** Python 3.12 / FastAPI / Pillow / google-genai SDK / React 19 / TypeScript / Tailwind 4

**Spec:** `docs/superpowers/specs/2026-04-14-eli-vortex-thumbnail-design.md`

---

### Task 1: Add thumbnail reference storage and API endpoints

**Files:**
- Create: `backend/api/thumbnail_references.py`
- Modify: `backend/api/__init__.py:20-91` (register new router, remove eli router)
- Modify: `frontend/src/api.ts` (add 3 new functions)

- [ ] **Step 1: Create the thumbnail references API module**

```python
# backend/api/thumbnail_references.py
"""Thumbnail reference image management — upload, list, delete."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from config import DATA_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/character/thumbnail-references", tags=["character"])

REFERENCES_DIR = DATA_DIR / "character" / "thumbnail_references"


def _ensure_dir() -> Path:
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    return REFERENCES_DIR


@router.get("")
async def list_references():
    """List all uploaded thumbnail reference images."""
    ref_dir = _ensure_dir()
    files = sorted(
        [f.name for f in ref_dir.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")],
    )
    return {
        "references": [
            {"filename": f, "url": f"/static/character/thumbnail_references/{f}"}
            for f in files
        ],
    }


@router.post("")
async def upload_reference(file: UploadFile):
    """Upload a new thumbnail reference image."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="File must be an image")

    ref_dir = _ensure_dir()
    # Sanitize filename — keep original name but ensure no path traversal
    safe_name = Path(file.filename).name if file.filename else "reference.png"
    dest = ref_dir / safe_name

    # Avoid overwrites by appending a counter
    counter = 1
    stem = dest.stem
    suffix = dest.suffix
    while dest.exists():
        dest = ref_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    content = await file.read()
    dest.write_bytes(content)
    logger.info("Uploaded thumbnail reference: %s", dest.name)

    return {"filename": dest.name, "url": f"/static/character/thumbnail_references/{dest.name}"}


@router.delete("/{filename}")
async def delete_reference(filename: str):
    """Delete a thumbnail reference image."""
    ref_dir = _ensure_dir()
    # Prevent path traversal
    safe_name = Path(filename).name
    target = ref_dir / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Reference not found")
    target.unlink()
    logger.info("Deleted thumbnail reference: %s", safe_name)
    return {"deleted": safe_name}
```

- [ ] **Step 2: Register the router in `backend/api/__init__.py`**

Add the import and include. Also remove the eli router since we'll delete that module later.

In `backend/api/__init__.py`, add after line 22:
```python
from api.thumbnail_references import router as thumbnail_references_router
```

Remove line 20:
```python
from api.eli import router as eli_router
```

After line 91 (`app.include_router(eli_router)`), replace with:
```python
app.include_router(thumbnail_references_router)
```

Also ensure the `thumbnail_references` directory is created at startup. In the `lifespan` function, after line 60 (`character_dir.mkdir(parents=True, exist_ok=True)`), add:
```python
    thumb_ref_dir = DATA_DIR / "character" / "thumbnail_references"
    thumb_ref_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 3: Add frontend API functions in `frontend/src/api.ts`**

Add after the existing `regenerateThumbnailFrame` function (around line 263):

```typescript
// Thumbnail reference management
export async function getThumbnailReferences(): Promise<{
  references: { filename: string; url: string }[];
}> {
  return api.get("/api/character/thumbnail-references");
}

export async function uploadThumbnailReference(file: File): Promise<{ filename: string; url: string }> {
  const form = new FormData();
  form.append("file", file);
  return api.post("/api/character/thumbnail-references", form);
}

export async function deleteThumbnailReference(filename: string): Promise<{ deleted: string }> {
  return api.delete(`/api/character/thumbnail-references/${encodeURIComponent(filename)}`);
}
```

- [ ] **Step 4: Verify the API works**

Run the backend: `npm run dev:backend`

Test with:
```bash
# List (empty)
curl http://localhost:8420/api/character/thumbnail-references

# Upload
curl -X POST http://localhost:8420/api/character/thumbnail-references \
  -F "file=@/path/to/some/thumbnail.png"

# List (should show upload)
curl http://localhost:8420/api/character/thumbnail-references

# Delete
curl -X DELETE http://localhost:8420/api/character/thumbnail-references/thumbnail.png
```

- [ ] **Step 5: Commit**

```bash
git add backend/api/thumbnail_references.py backend/api/__init__.py frontend/src/api.ts
git commit -m "Add thumbnail reference upload/list/delete API endpoints"
```

---

### Task 2: Add Gemini multi-image transform function

**Files:**
- Modify: `backend/integrations/google_image_client.py:86-173` (add new function)

- [ ] **Step 1: Add `transform_with_references()` to `google_image_client.py`**

Add this function after the existing `generate_image()` function (after line 173):

```python
def transform_with_references(
    prompt: str,
    image_paths: list[str],
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    script_id: str | None = None,
) -> str:
    """Transform an image using Gemini with multiple reference images.

    Sends all provided images as multi-modal Parts alongside the text prompt.
    Gemini returns a single transformed image.

    Args:
        prompt: Text instructions for how to transform the image.
        image_paths: List of image file paths to include (base image, references, etc.).
        width: Output width for aspect ratio calculation.
        height: Output height for aspect ratio calculation.
        script_id: Optional script ID for usage tracking.

    Returns:
        Path to the generated image temp file.

    Raises:
        RuntimeError: If Gemini fails to produce an image.
    """
    client = _get_client()
    aspect = _closest_aspect_ratio(width, height)
    logger.info("Transforming image via Gemini with %d reference images", len(image_paths))

    # Build contents: all images first, then prompt text
    contents: list = []
    for img_path in image_paths:
        mime = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"
        with open(img_path, "rb") as f:
            part = types.Part.from_bytes(data=f.read(), mime_type=mime)
        contents.append(part)
    contents.append(prompt)

    result = _call_gemini(client, contents, aspect, script_id=script_id)
    if result:
        return result

    raise RuntimeError(
        f"Gemini returned empty response for image transformation. "
        f"Prompt: {prompt[:200]}"
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/integrations/google_image_client.py
git commit -m "Add Gemini multi-image transform function for thumbnail enhancement"
```

---

### Task 3: Add thumbnail enhancement pipeline

**Files:**
- Modify: `backend/pipeline/thumbnail.py` (add `gemini_enhance_thumbnail()`)

- [ ] **Step 1: Add the enhancement function to `backend/pipeline/thumbnail.py`**

Add these imports at the top (after line 11):
```python
import random
from pathlib import Path
```

Add this function after `get_composite_thumbnail_no_eli()` (after line 49):

```python
THUMBNAIL_REFERENCES_DIR = DATA_DIR / "character" / "thumbnail_references"

# CTR expression tier guidance for Gemini prompt
_CTR_EXPRESSION_GUIDANCE = """
Choose the character's expression/pose based on the video title and topic, using one of these CTR-optimized tiers:

1. Pattern Interrupt (High Surprise) — for shocking/unexpected content:
   - Gasped Breath: mouth slightly open, eyes wide, eyebrows raised
   - Wince/Cringe: one eye squinting, mouth pulled to side
   - Wide-Eyed Hyper-Focus: leaning into camera, dilated pupils

2. Negative Tension (Anxiety & Concern) — for warning/cautionary content:
   - Forehead Furrow: brows pinched, hand on chin/forehead
   - Tears/Red Eyes: glistening eyes, empathy-driving
   - Secretive "Shush": finger to lips, eyes darting

3. Action-Oriented (Excitement & Joy) — for travel, tech, challenge content:
   - Mid-Laugh: genuine squinty-eyed laugh
   - "Look at This" Gaze: looking with wonder at the subject
   - Exertion/Struggle: teeth grit, brow sweating

Pick the tier and specific expression that best matches the video title/topic.
"""


def gemini_enhance_thumbnail(
    base_image_path: str,
    video_title: str,
    script_id: str | None = None,
) -> str | None:
    """Enhance a base title card composite using Gemini with reference thumbnails.

    Sends the base image + a random reference thumbnail + a random Eli character
    frame to Gemini, which transforms the image for higher CTR.

    Args:
        base_image_path: Path to the base Pillow-generated composite.
        video_title: The video title (provides context for expression selection).
        script_id: Optional script ID for usage tracking.

    Returns:
        Path to the enhanced image, or None if enhancement can't be performed
        (no references uploaded, no character frames, etc.).
    """
    from integrations.google_image_client import transform_with_references
    from pipeline.character_frames import get_manifest, FRAMES_DIR

    # Check for reference thumbnails
    ref_dir = THUMBNAIL_REFERENCES_DIR
    if not ref_dir.exists():
        logger.info("No thumbnail references directory — skipping enhancement")
        return None

    ref_files = [
        f for f in ref_dir.iterdir()
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    ]
    if not ref_files:
        logger.info("No thumbnail references uploaded — skipping enhancement")
        return None

    # Pick a random reference thumbnail
    ref_path = str(random.choice(ref_files))
    logger.info("Using thumbnail reference: %s", ref_path)

    # Pick a random Eli character frame
    eli_frame_path = None
    try:
        manifest = get_manifest()
        if manifest and manifest.get("frames"):
            # Prefer thumbnail frames with open mouth
            thumbnail_frames = manifest.get("thumbnail_frames", [])
            frames = thumbnail_frames if thumbnail_frames else manifest["frames"]
            frame = random.choice(frames)
            mouth_key = "file_open" if thumbnail_frames else "file_closed"
            file_name = frame.get(mouth_key, "")
            if file_name:
                candidate = FRAMES_DIR / file_name
                if candidate.exists():
                    eli_frame_path = str(candidate)
    except Exception as exc:
        logger.debug("Could not load Eli frame for thumbnail: %s", exc)

    # Build image list: base image first, then reference, then Eli frame
    image_paths = [base_image_path, ref_path]
    if eli_frame_path:
        image_paths.append(eli_frame_path)

    # Build prompt
    character_instruction = ""
    if eli_frame_path:
        character_instruction = (
            "The third image is a character to insert into the title card. "
            "Choose one of the segment circles at random and replace its image with "
            "this character popping out of that circle, matching how the character "
            "appears in the reference thumbnail (head extending past the circle, "
            "hands gripping the edge, emerging from a glowing blue plasma vortex). "
            "Keep the segment label badge beneath the chosen circle readable.\n\n"
            f"{_CTR_EXPRESSION_GUIDANCE}\n"
        )

    prompt = (
        "You are a YouTube thumbnail optimizer. You have been given:\n"
        "1. A base title card image with circular segment thumbnails arranged in a grid\n"
        "2. A reference thumbnail showing the target visual style\n"
        f"{'3. A character image to insert into the title card' if eli_frame_path else ''}\n\n"
        "Your task:\n"
        "- Study the reference thumbnail's visual style (circle borders, glow effects, "
        "character positioning, title treatment)\n"
        f"{character_instruction}"
        "- Apply the reference thumbnail's circle border styling (glowing magical borders) "
        "to ALL circles in the image\n"
        "- Update the title text styling to be more punchy, bold, and attention-grabbing, "
        "matching the reference thumbnail's title treatment\n"
        f'- The video title is: "{video_title}"\n'
        "- Optimize everything for maximum YouTube CTR\n\n"
        "Keep the segment label badges readable. Keep the overall layout and grid intact. "
        "Return the modified image."
    )

    try:
        result_path = transform_with_references(
            prompt=prompt,
            image_paths=image_paths,
            script_id=script_id,
        )
        logger.info("Gemini thumbnail enhancement complete: %s", result_path)
        return result_path
    except Exception as exc:
        logger.warning("Gemini thumbnail enhancement failed, using base image: %s", exc)
        return None
```

- [ ] **Step 2: Commit**

```bash
git add backend/pipeline/thumbnail.py
git commit -m "Add Gemini-powered thumbnail enhancement pipeline"
```

---

### Task 4: Modify title card composer — remove Eli overlay and circle outline/energy ring

**Files:**
- Modify: `backend/pipeline/title_card_composer.py:617-768`

- [ ] **Step 1: Update `compose_title_card()` to skip Eli overlay and outline/energy ring**

In `backend/pipeline/title_card_composer.py`, make three changes:

**Change 1:** In the `compose_title_card` function signature (line 617), change `include_eli` default to `False`:

Replace line 627:
```python
    include_eli: bool = True,
```
With:
```python
    include_eli: bool = False,
```

**Change 2:** Remove the circle outline (Layer 5) and energy ring (Layer 5b). Replace lines 716-727:

```python
        # Layer 5: Circle outline (dark border stroke)
        outline_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        od = ImageDraw.Draw(outline_layer)
        od.ellipse(
            (cx - bg_radius, cy - bg_radius, cx + bg_radius, cy + bg_radius),
            outline=border_rgb + (255,),
            width=_CIRCLE_BORDER_WIDTH,
        )
        canvas = Image.alpha_composite(canvas, outline_layer)

        # Layer 5b: Energy glow ring
        canvas = _draw_circle_energy_ring(canvas, cx, cy, bg_radius, color)
```

With:
```python
        # Layers 5/5b removed — Gemini adds glowing borders during enhancement
```

**Change 3:** In the `compose_title_card` call, save to `composite_title_card_base.png` as well. After line 765 (`final.save(output_path, "PNG")`), add:

```python
    # Also save as base image for Gemini enhancement
    base_path = str(Path(output_path).parent / "composite_title_card_base.png")
    final.save(base_path, "PNG")
```

Add `from pathlib import Path` to imports at top if not already present (it's already imported on line 10).

- [ ] **Step 2: Commit**

```bash
git add backend/pipeline/title_card_composer.py
git commit -m "Remove Eli overlay and circle outline from title card composer"
```

---

### Task 5: Update thumbnail API to integrate Gemini enhancement

**Files:**
- Modify: `backend/api/thumbnail.py:73-172` (update `recomposite_thumbnail`)
- Modify: `backend/pipeline/thumbnail.py` (update `get_composite_thumbnail_no_eli` naming)

- [ ] **Step 1: Update `recomposite_thumbnail` in `backend/api/thumbnail.py`**

Add import at top of file (after existing imports around line 16):
```python
from pipeline.thumbnail import gemini_enhance_thumbnail
```

In the `recomposite_thumbnail` function, after the first `compose_title_card` call (around line 117-130 where the with-Eli version is generated), replace the Eli variant logic.

The key changes:
1. Call `compose_title_card` with `include_eli=False` (for the main thumbnail)
2. After compositing, call `gemini_enhance_thumbnail` on the base image
3. If enhancement succeeds, copy the enhanced image as the final thumbnail
4. If enhancement fails, use the base composite as fallback
5. Remove the "without Eli" variant (no longer relevant — there's no Eli corner overlay)

Replace the body of `recomposite_thumbnail` from the `compose_title_card` call onward. The exact replacement depends on the current structure, but the logic should be:

```python
    # Generate base composite (no Eli overlay, no circle outlines)
    output_path = str(images_dir / "composite_title_card.png")
    compose_title_card(
        circle_image_paths=circle_paths,
        segment_names=names,
        circle_colors=colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=accent_color,
        output_path=output_path,
        include_title=True,
        include_eli=False,
        card_subtitle=card_subtitle,
    )

    # Also generate no-title variant for video zoom scenes (stays Pillow-only)
    notitle_path = str(images_dir / "composite_title_card_notitle.png")
    compose_title_card(
        circle_image_paths=circle_paths,
        segment_names=names,
        circle_colors=colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=accent_color,
        output_path=notitle_path,
        include_title=False,
        include_eli=False,
        card_subtitle=card_subtitle,
    )

    # Gemini enhancement — transforms the base into a CTR-optimized thumbnail
    base_path = str(images_dir / "composite_title_card_base.png")
    enhanced_path = gemini_enhance_thumbnail(
        base_image_path=base_path,
        video_title=card_title,
        script_id=body.script_id,
    )

    # If Gemini succeeded, use the enhanced version as the final thumbnail
    if enhanced_path:
        import shutil as _shutil
        _shutil.copy2(enhanced_path, output_path)
        logger.info("Using Gemini-enhanced thumbnail")

    # Copy to renders/thumbnails for export
    thumbs_dir = DATA_DIR / "projects" / body.script_id / "renders" / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    thumb_dest = thumbs_dir / "0.png"
    shutil.copy2(output_path, str(thumb_dest))
    url = f"/static/projects/{body.script_id}/renders/thumbnails/0.png"
    url = _cache_bust(url, str(thumb_dest))

    return GenerateThumbnailResponse(
        concepts=[ThumbnailConceptResult(idx=0, title_text=card_title, visual_description="Gemini-enhanced title card", image_url=url)]
    )
```

- [ ] **Step 2: Update `get_existing_thumbnails` to remove Eli variant**

In the `get_existing_thumbnails` function (line 40), simplify to return just the single thumbnail (no "with Eli" / "without Eli" split):

```python
@router.get("/{script_id}", response_model=GenerateThumbnailResponse)
async def get_existing_thumbnails(script_id: str, session: Session = Depends(get_session)):
    """Return pre-existing thumbnail for a script."""
    url = get_composite_thumbnail(script_id)
    concepts = []
    if url:
        concepts.append(ThumbnailConceptResult(idx=0, title_text="", visual_description="Title card thumbnail", image_url=url))
    return GenerateThumbnailResponse(concepts=concepts)
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/thumbnail.py
git commit -m "Integrate Gemini thumbnail enhancement into recomposite endpoint"
```

---

### Task 6: Add thumbnail reference upload UI in Settings

**Files:**
- Modify: `frontend/src/components/settings/CharacterSection.tsx`

- [ ] **Step 1: Add state and data loading for thumbnail references**

In `CharacterSection.tsx`, add state variables alongside the existing character state (around line 45-76):

```typescript
const [thumbnailRefs, setThumbnailRefs] = useState<{ filename: string; url: string }[]>([]);
const [uploadingRef, setUploadingRef] = useState(false);
```

Add imports at top:
```typescript
import { getThumbnailReferences, uploadThumbnailReference, deleteThumbnailReference } from "../../api";
```

In the `useEffect` that loads initial data (around line 78-101), add:
```typescript
getThumbnailReferences().then((data) => setThumbnailRefs(data.references)).catch(() => {});
```

- [ ] **Step 2: Add upload and delete handlers**

Add these handlers alongside the existing character handlers:

```typescript
async function handleUploadThumbnailRef(e: React.ChangeEvent<HTMLInputElement>) {
  const file = e.target.files?.[0];
  if (!file) return;
  setUploadingRef(true);
  try {
    const result = await uploadThumbnailReference(file);
    setThumbnailRefs((prev) => [...prev, result]);
  } finally {
    setUploadingRef(false);
    e.target.value = "";
  }
}

async function handleDeleteThumbnailRef(filename: string) {
  await deleteThumbnailReference(filename);
  setThumbnailRefs((prev) => prev.filter((r) => r.filename !== filename));
}
```

- [ ] **Step 3: Add the thumbnail references UI section**

Add a new section in the JSX, after the existing thumbnail expressions section (around line 731) and before the Eli position picker (around line 742). Place it as a new subsection:

```tsx
{/* Thumbnail Reference Images */}
<div className="space-y-3">
  <h3 className="text-sm font-medium text-neutral-300">Thumbnail References</h3>
  <p className="text-xs text-neutral-500">
    Upload thumbnails from channels you admire. These guide the style of your generated thumbnails — glowing borders, character placement, title treatment.
  </p>

  {/* Upload button */}
  <label className="inline-flex items-center gap-2 px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white text-sm rounded-lg cursor-pointer transition-colors">
    {uploadingRef ? "Uploading..." : "Upload Reference"}
    <input
      type="file"
      accept="image/*"
      className="hidden"
      onChange={handleUploadThumbnailRef}
      disabled={uploadingRef}
    />
  </label>

  {/* Grid of uploaded references */}
  {thumbnailRefs.length > 0 && (
    <div className="grid grid-cols-3 gap-3">
      {thumbnailRefs.map((ref) => (
        <div key={ref.filename} className="relative group rounded-lg overflow-hidden border border-neutral-800">
          <img
            src={assetUrl(ref.url)}
            alt={ref.filename}
            className="w-full aspect-video object-cover"
          />
          <button
            onClick={() => handleDeleteThumbnailRef(ref.filename)}
            className="absolute top-1 right-1 w-6 h-6 bg-red-600 hover:bg-red-500 rounded-full text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
            title="Delete reference"
          >
            x
          </button>
          <div className="absolute bottom-0 left-0 right-0 bg-black/60 px-2 py-1 text-xs text-neutral-300 truncate">
            {ref.filename}
          </div>
        </div>
      ))}
    </div>
  )}
</div>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/settings/CharacterSection.tsx frontend/src/api.ts
git commit -m "Add thumbnail reference upload UI in Settings"
```

---

### Task 7: Remove video Eli overlay system

**Files:**
- Modify: `remotion/src/scenes/SceneRenderer.tsx:16,58-65` (remove EliOverlay import and rendering)
- Delete: `remotion/src/effects/overlays/EliOverlay.tsx`
- Delete: `backend/api/eli.py`
- Delete: `backend/pipeline/eli_animator.py`
- Modify: `backend/api/__init__.py` (already handled in Task 1 — eli router removed)

- [ ] **Step 1: Remove EliOverlay from SceneRenderer.tsx**

In `remotion/src/scenes/SceneRenderer.tsx`:

Remove the import (line 16):
```typescript
import { EliOverlay } from "../effects/overlays/EliOverlay";
```

Remove the EliOverlay rendering block (lines 58-65):
```tsx
      {scene.eli_overlay?.enabled && scene.eli_overlay.keyframes.length > 0 && scene.character_frames_base_url && (
        <EliOverlay
          overlay={scene.eli_overlay}
          wordTimestamps={scene.word_timestamps}
          characterFramesBaseUrl={scene.character_frames_base_url}
          variantCounts={scene.variant_counts}
        />
      )}
```

- [ ] **Step 2: Delete the EliOverlay component**

```bash
rm remotion/src/effects/overlays/EliOverlay.tsx
```

- [ ] **Step 3: Delete the backend Eli API and pipeline**

```bash
rm backend/api/eli.py
rm backend/pipeline/eli_animator.py
```

- [ ] **Step 4: Verify Remotion still compiles**

```bash
cd remotion && npx tsc --noEmit
```

Expected: No errors (EliOverlay was only imported in SceneRenderer.tsx).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Remove video Eli overlay system (EliOverlay, eli_animator, eli API)"
```

---

### Task 8: Clean up timeline Eli UI

**Files:**
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`
- Modify: `frontend/src/components/timeline/PipelineSteps.tsx`
- Modify: `frontend/src/api.ts` (remove `generateEli`, `regenerateEli`)
- Delete: `frontend/src/components/timeline/useEliPosition.ts`
- Delete: `frontend/src/components/shared/EliPositionPicker.tsx`

- [ ] **Step 1: Remove Eli functions from `frontend/src/api.ts`**

Remove the `generateEli` and `regenerateEli` functions (around lines 266-273):
```typescript
export async function generateEli(scriptId: string, missingOnly = false) {
  return api.post("/api/eli/generate", { script_id: scriptId, missing_only: missingOnly });
}

export async function regenerateEli(scriptId: string, sceneId: string) {
  return api.post("/api/eli/regenerate", { script_id: scriptId, scene_id: sceneId });
}
```

- [ ] **Step 2: Remove Eli state and handlers from `TimelinePage.tsx`**

In `frontend/src/components/timeline/TimelinePage.tsx`:

Remove from imports (line 2): `generateEli` from the api import.

Remove the `useEliPosition` import and hook usage (line 162): `const eliPosition = useEliPosition(initialContent);`

Remove state variables:
- `generatingEli` state (line 168)
- Eli-related entries in `confirmOverwrite` type (line 169 — remove `"eli"` from the union)

Remove Eli completion logic (lines 385-386, 392):
- `eliScenes` filter
- `allEliGenerated` check
- `missingEliCount` calculation

Remove handler functions:
- `handleGenerateEli()` (lines 437-454)
- `confirmAndGenerateEli()` (lines 456-462)
- `generateMissingEli()` (lines 483-499)

Remove all Eli-related props passed to `PipelineSteps` (lines 644-703 — remove the `generatingEli`, `setGeneratingEli`, `confirmAndGenerateEli`, `generateMissingEli`, `hasExistingEli`, `missingEliCount`, `eliCancelledRef`, and all Eli position props).

Remove the Eli overwrite confirmation case (line 963, 979).

Remove the Eli progress bar section (lines 762-774).

- [ ] **Step 3: Remove Eli section from `PipelineSteps.tsx`**

In `frontend/src/components/timeline/PipelineSteps.tsx`:

Remove the `EliPositionPicker` import (line 5) and `EliPosition` type import (line 3).

Remove all Eli-related props from the Props interface (lines 14-63 — all the `allEliGenerated`, `generatingEli`, `confirmAndGenerateEli`, `generateMissingEli`, `hasExistingEli`, `missingEliCount`, `eliCancelledRef`, `showEliPositionPicker`, `setShowEliPositionPicker`, `eliPositionMode`, `setEliPositionMode`, `brandEliPosition`, `customEliPosition`, `setCustomEliPosition`, `eliPositionRef` props).

Remove the corresponding destructured props in the function signature (lines 82-125).

Remove "Step 4 — Add Eli" section entirely (lines 358-465 approximately).

- [ ] **Step 4: Delete Eli-specific files**

```bash
rm frontend/src/components/timeline/useEliPosition.ts
rm frontend/src/components/shared/EliPositionPicker.tsx
```

- [ ] **Step 5: Remove EliPositionPicker from CharacterSection.tsx**

In `frontend/src/components/settings/CharacterSection.tsx`:

Remove the `EliPositionPicker` import and the Eli position state (`eliPosition`, `setEliPosition`).

Remove the Eli position picker section in the JSX (around lines 742-749 and the useEffect that loads `eli_position` from brand).

- [ ] **Step 6: Verify frontend compiles**

```bash
cd frontend && npx tsc --noEmit
```

Fix any remaining references to removed Eli code.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Remove Eli overlay UI from timeline and settings"
```

---

### Task 9: End-to-end verification

**Files:** None (testing only)

- [ ] **Step 1: Start the dev server**

```bash
npm run dev
```

- [ ] **Step 2: Upload a reference thumbnail**

Navigate to Settings → Character section. Upload one or more reference thumbnail images using the new upload UI.

- [ ] **Step 3: Generate a thumbnail for an existing script**

In the timeline export panel, click "Recomposite Thumbnail". Verify:
- Base composite is generated (circles, labels, title — no Eli corner, no circle outlines)
- Gemini enhancement runs (check backend logs for "Gemini thumbnail enhancement complete")
- Final thumbnail shows glowing borders, Eli in one circle, punchy title

- [ ] **Step 4: Verify video rendering still works**

Render a preview scene. Verify:
- No EliOverlay errors in Remotion
- Video plays without the corner Eli overlay
- All other effects (zoom punch, subtitles, chapter indicators) still work

- [ ] **Step 5: Verify graceful fallback**

Delete all reference thumbnails from Settings. Recomposite again. Verify the base composite is used as the final thumbnail (no Gemini call).

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "Verify Eli vortex thumbnail system end-to-end"
```

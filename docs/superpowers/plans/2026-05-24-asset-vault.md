# Asset Vault Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save popup crop cutouts into a reusable image vault and expose a Settings browser for those assets.

**Architecture:** Add a small file-backed vault service that stores only final cleaned PNG cutouts under `data/projects/asset-vault/{characters,items}`. Filenames encode kind, descriptive label, and timestamp; the list API infers display metadata from file paths and filesystem timestamps.

**Tech Stack:** Python 3.12/FastAPI/Pillow backend, React 19/TypeScript/Tailwind/lucide frontend, pytest and Vite build verification.

---

### Task 1: Backend Vault Service and Popup Crop Hook

**Files:**
- Create: `backend/pipeline/asset_vault.py`
- Modify: `backend/pipeline/test_lab_popup_crop.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] Add failing pytest coverage showing `chroma_popup_crop_anchor` saves a cleaned PNG into `projects/asset-vault/characters/character_anchor_character_*.png`.
- [ ] Add failing pytest coverage showing `chroma_popup_crop_item_sheet` saves each cleaned item into `projects/asset-vault/items/item_<label>_*.png`.
- [ ] Implement `save_vault_image(kind, label, source_path)` with filename-only metadata and collision-safe timestamp suffixes.
- [ ] Call `save_vault_image` only after `_save_keyed_trimmed_cutout` writes the cleaned cutout.
- [ ] Run the targeted popup crop tests with `uv run --project backend pytest backend/tests/test_test_lab.py -k "popup_crop"`.

### Task 2: Vault Listing API

**Files:**
- Create: `backend/api/assets.py`
- Modify: `backend/api/__init__.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] Add failing API coverage for `GET /api/assets/vault` returning stored character/item PNGs with `kind`, `name`, `filename`, `url`, and `created_at`.
- [ ] Implement `list_vault_images(kind=None)` in `backend/pipeline/asset_vault.py`.
- [ ] Add the FastAPI router and include it in `backend/api/__init__.py`.
- [ ] Run the targeted API test with `uv run --project backend pytest backend/tests/test_test_lab.py -k "asset_vault"`.

### Task 3: Settings Vault Browser

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/settings/SettingsPage.tsx`
- Create: `frontend/src/components/settings/AssetVaultSection.tsx`

- [ ] Add frontend API types and `getAssetVaultImages(kind?)`.
- [ ] Add an `Asset Vault` Settings section under `Brand & Style`.
- [ ] Build a compact grid browser with All/Characters/Items filters, image thumbnails, inferred name, kind badge, and created date.
- [ ] Run `cd frontend && npm run build`.

### Task 4: Project Instructions and Final Verification

**Files:**
- Modify: `AGENTS.md`

- [ ] Add the project convention that cropped reusable cutouts are saved as filename-only PNGs in the asset vault.
- [ ] Run `uv run --project backend pytest backend/tests/test_test_lab.py -k "popup_crop or asset_vault"`.
- [ ] Run `cd frontend && npm run build`.
- [ ] Commit, push to `main`, run delegated review, fix findings, and repeat until LGTM.

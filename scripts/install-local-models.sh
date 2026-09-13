#!/usr/bin/env bash
# Provision the local model stack for Headless Hero's Local Models Mode.
#
# Installs and verifies three daemons plus their weights:
#   ollama     :11434  text
#   ComfyUI    :8188   images (GGUF via ComfyUI-GGUF, PyTorch MPS)
#   mlx-audio  :8770   voice
#
# Idempotent: every step is skipped when already satisfied. Pass --check to
# verify without installing anything (exits non-zero if something is missing).
#
# AI video is deliberately not covered — it stays on the cloud provider
# configured in Settings -> Visuals.

set -euo pipefail

LOCAL_ROOT="${HEADLESS_HERO_LOCAL_ROOT:-$HOME/.headless-hero-local}"
COMFY_DIR="$LOCAL_ROOT/ComfyUI"
ALLOWLIST="$HOME/.claude/apple/dangerous_allowed_domains.csv"

CHECK_ONLY=0
WITH_QWEN_IMAGE=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --with-qwen-image) WITH_QWEN_IMAGE=1 ;;
    *) echo "Unknown option: $arg"; echo "Usage: $0 [--check] [--with-qwen-image]"; exit 2 ;;
  esac
done

# Model pull specs. Keep these in sync with backend/integrations/local_models.py.
# The exact tags matter: Unsloth publishes the text GGUF as UD-Q4_K_M (Unsloth
# Dynamic), and mlx-audio needs MLX-converted voice repos rather than the
# upstream PyTorch ones.
TEXT_MODEL="hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_M"
VOICE_REPO="whitelabel/mlx-q6-higgs-tts-3-4b"

# Default image model (fastest by a wide margin — see docs/local-models-benchmarks.md).
FLUX_REPO="Comfy-Org/vae-text-encorder-for-flux-klein-4b"
FLUX_UNET="split_files/diffusion_models/flux-2-klein-4b.safetensors"
FLUX_CLIP="split_files/text_encoders/qwen_3_4b.safetensors"
FLUX_VAE="split_files/vae/flux2-vae.safetensors"

# Optional high-fidelity image model, ~24x slower on this hardware. Installed
# only with --with-qwen-image.
QWEN_IMAGE_REPO="unsloth/Qwen-Image-Edit-2511-GGUF"
QWEN_IMAGE_FILE="qwen-image-edit-2511-Q4_K_M.gguf"
QWEN_COMPANION_REPO="Comfy-Org/Qwen-Image_ComfyUI"
QWEN_CLIP="split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"
QWEN_VAE="split_files/vae/qwen_image_vae.safetensors"

# Hosts this stack needs. Apple's proxy blocks everything not listed in the
# allowlist CSV; huggingface.co and its CDN hosts are usually already present.
REQUIRED_DOMAINS=(
  registry.npmjs.org
  ollama.com
  registry.ollama.ai
  hf.co
  pypi.org
  files.pythonhosted.org
  formulae.brew.sh
  ghcr.io
  pkg-containers.githubusercontent.com
  objects.githubusercontent.com
  raw.githubusercontent.com
  codeload.github.com
)

say()  { printf '\033[1;36m==>\033[0m %s\n' "$1"; }
ok()   { printf '    \033[0;32mok\033[0m   %s\n' "$1"; }
warn() { printf '    \033[0;33mwarn\033[0m %s\n' "$1"; }
fail() { printf '    \033[0;31mfail\033[0m %s\n' "$1"; }

# -f so curl fails on HTTP >= 400. Without it curl exits 0 for an error page
# (including a proxy's 502), which would report a dead daemon as healthy.
probe() { curl -sf -o /dev/null --max-time 3 "$1" 2>/dev/null; }

# ---------------------------------------------------------------- allowlist
say "Checking the proxy domain allowlist"
if [ ! -f "$ALLOWLIST" ]; then
  warn "no allowlist at $ALLOWLIST — assuming unrestricted network"
else
  for domain in "${REQUIRED_DOMAINS[@]}"; do
    if grep -qE "^${domain}( |$|#)" "$ALLOWLIST"; then
      continue
    fi
    if [ "$CHECK_ONLY" = "1" ]; then
      fail "$domain is not allowlisted"
      MISSING=1
    else
      echo "${domain} # Added $(date +%Y-%m-%d) - Headless Hero local models" >> "$ALLOWLIST"
      ok "allowlisted $domain"
    fi
  done
  ok "allowlist checked"
fi

# ------------------------------------------------------------------- ollama
say "Setting up ollama (text)"
if ! command -v ollama > /dev/null 2>&1; then
  if [ "$CHECK_ONLY" = "1" ]; then fail "ollama is not installed"; MISSING=1; else
    brew install ollama
    ok "installed ollama"
  fi
else
  ok "ollama present"
fi

if command -v ollama > /dev/null 2>&1; then
  if ! probe http://127.0.0.1:11434/api/tags; then
    if [ "$CHECK_ONLY" = "1" ]; then fail "ollama is not running"; MISSING=1; else
      ollama serve > /tmp/ollama.log 2>&1 &
      for _ in $(seq 1 30); do probe http://127.0.0.1:11434/api/tags && break; sleep 1; done
      ok "started ollama serve"
    fi
  else
    ok "ollama serving"
  fi

  if ollama list 2>/dev/null | grep -q "$(echo "$TEXT_MODEL" | cut -d: -f1 | sed 's#hf.co/##')"; then
    ok "text model present"
  elif [ "$CHECK_ONLY" = "1" ]; then
    fail "text model $TEXT_MODEL is not pulled"; MISSING=1
  else
    say "Pulling $TEXT_MODEL (about 16 GB)"
    ollama pull "$TEXT_MODEL"
    ok "pulled text model"
  fi
fi

# ------------------------------------------------------------------ ComfyUI
say "Setting up ComfyUI (images)"
if [ ! -d "$COMFY_DIR" ]; then
  if [ "$CHECK_ONLY" = "1" ]; then fail "ComfyUI is not installed at $COMFY_DIR"; MISSING=1; else
    mkdir -p "$LOCAL_ROOT"
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY_DIR"
    ok "cloned ComfyUI"
  fi
else
  ok "ComfyUI present"
fi

if [ -d "$COMFY_DIR" ] && [ "$CHECK_ONLY" != "1" ]; then
  if [ ! -d "$COMFY_DIR/custom_nodes/ComfyUI-GGUF" ]; then
    git clone --depth 1 https://github.com/city96/ComfyUI-GGUF.git "$COMFY_DIR/custom_nodes/ComfyUI-GGUF"
    ok "installed ComfyUI-GGUF"
  else
    ok "ComfyUI-GGUF present"
  fi

  if [ ! -d "$COMFY_DIR/.venv" ]; then
    (cd "$COMFY_DIR" && uv venv --python 3.12)
    ok "created ComfyUI venv"
  fi
  (cd "$COMFY_DIR" && uv pip install -q -r requirements.txt)
  (cd "$COMFY_DIR" && uv pip install -q gguf huggingface_hub)
  ok "ComfyUI dependencies installed"

  say "Fetching image weights"
  mkdir -p "$COMFY_DIR/models/diffusion_models" "$COMFY_DIR/models/unet" \
           "$COMFY_DIR/models/text_encoders" "$COMFY_DIR/models/vae"

  # hf, not huggingface-cli: the old CLI is deprecated and exits 0 without
  # downloading anything, which silently produces an empty model directory.
  hf_get() {  # repo, path-in-repo, destination dir
    local repo="$1" path="$2" dest="$3" name
    name="$(basename "$path")"
    if [ -f "$dest/$name" ]; then ok "$name present"; return 0; fi
    (cd "$COMFY_DIR" && uv run --with huggingface_hub hf download "$repo" "$path" --local-dir /tmp/hh-dl)
    mv "/tmp/hh-dl/$path" "$dest/$name"
    ok "downloaded $name"
  }

  hf_get "$FLUX_REPO" "$FLUX_UNET" "$COMFY_DIR/models/diffusion_models"
  hf_get "$FLUX_REPO" "$FLUX_CLIP" "$COMFY_DIR/models/text_encoders"
  hf_get "$FLUX_REPO" "$FLUX_VAE"  "$COMFY_DIR/models/vae"

  if [ "$WITH_QWEN_IMAGE" = "1" ]; then
    say "Fetching Qwen-Image-Edit weights (optional, ~21 GB, much slower to run)"
    if [ ! -f "$COMFY_DIR/models/unet/$QWEN_IMAGE_FILE" ]; then
      (cd "$COMFY_DIR" && uv run --with huggingface_hub hf download "$QWEN_IMAGE_REPO" \
        --include "*Q4_K_M*" --local-dir models/unet)
      ok "downloaded $QWEN_IMAGE_FILE"
    else
      ok "$QWEN_IMAGE_FILE present"
    fi
    hf_get "$QWEN_COMPANION_REPO" "$QWEN_CLIP" "$COMFY_DIR/models/text_encoders"
    hf_get "$QWEN_COMPANION_REPO" "$QWEN_VAE"  "$COMFY_DIR/models/vae"
  else
    ok "skipping Qwen-Image-Edit (pass --with-qwen-image to install it)"
  fi
  rm -rf /tmp/hh-dl
fi

# ---------------------------------------------------------------- mlx-audio
say "Setting up mlx-audio (voice)"
if ! command -v mlx_audio.server > /dev/null 2>&1 && [ ! -x "$HOME/.local/bin/mlx_audio.server" ]; then
  if [ "$CHECK_ONLY" = "1" ]; then fail "mlx-audio is not installed"; MISSING=1; else
    # The server entrypoint needs uvicorn/fastapi, and webrtcvad's C extension
    # does not build against this machine's SDK — webrtcvad-wheels ships a
    # prebuilt arm64 binary instead. misaki is required by Kokoro.
    uv tool install --force --prerelease=allow \
      --with uvicorn --with fastapi --with python-multipart \
      --with webrtcvad-wheels --with misaki \
      mlx-audio
    ok "installed mlx-audio"
  fi
else
  ok "mlx-audio present"
fi

if [ "$CHECK_ONLY" != "1" ]; then
  say "Fetching voice weights (about 4 GB)"
  uv run --with huggingface_hub hf download "$VOICE_REPO" > /dev/null || \
    warn "voice weight prefetch failed; mlx-audio will fetch on first use"
  ok "voice weights ready"
fi

# ffmpeg backs local TTS transcoding and the existing audio-export path.
if ! command -v ffmpeg > /dev/null 2>&1; then
  if [ "$CHECK_ONLY" = "1" ]; then fail "ffmpeg is not installed"; MISSING=1; else
    brew install ffmpeg
    ok "installed ffmpeg"
  fi
else
  ok "ffmpeg present"
fi

# ------------------------------------------------------------------- verify
# Start the image and voice daemons before verifying, otherwise a successful
# fresh install reports "not running" and exits non-zero. ollama was already
# started above.
if [ "$CHECK_ONLY" != "1" ]; then
  if [ -d "$COMFY_DIR/.venv" ] && ! probe http://127.0.0.1:8188/system_stats; then
    ( cd "$COMFY_DIR" && ./.venv/bin/python main.py --port 8188 > /tmp/headless-hero-comfyui.log 2>&1 & )
    for _ in $(seq 1 60); do probe http://127.0.0.1:8188/system_stats && break; sleep 1; done
  fi
  if [ -x "$HOME/.local/bin/mlx_audio.server" ] && ! probe http://127.0.0.1:8770/v1/models; then
    ( "$HOME/.local/bin/mlx_audio.server" --host 127.0.0.1 --port 8770 > /tmp/headless-hero-mlx-audio.log 2>&1 & )
    for _ in $(seq 1 45); do probe http://127.0.0.1:8770/v1/models && break; sleep 1; done
  fi
fi

say "Verifying daemons"
STATUS=0
printf '    %-12s %-30s %s\n' DAEMON URL STATUS
for entry in "ollama|http://127.0.0.1:11434/api/tags" \
             "comfyui|http://127.0.0.1:8188/system_stats" \
             "mlx-audio|http://127.0.0.1:8770/v1/models"; do
  name="${entry%%|*}"; url="${entry#*|}"
  if probe "$url"; then
    printf '    %-12s %-30s \033[0;32mhealthy\033[0m\n' "$name" "${url%/*}"
  else
    printf '    %-12s %-30s \033[0;33mnot running\033[0m\n' "$name" "${url%/*}"
    STATUS=1
  fi
done

if [ -d "$COMFY_DIR/models" ]; then
  say "On-disk model sizes"
  du -sh "$COMFY_DIR/models"/* 2>/dev/null | sed 's/^/    /' || true
fi
if command -v ollama > /dev/null 2>&1; then
  ollama list 2>/dev/null | sed 's/^/    /' || true
fi

if [ "${MISSING:-0}" = "1" ]; then
  fail "Some components are missing. Re-run without --check to install them."
  exit 1
fi
if [ "$STATUS" != "0" ]; then
  warn "Not every daemon is running. Start them, or let the mac launcher start them on next app launch."
  exit "$STATUS"
fi
say "Local model stack is ready."

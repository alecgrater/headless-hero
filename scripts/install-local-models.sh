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
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

# Model pull specs. Keep these in sync with backend/integrations/local_models.py.
TEXT_MODEL="hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_M"
IMAGE_REPO_QWEN="unsloth/Qwen-Image-Edit-2511-GGUF"
IMAGE_FILE_QWEN="Qwen-Image-Edit-2511-Q4_K_M.gguf"
IMAGE_REPO_FLUX="black-forest-labs/FLUX.2-klein-4B"
VOICE_REPO="whitelabel/mlx-q6-higgs-tts-3-4b"

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

probe() { curl -s -o /dev/null --max-time 3 "$1" 2>/dev/null; }

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

  say "Fetching image weights (about 27 GB for both models)"
  mkdir -p "$COMFY_DIR/models/unet" "$COMFY_DIR/models/clip" "$COMFY_DIR/models/vae"
  if [ ! -f "$COMFY_DIR/models/unet/$IMAGE_FILE_QWEN" ]; then
    (cd "$COMFY_DIR" && uv run huggingface-cli download "$IMAGE_REPO_QWEN" "$IMAGE_FILE_QWEN" \
      --local-dir models/unet)
    ok "downloaded $IMAGE_FILE_QWEN"
  else
    ok "$IMAGE_FILE_QWEN present"
  fi
  if [ ! -d "$COMFY_DIR/models/diffusion_models/FLUX.2-klein-4B" ]; then
    (cd "$COMFY_DIR" && uv run huggingface-cli download "$IMAGE_REPO_FLUX" \
      --local-dir "models/diffusion_models/FLUX.2-klein-4B") || \
      warn "FLUX.2-klein-4B download failed (gated repo needs `huggingface-cli login`)"
  else
    ok "FLUX.2-klein-4B present"
  fi
fi

# ---------------------------------------------------------------- mlx-audio
say "Setting up mlx-audio (voice)"
if ! command -v mlx_audio.server > /dev/null 2>&1 && ! uv tool list 2>/dev/null | grep -q mlx-audio; then
  if [ "$CHECK_ONLY" = "1" ]; then fail "mlx-audio is not installed"; MISSING=1; else
    uv tool install --force mlx-audio --prerelease=allow
    ok "installed mlx-audio"
  fi
else
  ok "mlx-audio present"
fi

if [ "$CHECK_ONLY" != "1" ]; then
  say "Fetching voice weights (about 4 GB)"
  uv run --with huggingface_hub huggingface-cli download "$VOICE_REPO" > /dev/null || \
    warn "voice weight prefetch failed; mlx-audio will fetch on first use"
  ok "voice weights ready"
fi

# ------------------------------------------------------------------- verify
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

"""Local image generation through a ComfyUI server.

Mirrors the google_image_client surface so integrations.image_client can
dispatch to either backend without adapters. Reference images are uploaded to
ComfyUI, then injected into a workflow graph loaded from backend/comfy_workflows.

The workflow files carry placeholder tokens that are substituted per call:
__PROMPT__, __WIDTH__, __HEIGHT__, __SEED__, plus __MODEL__ / __CLIP__ / __VAE__
which the provisioning script fills with the installed weight filenames.
"""

import json
import logging
import os
import random
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from config import IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.local_models import active_model
from integrations.usage_tracker import record_usage
from pipeline.local_runtime import daemon_url, ensure_daemon, hold

logger = logging.getLogger(__name__)

WORKFLOW_DIR = Path(__file__).resolve().parent.parent / "comfy_workflows"


@dataclass(frozen=True)
class WorkflowSpec:
    """How one local image model's workflow graph is parameterised.

    reference_mode says how reference images attach to the graph, because the
    two supported models condition on references in structurally different ways:

    - "encoder_slots": Qwen-Image-Edit's TextEncodeQwenImageEditPlus takes
      image1..imageN inputs directly on the prompt encoder.
    - "reference_latent": FLUX.2 encodes each reference through the VAE and
      chains ReferenceLatent nodes onto the positive conditioning.
    """

    filename: str
    reference_mode: str
    max_references: int


WORKFLOW_SPECS: dict[str, WorkflowSpec] = {
    "qwen-image-edit-2511": WorkflowSpec("qwen_image_edit_2511.json", "encoder_slots", 3),
    "flux2-klein-4b": WorkflowSpec("flux2_klein_4b.json", "reference_latent", 3),
}

POLL_INTERVAL_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 900.0

# Graph conventions shared by every committed workflow file.
PROMPT_NODE_ID = "6"
SAMPLER_NODE_ID = "3"
VAE_NODE_ID = "12"


def _http() -> httpx.Client:
    return httpx.Client(timeout=60.0)


def _upload_image(path: str) -> str:
    """Upload one reference image to ComfyUI and return its server-side name."""
    name = Path(path).name
    with open(path, "rb") as handle:
        response = _http().post(
            f"{daemon_url('comfyui')}/upload/image",
            files={"image": (name, handle, "image/png")},
            data={"overwrite": "true"},
        )
    response.raise_for_status()
    return response.json().get("name", name)


def _workflow_spec(model_id: str) -> WorkflowSpec:
    spec = WORKFLOW_SPECS.get(model_id)
    if spec is None:
        raise RuntimeError(f"No ComfyUI workflow registered for local image model {model_id!r}")
    return spec


def _load_workflow(spec: WorkflowSpec) -> dict:
    path = WORKFLOW_DIR / spec.filename
    if not path.exists():
        raise RuntimeError(f"ComfyUI workflow file is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _attach_references(graph: dict, spec: WorkflowSpec, reference_names: list[str]) -> None:
    """Wire uploaded reference images into the graph for this model's scheme."""
    if spec.reference_mode == "encoder_slots":
        for index, name in enumerate(reference_names):
            node_id = f"ref_{index}"
            graph[node_id] = {"class_type": "LoadImage", "inputs": {"image": name}}
            graph[PROMPT_NODE_ID]["inputs"][f"image{index + 1}"] = [node_id, 0]
        return

    if spec.reference_mode == "reference_latent":
        # Each reference is VAE-encoded and chained onto the positive
        # conditioning, so the final ReferenceLatent carries every reference.
        conditioning: list = [PROMPT_NODE_ID, 0]
        for index, name in enumerate(reference_names):
            load_id, encode_id, ref_id = f"ref_{index}", f"refenc_{index}", f"reflat_{index}"
            graph[load_id] = {"class_type": "LoadImage", "inputs": {"image": name}}
            graph[encode_id] = {
                "class_type": "VAEEncode",
                "inputs": {"pixels": [load_id, 0], "vae": [VAE_NODE_ID, 0]},
            }
            graph[ref_id] = {
                "class_type": "ReferenceLatent",
                "inputs": {"conditioning": conditioning, "latent": [encode_id, 0]},
            }
            conditioning = [ref_id, 0]
        graph[SAMPLER_NODE_ID]["inputs"]["positive"] = conditioning
        return

    raise RuntimeError(f"Unknown reference mode {spec.reference_mode!r}")


def _substitute(
    workflow: dict,
    spec: WorkflowSpec,
    *,
    prompt: str,
    width: int,
    height: int,
    seed: int,
    reference_names: list[str],
) -> dict:
    """Replace placeholder tokens in a workflow graph and wire reference loaders.

    The numeric placeholders are quoted in the JSON files, so replacing the
    quoted form yields real ints rather than strings — ComfyUI rejects string
    widths. The prompt is escaped through json.dumps so quotes in a visual
    prompt cannot break the graph.

    References beyond the model's limit are dropped with a warning rather than
    silently producing an invalid graph.
    """
    raw = json.dumps(workflow)
    raw = raw.replace("__PROMPT__", json.dumps(prompt)[1:-1])
    raw = raw.replace('"__WIDTH__"', str(int(width)))
    raw = raw.replace('"__HEIGHT__"', str(int(height)))
    raw = raw.replace('"__SEED__"', str(int(seed)))
    graph = json.loads(raw)

    if len(reference_names) > spec.max_references:
        logger.warning(
            "Local image model accepts %d reference images; dropping %d extra",
            spec.max_references, len(reference_names) - spec.max_references,
        )
        reference_names = reference_names[:spec.max_references]

    _attach_references(graph, spec, reference_names)
    return graph


def _await_image(prompt_id: str, timeout_seconds: float) -> bytes:
    """Poll ComfyUI history until the prompt completes, then fetch the PNG."""
    deadline = time.monotonic() + timeout_seconds
    client = _http()
    while True:
        response = client.get(f"{daemon_url('comfyui')}/history/{prompt_id}")
        response.raise_for_status()
        history = response.json() or {}
        entry = history.get(prompt_id)
        if entry:
            outputs = entry.get("outputs", {})
            for node_output in outputs.values():
                images = node_output.get("images") or []
                if images:
                    image = images[0]
                    fetched = client.get(
                        f"{daemon_url('comfyui')}/view"
                        f"?filename={image['filename']}"
                        f"&subfolder={image.get('subfolder', '')}"
                        f"&type={image.get('type', 'output')}"
                    )
                    fetched.raise_for_status()
                    return fetched.content
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"ComfyUI did not return an image within {timeout_seconds:.0f}s (prompt_id={prompt_id})"
            )
        time.sleep(POLL_INTERVAL_SECONDS)


def transform_with_references(
    prompt: str,
    image_paths: list[str],
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    script_id: str | None = None,
) -> str:
    """Generate one image locally, optionally conditioned on reference images.

    Returns the path to a temp PNG, matching google_image_client's contract.
    """
    ensure_daemon("comfyui")
    model = active_model("image")
    spec = _workflow_spec(model.id)
    timeout_seconds = float(os.environ.get("LOCAL_IMAGE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))

    with hold("image"):
        reference_names = [_upload_image(path) for path in image_paths]
        graph = _substitute(
            _load_workflow(spec),
            spec,
            prompt=prompt,
            width=width,
            height=height,
            seed=random.randint(1, 2**31 - 1),
            reference_names=reference_names,
        )
        logger.info(
            "Generating image via local ComfyUI (model=%s, %dx%d, refs=%d)",
            model.id, width, height, len(reference_names),
        )
        started = time.monotonic()
        response = _http().post(f"{daemon_url('comfyui')}/prompt", json={"prompt": graph})
        response.raise_for_status()
        prompt_id = response.json()["prompt_id"]
        png_bytes = _await_image(prompt_id, timeout_seconds)
        elapsed = time.monotonic() - started

    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    handle.write(png_bytes)
    handle.close()

    record_usage(
        service="local_image",
        operation="generate",
        model=model.id,
        cost_estimate=0.0,
        script_id=script_id,
    )
    logger.info("Local image generated in %.1fs via %s -> %s", elapsed, model.id, handle.name)
    return handle.name


def generate_image(
    prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    reference_image_path: str | None = None,
    style_reference_path: str | None = None,
    original_prompt: str | None = None,
    script_id: str | None = None,
) -> str:
    """Generate one scene image locally.

    original_prompt exists for signature parity with the Google client, which
    uses it to retry past content filters. Local models have no such filter, so
    it is accepted and ignored.
    """
    references = [p for p in (reference_image_path, style_reference_path) if p]
    return transform_with_references(
        prompt,
        references,
        width=width,
        height=height,
        script_id=script_id,
    )

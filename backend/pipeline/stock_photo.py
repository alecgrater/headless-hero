"""Stock photo pipeline — searches Pexels and stores images for scenes."""

import logging
import shutil
from pathlib import Path

from config import DATA_DIR
from integrations.pexels_client import search_and_download

logger = logging.getLogger(__name__)


def generate_stock_photo(script_id: str, scene_id: str, search_query: str) -> str:
    """Download a stock photo for a scene and store it in the project images dir.

    Returns the web-relative URL for the stored image.
    """
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    dest = images_dir / f"{scene_id}.png"

    if dest.exists():
        logger.info("Stock photo already exists: %s", dest)
        return f"/static/projects/{script_id}/images/{scene_id}.png"

    tmp_path = search_and_download(search_query)
    if not tmp_path:
        raise RuntimeError(f"No stock photo found for query: {search_query!r}")

    shutil.move(tmp_path, str(dest))
    logger.info("Stock photo stored: %s → %s", search_query, dest)
    return f"/static/projects/{script_id}/images/{scene_id}.png"

"""Thumbnail pipeline — composite title card lookup.

When the title_cards modifier is active and a composite title card exists,
it is used directly as the thumbnail.
"""

import logging
import shutil

from config import DATA_DIR

logger = logging.getLogger(__name__)


def get_composite_thumbnail(script_id: str) -> str | None:
    """Check if a composite title card exists and return its web path if so."""
    composite = DATA_DIR / "projects" / script_id / "images" / "composite_title_card.png"
    if composite.exists():
        # Copy to thumbnail location
        thumbs_dir = DATA_DIR / "projects" / script_id / "renders" / "thumbnails"
        thumbs_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumbs_dir / "0.png"
        shutil.copy2(str(composite), str(thumb_path))
        return f"/static/projects/{script_id}/renders/thumbnails/0.png"
    return None

"""Google Images scraper — downloads real photos for montage beat frames.

Scrapes Google Images search results, downloads the best candidate,
and resizes/center-crops to the target dimensions.

Falls back gracefully: returns None on any failure so the caller can
fall through to Gemini AI generation.
"""

import logging
import re
from pathlib import Path

import httpx
from PIL import Image

from config import VIDEO_HEIGHT, VIDEO_WIDTH

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Regex to extract image URLs from Google Images HTML response
_IMG_URL_RE = re.compile(
    r'(?:imgurl|ou)(?:=|":"|%3D)(https?://[^&"\\]+\.(?:jpg|jpeg|png|webp))',
    re.IGNORECASE,
)


def _extract_image_urls(html: str) -> list[str]:
    """Extract candidate image URLs from Google Images HTML."""
    urls = _IMG_URL_RE.findall(html)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _download_image(url: str, timeout: float = 10.0) -> bytes | None:
    """Download an image from a URL, return bytes or None on failure."""
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 1000:
            return resp.content
    except Exception as e:
        logger.debug("Failed to download %s: %s", url, e)
    return None


def _resize_center_crop(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize and center-crop an image to the target dimensions."""
    target_ratio = width / height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Image is wider — fit height, crop width
        new_height = height
        new_width = int(height * img_ratio)
    else:
        # Image is taller — fit width, crop height
        new_width = width
        new_height = int(width / img_ratio)

    img = img.resize((new_width, new_height), Image.LANCZOS)

    # Center crop
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return img.crop((left, top, left + width, top + height))


def scrape_google_image_sync(
    query: str,
    output_path: str,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
) -> str | None:
    """Search Google Images, download top result, resize to target dimensions.

    Returns output_path on success, None on failure.
    Uses .prompt marker file for caching (same pattern as AI-generated images).
    """
    out = Path(output_path)
    prompt_marker = out.with_suffix(".prompt")

    # Cache check: if output exists and query matches, skip
    if out.exists() and prompt_marker.exists():
        cached = prompt_marker.read_text(encoding="utf-8").strip()
        if cached == query:
            logger.info("Google image cache hit for query %r", query)
            return output_path

    logger.info("Scraping Google Images for: %r", query)

    try:
        search_url = f"https://www.google.com/search?q={httpx.QueryParams({'q': query}).get('q', query)}&tbm=isch&tbs=isz:l"
        # Actually build URL properly
        params = {"q": query, "tbm": "isch", "tbs": "isz:l"}
        resp = httpx.get(
            "https://www.google.com/search",
            params=params,
            headers=_HEADERS,
            timeout=10.0,
            follow_redirects=True,
        )

        if resp.status_code != 200:
            logger.warning("Google Images returned status %d for query %r", resp.status_code, query)
            return None

        urls = _extract_image_urls(resp.text)
        if not urls:
            logger.warning("No image URLs found for query %r", query)
            return None

        # Try downloading candidates until one succeeds
        for url in urls[:5]:
            img_bytes = _download_image(url)
            if img_bytes is None:
                continue

            try:
                from io import BytesIO
                img = Image.open(BytesIO(img_bytes)).convert("RGB")

                # Skip tiny images
                if img.width < 400 or img.height < 300:
                    continue

                img = _resize_center_crop(img, width, height)

                out.parent.mkdir(parents=True, exist_ok=True)
                img.save(str(out), "PNG")
                prompt_marker.write_text(query, encoding="utf-8")
                logger.info("Saved Google image for %r → %s", query, output_path)
                return output_path

            except Exception as e:
                logger.debug("Failed to process image from %s: %s", url, e)
                continue

        logger.warning("All candidates failed for query %r", query)
        return None

    except Exception as e:
        logger.warning("Google Images scrape failed for %r: %s", query, e)
        return None

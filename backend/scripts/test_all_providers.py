"""Generate one image from each provider (Pexels, Gemini, Twitch) and save to Downloads.

Run from the backend directory:
    uv run python scripts/test_all_providers.py
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select
from database import engine
from models.settings import AppSetting

DOWNLOADS = Path.home() / "Downloads" / "headless-hero-provider-test"


def load_keys():
    """Load API keys from the app's SQLite DB into os.environ."""
    with Session(engine) as session:
        settings = session.exec(select(AppSetting)).all()
        for s in settings:
            if s.value:
                os.environ.setdefault(s.key, s.value)


def test_pexels():
    """Fetch a real stock photo from Pexels."""
    print("\n[PEXELS] Searching for 'mountain landscape sunrise'...")
    from integrations.pexels_client import search_and_download

    tmp_path = search_and_download("mountain landscape sunrise")
    if not tmp_path:
        print("[PEXELS] FAILED — no results returned")
        return False

    dest = DOWNLOADS / "stock_photo_pexels.jpg"
    shutil.move(tmp_path, str(dest))
    size_kb = dest.stat().st_size / 1024
    print(f"[PEXELS] SUCCESS — saved to {dest} ({size_kb:.0f} KB)")
    return True


def test_gemini():
    """Generate an AI image via Gemini."""
    print("\n[GEMINI] Generating 'a futuristic robot reading a book in a library'...")
    from integrations.image_client import generate_image

    tmp_path = generate_image(
        "a futuristic robot reading a book in a cozy library, digital illustration, vibrant colors",
        width=1920,
        height=1080,
    )

    dest = DOWNLOADS / "ai_generated_gemini.png"
    shutil.move(tmp_path, str(dest))
    size_kb = dest.stat().st_size / 1024
    print(f"[GEMINI] SUCCESS — saved to {dest} ({size_kb:.0f} KB)")
    return True


def test_twitch():
    """Download a gameplay clip from Twitch."""
    print("\n[TWITCH] Looking up 'Minecraft' and downloading a clip...")
    from integrations.twitch_client import lookup_game, search_clips, filter_clips, search_vods
    from integrations.gameplay_downloader import download_clip, download_vod_segment

    game = lookup_game("Minecraft")
    if not game:
        print("[TWITCH] FAILED — game not found on Twitch")
        return False
    print(f"[TWITCH] Found game: {game['name']} (id={game['id']})")

    # Prefer clips (guaranteed correct game)
    clips = search_clips(game["id"])
    clips = filter_clips(clips, "Minecraft")
    if clips:
        print(f"[TWITCH] Found {len(clips)} clips after filtering. First 5:")
        for i, c in enumerate(clips[:5]):
            print(f"         {i+1}. \"{c.get('title', '?')}\" by {c.get('broadcaster_name', '?')} — views={c.get('view_count', 0)} — {c['url']}")

        clip = clips[0]
        print(f"\n[TWITCH] Downloading clip: \"{clip.get('title', '?')}\"")
        print(f"         URL: {clip['url']}")
        print(f"         Broadcaster: {clip.get('broadcaster_name', '?')}")
        print(f"         Game ID on clip: {clip.get('game_id', '?')} (searched for: {game['id']})")

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.close()
        os.unlink(tmp.name)
        download_clip(clip["url"], tmp.name)
    else:
        print("[TWITCH] No clips found, falling back to VODs...")
        vods = search_vods(game["id"])
        if not vods:
            print("[TWITCH] FAILED — no VODs found either")
            return False
        print(f"[TWITCH] Found {len(vods)} VODs, downloading 5s from: {vods[0]['url']}")

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.close()
        os.unlink(tmp.name)
        download_vod_segment(vods[0]["url"], 5.0, tmp.name)

    # yt-dlp may add format suffix — find the actual output file
    output = Path(tmp.name)
    if not output.exists() or output.stat().st_size == 0:
        parent = output.parent
        stem = output.stem
        candidates = list(parent.glob(f"{stem}*"))
        actual = next((c for c in candidates if c.stat().st_size > 0), None)
        if actual:
            output = actual
        else:
            print("[TWITCH] FAILED — yt-dlp produced no output")
            return False

    dest = DOWNLOADS / "gameplay_video_twitch.mp4"
    shutil.move(str(output), str(dest))
    size_kb = dest.stat().st_size / 1024
    print(f"[TWITCH] SUCCESS — saved to {dest} ({size_kb:.0f} KB)")
    print(f"         Open the clip URL above in a browser to verify it matches the downloaded video.")
    return True


def main():
    print("=" * 60)
    print("HEADLESS HERO — Provider Test")
    print("=" * 60)
    print(f"Output folder: {DOWNLOADS}")

    DOWNLOADS.mkdir(parents=True, exist_ok=True)

    print("\nLoading API keys from database...")
    load_keys()

    results = {}

    # --- Pexels ---
    try:
        results["pexels"] = test_pexels()
    except Exception as e:
        print(f"[PEXELS] ERROR — {e}")
        results["pexels"] = False

    # --- Gemini ---
    try:
        results["gemini"] = test_gemini()
    except Exception as e:
        print(f"[GEMINI] ERROR — {e}")
        results["gemini"] = False

    # --- Twitch ---
    try:
        results["twitch"] = test_twitch()
    except Exception as e:
        print(f"[TWITCH] ERROR — {e}")
        results["twitch"] = False

    # --- Summary ---
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for provider, success in results.items():
        status = "PASS" if success else "FAIL"
        icon = "✓" if success else "✗"
        print(f"  {icon} {provider.upper():10s} {status}")

    passed = sum(results.values())
    total = len(results)
    print(f"\n{passed}/{total} providers working.")

    if passed == total:
        print(f"\nAll files saved to: {DOWNLOADS}/")
        print("  - stock_photo_pexels.jpg    (real photo from Pexels)")
        print("  - ai_generated_gemini.png   (AI-generated via Gemini)")
        print("  - gameplay_video_twitch.mp4 (Twitch VOD clip)")
    else:
        print("\nCheck the errors above. Missing API keys? Add them in Settings → API Keys.")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

from pathlib import Path

from PIL import Image

from integrations.google_image_client import GoogleBatchImageResult
from pipeline import image_gen


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2, 2), "red").save(path)


def test_generate_batch_with_google_batch_routes_eligible_scene(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    generated = tmp_path / "generated.png"
    _write_png(generated)
    captured_requests = []

    def fake_batch(requests, script_id):
        captured_requests.extend(requests)
        return [GoogleBatchImageResult(key=requests[0].key, image_path=str(generated))]

    monkeypatch.setattr(image_gen, "generate_images_batch", fake_batch)

    results = image_gen.generate_batch_with_google_batch(
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "A bright classroom",
                "visual_mode": "full_frame",
                "contains_person": False,
            }
        ],
        script_id="script-1",
    )

    assert len(captured_requests) == 1
    assert captured_requests[0].key == "scene_001"
    assert captured_requests[0].prompt
    assert results[0]["image_url"] == "/static/projects/script-1/images/scene_001.png"
    assert (tmp_path / "projects" / "script-1" / "images" / "scene_001.png").exists()
    assert (tmp_path / "projects" / "script-1" / "images" / "scene_001.prompt").exists()


def test_generate_batch_with_google_batch_keeps_layered_mode_standard(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    calls = {"batch": 0, "standard": 0}

    def fake_batch(*_args, **_kwargs):
        calls["batch"] += 1
        return []

    def fake_standard(scene, script_id, width, height, style_guide):
        calls["standard"] += 1
        return {
            "scene_id": scene["scene_id"],
            "image_url": None,
            "frame_urls": [],
            "video_url": "",
            "prompt_used": None,
            "error": None,
        }

    monkeypatch.setattr(image_gen, "generate_images_batch", fake_batch)
    monkeypatch.setattr(image_gen, "_generate_one_scene", fake_standard)

    results = image_gen.generate_batch_with_google_batch(
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "A popup sequence",
                "visual_mode": "popup_sequence",
                "visual_layers": [{"id": "item_1", "prompt": "An object"}],
            }
        ],
        script_id="script-1",
    )

    assert calls == {"batch": 0, "standard": 1}
    assert results[0]["scene_id"] == "scene_001"



def test_single_directive_full_frame_scene_goes_through_google_batch(monkeypatch, tmp_path):
    # Post-processing gives most full_frame scenes exactly one directive; it is one
    # independent image, so it must not push the scene onto the full-price path.
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    generated = tmp_path / "generated.png"
    _write_png(generated)
    captured_requests = []

    def fake_batch(requests, script_id):
        captured_requests.extend(requests)
        return [GoogleBatchImageResult(key=requests[0].key, image_path=str(generated))]

    def fail_standard(*_args, **_kwargs):
        raise AssertionError("single-directive scene must not use the standard path")

    monkeypatch.setattr(image_gen, "generate_images_batch", fake_batch)
    monkeypatch.setattr(image_gen, "_generate_one_scene", fail_standard)

    results = image_gen.generate_batch_with_google_batch(
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "A radar room",
                "visual_mode": "full_frame",
                "frame_directives": [
                    {"prompt": "A dim radar scope glowing green", "source": "ai_generated", "reference_previous": False}
                ],
            }
        ],
        script_id="script-1",
    )

    assert [request.key for request in captured_requests] == ["scene_001"]
    # The scene prompt wins (it is what the render phase uses); the directive is a copy.
    assert captured_requests[0].prompt.endswith("A radar room")
    assert results[0]["image_url"] == "/static/projects/script-1/images/scene_001.png"
    assert results[0]["frame_urls"] == []


def test_multi_directive_full_frame_scene_stays_standard():
    # Two or more directives render as a sequence whose later frames anchor on the
    # earlier ones, which Batch cannot express.
    scene = {
        "scene_id": "scene_001",
        "visual_prompt": "A radar room",
        "visual_mode": "full_frame",
        "frame_directives": [
            {"prompt": "First", "source": "ai_generated", "reference_previous": False},
            {"prompt": "Second", "source": "ai_generated", "reference_previous": True},
        ],
    }
    assert image_gen._is_google_batch_eligible(scene) is False
    assert image_gen._is_google_batch_eligible({**scene, "frame_directives": scene["frame_directives"][:1]}) is True
    subtitle_only = {**scene, "frame_directives": [{"prompt": "Words", "source": "subtitle"}]}
    assert image_gen._is_google_batch_eligible(subtitle_only) is False


def test_batch_and_interactive_paths_share_the_single_directive_cache(monkeypatch, tmp_path):
    # Both paths must land on {scene}.png with the same marker, or each would keep
    # regenerating the other's image and staling every short render.
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    generated = tmp_path / "generated.png"
    _write_png(generated)
    scene = {
        "scene_id": "scene_001",
        "visual_prompt": "A dim radar scope glowing green",
        "visual_mode": "full_frame",
        "frame_directives": [
            {"prompt": "A dim radar scope glowing green", "source": "ai_generated", "reference_previous": False}
        ],
    }
    monkeypatch.setattr(
        image_gen, "generate_images_batch",
        lambda requests, script_id: [GoogleBatchImageResult(key=requests[0].key, image_path=str(generated))],
    )
    image_gen.generate_batch_with_google_batch(scenes=[scene], script_id="script-1")

    def no_provider_call(*_args, **_kwargs):
        raise AssertionError("expected a cache hit, not a new generation")

    monkeypatch.setattr(image_gen, "generate_image", no_provider_call)
    monkeypatch.setattr(image_gen, "generate_scene_frames_v2", no_provider_call)
    result = image_gen._generate_one_scene(dict(scene), "script-1", image_gen.IMAGE_WIDTH, image_gen.IMAGE_HEIGHT, "")

    assert result["error"] is None
    assert result["image_url"] == "/static/projects/script-1/images/scene_001.png"
    assert result["frame_urls"] == []


def test_directive_contains_person_pulls_in_the_character_reference(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    seen = {}

    def fake_compose(*, visual_prompt, script_id, style_guide, contains_person):
        seen["contains_person"] = contains_person
        return visual_prompt, None, None

    monkeypatch.setattr(image_gen, "_compose_image_prompt_context", fake_compose)
    image_gen._prepare_google_batch_scene(
        {
            "scene_id": "scene_001",
            "visual_prompt": "Casey at the scope",
            "visual_mode": "full_frame",
            "contains_person": False,
            "frame_directives": [{"prompt": "Casey at the scope", "source": "ai_generated", "contains_person": True}],
        },
        "script-1", 1920, 1080, "",
    )
    assert seen["contains_person"] is True


def test_single_image_prompt_falls_back_to_the_directive():
    scene = {"visual_prompt": "", "frame_directives": [{"prompt": "From the directive", "source": "ai_generated"}]}
    assert image_gen.single_image_prompt(scene) == "From the directive"
    assert image_gen.single_image_prompt({**scene, "visual_prompt": "From the scene"}) == "From the scene"


def test_a_lone_directive_on_a_sequence_mode_stays_a_frame():
    scene = {"visual_prompt": "Examples", "frame_directives": [{"prompt": "One", "source": "ai_generated"}]}
    assert image_gen.single_image_directive({**scene, "visual_mode": "full_frame"}) is not None
    assert image_gen.single_image_directive({**scene, "visual_mode": "multi_frame"}) is None
    assert image_gen.single_image_directive({**scene, "visual_mode": "continuous"}) is None


def _sequence_env(monkeypatch, tmp_path):
    """Isolate the frame planner from the project DB and character files."""
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    style = tmp_path / "style.png"
    ref = tmp_path / "ref.png"
    _write_png(style)
    _write_png(ref)
    monkeypatch.setattr(image_gen, "_load_project_character_context", lambda sid: (False, "/ref", None))
    monkeypatch.setattr(image_gen, "_ensure_project_character_reference_ready", lambda **_k: None)
    monkeypatch.setattr(image_gen, "_load_project_style_enabled", lambda sid: True)
    monkeypatch.setattr(image_gen, "_resolve_style_preset", lambda **_k: str(style))
    monkeypatch.setattr(
        image_gen, "_resolve_character_reference",
        lambda **k: (str(ref), "CHARACTER") if k["contains_person"] else (None, ""),
    )


def _sequence_scene(scene_id: str, frames: int, mode: str = "continuous") -> dict:
    return {
        "scene_id": scene_id,
        "visual_prompt": f"Brief for {scene_id}",
        "visual_mode": mode,
        "frame_directives": [
            {"prompt": f"{scene_id} frame {i}", "source": "ai_generated", "reference_previous": i > 0}
            for i in range(frames)
        ],
    }


def _fake_rounds(tmp_path, rounds, fail_keys=()):
    def fake_batch(requests, script_id):
        rounds.append([(r.key, r.reference_image_path) for r in requests])
        results = []
        for request in requests:
            if request.key in fail_keys:
                results.append(GoogleBatchImageResult(key=request.key, error="blocked"))
                continue
            out = tmp_path / f"out_{len(rounds)}_{request.key.replace(':', '_')}.png"
            _write_png(out)
            results.append(GoogleBatchImageResult(key=request.key, image_path=str(out)))
        return results
    return fake_batch


def test_frame_sequences_batch_one_frame_per_round(monkeypatch, tmp_path):
    _sequence_env(monkeypatch, tmp_path)
    rounds = []
    monkeypatch.setattr(image_gen, "generate_images_batch", _fake_rounds(tmp_path, rounds))
    monkeypatch.setattr(image_gen, "_generate_one_scene", lambda *a, **k: (_ for _ in ()).throw(AssertionError("standard path")))

    results = image_gen.generate_batch_with_google_batch(
        scenes=[
            _sequence_scene("scene_a", 3),
            _sequence_scene("scene_b", 2, mode="multi_frame"),
            {"scene_id": "scene_c", "visual_prompt": "One image", "visual_mode": "full_frame"},
        ],
        script_id="s1",
    )

    images = tmp_path / "projects" / "s1" / "images"
    assert [[key for key, _ in batch] for batch in rounds] == [
        ["scene_c", "scene_a::f0", "scene_b::f0"],
        ["scene_a::f1", "scene_b::f1"],
        ["scene_a::f2"],
    ]
    # Each later frame is anchored on the frame the previous round produced.
    assert dict(rounds[1])["scene_a::f1"] == str(images / "scene_a_f0.png")
    assert dict(rounds[2])["scene_a::f2"] == str(images / "scene_a_f1.png")
    by_id = {r["scene_id"]: r for r in results}
    assert by_id["scene_a"]["frame_urls"] == [f"/static/projects/s1/images/scene_a_f{i}.png" for i in range(3)]
    assert by_id["scene_b"]["image_url"] == "/static/projects/s1/images/scene_b_f0.png"
    assert by_id["scene_c"]["image_url"] == "/static/projects/s1/images/scene_c.png"
    assert all(r["error"] is None for r in results)


def test_batched_frames_are_cache_hits_for_both_paths(monkeypatch, tmp_path):
    _sequence_env(monkeypatch, tmp_path)
    rounds = []
    monkeypatch.setattr(image_gen, "generate_images_batch", _fake_rounds(tmp_path, rounds))
    scene = _sequence_scene("scene_a", 3)
    image_gen.generate_batch_with_google_batch(scenes=[scene], script_id="s1")
    assert len(rounds) == 3

    def no_generation(*_args, **_kwargs):
        raise AssertionError("expected a cache hit")

    monkeypatch.setattr(image_gen, "generate_image", no_generation)
    again = image_gen.generate_batch_with_google_batch(scenes=[scene], script_id="s1")
    assert len(rounds) == 3  # no new batch round
    frames = image_gen.generate_scene_frames_v2(
        "scene_a", scene["frame_directives"], "s1", visual_prompt=scene["visual_prompt"],
    )
    assert [url for url, _, _ in frames] == again[0]["frame_urls"]


def test_a_failed_frame_stops_only_its_own_scene(monkeypatch, tmp_path):
    _sequence_env(monkeypatch, tmp_path)
    rounds = []
    monkeypatch.setattr(image_gen, "generate_images_batch", _fake_rounds(tmp_path, rounds, fail_keys={"scene_a::f1"}))

    results = image_gen.generate_batch_with_google_batch(
        scenes=[_sequence_scene("scene_a", 3), _sequence_scene("scene_b", 3)],
        script_id="s1",
    )

    by_id = {r["scene_id"]: r for r in results}
    assert by_id["scene_a"]["error"] == "blocked"
    assert len(by_id["scene_b"]["frame_urls"]) == 3
    assert [key for key, _ in rounds[2]] == ["scene_b::f2"]

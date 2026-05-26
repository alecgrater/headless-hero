from api import scripts as scripts_api
from models.script import (
    Scene,
    Script,
    ScriptContent,
    ScriptRating,
    ScriptRatingCategory,
    ScriptRatingCriterion,
    Segment,
)


def _rating(overall: float = 7.4) -> ScriptRating:
    return ScriptRating(
        viewer_retention=ScriptRatingCategory(
            average=7.3,
            explanation="Good hook with room for sharper curiosity gaps.",
            criteria={
                "hook_strength": ScriptRatingCriterion(score=8),
                "curiosity_gaps": ScriptRatingCriterion(score=7),
                "pacing_variance": ScriptRatingCriterion(score=7),
            },
        ),
        narrative_quality=ScriptRatingCategory(
            average=6.5,
            explanation="Coherent, but the throughline could be stronger.",
            criteria={
                "coherence": ScriptRatingCriterion(score=7),
                "throughline": ScriptRatingCriterion(score=6),
            },
        ),
        script_craft=ScriptRatingCategory(
            average=8.0,
            explanation="Specific and economical.",
            criteria={
                "sentence_variety": ScriptRatingCriterion(score=8),
                "specificity": ScriptRatingCriterion(score=9),
                "redundancy": ScriptRatingCriterion(score=7),
                "word_economy": ScriptRatingCriterion(score=8),
            },
        ),
        audience_fit=ScriptRatingCategory(
            average=7.5,
            explanation="Audience fit is clear.",
            criteria={
                "assumed_knowledge_level": ScriptRatingCriterion(score=8),
                "relatability": ScriptRatingCriterion(score=7),
                "tone_consistency": ScriptRatingCriterion(score=8),
                "emotional_range": ScriptRatingCriterion(score=7),
            },
        ),
        seo_alignment=ScriptRatingCategory(
            average=6.7,
            explanation="Search intent can be more direct.",
            criteria={
                "title_hook_match": ScriptRatingCriterion(score=7),
                "search_intent_match": ScriptRatingCriterion(score=6),
                "rewatch_value": ScriptRatingCriterion(score=7),
            },
        ),
        overall=overall,
        model="gpt-5-mini",
    )


def _script_record(script_id: str) -> Script:
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        cinematic_thumbnail_prompt="A dramatic split life thumbnail",
        segments=[
            Segment(
                name="First",
                scenes=[
                    Scene(
                        id="scene-1",
                        narration="Hello",
                        visual_prompt="A scene fallback",
                        image_url=f"/static/projects/{script_id}/images/scene_1.png",
                    ),
                ],
            ),
        ],
    )
    return Script(
        id=script_id,
        brand_id="brand-1",
        topic_title=content.title,
        topic_description="",
        script_json=content.model_dump_json(),
    )


def test_summary_exposes_script_rating_overall(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts_api, "DATA_DIR", tmp_path)
    script_id = "script-rating-summary"
    record = _script_record(script_id)
    content = ScriptContent.model_validate_json(record.script_json)
    content.script_rating = _rating(7.4)
    record.script_json = content.model_dump_json()

    summary = scripts_api._build_summary(record)

    assert summary.script_rating_overall == 7.4


def test_summary_prefers_active_longform_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts_api, "DATA_DIR", tmp_path)
    script_id = "script-life-active"
    thumbs_dir = tmp_path / "projects" / script_id / "renders" / "thumbnails"
    images_dir = tmp_path / "projects" / script_id / "images"
    thumbs_dir.mkdir(parents=True)
    images_dir.mkdir(parents=True)
    (thumbs_dir / "0.png").write_bytes(b"active thumbnail")
    (images_dir / "cinematic_thumbnail.png").write_bytes(b"cinematic thumbnail")

    summary = scripts_api._build_summary(_script_record(script_id))

    assert summary.thumbnail_url == f"/static/projects/{script_id}/renders/thumbnails/0.png"


def test_summary_uses_life_as_a_cinematic_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts_api, "DATA_DIR", tmp_path)
    script_id = "script-life-cinematic"
    images_dir = tmp_path / "projects" / script_id / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "cinematic_thumbnail.png").write_bytes(b"cinematic thumbnail")

    summary = scripts_api._build_summary(_script_record(script_id))

    assert summary.thumbnail_url == f"/static/projects/{script_id}/images/cinematic_thumbnail.png"
    assert summary.format_id == "life-as-a"


def test_summary_falls_back_to_first_scene_image(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts_api, "DATA_DIR", tmp_path)
    script_id = "script-life-fallback"

    summary = scripts_api._build_summary(_script_record(script_id))

    assert summary.thumbnail_url == f"/static/projects/{script_id}/images/scene_1.png"

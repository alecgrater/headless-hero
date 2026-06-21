"""One-click smoke diagnostics for high-risk Test Lab/project generation paths."""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Literal

from pathlib import Path
from pydantic import BaseModel, Field
from sqlmodel import Session

from config import DATA_DIR
from models.script import VISUAL_MODES
from models.settings import AppSetting
from pipeline.blink_actions import PRODUCTION_BLINK_ACTIONS, blink_action_prompt_guidance
from pipeline.test_lab import TEST_LAB_PRESETS, VISUAL_TREATMENT_TEXT_DEFAULTS, load_run_manifest, run_test_lab
from pipeline.visual_mode_policy import prompt_visual_opportunity_guidance

SmokeStatus = Literal["pass", "warn", "fail"]
SAFE_REPORT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

REPRESENTATIVE_MODES = (
    "full_frame",
    "captions",
    "popup_sequence",
    "comparison_board",
    "stat_card",
    "blink",
)
CUTOUT_ASSET_MODES = {"popup_sequence", "comparison_board", "blink"}


class SmokeTestOptions(BaseModel):
    render_heavy: bool = True
    external_api: bool = False


class SmokeTestCheck(BaseModel):
    id: str
    label: str
    group: str
    status: SmokeStatus
    detail: str
    next_action: str = ""
    evidence: str = ""
    run_id: str = ""
    render_url: str = ""


class SmokeTestReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    started_at: str
    completed_at: str
    options: SmokeTestOptions
    summary: dict[str, int]
    total_cost: float = 0.0
    checks: list[SmokeTestCheck]


class SmokeTestExport(BaseModel):
    report_id: str
    markdown: str


def run_smoke_test(*, engine=None, options: SmokeTestOptions | None = None) -> SmokeTestReport:
    started_at = _utc_now()
    resolved_options = options or SmokeTestOptions()
    checks: list[SmokeTestCheck] = []

    _append_check(checks, _check_visual_mode_vocabulary)
    _append_check(checks, _check_blink_guardrail)
    _append_check(checks, _check_representative_presets)
    _append_check(checks, lambda: _check_voice_settings(engine))
    _append_check(checks, lambda: _check_subtitle_settings(engine))
    _append_check(checks, lambda: _check_style_character(engine))

    total_cost = 0.0
    if resolved_options.render_heavy:
        render_checks, total_cost = _run_render_probes(engine=engine, external_api=resolved_options.external_api)
        checks.extend(render_checks)
    else:
        checks.append(
            SmokeTestCheck(
                id="render-probes-skipped",
                label="Render probes",
                group="Pipeline",
                status="warn",
                detail="Render-heavy probes were skipped for this smoke test.",
                next_action="Run again with render-heavy probes enabled before generating a full project.",
            )
        )

    return SmokeTestReport(
        started_at=started_at,
        completed_at=_utc_now(),
        options=resolved_options,
        summary=_summary(checks),
        total_cost=round(float(total_cost), 4),
        checks=checks,
    )


def run_and_save_smoke_test(*, engine=None, options: SmokeTestOptions | None = None) -> SmokeTestReport:
    report = run_smoke_test(engine=engine, options=options)
    save_smoke_report(report)
    return report


def save_smoke_report(report: SmokeTestReport) -> None:
    path = smoke_report_path(report.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def list_smoke_reports() -> list[SmokeTestReport]:
    reports: list[SmokeTestReport] = []
    for path in smoke_reports_dir().glob("*.json"):
        try:
            reports.append(SmokeTestReport.model_validate_json(path.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return sorted(reports, key=lambda report: report.completed_at, reverse=True)


def load_smoke_report(report_id: str) -> SmokeTestReport:
    path = smoke_report_path(report_id)
    if not path.exists():
        raise FileNotFoundError(report_id)
    return SmokeTestReport.model_validate_json(path.read_text(encoding="utf-8"))


def export_smoke_report(report_id: str) -> SmokeTestExport:
    report = load_smoke_report(report_id)
    return SmokeTestExport(report_id=report.id, markdown=smoke_report_markdown(report))


def smoke_report_markdown(report: SmokeTestReport) -> str:
    failures = [check for check in report.checks if check.status == "fail"]
    warnings = [check for check in report.checks if check.status == "warn"]
    passes = [check for check in report.checks if check.status == "pass"]
    lines = [
        "Please fix the Headless Hero Smoke Test issues below.",
        "",
        f"# Smoke Test Report `{report.id}`",
        "",
        f"- Started: {report.started_at}",
        f"- Completed: {report.completed_at}",
        f"- Options: render_heavy={report.options.render_heavy}, external_api={report.options.external_api}",
        f"- Summary: {report.summary.get('fail', 0)} failed, {report.summary.get('warn', 0)} warnings, {report.summary.get('pass', 0)} passed",
        f"- Total cost: ${report.total_cost:.4f}",
        "",
        "## Fix Priority",
        "",
        "- Fix every failure first.",
        "- Then inspect warnings; warnings may be expected when external API asset generation was disabled.",
        "- Use any run IDs or render URLs below to inspect local Test Lab artifacts.",
        "",
    ]
    lines.extend(_markdown_check_section("Failures", failures, empty_text="No failures."))
    lines.extend(_markdown_check_section("Warnings", warnings, empty_text="No warnings."))
    lines.extend(_markdown_check_section("Passed Checks", passes, empty_text="No passing checks."))
    lines.extend(
        [
            "## Raw Report JSON",
            "",
            "```json",
            json.dumps(report.model_dump(mode="json"), indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def smoke_reports_dir() -> Path:
    return DATA_DIR / "test-lab" / "smoke-tests"


def smoke_report_path(report_id: str) -> Path:
    safe_report_id = validate_smoke_report_id(report_id)
    path = smoke_reports_dir() / f"{safe_report_id}.json"
    if not _path_under(path, smoke_reports_dir()):
        raise ValueError("report_id resolved outside Smoke Test history directory")
    return path


def validate_smoke_report_id(report_id: str) -> str:
    if not SAFE_REPORT_ID_RE.match(report_id):
        raise ValueError("Invalid Smoke Test report id")
    return report_id


def _append_check(checks: list[SmokeTestCheck], fn) -> None:
    try:
        checks.append(fn())
    except Exception as exc:
        checks.append(
            SmokeTestCheck(
                id=getattr(fn, "__name__", "smoke-check-error"),
                label="Smoke check error",
                group="Infrastructure",
                status="fail",
                detail="A smoke-test check raised unexpectedly.",
                evidence=str(exc),
                next_action="Open the backend logs for the traceback and fix this diagnostic first.",
            )
        )


def _check_visual_mode_vocabulary() -> SmokeTestCheck:
    expected = {
        "video",
        "full_frame",
        "multi_frame",
        "continuous",
        "captions",
        "popup_sequence",
        "blink",
        "comparison_board",
        "stat_card",
    }
    missing = sorted(expected - VISUAL_MODES)
    extra = sorted(VISUAL_MODES - expected)
    if missing or extra:
        return SmokeTestCheck(
            id="visual-mode-vocabulary",
            label="Visual mode vocabulary",
            group="Contracts",
            status="fail",
            detail=f"Visual mode vocabulary mismatch. Missing: {missing or 'none'}; extra: {extra or 'none'}.",
            next_action="Update the model vocabulary, policy helpers, Test Lab presets, and Remotion types together.",
            evidence=", ".join(sorted(VISUAL_MODES)),
        )
    return SmokeTestCheck(
        id="visual-mode-vocabulary",
        label="Visual mode vocabulary",
        group="Contracts",
        status="pass",
        detail="All expected visual modes are present in the backend model vocabulary.",
        evidence=", ".join(sorted(VISUAL_MODES)),
    )


def _check_blink_guardrail() -> SmokeTestCheck:
    prompt_guidance = blink_action_prompt_guidance()
    opportunity_guidance = prompt_visual_opportunity_guidance(projected_scene_count=36)
    production_guarded = not PRODUCTION_BLINK_ACTIONS and "Do not choose `visual_mode=\"blink\"`" in prompt_guidance
    policy_encourages_blink = "Treat blink and captions as common expressive rhythm opportunities" in opportunity_guidance
    if not production_guarded:
        return SmokeTestCheck(
            id="blink-production-guardrail",
            label="Blink production guardrail",
            group="Visual Modes",
            status="fail",
            detail="Blink is not clearly guarded from production script routing.",
            next_action="Keep production blink actions empty or finish hardening blink before allowing production routing.",
            evidence=prompt_guidance,
        )
    if policy_encourages_blink:
        return SmokeTestCheck(
            id="blink-production-guardrail",
            label="Blink production guardrail",
            group="Visual Modes",
            status="warn",
            detail="Blink production actions are disabled, but policy text still presents blink as a planning opportunity.",
            next_action="Align visual opportunity guidance with the current Test Lab-only blink policy.",
            evidence="Production actions: none; opportunity guidance mentions blink as common.",
        )
    return SmokeTestCheck(
        id="blink-production-guardrail",
        label="Blink production guardrail",
        group="Visual Modes",
        status="pass",
        detail="Blink is disabled for production routing and guidance no longer encourages production selection.",
        evidence="Production actions: none.",
    )


def _check_representative_presets() -> SmokeTestCheck:
    available = {preset.visual_mode for preset in TEST_LAB_PRESETS} | set(VISUAL_TREATMENT_TEXT_DEFAULTS)
    missing = [mode for mode in REPRESENTATIVE_MODES if mode not in available]
    if missing:
        return SmokeTestCheck(
            id="representative-presets",
            label="Representative Test Lab presets",
            group="Test Lab",
            status="fail",
            detail=f"Missing representative presets for: {', '.join(missing)}.",
            next_action="Add or repair Test Lab presets so Smoke Test can probe every high-risk visual mode.",
            evidence=", ".join(sorted(available)),
        )
    return SmokeTestCheck(
        id="representative-presets",
        label="Representative Test Lab presets",
        group="Test Lab",
        status="pass",
        detail="Test Lab has representative presets for the high-risk visual modes.",
        evidence=", ".join(REPRESENTATIVE_MODES),
    )


def _check_voice_settings(engine) -> SmokeTestCheck:
    model_id = _setting(engine, "ELEVENLABS_TTS_MODEL", "default")
    status: SmokeStatus = "pass" if model_id else "warn"
    return SmokeTestCheck(
        id="voice-settings",
        label="Voice settings readable",
        group="Settings",
        status=status,
        detail="Voice settings are readable for Test Lab diagnostics." if model_id else "No voice model setting was found.",
        next_action="" if model_id else "Open Settings -> Voices and confirm the default model/voice.",
        evidence=f"ELEVENLABS_TTS_MODEL={model_id}",
    )


def _check_subtitle_settings(engine) -> SmokeTestCheck:
    coverage = _setting(engine, "SUBTITLE_COVERAGE_MODE", "all").strip().lower()
    label = "Punchy scenes" if coverage == "punchy" else "All scenes"
    return SmokeTestCheck(
        id="subtitle-settings",
        label="Subtitle settings readable",
        group="Settings",
        status="pass",
        detail="Subtitle settings are readable for Test Lab diagnostics.",
        evidence=f"{label}; clean={_setting(engine, 'SUBTITLE_STYLE_CLEAN_ENABLED', 'true')}; "
        f"kinetic={_setting(engine, 'SUBTITLE_STYLE_KINETIC_ENABLED', 'true')}; "
        f"burst={_setting(engine, 'SUBTITLE_STYLE_BURST_ENABLED', 'true')}",
    )


def _check_style_character(engine) -> SmokeTestCheck:
    if engine is None:
        return SmokeTestCheck(
            id="style-character",
            label="Active style character",
            group="Settings",
            status="warn",
            detail="No database engine was provided, so active style character availability was not checked.",
            next_action="Run the smoke test through the app endpoint to include settings-backed character checks.",
        )
    try:
        from pipeline.main_character import get_active_style_preset_character, read_active_style_preset_id

        with Session(engine) as session:
            preset_id = read_active_style_preset_id(session)
            character = get_active_style_preset_character(session, preset_id) if preset_id else None
    except Exception as exc:
        return SmokeTestCheck(
            id="style-character",
            label="Active style character",
            group="Settings",
            status="warn",
            detail="Active style character lookup raised an error.",
            evidence=str(exc),
            next_action="Check Settings -> Style Presets before relying on character-continuity probes.",
        )
    if not preset_id:
        return SmokeTestCheck(
            id="style-character",
            label="Active style character",
            group="Settings",
            status="warn",
            detail="No active style preset is selected.",
            next_action="Select a style preset and active character if the next project depends on character continuity.",
        )
    if character is None:
        return SmokeTestCheck(
            id="style-character",
            label="Active style character",
            group="Settings",
            status="warn",
            detail="An active style preset exists, but it has no active character.",
            evidence=f"style_preset_id={preset_id}",
            next_action="Generate or select an active character for the active style preset.",
        )
    return SmokeTestCheck(
        id="style-character",
        label="Active style character",
        group="Settings",
        status="pass",
        detail="An active style preset character is available.",
        evidence=character.name,
    )


def _run_render_probes(*, engine, external_api: bool) -> tuple[list[SmokeTestCheck], float]:
    if engine is None:
        return (
            [
                SmokeTestCheck(
                    id="render-probes",
                    label="Render probes",
                    group="Pipeline",
                    status="fail",
                    detail="Render-heavy probes need a database engine.",
                    next_action="Run Smoke Test from the app so the endpoint can use the configured database engine.",
                )
            ],
            0.0,
        )
    checks: list[SmokeTestCheck] = []
    total_cost = 0.0
    for mode in REPRESENTATIVE_MODES:
        preset = _probe_preset_for_mode(mode)
        if preset is None:
            continue
        check, cost = _run_single_probe(engine=engine, preset_id=preset.id, mode=mode, external_api=external_api)
        checks.append(check)
        total_cost += cost
    return checks, round(float(total_cost), 4)


def _run_single_probe(*, engine, preset_id: str, mode: str, external_api: bool) -> tuple[SmokeTestCheck, float]:
    run_id = f"smoke-{mode.replace('_', '-')}-{uuid.uuid4().hex[:8]}"
    mode_defaults = VISUAL_TREATMENT_TEXT_DEFAULTS.get(mode, {})
    settings = {
        "visual_mode": mode,
        **mode_defaults,
        "stages": {
            "audio": external_api,
            "visual": external_api,
            "treatment_assets": external_api,
            "fx": False,
            "render": True,
        },
        "segment_timer_enabled": True,
        "subtitle_style": "auto",
    }
    if mode == "blink":
        settings["blink_action"] = "blink"
    try:
        run_test_lab(engine=engine, run_id=run_id, preset_id=preset_id, settings=settings, job_id=None)
        manifest = load_run_manifest(run_id)
    except Exception as exc:
        return (
            SmokeTestCheck(
                id=f"render-probe-{mode}",
                label=f"{mode} render probe",
                group="Pipeline",
                status="fail",
                detail=f"The {mode} Test Lab probe failed.",
                evidence=str(exc),
                run_id=run_id,
                next_action=f"Open Test Lab run {run_id} and backend logs; fix the failing {mode} pipeline stage.",
            ),
            0.0,
        )
    probe_cost = round(float(manifest.total_cost or 0.0), 4)
    if manifest.status != "completed":
        return (
            SmokeTestCheck(
                id=f"render-probe-{mode}",
                label=f"{mode} render probe",
                group="Pipeline",
                status="fail",
                detail=f"The {mode} Test Lab probe ended with status {manifest.status}.",
                run_id=run_id,
                next_action=f"Open Test Lab run {run_id} and inspect stage logs.",
            ),
            probe_cost,
        )
    if not manifest.render_url:
        return (
            SmokeTestCheck(
                id=f"render-probe-{mode}",
                label=f"{mode} render probe",
                group="Pipeline",
                status="fail",
                detail=f"The {mode} Test Lab probe completed without a render URL.",
                run_id=run_id,
                next_action="Check Remotion render output collection and manifest serialization.",
            ),
            probe_cost,
        )
    if mode in CUTOUT_ASSET_MODES and not external_api:
        return (
            SmokeTestCheck(
                id=f"render-probe-{mode}",
                label=f"{mode} render probe",
                group="Pipeline",
                status="warn",
                detail=(
                    f"The {mode} render-only probe completed, but cutout asset generation was disabled. "
                    "This confirms Remotion can render the mode shell, not that generated assets are valid."
                ),
                run_id=run_id,
                render_url=manifest.render_url,
                evidence=f"{len(manifest.assets)} assets",
                next_action="Run again with external API asset generation enabled before trusting this cutout-based mode.",
            ),
            probe_cost,
        )
    return (
        SmokeTestCheck(
            id=f"render-probe-{mode}",
            label=f"{mode} render probe",
            group="Pipeline",
            status="pass",
            detail=f"The {mode} Test Lab probe completed and produced a render.",
            run_id=run_id,
            render_url=manifest.render_url,
            evidence=f"{len(manifest.assets)} assets",
        ),
        probe_cost,
    )


def _probe_preset_for_mode(mode: str):
    explicit = next((item for item in TEST_LAB_PRESETS if item.visual_mode == mode), None)
    if explicit is not None:
        return explicit
    if mode in VISUAL_TREATMENT_TEXT_DEFAULTS:
        return next((item for item in TEST_LAB_PRESETS if item.id != "blank"), TEST_LAB_PRESETS[0] if TEST_LAB_PRESETS else None)
    return None


def _setting(engine, key: str, fallback: str) -> str:
    if engine is None:
        return fallback
    with Session(engine) as session:
        row = session.get(AppSetting, key)
        return row.value if row and row.value else fallback


def _summary(checks: list[SmokeTestCheck]) -> dict[str, int]:
    counts = Counter(check.status for check in checks)
    return {status: counts.get(status, 0) for status in ("pass", "warn", "fail")}


def _markdown_check_section(title: str, checks: list[SmokeTestCheck], *, empty_text: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not checks:
        lines.extend([empty_text, ""])
        return lines
    for index, check in enumerate(checks, start=1):
        lines.extend(
            [
                f"### {index}. {check.label} (`{check.id}`)",
                "",
                f"- Status: {check.status.upper()}",
                f"- Group: {check.group}",
                f"- Detail: {check.detail}",
            ]
        )
        if check.next_action:
            lines.append(f"- Next action: {check.next_action}")
        if check.evidence:
            lines.append(f"- Evidence: {check.evidence}")
        if check.run_id:
            lines.append(f"- Test Lab run id: {check.run_id}")
        if check.render_url:
            lines.append(f"- Render URL: {check.render_url}")
        lines.append("")
    return lines


def _path_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

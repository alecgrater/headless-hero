# Caption Normal Duration Audit Design

## Problem

Recent scripts still produce zero `captions` and zero `stat_card` scenes even when the narration has obvious candidates. The previous outline-time coverage change made the model search harder, but two deeper issues remain:

- `captions` is classified as an extended-duration mode, which makes the scene writer avoid it when most scenes are short.
- Visual-mode planning language can leak into narration, producing lines such as "The captions rendering..." or "The popup sequence..." instead of keeping those concepts in metadata.

## Goal

Make `captions` a normal-duration editorial punch mode that can appear in any long script, add a pre-voiceover metadata-only audit to promote obvious caption and stat-card candidates, and block internal visual-mode terms from narration.

## Non-Goals

- Do not rewrite narration in the audit pass.
- Do not add hard final quotas for every visual mode.
- Do not force `stat_card` when the number is incidental.
- Do not move `popup_sequence` or `comparison_board` to post-generation repair; they still need outline-time scene shaping.
- Do not add an extra LLM call.

## Design

### Captions Duration

Change `captions` from extended to normal duration. Caption beats can be short editorial punches such as "This isn't that version," "none of this counts," or "just for now." They do not need the same parsing time as a comparison board or popup sequence.

### Metadata-Only Audit

Add a deterministic pre-voiceover audit after scene generation and before assets/audio. The audit may only edit scene metadata:

- promote strong existing narration phrases to `visual_mode="captions"`,
- fill `caption_text` and `caption_emphasis` from an exact contiguous narration phrase,
- promote scenes with one meaningful money/time/count figure to `visual_mode="stat_card"` when spacing and context allow,
- fill `stat_value` and `stat_label`,
- leave narration unchanged.

The audit should prefer currently `full_frame` scenes and respect non-title spacing for specialized modes. It should not override `popup_sequence`, `comparison_board`, `video`, `multi_frame`, `continuous`, or `flipflop` unless a scene is already invalid.

### Leakage Guard

Add a deterministic validation/sanitization guard for internal visual-mode language in narration. It should detect phrases such as "captions rendering," "popup sequence," "comparison board," "stat card," and "visual mode" in non-title narration before voiceover. Because automatic narration rewrites are not allowed, the safe behavior is to fail generation with a clear error so the script can be regenerated instead of voiced with renderer jargon.

### Stat Cards

Keep `stat_card` contextual but broaden "decisive statistic" to include emotionally important life-story numbers: first paycheck amounts, salaries, years of service, repeated durations, and similar concrete figures. It remains capped and spaced.

## Documentation

Update `AGENTS.md` and in-app docs to state that captions are normal-duration editorial punch beats and that pre-voiceover audit may fill caption/stat metadata without rewriting narration.

## Testing

Backend tests should verify:

- `captions` uses normal duration and prompt guidance says it can be short.
- The audit promotes multiple caption candidates in a long script without changing narration.
- The audit promotes a salary/years/paycheck scene to `stat_card` when it has one clear number.
- The audit preserves spacing and does not override stronger existing specialized modes.
- Internal visual-mode terms in narration raise a generation-time error before voiceover.

Frontend docs tests should verify the invisible behavior is described.

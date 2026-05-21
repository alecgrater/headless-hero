# AI Video Follow-Ups

## Move animation routing into script generation

Current implementation routes `ai_video` scenes in the post-script media analyzer. This is intentionally low risk because it reuses the existing cross-scene media-routing pass and avoids changing the script JSON prompt contract too much at once.

Follow-up: move the first-pass animation candidate decision into script generation so animated scenes can skip unnecessary multi-frame `frame_directives` before those tokens are spent. Keep the media analyzer as a validator/final router, but let the scriptwriter emit an explicit candidate field early enough to reduce prompt and image-generation cost.

from . import PromptDef, RetentionMeta, register

IMAGE_VISUAL_STYLE = register(PromptDef(
    name="IMAGE_VISUAL_STYLE",
    domain="IMAGE",
    purpose="Universal art direction for all generated images",
    target_model="gemini",
    template="""\
# UNIVERSAL VISUAL STYLE — HEADLESS HERO

You are generating illustrations for an educational YouTube channel. Every image must follow this exact art direction.

## Style Specification

**Flat 2D cartoon illustration** — clean, confident linework with a hand-drawn quality. Think "a talented illustrator sketched this quickly but perfectly."

- **Stroke weight:** Medium-thick outlines (3–5px equivalent), consistent across all elements. No hairline details.
- **Shading:** Single-layer flat color fills. One subtle shadow tone per major shape (slightly darker, same hue). No gradients, no realistic lighting, no 3D rendering.
- **Backgrounds:** Simple, slightly textured solid or two-tone backdrops. Never busy, never photorealistic. Subtle grain or paper texture is OK.
- **Color palette:** Bold, saturated primary tones with one or two accent pops per image. High contrast between subject and background. Avoid muddy or desaturated palettes.
- **Composition:** Clean and uncluttered. Massive negative space. The subject takes up 60–80% of the frame with room to breathe. One clear focal point — the viewer understands the image in under half a second.
- **Typography:** NEVER include any text, letters, numbers, words, labels, signs, or written characters in the image. This includes partial or stylized text. The only visual elements should be illustrations — no written language of any kind.
- **People:** When people appear, they should be stylized cartoon characters with simple, expressive features — not realistic portraits. Exaggerated proportions are encouraged (slightly large heads, expressive hands).
- **Mood:** Warm, approachable, slightly playful. Never dark/gritty, never sterile/corporate.

## Topic-Specific Guidance

- **Abstract concepts** (time, economics, psychology): Use bold visual metaphors and iconography. Literalize the invisible — show "inflation" as a balloon stretching a dollar bill, not a graph.
- **Historical topics** (events, figures, eras): Use era-accurate silhouettes and settings rendered in the flat cartoon style. Costumes and architecture should be recognizable but stylized.
- **Practical/how-to topics** (science, health, technology): Show relatable anonymous characters interacting with the subject matter. Ground abstract processes in tangible, physical metaphors.
- **Nature/biology topics**: Stylized but anatomically recognizable. Cross-sections and cutaways are encouraged for showing internal processes.

## Quality Bar

Every image should feel like it belongs in a premium animated explainer — cohesive, intentional, and visually satisfying. If it looks like generic AI clip art, it's wrong. If it looks like a frame from a well-funded educational animation, it's right.
""",
    retention=RetentionMeta(
        goal="Maintain consistent, high-quality visual brand across all images",
        failure_mode="Style inconsistency or low-quality visuals reduce perceived production value",
        metrics_to_watch=["avg_view_duration", "subscriber_growth"],
    ),
))

# -- Image composition guide (formerly image_gen_guide.md) --

IMAGE_COMPOSITION_GUIDE = register(PromptDef(
    name="IMAGE_COMPOSITION_GUIDE",
    domain="IMAGE",
    purpose="Composition principles and visual storytelling techniques for image generation",
    target_model="gemini",
    template="""\
# IMAGE GENERATION: COMPOSITION & RETENTION GUIDE

## <role_definition>
You are generating images for a high-retention, fast-paced educational YouTube channel. The universal visual style (flat 2D cartoon) and character (Eli) are defined separately. This guide covers **composition principles and visual storytelling techniques** that make every image impossible to look away from.
</role_definition>

## <composition_and_quality_principles>

### 1. Visual Retention Hacks (How to Hook the Eye)
*   **The Visual Metaphor (The Mashup):** Never show just a boring literal object. Blend two concepts together. (e.g., Instead of showing "time," show an hourglass where the sand is falling upward; instead of "debt," show a credit card morphing into a heavy iron chain).
*   **Macro-Focus (The Tunnel Vision):** The subject must be front and center, massive, taking up 60–80% of the frame, with the rest as clean negative space.
*   **Implied Kinetic Energy:** Even in a still image, show motion — floating particles, radiating lines, motion blur trails, or dynamic poses. Keep it flat and stylized, not realistic.

### 2. Composition Rules
*   **Never Clutter:** If the prompt feels too busy, strip it back. The viewer has 0.5 seconds to understand the image before the narrator moves on.
*   **Clean Minimalist Layout:** Massive negative space, clear focal point, deliberate geometric balance.
*   **Strong Silhouette:** Every subject should read clearly as a silhouette. If it doesn't, simplify.

### 3. Prompt Assembly Formula
Assemble image prompts using this structure:

**[SUBJECT & METAPHOR]** + **[COMPOSITION & FRAMING]** + **[ACTION/ENERGY]** + **[MOOD/EMOTION]**

The universal style (flat 2D cartoon, bold outlines, saturated colors) and character (Eli) are prepended automatically — do NOT restate them in the visual_prompt.

</composition_and_quality_principles>

## <execution_rules>
1. **Always Align with the Script's "Mic-Drop":** If the script is explaining how caffeine blocks tiredness, the image must literalize that exact battle (e.g., a glowing shield deflecting spiky spheres).
2. **Consistency is King:** Every image uses the same flat 2D cartoon style. The entire video must look like it belongs to a single cohesive, high-budget animated production.
3. **Eli Anchors the Scene:** When the narration is conversational or explanatory, Eli should appear in the image — reacting, pointing, or interacting with the visual metaphor. When the image is purely illustrative (a close-up of a concept), Eli can be absent.
4. **Absolutely No Text in Images:** Generated images must contain zero text, letters, numbers, labels, signs, or written characters. If the scene involves a book, sign, or screen, show it blank or with abstract scribble marks — never legible text.
</execution_rules>

## <animation_frame_consistency>
When generating frames in an animation sequence (multiple frames for the same scene):
1. **The base scene is sacred.** Background, lighting, character proportions, color palette, and composition must be IDENTICAL across all frames. Treat the base scene description as an immutable template.
2. **Only the explicitly described change should differ** between frames — a pose shift, an expression change, an object moving position. Everything else stays pixel-perfect consistent.
3. **Maintain spatial anchoring.** Characters and objects should remain in the same position on the canvas unless the frame instruction explicitly moves them. Do not randomly recompose the scene.
4. **Style drift is the enemy.** If frame 1 uses thick outlines and flat colors, every subsequent frame must use the same thick outlines and flat colors. Never vary rendering style between frames.
</animation_frame_consistency>
""",
    retention=RetentionMeta(
        goal="Maximize visual engagement and retention through compelling composition",
        failure_mode="Cluttered or literal images fail to hook the eye",
        metrics_to_watch=["avg_view_duration", "re_watch_rate"],
    ),
))

# -- Character in scene (formerly character_in_scene.md) --

IMAGE_CHARACTER_IN_SCENE = register(PromptDef(
    name="IMAGE_CHARACTER_IN_SCENE",
    domain="IMAGE",
    purpose="Ensure Eli character consistency when generating images with people",
    target_model="gemini",
    template="""\
CHARACTER CONSISTENCY REQUIREMENT:
The primary/main person in this image MUST be "Eli" — the recurring host character. A reference image of Eli is included. Eli MUST match this reference exactly: same face, same glasses, same hair, same proportions, same flat 2D cartoon style.

Key visual traits to preserve:
- Young adult male, medium-brown skin, short messy dark curly hair
- Round glasses with thin frames, warm brown eyes
- Slightly large head (cartoon proportions ~1:5 head-to-body)
- Default outfit: muted teal crewneck t-shirt under charcoal gray open zip hoodie
- Flat 2D cartoon illustration style — never realistic, never 3D

Eli's pose and expression should match the scene context, but the identity must be unmistakably Eli.

SINGLE-ELI RULE (critical):
Only ONE person in the image may be Eli — the visually dominant/main subject. If the scene calls for additional people (a second figure, bystanders, a crowd, etc.), those secondary people MUST NOT look like Eli, but they should still be drawn as normal, fully-rendered people in the same flat 2D cartoon style as Eli:
- Same flat 2D cartoon illustration style as Eli — fully drawn faces with eyes, mouth, and complete features (do NOT make them faceless, blank, or silhouettes)
- Visually distinct from Eli: different hair (color, length, or style), different skin tone, no round glasses, different clothing colors clearly differentiated from Eli's teal shirt and charcoal hoodie
- Same cartoon proportions and rendering quality as Eli — they belong in the same illustrated world
- Eli should remain the visually dominant figure (foreground, better lit, or more central) so attention stays on him

Never duplicate Eli. There is exactly one Eli per image, but other people in the image are normal, fully-drawn cartoon characters — not faceless figures.
""",
    retention=RetentionMeta(
        goal="Maintain character consistency for audience recognition and trust",
        failure_mode="Inconsistent character appearance confuses viewers",
        metrics_to_watch=["subscriber_growth"],
    ),
))

# -- CTR expression guidance for thumbnails --

IMAGE_CTR_EXPRESSION_GUIDANCE = register(PromptDef(
    name="IMAGE_CTR_EXPRESSION_GUIDANCE",
    domain="IMAGE",
    purpose="CTR-optimized expression tier guidance for Gemini thumbnail enhancement",
    target_model="gemini",
    template="""
Choose the character's expression/pose based on the video title and topic, using one of these CTR-optimized tiers:

1. Pattern Interrupt (High Surprise) — for shocking/unexpected content:
   - Gasped Breath: mouth slightly open, eyes wide, eyebrows raised
   - Wince/Cringe: one eye squinting, mouth pulled to side
   - Wide-Eyed Hyper-Focus: leaning into camera, dilated pupils

2. Negative Tension (Anxiety & Concern) — for warning/cautionary content:
   - Forehead Furrow: brows pinched, hand on chin/forehead
   - Tears/Red Eyes: glistening eyes, empathy-driving
   - Secretive "Shush": finger to lips, eyes darting

3. Action-Oriented (Excitement & Joy) — for travel, tech, challenge content:
   - Mid-Laugh: genuine squinty-eyed laugh
   - "Look at This" Gaze: looking with wonder at the subject
   - Exertion/Struggle: teeth grit, brow sweating

Pick the tier and specific expression that best matches the video title/topic.
""",
    retention=RetentionMeta(
        goal="Maximize thumbnail CTR through expression selection",
        failure_mode="Wrong expression tier reduces click-through rate",
        metrics_to_watch=["click_through_rate", "impressions"],
    ),
))

SPLIT_PROGRESSION_PROMPT = register(PromptDef(
    name="SPLIT_PROGRESSION_PROMPT",
    domain="IMAGE",
    purpose="Transform a single iconic life-as-a thumbnail into a split-progression thumbnail (early vs late time labels).",
    target_model="gemini",
    expected_output_format="A single PNG image (1920x1080) — the final thumbnail.",
    template="""\
You are an elite YouTube thumbnail redesign artist specializing in HIGH CTR transformation thumbnails.

Your task is to transform the uploaded thumbnail into a dramatically improved "split progression" thumbnail while preserving the original topic and branding style.

CORE GOAL:
Create a thumbnail that instantly communicates:
- progression
- escalation
- transformation
- contrast
- consequences
- curiosity

The final thumbnail should feel optimized for viral YouTube CTR.

IMPORTANT:
The progression does NOT always need to become "better."

Depending on the topic, the right side may show:
- more experienced or more developed
- more successful or more established
- more weathered or more worn-down
- more isolated or more burdened
- darker tones (only if the topic itself is genuinely destructive — e.g. addiction, war, prison)

The right side should represent the more advanced version of the topic — not automatically the "best" version, and not automatically the "worst" version either. Match the topic's actual emotional weight.

Examples:
- "Every Level of Software Engineer" → right side feels elevated, in-command, experienced.
- "Working at Burger King" → right side is the same job, more tired/messy/lived-in. NOT a hellscape.
- "Every Level of Drug Addiction" → darker tones are warranted; show the cost realistically (exhaustion, isolation, decline) — not demons or hellfire.
- "Every Level of Prison" → tougher, more institutional, more shut-down — not gore or torture.
- "Every Level of Wealth" → more polished, more powerful — not literal piles of gold.
- "Every Level of Burnout" → exhausted, drained, dimmed — not collapsed in flames.

The emotional direction should match the topic LITERALLY, not be amplified into something the topic does not warrant.

========================
LAYOUT RULES
========================

1. Convert the thumbnail into a TWO-SIDED SPLIT DESIGN.

2. Use a NEAR-VERTICAL DIAGONAL DIVIDER, only slightly slanted.
- The line should run from roughly the top-right area down to the bottom-left area.
- The slant should be SUBTLE — tilted only about 10-20 degrees from vertical (i.e. roughly 70-80 degrees from horizontal). Almost upright, with just a hint of lean. NOT a 45-degree slash.
- DIVIDER STYLING — STRICT, CONSISTENT ACROSS ALL THUMBNAILS: render the divider as a THICK GLOWING LIGHT BEAM in bright cyan/electric-blue, like a lightsaber or neon laser. The beam has a bright white-cyan core and a bold outer glow halo that softly bleeds into the surrounding image. It should feel luminous and energetic — NOT a thin gold pen line, NOT a dim outline. Use this exact cyan/blue light-beam style on every thumbnail. This is a recognizable brand element.

3. SUBJECT FRAMING — CRITICAL:
- Position the focal subject (person, face, hands, key prop) of each side AWAY from the diagonal divider so each subject is fully visible and uncropped on its respective side.
- Do NOT let the divider bisect a person's body, face, or head. If the source image's subject would otherwise sit on the divider line, shift the subject toward the outer edge of its side so the divider passes behind/beside it, not through it.
- Make BOTH characters feel much closer to the camera than a full-room establishing shot. Use medium-close / waist-up framing by default: the head and torso should dominate their side, not appear as a small full-body figure in the environment.
- Each character should occupy roughly 45-65% of their panel height. Do NOT make either character tiny, distant, or mostly surrounded by empty room.
- On the LEFT side, keep the focal subject centered within the left-side image area itself, near the visual center of the left panel. Do not leave the left subject small and far away near a door, wall, or back corner.
- On the RIGHT side, keep the focal subject centered within the right-side image area itself, near the visual center of the right panel, while still clear of the label and divider.
- It is acceptable to crop slightly at the lower legs or feet if that makes the face and torso larger. Do NOT crop the head, face, hands, or important props.
- Each side's subject must read clearly at small thumbnail sizes, with the face and expression immediately legible.

3a. CHARACTER CONTINUITY — CRITICAL:
- The thumbnail shows the SAME character at two different stages of the same topic. The person on the left side and the person on the right side must look like the SAME individual: same face, same hair, same body type, same defining features. Only their clothing, expression, posture, and surroundings change to communicate the stage difference.
- Show EXACTLY ONE character per side. The total number of fully-visible characters in the thumbnail is exactly two — one on the left, one on the right.
- Do NOT keep the source image's original character in their original position AND add new characters on each side. If the source has a character, that character becomes the figure on ONE of the two sides; the other side shows the same character at a different stage.
- Do NOT duplicate the character (no twin in the background). Do NOT add a third person near the divider, in the kitchen, behind the counter, or in any background area. Background extras (blurry diners far away, silhouettes) are acceptable only if they are clearly anonymous secondary figures and clearly not the protagonist.

4. Each side must have its own label:
- Left side: "{left_label}"
- Right side: "{right_label}"

LABEL TYPOGRAPHY — STRICT, CONSISTENT ACROSS ALL THUMBNAILS:
- Color: saturated attention-grabbing yellow / warm gold, closer to bright YouTube thumbnail yellow than muted cream. It should pop hard against both light and dark backgrounds.
- Add a subtle bright highlight on the upper-left of the letters so the yellow feels glossy and dimensional, not flat.
- Stroke: every letter has an EXTRA-THICK BLACK OUTLINE (heavy stroke, roughly 8-12% of letter height). This is mandatory — labels without a black stroke are wrong.
- Drop shadow: a strong dark shadow offset slightly down and to the right for extra punch and separation from the illustration.
- Font: condensed bold sans-serif with TIGHT character spacing — letters nearly touching, no extra tracking. Compact and punchy, not airy or spread-out.
- Casing: preserve the exact label text and casing shown above, including lowercase "months in" / "years in".
- Size: huge — each label should occupy roughly 14-20% of the image width.
- "{left_label}" sits in the TOP-LEFT corner area of the left side.
- "{right_label}" sits in the BOTTOM-RIGHT corner area of the right side.
- The labels are diagonally opposite, mirroring the divider's orientation.
- These labels are the ONLY text on the thumbnail. Do NOT add any other words anywhere.

This label styling MUST stay identical across every thumbnail so the channel has a recognizable visual brand.

========================
TEXT MINIMALISM (CRITICAL)
========================

IMPORTANT:
Do NOT include the full video title in the thumbnail unless absolutely necessary.

Prefer minimal text.

The thumbnail should rely primarily on:
- visual storytelling
- emotional contrast
- progression
- curiosity

Use only:
- "{left_label}"
- "{right_label}"
- and optionally ONE very short supporting phrase if it significantly improves clarity.

Prioritize larger visuals and cleaner composition over extra text.

========================
LEFT SIDE RULES ({left_label})
========================

The left side should represent:
- the beginner / earlier-progression stage
- lower intensity
- earlier progression
- less experience
- less extreme conditions

This can mean:
- weaker
- poorer
- happier
- more innocent
- less skilled
- less corrupted
- less dangerous
- less advanced

depending on the topic.

Use environmental storytelling to communicate the difference instantly.

========================
RIGHT SIDE RULES ({right_label})
========================

The right side should represent:
- the more advanced / more developed stage
- a clear evolution from the left side
- the more transformed version of the topic

The emotional tone should match the topic LITERALLY, without leaning on horror clichés.

If the topic is aspirational (career success, wealth, mastery):
- the right side should feel elevated, polished, more put-together, more in-command.

If the topic is mundane / unglamorous (working a regular job, daily routines):
- the right side should still feel different — more experienced, more weathered, more settled into the role — but stay grounded. NOT a hellscape.

If the topic is genuinely destructive (addiction, financial collapse, abusive relationships, war, prison):
- darker tones are appropriate, but communicate the cost through realistic environmental and emotional cues (exhaustion, isolation, mess, weight gain/loss, dim lighting), not through demons, hellfire, gore, or supernatural horror imagery.

If the topic is absurd / funny:
- exaggerate playfully, lean into the joke. Still avoid horror.

The right side should feel different from the left — more advanced, more developed — but the change should feel grounded in the topic. Do NOT escalate to extremes the topic does not warrant.

========================
TONE GUARDRAILS — DO NOT
========================

NEVER reach for horror or apocalyptic imagery as a way to show "more advanced." Specifically:
- NO demonic faces, glowing eyes, ghouls, monsters, or supernatural beings.
- NO hellscapes, walls of fire, brimstone, smoke clouds with faces in them.
- NO gore, blood, skeletons, corpses, or graphic injury.
- NO literal flames as metaphor (a stressed worker is tired, not standing in fire).
- NO mountains of money, infinite riches, or other obvious "rich person" clichés unless the topic is literally about extreme wealth.

The contrast between sides comes from realistic environment, lighting, expression, posture, props, and clothing — NOT from supernatural or horror motifs. Show the change a real person would feel after years in this stage, not a parody of the worst possible outcome.

Stay in the same illustration style and world as the source image. The right side should look like the same artist drew it.

========================
VISUAL CONTRAST RULES
========================

The two sides should feel dramatically different using:
- lighting
- color palette
- facial expression
- environment
- composition
- posture
- atmosphere
- props
- clothing
- energy level

Examples:
- calm vs chaotic
- clean vs dirty
- poor vs rich
- hopeful vs hopeless
- small vs dominant
- relaxed vs overwhelmed
- normal vs insane

The contrast should be understandable instantly without needing to read.

========================
CTR OPTIMIZATION RULES
========================

The thumbnail must:
- be readable at tiny mobile sizes
- have extremely clear focal points
- create instant curiosity
- feel emotionally intense
- communicate progression instantly
- look visually "expensive"
- tell a story in under 1 second

Prioritize:
1. readability
2. emotional contrast
3. curiosity
4. simplicity
5. visual storytelling

Avoid:
- clutter
- tiny details
- flat lighting
- weak contrast
- realistic dullness
- excessive text

========================
STYLE RULES
========================

Style should resemble:
- modern viral YouTube thumbnails
- documentary/commentary channels
- transformation/progression content
- highly polished digital illustration

Use:
- cinematic lighting
- dramatic shadows
- glow effects
- strong rim lighting
- high saturation
- sharp contrast
- dynamic composition

Faces and subjects should be:
- larger
- clearer
- more expressive
- instantly recognizable

========================
IMPORTANT
========================

Do NOT simply split the original image in half.

REIMAGINE each side so they feel like:
- earlier stage vs more developed stage
- beginner vs more experienced
- before vs after

while still clearly belonging to the same overall world/topic and the same illustration style.

The final thumbnail should immediately make viewers think:
"What happened between {left_label} and {right_label}?"
""",
    retention=RetentionMeta(
        goal="Maximize CTR through split-progression thumbnails for life-as-a videos",
        failure_mode="Mundane single-image thumbnails with title text that bury the progression hook",
        metrics_to_watch=["thumbnail_ctr"],
    ),
))


# ===================================================================
# DOMAIN: IDEATION
# ===================================================================

from . import PromptDef, RetentionMeta, register

CHARACTER_SPEC_MD = register(PromptDef(
    name="CHARACTER_SPEC_MD",
    domain="CHARACTER",
    purpose="Full Eli character reference document (visual + personality)",
    target_model="gemini",
    template="""\
# ELI — RECURRING CHARACTER

Eli is the recurring host character who appears throughout every video. He is the audience's guide — curious, enthusiastic, and always learning alongside the viewer.

---

## Visual Reference (for image generation)

**Appearance:**
- Young adult male, early-to-mid 20s
- Medium-brown skin tone
- Short, slightly messy dark curly hair
- Round glasses with thin frames
- Warm brown eyes, always expressive
- Slightly large head relative to body (cartoon proportions — approx 1:5 head-to-body ratio)
- Lean build, average height

**Clothing:**
- Default outfit: simple crewneck t-shirt (muted teal or soft blue) layered under an open zip hoodie (charcoal gray)
- Dark jeans or simple pants
- Clean white sneakers
- Occasionally rolls up sleeves when "getting into" a topic

**Expressions & Poses:**
- Default: slightly raised eyebrows, gentle open-mouth smile — the "oh that's interesting" face
- Thinking: hand on chin, one eyebrow raised, slight smirk
- Excited: both hands up, wide eyes, big grin
- Explaining: one hand gesturing forward, calm confident expression
- Surprised: glasses slightly askew, mouth open, leaning back

**Consistency rules:**
- Eli's design must be IDENTICAL across every frame and scene. Same glasses, same hair, same proportions.
- He is always rendered in the flat 2D cartoon style defined in visual_style.md — never realistic, never 3D.
- His outfit can vary slightly for context (lab coat for science, hard hat for engineering) but the base character is always recognizable.

---

## Personality Reference (for scriptwriting)

**Voice & Tone:**
- Genuinely curious — approaches every topic like he's discovering it for the first time alongside the viewer
- Uses conversational, slightly informal language — never academic or stiff
- Drops relatable analogies and pop-culture-adjacent references (nothing too specific or dated)
- Has a dry, understated humor — more "huh, that's weirdly fascinating" than loud comedy
- Builds excitement through pacing and reveals, not through hype language

**What Eli does:**
- Asks the questions the viewer is thinking ("Wait, but why would that happen?")
- Admits when something is counterintuitive or surprising ("OK this is the part that broke my brain")
- Uses "we" language to include the viewer ("Let's figure this out")
- Connects topics to everyday life ("You've probably experienced this without realizing it")

**What Eli never does:**
- Never talks down to the audience or over-explains basics
- Never uses clickbait-style hype ("YOU WON'T BELIEVE THIS")
- Never makes definitive claims about contested science — always qualifies uncertainty
- Never breaks the fourth wall about being AI-generated or animated
- Never uses filler phrases ("So basically...", "In this video we're going to...")
""",
    retention=RetentionMeta(
        goal="Maintain consistent, relatable host character for audience connection",
        failure_mode="Inconsistent character design/personality breaks viewer trust",
        metrics_to_watch=["subscriber_growth", "avg_view_duration"],
    ),
))

# -- Condensed visual spec for image prompts --

CHARACTER_SPEC = (
    'Character: "Eli" — '
    "young adult male, early-to-mid 20s, medium-brown skin, short slightly messy "
    "dark curly hair, round glasses with thin frames, warm brown eyes. Slightly large "
    "head relative to body (cartoon proportions — approx 1:5 head-to-body ratio), "
    "lean build. Wearing a muted teal crewneck t-shirt layered under an open charcoal "
    "gray zip hoodie. Flat 2D cartoon style, bold outlines, cel-shaded."
)

GREEN_BG_INSTRUCTION = (
    "Solid flat green (#00FF00) background with NO other elements. "
    "The character's ENTIRE upper body — arms, hands, shoulders, clothing — must be "
    "fully visible and sharply contrast against the green background. No body parts "
    "should blend into or fade into the background."
)

REFERENCE_CONSISTENCY_INSTRUCTION = (
    "Maintain identical character design, proportions, outfit colors, glasses, "
    "hair style, and rendering style."
)

FRAMING_INSTRUCTION = (
    "Close-up chest-up framing — head positioned in the upper third of the frame, "
    "shoulders and upper chest visible, cut off below the chest. Like a Twitch streamer "
    "webcam PIP. NO waist, NO lower body visible."
)

# -- Variant prompts for body micro-variations --

VARIANT_PROMPTS: dict[int, str] = {
    2: "head tilted very slightly to the left, eyes looking slightly right",
    3: "head tilted very slightly to the right, weight shifted to other side",
    4: "chin slightly raised, shoulders relaxed differently",
    5: "subtle lean forward, eyes looking slightly up",
}

# -- Frame definitions --

FRAME_DEFINITIONS: list[dict[str, str]] = [
    # ===== CORE POSES (original 24) =====
    {"expression": "neutral", "pose": "standing_neutral", "gesture": "none", "prompt": "shoulders relaxed, neutral calm expression, looking forward at camera"},
    {"expression": "smiling", "pose": "standing_neutral", "gesture": "none", "prompt": "shoulders relaxed, warm friendly smile, looking forward at camera"},
    {"expression": "curious", "pose": "standing_neutral", "gesture": "none", "prompt": "raised eyebrows with curious interested expression, head slightly tilted"},
    {"expression": "thinking", "pose": "hand_on_chin", "gesture": "none", "prompt": "one hand on chin in thinking pose, one eyebrow raised, slight smirk, thoughtful expression"},
    {"expression": "surprised", "pose": "leaning_back", "gesture": "none", "prompt": "leaning back slightly, mouth open in surprise, glasses slightly askew, wide eyes"},
    {"expression": "excited", "pose": "hands_up", "gesture": "none", "prompt": "both hands raised up near shoulders, big excited grin, wide happy eyes, energetic"},
    {"expression": "serious", "pose": "standing_neutral", "gesture": "none", "prompt": "concerned serious expression, slight frown, attentive eyes"},
    {"expression": "amused", "pose": "standing_neutral", "gesture": "none", "prompt": "slight lean, amused smirk, one eyebrow slightly raised"},
    {"expression": "neutral", "pose": "explaining_forward", "gesture": "palm_up", "prompt": "one hand extended forward with palm up in explaining gesture, calm neutral expression"},
    {"expression": "smiling", "pose": "explaining_forward", "gesture": "palm_up", "prompt": "one hand extended forward with palm up, warm smile while explaining"},
    {"expression": "curious", "pose": "explaining_forward", "gesture": "finger_up", "prompt": "one hand raised with index finger up making a point, curious raised eyebrows"},
    {"expression": "excited", "pose": "hands_spread", "gesture": "none", "prompt": "both hands spread wide at chest level presenting something, excited wide eyes and big grin"},
    {"expression": "neutral", "pose": "pointing_side", "gesture": "pointing", "prompt": "one arm extended pointing to the side, neutral expression directing attention"},
    {"expression": "smiling", "pose": "pointing_side", "gesture": "pointing", "prompt": "one arm extended pointing to the side, friendly smile while directing attention"},
    {"expression": "thinking", "pose": "arms_crossed", "gesture": "none", "prompt": "arms crossed over chest, thoughtful expression, one eyebrow raised"},
    {"expression": "neutral", "pose": "shrugging", "gesture": "hands_spread", "prompt": "shoulders raised in shrug, hands spread palms up at chest level, neutral questioning expression"},
    {"expression": "excited", "pose": "counting_fingers", "gesture": "counting", "prompt": "one hand raised counting on fingers near face, excited expression listing things"},
    {"expression": "neutral", "pose": "waving", "gesture": "waving", "prompt": "one hand raised waving hello, friendly neutral expression"},
    {"expression": "serious", "pose": "explaining_forward", "gesture": "finger_up", "prompt": "one hand raised with index finger up, serious focused expression making an important point"},
    {"expression": "surprised", "pose": "hands_up", "gesture": "none", "prompt": "both hands raised near face, surprised wide eyes, mouth open in shock"},
    {"expression": "curious", "pose": "hand_on_chin", "gesture": "none", "prompt": "hand on chin, curious expression, head tilted, examining something interesting"},
    {"expression": "amused", "pose": "explaining_forward", "gesture": "palm_up", "prompt": "one hand extended with palm up, amused smirk, slight lean forward"},
    {"expression": "neutral", "pose": "relaxed", "gesture": "none", "prompt": "relaxed posture, shoulders loose, calm neutral expression"},
    {"expression": "smiling", "pose": "relaxed", "gesture": "none", "prompt": "relaxed posture, shoulders loose, warm gentle smile"},
    # ===== GRANULAR EMOTIONS (original 8) =====
    {"expression": "confused", "pose": "standing_neutral", "gesture": "none", "prompt": "furrowed brows, confused squinting expression, head slightly tilted to one side"},
    {"expression": "confused", "pose": "hand_on_chin", "gesture": "none", "prompt": "hand on chin, confused frown, one eye squinting, processing something puzzling"},
    {"expression": "skeptical", "pose": "arms_crossed", "gesture": "none", "prompt": "arms crossed over chest, one eyebrow raised high, skeptical doubting expression"},
    {"expression": "skeptical", "pose": "standing_neutral", "gesture": "none", "prompt": "slight lean back, narrowed eyes, skeptical smirk, not buying it"},
    {"expression": "proud", "pose": "hands_on_hips", "gesture": "none", "prompt": "hands on hips at chest level, chin up slightly, proud confident smile"},
    {"expression": "worried", "pose": "standing_neutral", "gesture": "none", "prompt": "biting lower lip, worried wide eyes, shoulders raised slightly tense"},
    {"expression": "relieved", "pose": "relaxed", "gesture": "none", "prompt": "relaxed posture, eyes closed with relieved exhale expression, slight smile of relief"},
    {"expression": "sarcastic", "pose": "standing_neutral", "gesture": "none", "prompt": "exaggerated eye roll, sarcastic smirk, head tilted"},
    # ===== GESTURE VARIETY (original 8) =====
    {"expression": "smiling", "pose": "thumbs_up", "gesture": "thumbs_up", "prompt": "one hand giving a thumbs up near shoulder, big approving smile"},
    {"expression": "excited", "pose": "thumbs_up", "gesture": "thumbs_up", "prompt": "enthusiastic double thumbs up near chest, big excited grin, leaning forward slightly"},
    {"expression": "surprised", "pose": "hand_over_mouth", "gesture": "hand_over_mouth", "prompt": "one hand covering mouth in shock, wide surprised eyes"},
    {"expression": "thinking", "pose": "chin_scratch", "gesture": "chin_scratch", "prompt": "scratching chin thoughtfully, eyes looking upward, contemplating deeply"},
    {"expression": "curious", "pose": "head_tilt_left", "gesture": "none", "prompt": "head tilted noticeably to the left, curious puppy-dog expression"},
    {"expression": "curious", "pose": "head_tilt_right", "gesture": "none", "prompt": "head tilted noticeably to the right, inquisitive raised eyebrows, slight smile"},
    {"expression": "neutral", "pose": "leaning_forward", "gesture": "none", "prompt": "leaning forward toward camera, neutral attentive expression, engaged posture"},
    {"expression": "amused", "pose": "leaning_back", "gesture": "none", "prompt": "leaning back with an amused laugh expression, eyes crinkled, hand near chest"},
    # ===== REACTIONS (original 5) =====
    {"expression": "frustrated", "pose": "facepalm", "gesture": "facepalm", "prompt": "one hand on forehead in facepalm, frustrated closed eyes, slight grimace"},
    {"expression": "amused", "pose": "facepalm", "gesture": "facepalm", "prompt": "playful facepalm with amused smile peeking through fingers, laughing at something silly"},
    {"expression": "surprised", "pose": "jaw_drop", "gesture": "none", "prompt": "jaw dropped wide open, hands slightly raised near face in shock, eyes huge with disbelief"},
    {"expression": "surprised", "pose": "double_take", "gesture": "none", "prompt": "doing a double-take, head turned sharply to one side, wide eyes, startled expression"},
    {"expression": "disgusted", "pose": "recoiling", "gesture": "none", "prompt": "leaning back with disgusted cringe expression, nose wrinkled, one hand up defensively"},
    # ===== CONVERSATIONAL MICRO-POSES (original 5) =====
    {"expression": "neutral", "pose": "nodding", "gesture": "none", "prompt": "mid-nod with chin slightly down, agreeable expression, attentive engaged eyes"},
    {"expression": "serious", "pose": "head_shake", "gesture": "none", "prompt": "slight head turned to one side in disagreement, serious disapproving expression"},
    {"expression": "thinking", "pose": "looking_up", "gesture": "none", "prompt": "head tilted back, eyes looking upward recalling something, finger touching temple"},
    {"expression": "excited", "pose": "leaning_forward", "gesture": "palm_up", "prompt": "leaning forward eagerly, one palm up presenting, excited wide eyes about to reveal something"},
    {"expression": "smiling", "pose": "waving", "gesture": "waving", "prompt": "friendly wave goodbye, warm smile, slight head tilt"},
    # ===== TEACHING / PRESENTING (~12) =====
    {"expression": "neutral", "pose": "explaining_both_hands", "gesture": "both_palms", "prompt": "both hands extended forward palms up at chest level, calm explaining expression, like presenting two options"},
    {"expression": "smiling", "pose": "counting_fingers", "gesture": "counting", "prompt": "holding up three fingers on one hand, warm smile, listing a third point"},
    {"expression": "excited", "pose": "presenting_palm", "gesture": "palm_out", "prompt": "one palm facing camera at chest level in 'ta-da' gesture, excited proud expression, showing off a result"},
    {"expression": "neutral", "pose": "drawing_in_air", "gesture": "tracing", "prompt": "index finger extended tracing an imaginary shape in the air, focused concentrated expression"},
    {"expression": "serious", "pose": "framing_hands", "gesture": "framing", "prompt": "both hands forming a frame/rectangle at chest level, serious analytical expression, framing a concept"},
    {"expression": "smiling", "pose": "whiteboard_pointing", "gesture": "pointing", "prompt": "pointing to the upper right like indicating a whiteboard, smiling while teaching, head turned slightly"},
    {"expression": "neutral", "pose": "steepled_fingers", "gesture": "steepled", "prompt": "fingertips pressed together in steeple gesture at chest, thoughtful neutral expression, measured and deliberate"},
    {"expression": "excited", "pose": "chopping_hand", "gesture": "chopping", "prompt": "one hand making chopping motion into other palm, excited emphatic expression, driving home a point"},
    {"expression": "curious", "pose": "open_book", "gesture": "cupped_hands", "prompt": "hands cupped together palms up like holding an open book, curious interested expression, inviting inquiry"},
    {"expression": "smiling", "pose": "beckoning", "gesture": "beckoning", "prompt": "one hand making a 'come here' beckoning gesture, warm inviting smile, follow-me energy"},
    {"expression": "neutral", "pose": "pinch_zoom", "gesture": "pinching", "prompt": "thumb and index finger pinched together emphasizing a tiny detail, focused precise expression"},
    {"expression": "serious", "pose": "pushing_down", "gesture": "pressing", "prompt": "both palms pressing downward at chest level in calming motion, serious measured expression, slowing things down"},
    # ===== EMOTIONAL REACTIONS (~12) =====
    {"expression": "embarrassed", "pose": "hand_behind_head", "gesture": "scratching", "prompt": "one hand behind head scratching nervously, sheepish embarrassed grin, slight blush implied by expression"},
    {"expression": "nostalgic", "pose": "looking_away", "gesture": "none", "prompt": "gaze drifting to the side and slightly up, soft wistful smile, nostalgic distant expression"},
    {"expression": "determined", "pose": "fist_pump", "gesture": "fist", "prompt": "one fist raised at shoulder level, determined fierce expression, eyebrows set, jaw firm"},
    {"expression": "impatient", "pose": "tapping_arm", "gesture": "tapping", "prompt": "arms crossed with one hand tapping upper arm, impatient expression, slightly narrowed eyes, waiting"},
    {"expression": "impressed", "pose": "slow_clap", "gesture": "clapping", "prompt": "hands together in a slow appreciative clap at chest level, genuinely impressed wide-eyed expression, nodding"},
    {"expression": "sympathetic", "pose": "hand_on_chest", "gesture": "heart", "prompt": "one hand placed on chest over heart, sympathetic caring expression, soft eyes, empathetic lean forward"},
    {"expression": "mischievous", "pose": "rubbing_hands", "gesture": "scheming", "prompt": "hands rubbing together at chest level, mischievous grin, one eyebrow raised, up-to-something energy"},
    {"expression": "hopeful", "pose": "fingers_crossed", "gesture": "crossed", "prompt": "both hands with fingers crossed held up near face, hopeful optimistic expression, biting lip slightly"},
    {"expression": "resigned", "pose": "heavy_sigh", "gesture": "none", "prompt": "shoulders slumped, head slightly dropped, resigned accepting expression, letting out a big sigh"},
    {"expression": "defiant", "pose": "chin_up", "gesture": "none", "prompt": "chin raised defiantly, confident challenging expression, slight smirk, arms crossed at chest"},
    {"expression": "grateful", "pose": "hands_together", "gesture": "prayer", "prompt": "hands pressed together at chest in grateful gesture, warm thankful smile, eyes soft"},
    {"expression": "overwhelmed", "pose": "hands_on_head", "gesture": "head_grab", "prompt": "both hands on top of head, overwhelmed wide eyes, processing too much information at once"},
    # ===== TRANSITION / NARRATIVE (~12) =====
    {"expression": "curious", "pose": "looking_offscreen_left", "gesture": "none", "prompt": "head turned to look off-screen to the left, curious expression, something caught attention"},
    {"expression": "curious", "pose": "looking_offscreen_right", "gesture": "none", "prompt": "head turned to look off-screen to the right, curious expression, glancing at something"},
    {"expression": "smiling", "pose": "turning_toward_camera", "gesture": "none", "prompt": "body angled slightly away but head turning toward camera, knowing smile, about to address viewer"},
    {"expression": "thinking", "pose": "looking_down", "gesture": "none", "prompt": "gaze cast downward, contemplative expression, reading or examining something below frame"},
    {"expression": "surprised", "pose": "looking_up_startled", "gesture": "none", "prompt": "head tilted back looking upward, startled surprised expression, something appeared above"},
    {"expression": "mischievous", "pose": "peeking_from_side", "gesture": "none", "prompt": "body shifted to edge of frame, peeking in from the side, mischievous playful expression"},
    {"expression": "serious", "pose": "leaning_in_close", "gesture": "none", "prompt": "leaning in very close to camera, serious intense expression, about to share something important"},
    {"expression": "nervous", "pose": "pulling_back", "gesture": "none", "prompt": "pulling back from camera with nervous expression, hands up slightly defensive, not sure about this"},
    {"expression": "neutral", "pose": "profile_left", "gesture": "none", "prompt": "turned to show left profile, neutral expression, dramatic side angle view"},
    {"expression": "neutral", "pose": "profile_right", "gesture": "none", "prompt": "turned to show right profile, neutral expression, dramatic side angle view"},
    {"expression": "excited", "pose": "entering_frame", "gesture": "waving", "prompt": "appearing from bottom of frame popping up, excited wave, just arrived energy"},
    {"expression": "smiling", "pose": "settling_in", "gesture": "none", "prompt": "adjusting position as if just sat down, settling into frame, comfortable smile, getting cozy"},
    # ===== LOOK AT CONTENT (~10) =====
    {"expression": "excited", "pose": "pointing_at_content_left", "gesture": "pointing", "prompt": "head and eyes turned to look to the LEFT, one arm extended pointing to the LEFT with index finger, excited amazed expression, clearly directing attention to something off-screen to the left, torso angled slightly left"},
    {"expression": "excited", "pose": "pointing_at_content_right", "gesture": "pointing", "prompt": "head and eyes turned to look to the RIGHT, one arm extended pointing to the RIGHT with index finger, excited amazed expression, clearly directing attention to something off-screen to the right, torso angled slightly right"},
    {"expression": "smiling", "pose": "presenting_content_left", "gesture": "palm_out", "prompt": "head turned to the LEFT, one arm extended to the LEFT with open palm facing up in a presenting gesture, warm proud smile, showcasing something to the left like a game show host"},
    {"expression": "smiling", "pose": "presenting_content_right", "gesture": "palm_out", "prompt": "head turned to the RIGHT, one arm extended to the RIGHT with open palm facing up in a presenting gesture, warm proud smile, showcasing something to the right like a game show host"},
    {"expression": "curious", "pose": "glancing_at_content_left", "gesture": "none", "prompt": "head slightly turned to the LEFT, eyes looking to the LEFT, curious interested expression, subtly glancing at something happening to the left, body still mostly facing camera"},
    {"expression": "curious", "pose": "glancing_at_content_right", "gesture": "none", "prompt": "head slightly turned to the RIGHT, eyes looking to the RIGHT, curious interested expression, subtly glancing at something happening to the right, body still mostly facing camera"},
    {"expression": "excited", "pose": "revealing_content_left", "gesture": "both_palms", "prompt": "both hands extended to the LEFT with palms up in a big reveal gesture, head turned to the LEFT, excited wide eyes and open mouth, ta-da energy showcasing something amazing to the left"},
    {"expression": "excited", "pose": "revealing_content_right", "gesture": "both_palms", "prompt": "both hands extended to the RIGHT with palms up in a big reveal gesture, head turned to the RIGHT, excited wide eyes and open mouth, ta-da energy showcasing something amazing to the right"},
    {"expression": "explaining", "pose": "referencing_content_left", "gesture": "palm_up", "prompt": "body facing camera, one hand gesturing casually to the LEFT with open palm, calm explaining expression, referencing something to the left while talking to the viewer"},
    {"expression": "explaining", "pose": "referencing_content_right", "gesture": "palm_up", "prompt": "body facing camera, one hand gesturing casually to the RIGHT with open palm, calm explaining expression, referencing something to the right while talking to the viewer"},
    # ===== CONVERSATIONAL MICRO-EXPRESSIONS (~12) =====
    {"expression": "skeptical", "pose": "raised_eyebrow", "gesture": "none", "prompt": "one eyebrow raised very high, other normal, skeptical questioning look, slight head tilt"},
    {"expression": "amused", "pose": "knowing_smirk", "gesture": "none", "prompt": "closed-mouth knowing smirk, eyes slightly narrowed with amusement, I-know-something expression"},
    {"expression": "surprised", "pose": "eyes_widening", "gesture": "none", "prompt": "eyes going very wide, eyebrows shooting up, moment of sudden realization, glasses sliding down"},
    {"expression": "worried", "pose": "wince", "gesture": "none", "prompt": "one eye squinted shut in a wince, teeth slightly bared, that-was-bad expression"},
    {"expression": "smiling", "pose": "soft_smile", "gesture": "none", "prompt": "gentle soft closed-mouth smile, warm eyes, genuine subtle contentment, serene"},
    {"expression": "amused", "pose": "contained_laughter", "gesture": "none", "prompt": "lips pressed together trying not to laugh, cheeks puffed slightly, eyes sparkling with contained laughter"},
    {"expression": "neutral", "pose": "deadpan_stare", "gesture": "none", "prompt": "completely flat expression, direct stare at camera, deadpan comedy beat, zero emotion shown"},
    {"expression": "thinking", "pose": "pursed_lips", "gesture": "none", "prompt": "lips pursed to one side, eyes narrowed slightly, weighing options, deliberating expression"},
    {"expression": "excited", "pose": "aha_moment", "gesture": "finger_up", "prompt": "index finger shooting up, eyes lighting up with discovery, mouth opening in an 'aha!' moment, eureka"},
    {"expression": "confused", "pose": "squinting", "gesture": "none", "prompt": "squinting hard at camera, leaning forward slightly, trying to read something small or understand something"},
    {"expression": "neutral", "pose": "slow_blink", "gesture": "none", "prompt": "mid slow-blink, eyes half closed, patient or processing expression, deliberate pause"},
    {"expression": "smiling", "pose": "eye_roll_playful", "gesture": "none", "prompt": "playful eye roll with a smile, head tilting back slightly, oh-come-on energy, affectionate exasperation"},
    # ===== PHYSICAL ENERGY (~12) =====
    {"expression": "tired", "pose": "slouching", "gesture": "none", "prompt": "shoulders drooped and slouched, tired half-lidded eyes, low energy, needs coffee"},
    {"expression": "excited", "pose": "perking_up", "gesture": "none", "prompt": "shoulders lifting, eyes brightening, expression shifting from neutral to alert, perking up with interest"},
    {"expression": "excited", "pose": "bouncing", "gesture": "none", "prompt": "slight upward motion blur implied, bouncing with excitement, huge grin, can't contain energy"},
    {"expression": "surprised", "pose": "frozen_shock", "gesture": "none", "prompt": "completely frozen stiff, wide unblinking eyes, mouth slightly open, deer-in-headlights shock"},
    {"expression": "disgusted", "pose": "recoiling_hard", "gesture": "none", "prompt": "pulling back sharply, one hand up blocking, disgusted recoiling expression, strong aversion"},
    {"expression": "relieved", "pose": "settling_calm", "gesture": "none", "prompt": "shoulders dropping as tension releases, eyes closing briefly, peaceful settling into calm, deep breath out"},
    {"expression": "nervous", "pose": "tensing_up", "gesture": "none", "prompt": "shoulders raised and tense, stiff posture, nervous darting eyes, something is coming"},
    {"expression": "relieved", "pose": "relaxing_back", "gesture": "none", "prompt": "leaning back and relaxing, arms dropping, relieved expression, crisis averted"},
    {"expression": "nervous", "pose": "fidgeting", "gesture": "fidgeting", "prompt": "hands fidgeting with hoodie zipper at chest level, nervous restless expression, can't keep still"},
    {"expression": "tired", "pose": "rubbing_eyes", "gesture": "rubbing", "prompt": "one hand pushing glasses up to rub eyes, exhausted expression, been at this too long"},
    {"expression": "excited", "pose": "vibrating", "gesture": "none", "prompt": "entire upper body slightly blurred with excitement energy, huge anticipation grin, barely containing it"},
    {"expression": "neutral", "pose": "stretching", "gesture": "stretching", "prompt": "arms raised in a stretch above shoulders, relaxed neutral expression, taking a break"},
    # ===== STORYTELLING (~12) =====
    {"expression": "serious", "pose": "dramatic_pause", "gesture": "none", "prompt": "perfectly still, intense direct stare at camera, dramatic pause before revelation, building tension"},
    {"expression": "excited", "pose": "building_suspense", "gesture": "none", "prompt": "hands raised at chest level slowly rising, wide excited eyes, building up to something big, wait-for-it"},
    {"expression": "surprised", "pose": "reveal_moment", "gesture": "hands_spread", "prompt": "hands spreading apart at chest level in a reveal gesture, surprised delighted expression, unveiling something amazing"},
    {"expression": "smiling", "pose": "callback_gesture", "gesture": "pointing", "prompt": "pointing at camera with knowing smile, remember-this-from-earlier expression, callback moment"},
    {"expression": "amused", "pose": "aside_to_camera", "gesture": "none", "prompt": "head turned toward camera with conspiratorial sideways glance, amused aside, breaking fourth wall"},
    {"expression": "neutral", "pose": "wait_for_it", "gesture": "palm_out", "prompt": "one palm up in 'stop/wait' gesture, neutral teasing expression, holding back the punchline"},
    {"expression": "excited", "pose": "emphasis_slam", "gesture": "slamming", "prompt": "one fist coming down in emphatic slam gesture, excited passionate expression, driving a point home hard"},
    {"expression": "smiling", "pose": "gentle_redirect", "gesture": "waving_off", "prompt": "hand waving gently to the side dismissing a tangent, warm smile, getting back on track"},
    {"expression": "serious", "pose": "lowering_voice", "gesture": "none", "prompt": "leaning in slightly, hand cupped near mouth as if lowering voice, serious secretive expression"},
    {"expression": "neutral", "pose": "scene_setting", "gesture": "sweeping", "prompt": "one hand sweeping across in front at chest level, neutral narrator expression, setting the scene"},
    {"expression": "excited", "pose": "plot_twist", "gesture": "none", "prompt": "head snapping toward camera, eyes wide with excitement, plot-twist energy, everything just changed"},
    {"expression": "smiling", "pose": "wrapping_up", "gesture": "none", "prompt": "hands coming together at chest, satisfied smile, wrapping-up-the-story energy, tying it all together"},
    # ===== ENGAGEMENT (~12) =====
    {"expression": "smiling", "pose": "welcoming", "gesture": "open_arms", "prompt": "arms open wide at chest level in welcoming gesture, warm inviting smile, greeting the audience"},
    {"expression": "curious", "pose": "inviting_question", "gesture": "palm_up", "prompt": "one hand extended palm up inviting response, curious expression, what-do-you-think energy"},
    {"expression": "smiling", "pose": "acknowledging", "gesture": "nodding", "prompt": "small nod with knowing smile, acknowledging the viewer, I-see-you expression"},
    {"expression": "grateful", "pose": "thanking", "gesture": "hand_on_chest", "prompt": "hand on chest with genuine grateful expression, warm eyes, thanking the audience sincerely"},
    {"expression": "smiling", "pose": "encouraging", "gesture": "thumbs_up", "prompt": "thumbs up with encouraging warm smile, you-can-do-it energy, supportive lean forward"},
    {"expression": "serious", "pose": "challenging", "gesture": "pointing", "prompt": "pointing at camera with challenging expression, I-dare-you energy, eyebrows raised in challenge"},
    {"expression": "amused", "pose": "conspiratorial_whisper", "gesture": "hand_cupped", "prompt": "hand cupped at side of mouth as if whispering, conspiratorial amused expression, sharing a secret"},
    {"expression": "serious", "pose": "breaking_news", "gesture": "none", "prompt": "hands clasped at chest, serious urgent expression, about to deliver important information, news anchor energy"},
    {"expression": "excited", "pose": "hyping_up", "gesture": "both_fists", "prompt": "both fists raised near shoulders in hype gesture, excited pumped expression, getting the crowd going"},
    {"expression": "smiling", "pose": "high_five", "gesture": "palm_out", "prompt": "palm raised facing camera as if offering high five, big happy smile, celebratory energy"},
    {"expression": "neutral", "pose": "listening", "gesture": "none", "prompt": "slightly tilted head, hand near ear, attentive listening expression, focused on hearing something"},
    {"expression": "smiling", "pose": "sign_off", "gesture": "peace_sign", "prompt": "peace sign held up near face, casual warm smile, signing off for now, see-you-next-time energy"},
    # ===== ADDITIONAL COMBOS (~16) =====
    {"expression": "excited", "pose": "mind_blown", "gesture": "explosion", "prompt": "both hands at temples then spreading outward like explosion, mind-blown expression, eyes huge, jaw dropped"},
    {"expression": "confused", "pose": "shrugging", "gesture": "hands_spread", "prompt": "shoulders up in confused shrug, palms up at chest level, bewildered expression, no idea what happened"},
    {"expression": "proud", "pose": "arms_crossed_confident", "gesture": "none", "prompt": "arms crossed at chest with confident proud expression, slight smile, nailed-it energy"},
    {"expression": "worried", "pose": "biting_nails", "gesture": "biting", "prompt": "one hand near mouth with nervous nail-biting gesture, worried wide eyes, anxious about the outcome"},
    {"expression": "amused", "pose": "chef_kiss", "gesture": "chef_kiss", "prompt": "fingers pressed together at lips in chef's kiss gesture, eyes closed in appreciation, perfection expression"},
    {"expression": "frustrated", "pose": "pinching_bridge", "gesture": "pinching", "prompt": "fingers pinching bridge of nose under glasses, frustrated eyes-closed expression, dealing with nonsense"},
    {"expression": "excited", "pose": "air_guitar", "gesture": "playing", "prompt": "hands positioned as if playing air guitar, excited rocking expression, pure joy and energy"},
    {"expression": "thinking", "pose": "weighing_options", "gesture": "scales", "prompt": "both hands at chest level moving up and down like scales, thoughtful weighing expression, comparing two things"},
    {"expression": "smiling", "pose": "finger_guns", "gesture": "finger_guns", "prompt": "both hands making finger guns pointed at camera, playful wink and grin, got-you energy"},
    {"expression": "serious", "pose": "hand_stop", "gesture": "stop", "prompt": "one palm raised facing camera in firm stop gesture, serious expression, hold-on-a-second energy"},
    {"expression": "neutral", "pose": "adjusting_glasses", "gesture": "adjusting", "prompt": "one hand pushing glasses up on nose, neutral intellectual expression, classic anime glasses adjust"},
    {"expression": "surprised", "pose": "spit_take", "gesture": "none", "prompt": "head jerked to the side, eyes bulging, cheeks puffed, shocked spit-take reaction, did NOT expect that"},
    {"expression": "smiling", "pose": "heart_hands", "gesture": "heart", "prompt": "both hands forming a heart shape at chest level, warm loving smile, sending love to audience"},
    {"expression": "determined", "pose": "rolling_sleeves", "gesture": "rolling", "prompt": "miming rolling up hoodie sleeves, determined fierce expression, getting down to business"},
    {"expression": "nervous", "pose": "peeking_through_fingers", "gesture": "peeking", "prompt": "both hands over face with fingers spread apart to peek through, nervous scared expression, can't look but must"},
    {"expression": "excited", "pose": "touchdown", "gesture": "arms_up", "prompt": "both arms straight up in touchdown/victory pose, ecstatic expression, celebration mode, we did it"},
]

THUMBNAIL_FRAME_DEFINITIONS: list[dict[str, str]] = [
    # --- Pattern Interrupt (High Surprise) ---
    {"expression": "gasped", "pose": "breath_intake", "gesture": "none",
     "prompt": "mouth slightly open in a gasp, eyes wide open, eyebrows raised high, shocked intake of breath, looking directly at camera"},
    {"expression": "cringe", "pose": "wince", "gesture": "none",
     "prompt": "one eye squinting shut, mouth pulled to the side in a cringe, uncomfortable wincing expression"},
    {"expression": "hyperfocus", "pose": "leaning_forward", "gesture": "none",
     "prompt": "leaning slightly into camera, pupils dilated, wide intense eyes, mouth slightly open, hyper-focused stare at something incredible"},
    # --- Negative Tension (Anxiety & Concern) ---
    {"expression": "furrowed", "pose": "hand_on_forehead", "gesture": "hand_on_forehead",
     "prompt": "brows pinched together, deep forehead furrow, hand on forehead, worried concerned expression, mouth slightly open processing something troubling"},
    {"expression": "tearful", "pose": "glistening_eyes", "gesture": "none",
     "prompt": "eyes glistening with held-back tears, red-rimmed eyes, emotional expression, bottom lip slightly quivering, mouth slightly open, deeply moved"},
    {"expression": "secretive", "pose": "shush", "gesture": "finger_to_lips",
     "prompt": "index finger pressed to lips in shush gesture, eyes darting to the side, secretive conspiratorial expression, mouth slightly open behind finger"},
    # --- Action-Oriented (Excitement & Joy) ---
    {"expression": "laughing", "pose": "mid_laugh", "gesture": "none",
     "prompt": "genuine squinty-eyed laugh, mouth wide open laughing, eyes crinkled shut with joy, head tilted back slightly, infectious full laughter"},
    {"expression": "lookatthis", "pose": "gazing_offscreen", "gesture": "none",
     "prompt": "NOT looking at camera, head turned to the side gazing at something off-screen with intense wonder, mouth open in awe, captivated by something amazing"},
    {"expression": "exertion", "pose": "struggle", "gesture": "none",
     "prompt": "teeth gritted with effort, brow sweating, strained exertion expression, mouth open showing gritted teeth, determined struggle"},
]

# -- Eli pose picker system prompt --

ELI_POSE_PICKER_SYSTEM = register(PromptDef(
    name="ELI_POSE_PICKER_SYSTEM",
    domain="CHARACTER",
    purpose="Pick one pose per scene that matches narration emotional tone",
    target_model="claude",
    expected_output_format="JSON: {frame_id, corner}",
    template="""You pick ONE character pose for a scene overlay. The character is "Eli," an animated host who appears in a corner of educational YouTube videos.

## Input
- Narration text for this scene
- List of available pose names (frame IDs)
- Previous corner (if any)

## Output
Return a JSON object:
```json
{"frame_id": "...", "corner": "..."}
```

## Pose Selection
Pick the single pose that best matches the emotional tone of the narration:
- Explanatory content → explaining poses, hand gestures
- Surprising facts → excited, surprised
- Questions → curious, thinking
- Serious/concerning → serious, worried
- Default/neutral → neutral, smiling

## Corner Assignment
Pick one of: "TL", "TR", "BL", "BR"
- MUST be different from `previous_corner`
- Alternate left↔right sides (if previous was left, pick right)
- ~70% bottom, ~30% top
- First scene (no previous): use "BR"

Return ONLY the JSON object.""",
    retention=RetentionMeta(
        goal="Natural pose selection matching narration tone",
        failure_mode="Mismatched pose looks disconnected from content",
        metrics_to_watch=["avg_view_duration"],
    ),
))


ELI_POSE_PICKER_BATCH_SYSTEM = register(PromptDef(
    name="ELI_POSE_PICKER_BATCH_SYSTEM",
    domain="CHARACTER",
    purpose="Pick one pose for many scenes in a single response, keyed by scene id",
    target_model="claude",
    expected_output_format='JSON: {"scenes": [{"id", "frame_id"}]}',
    template="""You pick character poses for a batch of scenes. The character is "Eli," an animated host who appears in a corner of educational YouTube videos.

## Input
A JSON object:
```json
{
  "available_poses": ["pose_id_a", "pose_id_b", ...],
  "scenes": [
    {"id": "scene-id-1", "narration": "..."},
    {"id": "scene-id-2", "narration": "..."}
  ]
}
```

## Output
Return a JSON object with one entry per input scene, in the same order, echoing the same id:
```json
{
  "scenes": [
    {"id": "scene-id-1", "frame_id": "..."},
    {"id": "scene-id-2", "frame_id": "..."}
  ]
}
```

## Pose Selection
For each scene, pick the single `frame_id` from `available_poses` that best matches the narration's emotional tone:
- Explanatory content → explaining poses, hand gestures
- Surprising facts → excited, surprised
- Questions → curious, thinking
- Serious/concerning → serious, worried
- Default/neutral → neutral, smiling

Vary your selection across the batch — avoid repeating the same `frame_id` on consecutive scenes when the narration tone differs. Do NOT include `corner` — corner placement is handled deterministically by the caller.

Return ONLY the JSON object.""",
    retention=RetentionMeta(
        goal="Batched pose selection at one LLM call per chunk",
        failure_mode="Schema drift forces per-scene retries and wastes the batch call",
        metrics_to_watch=["fx_eli_cost_per_script"],
    ),
))


# ===================================================================
# DOMAIN: IMAGE
# ===================================================================

# -- Visual style (formerly visual_style.md) --

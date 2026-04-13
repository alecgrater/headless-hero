"""Character frame library generation — creates Eli character overlay frames.

Generates ~300 frames (150 pose combos x 2 mouth states) for the Eli character
overlay system. Uses Gemini image generation with reference image chaining
for cross-frame consistency. Supports reference candidate selection workflow.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import DATA_DIR
from integrations.google_image_client import generate_image

logger = logging.getLogger(__name__)

# --- Variant tier configuration ---
TIER_1_EXPRESSIONS = {"neutral", "thinking", "excited", "explaining", "curious", "smiling"}
TIER_2_EXPRESSIONS = {"surprised", "confused", "skeptical", "serious", "worried"}


def variant_count_for_expression(expression: str) -> int:
    """Return how many body micro-variants a given expression should have."""
    if expression in TIER_1_EXPRESSIONS:
        return 5
    if expression in TIER_2_EXPRESSIONS:
        return 3
    return 1


# Subtle variation instructions per variant number (v2-v5)
_VARIANT_PROMPTS: dict[int, str] = {
    2: "head tilted very slightly to the left, eyes looking slightly right",
    3: "head tilted very slightly to the right, weight shifted to other side",
    4: "chin slightly raised, shoulders relaxed differently",
    5: "subtle lean forward, eyes looking slightly up",
}

CHARACTER_DIR = DATA_DIR / "character"
FRAMES_DIR = CHARACTER_DIR / "frames"
REFERENCES_DIR = CHARACTER_DIR / "references"
MANIFEST_PATH = CHARACTER_DIR / "manifest.json"
REFERENCE_SELECTION_PATH = CHARACTER_DIR / "reference_selection.json"
SELECTED_REFERENCE_PATH = FRAMES_DIR / "selected_reference.png"

# Load character spec from canonical source
_CHARACTER_MD_PATH = Path(__file__).resolve().parent.parent / "prompts" / "character.md"
_CHARACTER_MD = _CHARACTER_MD_PATH.read_text() if _CHARACTER_MD_PATH.exists() else ""

# Condensed visual spec extracted from character.md for image generation prompts.
# Framing instructions are kept separate since they're specific to frame generation.
CHARACTER_SPEC = (
    "Character: \"Eli\" — " + (
        "young adult male, early-to-mid 20s, medium-brown skin, short slightly messy "
        "dark curly hair, round glasses with thin frames, warm brown eyes. Slightly large "
        "head relative to body (cartoon proportions — approx 1:5 head-to-body ratio), "
        "lean build. Wearing a muted teal crewneck t-shirt layered under an open charcoal "
        "gray zip hoodie. Flat 2D cartoon style, bold outlines, cel-shaded."
    )
)

# Repeated prompt fragments used across multiple prompt-building sites
GREEN_BG_INSTRUCTION = (
    "Solid flat green (#00FF00) background with NO other elements."
)
REFERENCE_CONSISTENCY_INSTRUCTION = (
    "Maintain identical character design, proportions, outfit colors, glasses, "
    "hair style, and rendering style."
)

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

    # ===== NEW: TEACHING / PRESENTING (~12) =====
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

    # ===== NEW: EMOTIONAL REACTIONS (~12) =====
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

    # ===== NEW: TRANSITION / NARRATIVE (~12) =====
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

    # ===== NEW: CONVERSATIONAL MICRO-EXPRESSIONS (~12) =====
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

    # ===== NEW: PHYSICAL ENERGY (~12) =====
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

    # ===== NEW: STORYTELLING (~12) =====
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

    # ===== NEW: ENGAGEMENT (~12) =====
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

    # ===== NEW: ADDITIONAL COMBOS (~16) =====
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


def _frame_id(definition: dict[str, str]) -> str:
    """Generate a frame ID from definition fields."""
    expr = definition["expression"]
    pose = definition["pose"].replace("_", "")
    return f"{expr}_{pose}"


def _make_unique_ids(definitions: list[dict[str, str]]) -> list[str]:
    """Generate unique frame IDs, appending suffix for duplicates."""
    ids: list[str] = []
    seen: dict[str, int] = {}
    for d in definitions:
        base = _frame_id(d)
        if base in seen:
            seen[base] += 1
            ids.append(f"{base}_{seen[base]}")
        else:
            seen[base] = 0
            ids.append(base)
    return ids


FRAMING_INSTRUCTION = (
    "Close-up chest-up framing — head positioned in the upper third of the frame, "
    "shoulders and upper chest visible, cut off below the chest. Like a Twitch streamer "
    "webcam PIP. NO waist, NO lower body visible."
)


def _build_prompt(definition: dict[str, str], mouth_state: str, is_canonical: bool) -> str:
    """Build the image generation prompt for a frame."""
    mouth_desc = "mouth open, speaking" if mouth_state == "open" else "mouth closed"

    if is_canonical:
        return (
            f"Generate a chest-up character illustration on a solid bright green (#00FF00) background.\n\n"
            f"{CHARACTER_SPEC}\n\n"
            f"Pose: {definition['prompt']}\n"
            f"Mouth: {mouth_desc}\n\n"
            f"IMPORTANT: {GREEN_BG_INSTRUCTION} "
            f"{FRAMING_INSTRUCTION} "
            f"16:9 aspect ratio composition. Flat 2D cartoon style with bold outlines."
        )
    else:
        return (
            f"Using the reference image as the character design reference, render the EXACT same character "
            f"in a different pose. {REFERENCE_CONSISTENCY_INSTRUCTION}\n\n"
            f"Pose: {definition['prompt']}\n"
            f"Mouth: {mouth_desc}\n\n"
            f"IMPORTANT: {GREEN_BG_INSTRUCTION} "
            f"{FRAMING_INSTRUCTION} "
            f"16:9 aspect ratio composition. Same flat 2D cartoon style as reference."
        )


def _chroma_key_green(img: "Image.Image") -> "Image.Image":
    """Replace green-ish background pixels with transparent using numpy.

    Handles both pure green (#00FF00) and the muted sage/pastel greens
    that Gemini often generates instead. Uses HSV color space for robust
    detection of any green-dominant background.
    """
    import numpy as np

    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    rgb = arr[:, :, :3].astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    # Method 1: Pure green (original) — g high, r and b low
    pure_green = (g > 180) & (r < 100) & (b < 100)

    # Method 2: Muted/sage green — green is dominant channel by a margin
    # Catches backgrounds like (140, 190, 130), (120, 180, 120), etc.
    green_dominant = (g > 120) & (g > r + 20) & (g > b + 20) & (r < 200) & (b < 200)

    # Method 3: Pastel/light green — lighter backgrounds where all channels are
    # high but green still leads. E.g. (170, 210, 160)
    pastel_green = (g > 150) & (g > r) & (g > b) & (r > 100) & (b > 100) & ((g - r) > 10) & ((g - b) > 10)

    mask = pure_green | green_dominant | pastel_green
    pixels_removed = int(np.sum(mask))
    total_pixels = arr.shape[0] * arr.shape[1]

    logger.info(
        "Chroma key: %d/%d pixels (%.1f%%) matched green — pure=%d, dominant=%d, pastel=%d",
        pixels_removed, total_pixels, pixels_removed / total_pixels * 100,
        int(np.sum(pure_green)), int(np.sum(green_dominant)), int(np.sum(pastel_green)),
    )

    arr[mask, 3] = 0  # set alpha to 0
    from PIL import Image as PILImage
    return PILImage.fromarray(arr, "RGBA")


def _has_background(img: "Image.Image", filename: str = "") -> bool:
    """Detect whether an RGBA image still has a non-transparent background.

    Samples corners and edges. Returns True if significant opaque areas are
    found in regions that should be transparent background.
    """
    import numpy as np

    w, h = img.size
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    alpha = arr[:, :, 3]

    # Sample multiple points in corners and edges (areas likely to be background)
    sample_points = [
        # Corners (multiple points per corner for robustness)
        (2, 2), (5, 5), (10, 10),
        (w - 3, 2), (w - 6, 5), (w - 11, 10),
        (2, h - 3), (5, h - 6), (10, h - 11),
        (w - 3, h - 3), (w - 6, h - 6), (w - 11, h - 11),
        # Edge midpoints
        (w // 2, 2), (w // 2, h - 3),  # top/bottom center
        (2, h // 2), (w - 3, h // 2),  # left/right center
    ]

    opaque_count = 0
    for x, y in sample_points:
        if 0 <= x < w and 0 <= y < h and alpha[y, x] > 200:
            opaque_count += 1

    # Also check what fraction of the top 10 rows are opaque (a strong background signal)
    top_strip = alpha[:10, :]
    top_opaque_frac = float(np.mean(top_strip > 200))

    # Check overall image transparency ratio
    total_opaque_frac = float(np.mean(alpha > 200))

    has_bg = opaque_count >= 8 or top_opaque_frac > 0.8

    logger.info(
        "Background check [%s]: opaque_samples=%d/%d, top_strip_opaque=%.1f%%, "
        "total_opaque=%.1f%% → %s",
        filename, opaque_count, len(sample_points),
        top_opaque_frac * 100, total_opaque_frac * 100,
        "HAS BACKGROUND" if has_bg else "ok",
    )

    return has_bg


def _corners_are_opaque(img: "Image.Image") -> bool:
    """Check if all four corners of an RGBA image are fully opaque."""
    w, h = img.size
    corners = [
        img.getpixel((5, 5)), img.getpixel((w - 6, 5)),
        img.getpixel((5, h - 6)), img.getpixel((w - 6, h - 6)),
    ]
    return all(c[3] == 255 for c in corners)


def _remove_background(src_path: str, dst_path: str) -> None:
    """Remove background from generated image using rembg + chroma key fallback."""
    from PIL import Image
    import io

    src_name = src_path.rsplit("/", 1)[-1] if "/" in src_path else src_path
    logger.info("Background removal starting: %s → %s", src_name, dst_path)

    try:
        from rembg import remove

        with open(src_path, "rb") as f:
            input_bytes = f.read()

        logger.info("Running rembg on %s (%d bytes)", src_name, len(input_bytes))
        output_bytes = remove(input_bytes)
        img = Image.open(io.BytesIO(output_bytes)).convert("RGBA")

        if _has_background(img, f"rembg-output:{src_name}"):
            logger.warning("rembg output still has background, applying chroma key: %s", src_name)
            img = _chroma_key_green(img)

            if _has_background(img, f"after-chroma:{src_name}"):
                logger.warning("Background STILL detected after chroma key: %s (may need manual review)", src_name)
            else:
                logger.info("Chroma key successfully removed remaining background: %s", src_name)
        else:
            logger.info("rembg fully removed background: %s", src_name)

        img.save(dst_path, "PNG")
        logger.info("Background removed and saved: %s", dst_path)
    except ImportError:
        logger.warning("rembg not installed, applying chroma key fallback: %s", dst_path)
        img = Image.open(src_path).convert("RGBA")
        img = _chroma_key_green(img)
        img.save(dst_path, "PNG")
    except Exception:
        logger.warning("rembg failed, applying chroma key fallback: %s", dst_path, exc_info=True)
        img = Image.open(src_path).convert("RGBA")
        img = _chroma_key_green(img)
        img.save(dst_path, "PNG")


def get_manifest() -> dict | None:
    """Read the frame manifest, or None if not generated yet."""
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text())


def clear_all_frames() -> dict[str, int]:
    """Delete all frames, references, manifest, and selection. Returns counts."""
    deleted_frames = 0
    deleted_refs = 0

    # Delete all frame PNGs (including selected_reference.png)
    if FRAMES_DIR.exists():
        for f in FRAMES_DIR.glob("*.png"):
            f.unlink()
            deleted_frames += 1

    # Delete references
    if REFERENCES_DIR.exists():
        for f in REFERENCES_DIR.glob("*.png"):
            f.unlink()
            deleted_refs += 1

    # Delete manifest and selection metadata
    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()
    if REFERENCE_SELECTION_PATH.exists():
        REFERENCE_SELECTION_PATH.unlink()

    logger.info("Cleared all frames (%d) and references (%d)", deleted_frames, deleted_refs)
    return {"deleted_frames": deleted_frames, "deleted_references": deleted_refs}


# ---------------------------------------------------------------------------
# Reference candidate generation & selection
# ---------------------------------------------------------------------------

# Subtle variation dimensions for reference candidates
_REFERENCE_VARIATIONS = [
    "slightly warmer color palette with golden undertones",
    "slightly cooler color palette with blue undertones",
    "thinner line weight with more delicate outlines",
    "thicker bolder line weight with chunky outlines",
    "slightly rounder face shape and softer features",
    "slightly more angular face shape and sharper features",
    "slightly larger eyes in anime-influenced proportion",
    "slightly smaller more realistic eye proportions",
    "more voluminous fluffy curly hair",
    "tighter neater shorter curly hair",
    "slightly more saturated vibrant clothing colors",
    "slightly more muted desaturated clothing colors",
    "softer cel-shading with gentle gradients",
    "harder cel-shading with sharp flat color blocks",
    "standard balanced design as described",
]


def generate_reference_candidates(
    count: int = 15,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[dict[str, Any]]:
    """Generate reference candidate images for user selection.

    Creates `count` independent character images with subtle style variations.
    No reference image chaining — each is generated from scratch.
    No background removal — user is just picking the look.

    Returns list of {"filename": "reference_01.png", "index": 1}.
    """
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)

    # Clear existing candidates
    for existing in REFERENCES_DIR.glob("reference_*.png"):
        existing.unlink()

    candidates: list[dict[str, Any]] = []

    for i in range(count):
        idx = i + 1
        filename = f"reference_{idx:02d}.png"
        output_path = REFERENCES_DIR / filename
        label = f"Reference candidate {idx}/{count}"

        variation = _REFERENCE_VARIATIONS[i % len(_REFERENCE_VARIATIONS)]

        prompt = (
            f"Generate a chest-up character illustration on a solid bright green (#00FF00) background.\n\n"
            f"{CHARACTER_SPEC}\n\n"
            f"Pose: shoulders relaxed, neutral calm expression, looking forward at camera\n"
            f"Mouth: mouth closed\n\n"
            f"Style variation: {variation}\n\n"
            f"IMPORTANT: {GREEN_BG_INSTRUCTION} "
            f"{FRAMING_INSTRUCTION} "
            f"16:9 aspect ratio composition. Flat 2D cartoon style with bold outlines."
        )

        logger.info("Generating reference candidate %d/%d", idx, count)

        try:
            tmp_path = generate_image(
                prompt=prompt,
                width=768,
                height=432,
                reference_image_path=None,
            )
            shutil.copy2(tmp_path, str(output_path))
            candidates.append({"filename": filename, "index": idx})
        except Exception:
            logger.error("Failed to generate reference candidate %d", idx, exc_info=True)

        if on_progress:
            on_progress(idx, count, label)

    return candidates


def get_reference_candidates() -> list[str]:
    """Return sorted list of reference candidate filenames."""
    if not REFERENCES_DIR.exists():
        return []
    return sorted(f.name for f in REFERENCES_DIR.glob("reference_*.png"))


def get_selected_reference() -> str | None:
    """Return filename of selected reference, or None if none selected."""
    if not REFERENCE_SELECTION_PATH.exists():
        return None
    data = json.loads(REFERENCE_SELECTION_PATH.read_text())
    return data.get("selected")


def select_reference(filename: str) -> str:
    """Select a reference candidate as the canonical reference for frame generation.

    Copies the chosen file to FRAMES_DIR/selected_reference.png and writes selection metadata.
    Returns the path to the selected reference.
    """
    src = REFERENCES_DIR / filename
    if not src.exists():
        raise FileNotFoundError(f"Reference candidate not found: {filename}")

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(SELECTED_REFERENCE_PATH))

    REFERENCE_SELECTION_PATH.write_text(json.dumps({
        "selected": filename,
        "selected_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))

    logger.info("Selected reference: %s -> %s", filename, SELECTED_REFERENCE_PATH)
    return str(SELECTED_REFERENCE_PATH)


def generate_frame_library(
    reference_path: str | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Generate the full Eli character frame library.

    If reference_path is provided, use it as the canonical reference for ALL frames
    (skip auto-generating the first frame as canonical).
    If None, check for selected_reference.png, then fall back to auto-generating first frame.

    on_progress(completed, total, current_label) is called after each frame.
    Returns the manifest dict.
    """
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve reference path
    if reference_path is None and SELECTED_REFERENCE_PATH.exists():
        reference_path = str(SELECTED_REFERENCE_PATH)

    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    total = len(FRAME_DEFINITIONS) * 2  # 2 mouth states each
    completed = 0
    canonical_path: str | None = reference_path

    manifest_frames: list[dict[str, Any]] = []

    for i, (defn, frame_id) in enumerate(zip(FRAME_DEFINITIONS, frame_ids)):
        # Only treat first frame as canonical if no reference was provided
        is_first_without_ref = (i == 0 and reference_path is None)

        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename
            label = f"{frame_id} ({mouth_state})"

            logger.info("Generating frame %d/%d: %s", completed + 1, total, label)

            needs_canonical_prompt = is_first_without_ref and mouth_state == "closed"
            prompt = _build_prompt(defn, mouth_state, needs_canonical_prompt)
            ref_path = None if needs_canonical_prompt else canonical_path

            try:
                tmp_path = generate_image(
                    prompt=prompt,
                    width=768,
                    height=432,
                    reference_image_path=ref_path,
                )
                _remove_background(tmp_path, str(output_path))

                # Set canonical path from the first generated frame (only if no reference provided)
                if needs_canonical_prompt:
                    canonical_path = str(output_path)

            except Exception:
                logger.error("Failed to generate frame %s", label, exc_info=True)

            completed += 1
            if on_progress:
                on_progress(completed, total, label)

        manifest_frames.append({
            "id": frame_id,
            "file_closed": f"{frame_id}_closed.png",
            "file_open": f"{frame_id}_open.png",
            "expression": defn["expression"],
            "pose": defn["pose"],
            "gesture": defn["gesture"],
            "variant_count": variant_count_for_expression(defn["expression"]),
        })

    # Write manifest
    manifest = {
        "canonical_frame": f"{frame_ids[0]}_closed.png",
        "reference_source": "selected_reference" if reference_path else "auto_generated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frames": manifest_frames,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    logger.info("Frame library generated: %d frames, manifest at %s", total, MANIFEST_PATH)

    return manifest


def regenerate_frame(frame_id: str) -> dict:
    """Regenerate a single frame (both mouth states) using canonical reference.

    Checks for selected_reference.png first, then falls back to manifest canonical_frame.
    Returns the updated frame entry.
    """
    manifest = get_manifest()
    if not manifest:
        raise RuntimeError("No frame library exists. Generate the full library first.")

    # Find the frame definition
    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    defn_idx = None
    for i, fid in enumerate(frame_ids):
        if fid == frame_id:
            defn_idx = i
            break

    if defn_idx is None:
        raise ValueError(f"Unknown frame_id: {frame_id}")

    defn = FRAME_DEFINITIONS[defn_idx]

    # Prefer selected reference over manifest canonical
    if SELECTED_REFERENCE_PATH.exists():
        canonical_path = str(SELECTED_REFERENCE_PATH)
    else:
        canonical_path = str(FRAMES_DIR / manifest["canonical_frame"])

    for mouth_state in ["closed", "open"]:
        filename = f"{frame_id}_{mouth_state}.png"
        output_path = FRAMES_DIR / filename

        prompt = _build_prompt(defn, mouth_state, False)
        tmp_path = generate_image(
            prompt=prompt,
            width=768,
            height=432,
            reference_image_path=canonical_path,
        )
        _remove_background(tmp_path, str(output_path))

    # Update manifest timestamp
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    return {
        "id": frame_id,
        "file_closed": f"{frame_id}_closed.png",
        "file_open": f"{frame_id}_open.png",
        "expression": defn["expression"],
        "pose": defn["pose"],
        "gesture": defn["gesture"],
        "variant_count": variant_count_for_expression(defn["expression"]),
    }


def count_missing_frames() -> int:
    """Count how many frame definitions are missing one or both PNG files on disk."""
    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    missing = 0
    for frame_id in frame_ids:
        closed = FRAMES_DIR / f"{frame_id}_closed.png"
        opened = FRAMES_DIR / f"{frame_id}_open.png"
        if not closed.exists() or not opened.exists():
            missing += 1
    return missing


def generate_missing_frames(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Generate only frames whose PNG files are missing from disk.

    Skips any frame where both closed and open mouth PNGs already exist.
    Uses selected_reference.png as the canonical reference.
    Returns the manifest dict.
    """
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve reference
    if SELECTED_REFERENCE_PATH.exists():
        canonical_path = str(SELECTED_REFERENCE_PATH)
    else:
        manifest = get_manifest()
        if manifest and manifest.get("canonical_frame"):
            canonical_path = str(FRAMES_DIR / manifest["canonical_frame"])
        else:
            raise RuntimeError("No reference image available. Select a reference first.")

    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)

    # Identify which frames need generation
    missing: list[tuple[int, str]] = []  # (defn_index, frame_id)
    for i, frame_id in enumerate(frame_ids):
        closed = FRAMES_DIR / f"{frame_id}_closed.png"
        opened = FRAMES_DIR / f"{frame_id}_open.png"
        if not closed.exists() or not opened.exists():
            missing.append((i, frame_id))

    total = len(missing) * 2  # 2 mouth states each
    completed = 0

    for defn_idx, frame_id in missing:
        defn = FRAME_DEFINITIONS[defn_idx]

        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename
            label = f"{frame_id} ({mouth_state})"

            # Skip if this specific file already exists (e.g. only one mouth state was missing)
            if output_path.exists():
                completed += 1
                if on_progress:
                    on_progress(completed, total, label)
                continue

            logger.info("Generating missing frame %d/%d: %s", completed + 1, total, label)

            prompt = _build_prompt(defn, mouth_state, False)

            try:
                tmp_path = generate_image(
                    prompt=prompt,
                    width=768,
                    height=432,
                    reference_image_path=canonical_path,
                )
                _remove_background(tmp_path, str(output_path))
            except Exception:
                logger.error("Failed to generate frame %s", label, exc_info=True)

            completed += 1
            if on_progress:
                on_progress(completed, total, label)

    # Rebuild manifest with all frame definitions
    manifest_frames = []
    for frame_id, defn in zip(frame_ids, FRAME_DEFINITIONS):
        manifest_frames.append({
            "id": frame_id,
            "file_closed": f"{frame_id}_closed.png",
            "file_open": f"{frame_id}_open.png",
            "expression": defn["expression"],
            "pose": defn["pose"],
            "gesture": defn["gesture"],
            "variant_count": variant_count_for_expression(defn["expression"]),
        })

    manifest = {
        "canonical_frame": f"{frame_ids[0]}_closed.png",
        "reference_source": "selected_reference",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frames": manifest_frames,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    logger.info("Missing frames generated: %d frames filled in", len(missing))

    return manifest


def load_variant_counts() -> dict[str, int]:
    """Read manifest and return a map of {frame_id: variant_count}.

    Returns empty dict if manifest doesn't exist.
    """
    manifest = get_manifest()
    if not manifest:
        return {}
    return {f["id"]: f.get("variant_count", 1) for f in manifest.get("frames", [])}


def _build_variant_prompt(definition: dict[str, str], mouth_state: str, variant_num: int) -> str:
    """Build the image generation prompt for a variant frame.

    Uses the original frame (variant 1) as reference and adds subtle variation instructions.
    """
    mouth_desc = "mouth open, speaking" if mouth_state == "open" else "mouth closed"
    variation_instruction = _VARIANT_PROMPTS.get(variant_num, "")

    return (
        f"Using the reference image as the character design reference, render the EXACT same character "
        f"in the EXACT same pose with a very subtle body micro-variation. {REFERENCE_CONSISTENCY_INSTRUCTION.rstrip('.')}, AND the same "
        f"expression and gesture.\n\n"
        f"Pose: {definition['prompt']}\n"
        f"Mouth: {mouth_desc}\n"
        f"Subtle variation: {variation_instruction}\n\n"
        f"IMPORTANT: The variation must be VERY subtle — this is the same pose with a tiny body shift, "
        f"not a different pose. {GREEN_BG_INSTRUCTION} "
        f"{FRAMING_INSTRUCTION} "
        f"16:9 aspect ratio composition. Same flat 2D cartoon style as reference."
    )


def generate_variants(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Generate body micro-variants for all frames that need them.

    Reads the manifest to find frames with variant_count > 1, then generates
    variants 2..N for each. Uses the existing frame (variant 1) as reference
    image for consistency.

    Returns the updated manifest.
    """
    manifest = get_manifest()
    if not manifest:
        raise RuntimeError("No frame library exists. Generate the full library first.")

    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    frames_by_id = {f["id"]: f for f in manifest.get("frames", [])}

    # Build work list: (defn_index, frame_id, variant_num)
    work: list[tuple[int, str, int]] = []
    for i, frame_id in enumerate(frame_ids):
        frame_entry = frames_by_id.get(frame_id)
        if not frame_entry:
            continue
        vc = frame_entry.get("variant_count", 1)
        if vc <= 1:
            continue
        for v in range(2, vc + 1):
            # Skip if variant files already exist
            suffix = f"_v{v}"
            closed = FRAMES_DIR / f"{frame_id}{suffix}_closed.png"
            opened = FRAMES_DIR / f"{frame_id}{suffix}_open.png"
            if closed.exists() and opened.exists():
                continue
            work.append((i, frame_id, v))

    total = len(work) * 2  # 2 mouth states each
    completed = 0

    for defn_idx, frame_id, variant_num in work:
        defn = FRAME_DEFINITIONS[defn_idx]
        variant_suffix = f"_v{variant_num}"

        # Use the original frame (variant 1, closed mouth) as reference for consistency
        ref_path = str(FRAMES_DIR / f"{frame_id}_closed.png")
        if not Path(ref_path).exists():
            logger.warning("Original frame missing for %s, skipping variants", frame_id)
            completed += 2
            if on_progress:
                on_progress(completed, total, f"{frame_id} v{variant_num} (skipped)")
            continue

        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}{variant_suffix}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename
            label = f"{frame_id} v{variant_num} ({mouth_state})"

            logger.info("Generating variant %d/%d: %s", completed + 1, total, label)

            prompt = _build_variant_prompt(defn, mouth_state, variant_num)

            try:
                tmp_path = generate_image(
                    prompt=prompt,
                    width=768,
                    height=432,
                    reference_image_path=ref_path,
                )
                _remove_background(tmp_path, str(output_path))
            except Exception:
                logger.error("Failed to generate variant %s", label, exc_info=True)

            completed += 1
            if on_progress:
                on_progress(completed, total, label)

    # Update manifest timestamp
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    logger.info("Variant generation complete: %d variant frames generated", len(work) * 2)

    return manifest


def generate_frame_variants(frame_id: str) -> dict:
    """Generate variants for a single frame.

    Uses the original frame (variant 1) as reference.
    Returns the updated frame entry.
    """
    manifest = get_manifest()
    if not manifest:
        raise RuntimeError("No frame library exists. Generate the full library first.")

    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    defn_idx = None
    for i, fid in enumerate(frame_ids):
        if fid == frame_id:
            defn_idx = i
            break

    if defn_idx is None:
        raise ValueError(f"Unknown frame_id: {frame_id}")

    defn = FRAME_DEFINITIONS[defn_idx]
    vc = variant_count_for_expression(defn["expression"])

    if vc <= 1:
        raise ValueError(f"Frame {frame_id} (expression: {defn['expression']}) has no variants (tier 3)")

    ref_path = str(FRAMES_DIR / f"{frame_id}_closed.png")
    if not Path(ref_path).exists():
        raise RuntimeError(f"Original frame not found: {ref_path}")

    for v in range(2, vc + 1):
        variant_suffix = f"_v{v}"
        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}{variant_suffix}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename

            prompt = _build_variant_prompt(defn, mouth_state, v)
            tmp_path = generate_image(
                prompt=prompt,
                width=768,
                height=432,
                reference_image_path=ref_path,
            )
            _remove_background(tmp_path, str(output_path))

    # Update manifest timestamp
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    return {
        "id": frame_id,
        "file_closed": f"{frame_id}_closed.png",
        "file_open": f"{frame_id}_open.png",
        "expression": defn["expression"],
        "pose": defn["pose"],
        "gesture": defn["gesture"],
        "variant_count": vc,
    }


def reprocess_backgrounds(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> int:
    """Re-run background removal on frames that still have non-transparent backgrounds.

    Scans all PNGs in FRAMES_DIR (excluding selected_reference.png),
    uses multi-point sampling to detect backgrounds, and re-runs chroma key
    + rembg on affected frames.

    Returns count of frames reprocessed.
    """
    from PIL import Image

    if not FRAMES_DIR.exists():
        logger.warning("FRAMES_DIR does not exist: %s", FRAMES_DIR)
        return 0

    all_pngs = [
        f for f in sorted(FRAMES_DIR.glob("*.png"))
        if f.name != "selected_reference.png"
    ]
    total = len(all_pngs)
    reprocessed = 0
    skipped = 0

    logger.info("=== Background reprocessing started: scanning %d frames in %s ===", total, FRAMES_DIR)

    for i, png_path in enumerate(all_pngs):
        label = png_path.stem
        try:
            img = Image.open(str(png_path)).convert("RGBA")
            logger.debug("Checking frame %d/%d: %s (size=%s)", i + 1, total, png_path.name, img.size)

            if _has_background(img, png_path.name):
                logger.info(">>> Reprocessing frame with background: %s", png_path.name)

                # First try chroma key (fast, handles green backgrounds)
                fixed = _chroma_key_green(img)

                if _has_background(fixed, f"after-chroma:{png_path.name}"):
                    # Chroma key wasn't enough, try rembg
                    logger.info("Chroma key insufficient for %s, trying rembg", png_path.name)
                    try:
                        from rembg import remove
                        import io

                        with open(str(png_path), "rb") as f:
                            input_bytes = f.read()
                        output_bytes = remove(input_bytes)
                        fixed = Image.open(io.BytesIO(output_bytes)).convert("RGBA")

                        if _has_background(fixed, f"after-rembg:{png_path.name}"):
                            # rembg wasn't enough either, apply chroma key on top
                            logger.warning("rembg insufficient, applying chroma key on rembg output: %s", png_path.name)
                            fixed = _chroma_key_green(fixed)
                    except ImportError:
                        logger.warning("rembg not installed, using chroma key result for %s", png_path.name)
                    except Exception:
                        logger.error("rembg failed for %s, using chroma key result", png_path.name, exc_info=True)

                fixed.save(str(png_path), "PNG")
                reprocessed += 1
                logger.info("Saved reprocessed frame: %s", png_path.name)
            else:
                skipped += 1
                logger.debug("Frame OK (no background detected): %s", png_path.name)
        except Exception:
            logger.error("Failed to check/reprocess %s", png_path.name, exc_info=True)

        if on_progress:
            on_progress(i + 1, total, label)

    logger.info(
        "=== Background reprocessing complete: %d reprocessed, %d already OK, %d total ===",
        reprocessed, skipped, total,
    )

    # Always update manifest timestamp so frontend cache-busting refreshes images
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
        manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
        logger.info("Updated manifest timestamp for cache busting")

    return reprocessed

"""Content modifiers package — registers all built-in modifiers on import."""

from pipeline.modifiers.registry import register

from pipeline.modifiers.title_cards import TitleCardsModifier
from pipeline.modifiers.real_media import RealMediaModifier
from pipeline.modifiers.animated_subtitles import AnimatedSubtitlesModifier

register(TitleCardsModifier())
register(RealMediaModifier())
register(AnimatedSubtitlesModifier())

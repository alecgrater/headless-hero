"""Content modifiers package — registers all built-in modifiers on import."""

from pipeline.modifiers.registry import register

from pipeline.modifiers.title_cards import TitleCardsModifier
from pipeline.modifiers.real_media import RealMediaModifier

register(TitleCardsModifier())
register(RealMediaModifier())

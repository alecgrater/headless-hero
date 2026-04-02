"""Content modifiers package — registers all built-in modifiers on import."""

from pipeline.modifiers.registry import register

from pipeline.modifiers.real_media import RealMediaModifier

register(RealMediaModifier())

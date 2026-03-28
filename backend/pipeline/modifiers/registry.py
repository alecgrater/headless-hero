"""Global registry for content modifiers."""

from pipeline.modifiers.base import ContentModifier, ModifierMeta

_registry: dict[str, ContentModifier] = {}


def register(modifier: ContentModifier) -> None:
    """Register a modifier instance by its meta.id."""
    _registry[modifier.meta.id] = modifier


def get_modifier(modifier_id: str) -> ContentModifier | None:
    """Look up a single modifier by ID."""
    return _registry.get(modifier_id)


def get_all() -> dict[str, ContentModifier]:
    """Return all registered modifiers."""
    return dict(_registry)


def get_active(ids: list[str]) -> list[ContentModifier]:
    """Return modifier instances for the given IDs, in order."""
    return [_registry[mid] for mid in ids if mid in _registry]


def all_metadata() -> list[dict]:
    """Return metadata dicts for all registered modifiers (for API response)."""
    return [
        {
            "id": m.meta.id,
            "name": m.meta.name,
            "description": m.meta.description,
            "icon": m.meta.icon,
        }
        for m in _registry.values()
    ]

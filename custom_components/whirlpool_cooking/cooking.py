"""Cooking control helpers for Whirlpool Cooking."""

from __future__ import annotations

from typing import Any

COOK_MODE_OPTIONS = (
    "Air Fry",
    "Bake",
    "Broil",
    "Convect Bake",
    "Convect Broil",
    "Convect Roast",
    "Keep Warm",
)


def cook_mode_option(mode: Any) -> str | None:
    """Return a Home Assistant option for a Whirlpool cook mode."""
    name = str(getattr(mode, "name", mode))
    option = enum_label(name)
    return option if option in COOK_MODE_OPTIONS else None


def cook_mode_from_option(option: str) -> Any:
    """Return a Whirlpool cook mode enum from a Home Assistant option."""
    from whirlpool.oven import CookMode

    normalized = _normalize_option(option)
    for mode in CookMode:
        if _normalize_option(mode.name) == normalized:
            return mode
    raise ValueError(option)


def cook_mode_attribute_value(option: str) -> str:
    """Return the raw Whirlpool attribute value for a cook mode option."""
    from whirlpool.oven import COOK_MODE_MAP

    return COOK_MODE_MAP[cook_mode_from_option(option)]


def cavity_attribute(cavity: Any, postfix: str) -> str:
    """Return a raw Whirlpool cavity attribute name."""
    from whirlpool.oven import CAVITY_PREFIX_MAP

    return f"{CAVITY_PREFIX_MAP[cavity]}_{postfix}"


def enum_label(value: Any) -> str | None:
    """Return a display label for a Whirlpool enum value."""
    if value is None:
        return None
    return _camel_to_label(str(getattr(value, "name", value)))


def _camel_to_label(value: str) -> str:
    """Convert Whirlpool enum names to display labels."""
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            chars.append(" ")
        chars.append(char)
    return "".join(chars)


def _normalize_option(value: str) -> str:
    """Normalize display labels and legacy snake-case options."""
    return value.replace("_", "").replace(" ", "").lower()

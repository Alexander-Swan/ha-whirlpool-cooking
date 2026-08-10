"""Cooking control helpers for Whirlpool Cooking."""

from __future__ import annotations

from typing import Any

COOK_MODE_OPTIONS = (
    "air_fry",
    "bake",
    "broil",
    "convect_bake",
    "convect_broil",
    "convect_roast",
    "keep_warm",
)


def cook_mode_option(mode: Any) -> str | None:
    """Return a Home Assistant option for a Whirlpool cook mode."""
    name = str(getattr(mode, "name", mode))
    option = _camel_to_snake(name)
    return option if option in COOK_MODE_OPTIONS else None


def cook_mode_from_option(option: str) -> Any:
    """Return a Whirlpool cook mode enum from a Home Assistant option."""
    from whirlpool.oven import CookMode

    normalized = option.replace("_", "")
    for mode in CookMode:
        if mode.name.lower() == normalized:
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


def _camel_to_snake(value: str) -> str:
    """Convert Whirlpool enum names to snake case."""
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)

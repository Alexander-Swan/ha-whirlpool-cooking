"""Oven cavity helpers for Whirlpool Cooking."""

from __future__ import annotations

from typing import Any


def cavity_exists(appliance: Any, cavity: Any) -> bool:
    """Return true when the Whirlpool API reports that an oven cavity exists."""
    from whirlpool.oven import ATTR_POSTFIX_STATUS_STATE, CAVITY_PREFIX_MAP

    if not has_attribute(
        appliance,
        f"{CAVITY_PREFIX_MAP[cavity]}_{ATTR_POSTFIX_STATUS_STATE}",
    ):
        return False

    exists = getattr(appliance, "get_oven_cavity_exists", None)
    if exists is None:
        return False
    return bool(exists(cavity))


def cavity_device_key(appliance: Any, cavity: Any | None) -> str | None:
    """Return a child device key when an appliance has multiple cavities."""
    if cavity is None or len(existing_cavities(appliance)) <= 1:
        return None
    return cavity_name(cavity).lower()


def cavity_device_name(appliance: Any, cavity: Any | None) -> str | None:
    """Return a child device label when an appliance has multiple cavities."""
    if cavity is None or len(existing_cavities(appliance)) <= 1:
        return None
    return cavity_name(cavity)


def default_cavity_device_key(appliance: Any) -> str | None:
    """Return the default child device key for appliance-level oven entities."""
    cavities = existing_cavities(appliance)
    if len(cavities) <= 1:
        return None
    return cavity_name(cavities[0]).lower()


def default_cavity_device_name(appliance: Any) -> str | None:
    """Return the default child device label for appliance-level oven entities."""
    cavities = existing_cavities(appliance)
    if len(cavities) <= 1:
        return None
    return cavity_name(cavities[0])


def existing_cavities(appliance: Any) -> tuple[Any, ...]:
    """Return the existing oven cavities for an appliance."""
    from whirlpool.oven import Cavity

    return tuple(
        cavity
        for cavity in (Cavity.Upper, Cavity.Lower)
        if cavity_exists(appliance, cavity)
    )


def cavity_name(cavity: Any) -> str:
    """Return a display-friendly cavity name."""
    return str(getattr(cavity, "name", cavity)).title()


def has_attribute(appliance: Any, attribute: str) -> bool:
    """Return true if an appliance reports a raw Whirlpool attribute."""
    has_attribute_fn = getattr(appliance, "has_attribute", None)
    if has_attribute_fn is None:
        return False
    return bool(has_attribute_fn(attribute))

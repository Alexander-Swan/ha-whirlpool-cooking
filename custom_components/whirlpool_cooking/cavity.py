"""Oven cavity helpers for Whirlpool Cooking."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

ATTR_POSTFIX_STATUS_STATE = "OpStatusState"
CAVITY_PREFIX_BY_NAME = {
    "Upper": "OvenUpperCavity",
    "Lower": "OvenLowerCavity",
}


def cavity_exists(appliance: Any, cavity: Any) -> bool:
    """Return true when the Whirlpool API reports that an oven cavity exists."""
    if not has_attribute(
        appliance,
        cavity_attribute(cavity, ATTR_POSTFIX_STATUS_STATE),
    ):
        return False

    exists = getattr(appliance, "get_oven_cavity_exists", None)
    if exists is None:
        _LOGGER.warning(
            "Whirlpool appliance does not expose get_oven_cavity_exists; "
            "skipping oven cavity entities",
        )
        return False
    try:
        return bool(exists(cavity))
    except Exception:
        _LOGGER.warning(
            "Unable to read Whirlpool oven cavity availability; skipping cavity",
            exc_info=True,
        )
        return False


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
    try:
        from whirlpool.oven import Cavity
    except ModuleNotFoundError:
        _LOGGER.warning(
            "Whirlpool oven support is unavailable; no oven cavity devices created",
            exc_info=True,
        )
        return ()

    return tuple(
        cavity
        for cavity in (Cavity.Upper, Cavity.Lower)
        if cavity_exists(appliance, cavity)
    )


def cavity_name(cavity: Any) -> str:
    """Return a display-friendly cavity name."""
    return str(getattr(cavity, "name", cavity)).title()


def cavity_prefix(cavity: Any) -> str:
    """Return the raw Whirlpool attribute prefix for a cavity."""
    name = str(getattr(cavity, "name", cavity))
    return CAVITY_PREFIX_BY_NAME.get(name, f"Oven{name.title()}Cavity")


def cavity_attribute(cavity: Any, postfix: str) -> str:
    """Return a raw Whirlpool cavity attribute name."""
    return f"{cavity_prefix(cavity)}_{postfix}"


def has_attribute(appliance: Any, attribute: str) -> bool:
    """Return true if an appliance reports a raw Whirlpool attribute."""
    has_attribute_fn = getattr(appliance, "has_attribute", None)
    if has_attribute_fn is None:
        return False
    try:
        return bool(has_attribute_fn(attribute))
    except Exception:
        _LOGGER.warning(
            "Unable to check Whirlpool attribute %s; treating it as unavailable",
            attribute,
            exc_info=True,
        )
        return False

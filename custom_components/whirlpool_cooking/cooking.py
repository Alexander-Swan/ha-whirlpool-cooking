"""Cooking control helpers for Whirlpool Cooking."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
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

PENDING_COOK_CONTROLS = "_whirlpool_cooking_pending_controls"

_COOK_MODE_KEY_PATTERN = re.compile(
    r"(?:cook[\w\s-]*mode|common[\w\s-]*mode|cycle[\w\s-]*mode|mode(?:id)?)"
    r'["\']?\s*[:=]\s*["\']?(\d+)',
    re.IGNORECASE,
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


def supported_cook_mode_options(appliance: Any, cavity: Any) -> list[str]:
    """Return cook mode options supported by a specific oven cavity."""
    supported_modes = _supported_modes_from_methods(appliance, cavity)
    supported_modes.extend(_supported_modes_from_capabilities(appliance, cavity))

    options: list[str] = []
    for mode in supported_modes:
        option = cook_mode_option(mode)
        if option is not None and option not in options:
            options.append(option)

    options = [option for option in COOK_MODE_OPTIONS if option in options]
    current_option = cook_mode_option(appliance.get_cook_mode(cavity))
    if current_option is not None and current_option not in options:
        options.append(current_option)

    return options or list(COOK_MODE_OPTIONS)


def get_pending_cook_mode_option(appliance: Any, cavity: Any) -> str | None:
    """Return the pending cook mode option for a cavity."""
    value = _pending_controls(appliance).get(_pending_key(cavity, "mode"))
    return str(value) if value is not None else None


def set_pending_cook_mode_option(appliance: Any, cavity: Any, option: str) -> None:
    """Store the pending cook mode option for a cavity."""
    _pending_controls(appliance)[_pending_key(cavity, "mode")] = option


def get_pending_target_temperature(appliance: Any, cavity: Any) -> float | None:
    """Return the pending target temperature in Celsius for a cavity."""
    value = _pending_controls(appliance).get(_pending_key(cavity, "target_temp"))
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def get_pending_cook_time(appliance: Any, cavity: Any) -> int | None:
    """Return the pending cook time in seconds for a cavity."""
    value = _pending_controls(appliance).get(_pending_key(cavity, "cook_time"))
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def set_pending_cook_time(appliance: Any, cavity: Any, seconds: int) -> None:
    """Store the pending cook time in seconds for a cavity."""
    _pending_controls(appliance)[_pending_key(cavity, "cook_time")] = seconds


def set_pending_target_temperature(
    appliance: Any,
    cavity: Any,
    temperature_celsius: float,
) -> None:
    """Store the pending target temperature in Celsius for a cavity."""
    _pending_controls(appliance)[_pending_key(cavity, "target_temp")] = (
        temperature_celsius
    )


def cavity_attribute(cavity: Any, postfix: str) -> str:
    """Return a raw Whirlpool cavity attribute name."""
    from whirlpool.oven import CAVITY_PREFIX_MAP

    return f"{CAVITY_PREFIX_MAP[cavity]}_{postfix}"


def enum_label(value: Any) -> str | None:
    """Return a display label for a Whirlpool enum value."""
    if value is None:
        return None
    return _camel_to_label(str(getattr(value, "name", value)))


def _supported_modes_from_methods(appliance: Any, cavity: Any) -> list[Any]:
    """Read supported cook modes from library methods when available."""
    supported_modes: list[Any] = []
    for name in (
        "get_supported_cook_modes",
        "get_supported_cavity_cook_modes",
        "supported_cook_modes",
    ):
        method = getattr(appliance, name, None)
        if not callable(method):
            continue
        for args in ((cavity,), ()):
            try:
                value = method(*args)
            except TypeError:
                continue
            supported_modes.extend(_flatten(value))
            break
    return supported_modes


def _supported_modes_from_capabilities(appliance: Any, cavity: Any) -> list[Any]:
    """Read supported cook modes from Whirlpool capability attributes."""
    from whirlpool.oven import COOK_MODE_MAP

    raw_modes: set[str] = set()
    cavity_name = str(getattr(cavity, "name", cavity)).lower()
    attributes = getattr(appliance, "_data_dict", {}).get("attributes", {})
    if not isinstance(attributes, dict):
        return []

    for name, details in attributes.items():
        attr_name = str(name)
        if "CapabilityMode" not in attr_name and not attr_name.endswith(
            "__RecipeSetFacadeMode",
        ):
            continue
        raw_value = _attribute_value(details)
        if raw_value is None:
            continue
        if attr_name.endswith("__RecipeSetFacadeMode") and cavity_name not in (
            attr_name.lower()
        ):
            continue
        raw_modes.update(_mode_values_from_payload(raw_value))

    mode_by_value = {str(value): mode for mode, value in COOK_MODE_MAP.items()}
    return [
        mode_by_value[raw_mode]
        for raw_mode in raw_modes
        if raw_mode in mode_by_value
    ]


def _camel_to_label(value: str) -> str:
    """Convert Whirlpool enum names to display labels."""
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            chars.append(" ")
        chars.append(char)
    return "".join(chars)


def _attribute_value(details: Any) -> Any:
    """Return a raw Whirlpool attribute value from an attribute payload."""
    if isinstance(details, dict) and "value" in details:
        return details["value"]
    return details


def _mode_values_from_payload(value: Any) -> set[str]:
    """Extract raw cook mode ids from structured capability payloads."""
    modes: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            key_name = str(key).replace("_", "").replace("-", "").lower()
            if key_name in {
                "mode",
                "modeid",
                "cookmode",
                "cookmodeid",
                "commonmode",
                "cyclemode",
                "cyclesetcommonmode",
            }:
                modes.add(str(item))
                continue
            modes.update(_mode_values_from_payload(item))
        return modes
    if isinstance(value, list | tuple | set):
        for item in value:
            modes.update(_mode_values_from_payload(item))
        return modes

    text = str(value)
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = None
    if parsed is not None and parsed is not value:
        return _mode_values_from_payload(parsed)

    return set(_COOK_MODE_KEY_PATTERN.findall(text))


def _flatten(value: Any) -> Iterable[Any]:
    """Flatten nested containers without splitting strings."""
    if value is None:
        return ()
    if isinstance(value, dict):
        return _flatten(value.values())
    if isinstance(value, str | bytes):
        return (value,)
    if isinstance(value, Iterable):
        flattened: list[Any] = []
        for item in value:
            flattened.extend(_flatten(item))
        return flattened
    return (value,)


def _normalize_option(value: str) -> str:
    """Normalize display labels and legacy snake-case options."""
    return value.replace("_", "").replace(" ", "").lower()


def _pending_controls(appliance: Any) -> dict[str, Any]:
    """Return pending HA-side controls for an appliance."""
    pending = getattr(appliance, PENDING_COOK_CONTROLS, None)
    if not isinstance(pending, dict):
        pending = {}
        setattr(appliance, PENDING_COOK_CONTROLS, pending)
    return pending


def _pending_key(cavity: Any, kind: str) -> str:
    """Return a pending control key."""
    cavity_name = str(getattr(cavity, "name", cavity)).lower()
    return f"{cavity_name}_{kind}"

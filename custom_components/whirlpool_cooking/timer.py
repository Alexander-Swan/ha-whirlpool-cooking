"""Kitchen timer helpers for Whirlpool Cooking."""

from __future__ import annotations

import re
from typing import Any

from .entity import has_callable
from .sensor import _has_attribute, _raw_attribute_value

ATTR_KITCHEN_TIMER_SET_TIME = "KitchenTimer01_SetTimeSet"
ATTR_KITCHEN_TIMER_SET_OPERATIONS = "KitchenTimer01_SetOperations"
ATTR_KITCHEN_TIMER_STATUS = "KitchenTimer01_StatusState"
ATTR_KITCHEN_TIMER_TIME_REMAINING = "KitchenTimer01_StatusTimeRemaining"

_DURATION_TOKEN_RE = re.compile(r"(?P<value>\d+)\s*(?P<unit>[hms])", re.IGNORECASE)


def kitchen_timer_supported(appliance: Any) -> bool:
    """Return true when the appliance exposes a controllable kitchen timer."""
    return (
        _has_attribute(appliance, ATTR_KITCHEN_TIMER_SET_TIME)
        and _has_attribute(appliance, ATTR_KITCHEN_TIMER_SET_OPERATIONS)
        and has_callable(appliance, "get_kitchen_timer")
    )


def kitchen_timer_duration(appliance: Any) -> int | None:
    """Return the configured kitchen timer duration in seconds."""
    timer = _kitchen_timer(appliance)
    if timer is not None and has_callable(timer, "get_total_time"):
        try:
            return _positive_int(timer.get_total_time())
        except Exception:
            return None
    return _positive_int(_raw_attribute_value(appliance, ATTR_KITCHEN_TIMER_SET_TIME))


async def set_kitchen_timer_duration(appliance: Any, seconds: int) -> bool:
    """Set the configured kitchen timer duration without starting it."""
    if not has_callable(appliance, "send_attributes"):
        return False
    return await appliance.send_attributes({ATTR_KITCHEN_TIMER_SET_TIME: str(seconds)})


async def start_kitchen_timer(appliance: Any) -> bool:
    """Start the first Whirlpool kitchen timer."""
    timer = _kitchen_timer(appliance)
    if timer is None:
        return False

    seconds = kitchen_timer_duration(appliance)
    if seconds is None or seconds <= 0:
        return False

    return await timer.set_timer(seconds)


async def cancel_kitchen_timer(appliance: Any) -> bool:
    """Cancel the first Whirlpool kitchen timer."""
    timer = _kitchen_timer(appliance)
    if timer is None:
        return False
    return await timer.cancel_timer()


def parse_duration(value: str) -> int:
    """Parse a duration string into seconds."""
    text = value.strip().lower()
    if not text:
        raise ValueError("Duration is required")

    if ":" in text:
        parts = text.split(":")
        if len(parts) > 3 or not all(part.isdigit() for part in parts):
            raise ValueError(f"Unsupported duration: {value}")
        numbers = [int(part) for part in parts]
        if len(numbers) == 3:
            hours, minutes, seconds = numbers
        elif len(numbers) == 2:
            hours = 0
            minutes, seconds = numbers
        else:
            hours = 0
            minutes = 0
            seconds = numbers[0]
        return _validate_duration(hours, minutes, seconds)

    if text.isdigit():
        return _validate_total_seconds(int(text))

    total = 0
    matched = False
    for match in _DURATION_TOKEN_RE.finditer(text):
        matched = True
        amount = int(match.group("value"))
        unit = match.group("unit").lower()
        if unit == "h":
            total += amount * 3600
        elif unit == "m":
            total += amount * 60
        else:
            total += amount
    if not matched:
        raise ValueError(f"Unsupported duration: {value}")
    return _validate_total_seconds(total)


def format_duration(seconds: int | None) -> str | None:
    """Format seconds as M:SS or H:MM:SS."""
    if seconds is None:
        return None
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _kitchen_timer(appliance: Any) -> Any | None:
    """Return the first kitchen timer object without raising."""
    if not has_callable(appliance, "get_kitchen_timer"):
        return None
    try:
        return appliance.get_kitchen_timer()
    except Exception:
        return None


def _positive_int(value: Any) -> int | None:
    """Return a non-negative integer or None."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _validate_duration(hours: int, minutes: int, seconds: int) -> int:
    """Validate and return a duration in seconds."""
    if minutes >= 60 or seconds >= 60:
        raise ValueError("Minutes and seconds must be less than 60")
    total = hours * 3600 + minutes * 60 + seconds
    return _validate_total_seconds(total)


def _validate_total_seconds(total: int) -> int:
    """Validate and return total seconds."""
    if total <= 0:
        raise ValueError("Duration must be greater than zero")
    return total

"""Diagnostics for Whirlpool Cooking."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

TO_REDACT = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "serial",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "brand": entry.data.get("brand"),
            "region": entry.data.get("region"),
            "username": "***",
        },
        "appliances": [
            _describe_appliance(appliance) for appliance in coordinator.data
        ],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator = entry.runtime_data
    saids = {identifier[1] for identifier in device.identifiers}
    return {
        "appliances": [
            _describe_appliance(appliance)
            for appliance in coordinator.data
            if str(_read(appliance, "said")) in saids
        ],
    }


def _describe_appliance(appliance: Any) -> dict[str, Any]:
    """Return safe appliance diagnostics."""
    return {
        "said": "***",
        "name": _read(appliance, "name", "appliance_name"),
        "model": _read(appliance, "model", "model_number"),
        "data_model": _read(
            appliance,
            "data_model",
            "data_model_key",
            "DATA_MODEL_KEY",
            "appliance_info.data_model",
        ),
        "type": type(appliance).__name__,
        "raw_attribute_keys": _raw_attribute_keys(appliance),
        "available_attributes": sorted(
            name
            for name in dir(appliance)
            if not name.startswith("_") and name.lower() not in TO_REDACT
        ),
    }


def _read(source: Any, *names: str) -> Any:
    """Read the first present attribute."""
    for name in names:
        target = source
        parts = name.split(".")
        missing = False
        for part in parts:
            if isinstance(target, dict) and part in target:
                target = target[part]
                continue
            if not hasattr(target, part):
                missing = True
                break
            target = getattr(target, part)
        if missing:
            continue
        value = target
        if callable(value):
            try:
                return value()
            except TypeError:
                return None
        return value
    return None


def _raw_attribute_keys(appliance: Any) -> list[str]:
    """Return safe raw Whirlpool attribute keys for diagnostics."""
    attributes = getattr(appliance, "_data_dict", {}).get("attributes", {})
    if not isinstance(attributes, dict):
        return []
    return sorted(
        str(name)
        for name in attributes
        if not any(secret in str(name).lower() for secret in TO_REDACT)
    )

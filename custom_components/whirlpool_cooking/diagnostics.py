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
        ),
        "type": type(appliance).__name__,
        "available_attributes": sorted(
            name
            for name in dir(appliance)
            if not name.startswith("_") and name.lower() not in TO_REDACT
        ),
    }


def _read(source: Any, *names: str) -> Any:
    """Read the first present attribute."""
    for name in names:
        if isinstance(source, dict) and name in source:
            return source[name]
        if hasattr(source, name):
            value = getattr(source, name)
            if callable(value):
                try:
                    return value()
                except TypeError:
                    return None
            return value
    return None

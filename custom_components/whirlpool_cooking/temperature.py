"""Temperature helpers for Whirlpool Cooking."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature

from .const import CONF_TEMPERATURE_UNIT, TEMP_UNIT_FAHRENHEIT


def configured_temperature_unit(entry: ConfigEntry) -> str:
    """Return the Home Assistant temperature unit for an integration entry."""
    if entry.options.get(CONF_TEMPERATURE_UNIT) == TEMP_UNIT_FAHRENHEIT:
        return UnitOfTemperature.FAHRENHEIT
    return UnitOfTemperature.CELSIUS


def temperature_from_celsius(entry: ConfigEntry, value: float | None) -> float | None:
    """Convert a Celsius value to the configured display unit."""
    if value is None:
        return None
    if configured_temperature_unit(entry) == UnitOfTemperature.FAHRENHEIT:
        return value * 9 / 5 + 32
    return value


def temperature_to_celsius(entry: ConfigEntry, value: float) -> float:
    """Convert a configured-unit value to Celsius."""
    if configured_temperature_unit(entry) == UnitOfTemperature.FAHRENHEIT:
        return (value - 32) * 5 / 9
    return value

"""Number platform for Whirlpool Cooking."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .cavity import cavity_device_key, cavity_device_name
from .cooking import cavity_attribute, set_pending_target_temperature
from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, appliance_label, has_callable
from .sensor import _cavity_exists, _has_attribute
from .temperature import (
    configured_temperature_unit,
    temperature_from_celsius,
    temperature_to_celsius,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class WhirlpoolNumberDescription(NumberEntityDescription):
    """Describe a Whirlpool number."""

    value_fn: Callable[[Any], float | None]
    set_fn: Callable[[Any, float], Awaitable[bool]]
    cavity: Any | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking numbers."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    entities: list[WhirlpoolCookingNumber] = []
    for appliance in coordinator.data:
        try:
            descriptions = _number_descriptions(appliance)
        except Exception:
            _LOGGER.warning(
                "Unable to build Whirlpool Cooking number entities for %s; "
                "skipping this appliance",
                appliance_label(appliance),
                exc_info=True,
            )
            continue
        entities.extend(
            WhirlpoolCookingNumber(coordinator, appliance, description)
            for description in descriptions
        )
    async_add_entities(entities)


def _number_descriptions(appliance: Any) -> list[WhirlpoolNumberDescription]:
    """Build number descriptions supported by an appliance."""
    return _cavity_number_descriptions(appliance)


def _cavity_number_descriptions(appliance: Any) -> list[WhirlpoolNumberDescription]:
    """Build oven cavity number controls."""
    try:
        from whirlpool.oven import ATTR_POSTFIX_TARGET_TEMP, Cavity
    except ModuleNotFoundError:
        _LOGGER.warning(
            "Whirlpool oven support is unavailable; skipping oven number controls",
            exc_info=True,
        )
        return []

    descriptions: list[WhirlpoolNumberDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        attribute = cavity_attribute(cavity, ATTR_POSTFIX_TARGET_TEMP)
        if not _cavity_exists(appliance, cavity) or not _has_attribute(
            appliance,
            attribute,
        ):
            continue
        if not has_callable(appliance, "get_target_temp") or not has_callable(
            appliance,
            "send_attributes",
        ):
            _LOGGER.debug(
                "Whirlpool appliance %s reports target temperature but lacks "
                "the required target temperature API; skipping %s target "
                "temperature control",
                appliance_label(appliance),
                cavity.name.lower(),
            )
            continue

        cavity_key = cavity.name.lower()
        descriptions.append(
            WhirlpoolNumberDescription(
                key=f"{cavity_key}_target_temperature_control",
                translation_key=f"{cavity_key}_target_temperature_control",
                cavity=cavity,
                native_min_value=40,
                native_max_value=260,
                native_step=1,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                value_fn=lambda item, oven_cavity=cavity: _target_temperature(
                    item,
                    oven_cavity,
                ),
                set_fn=lambda item, value, attr=attribute: _send_temperature(
                    item,
                    attr,
                    value,
                ),
            ),
        )
    return descriptions


def _target_temperature(appliance: Any, cavity: Any) -> float | None:
    """Return the target temperature for a cavity."""
    try:
        value = appliance.get_target_temp(cavity)
    except Exception:
        _LOGGER.warning(
            "Unable to read Whirlpool target temperature for %s; returning no value",
            appliance_label(appliance),
            exc_info=True,
        )
        return None
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _send_temperature(appliance: Any, attribute: str, value: float) -> bool:
    """Send a target temperature attribute."""
    return await appliance.send_attributes({attribute: str(round(value * 10))})


class WhirlpoolCookingNumber(WhirlpoolCookingEntity, NumberEntity):
    """Whirlpool Cooking number."""

    entity_description: WhirlpoolNumberDescription

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        description: WhirlpoolNumberDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(
            coordinator,
            appliance,
            description.key,
            device_key=cavity_device_key(appliance, description.cavity),
            device_name=cavity_device_name(appliance, description.cavity),
        )
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the current number value."""
        value = self.entity_description.value_fn(self.appliance)
        if self._is_temperature:
            return temperature_from_celsius(self.coordinator.config_entry, value)
        return value

    @property
    def native_min_value(self) -> float | None:
        """Return the minimum value."""
        if self._is_temperature:
            return temperature_from_celsius(
                self.coordinator.config_entry,
                self.entity_description.native_min_value,
            )
        return self.entity_description.native_min_value

    @property
    def native_max_value(self) -> float | None:
        """Return the maximum value."""
        if self._is_temperature:
            return temperature_from_celsius(
                self.coordinator.config_entry,
                self.entity_description.native_max_value,
            )
        return self.entity_description.native_max_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit."""
        if self._is_temperature:
            return configured_temperature_unit(self.coordinator.config_entry)
        return self.entity_description.native_unit_of_measurement

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        if self._is_temperature:
            value = temperature_to_celsius(self.coordinator.config_entry, value)
        if not await self.entity_description.set_fn(self.appliance, value):
            raise HomeAssistantError("Whirlpool rejected the number command")
        if self._is_temperature and self.entity_description.cavity is not None:
            set_pending_target_temperature(
                self.appliance,
                self.entity_description.cavity,
                value,
            )
        await self.coordinator.async_request_refresh()

    @property
    def _is_temperature(self) -> bool:
        """Return true for temperature number controls."""
        return (
            self.entity_description.native_unit_of_measurement
            == UnitOfTemperature.CELSIUS
        )

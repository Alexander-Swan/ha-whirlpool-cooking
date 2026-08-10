"""Number platform for Whirlpool Cooking."""

from __future__ import annotations

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
from .cooking import cavity_attribute
from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity
from .sensor import _cavity_exists, _has_attribute


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
    async_add_entities(
        WhirlpoolCookingNumber(coordinator, appliance, description)
        for appliance in coordinator.data
        for description in _number_descriptions(appliance)
    )


def _number_descriptions(appliance: Any) -> list[WhirlpoolNumberDescription]:
    """Build number descriptions supported by an appliance."""
    return _cavity_number_descriptions(appliance)


def _cavity_number_descriptions(appliance: Any) -> list[WhirlpoolNumberDescription]:
    """Build oven cavity number controls."""
    from whirlpool.oven import ATTR_POSTFIX_TARGET_TEMP, Cavity

    descriptions: list[WhirlpoolNumberDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        attribute = cavity_attribute(cavity, ATTR_POSTFIX_TARGET_TEMP)
        if not _cavity_exists(appliance, cavity) or not _has_attribute(
            appliance,
            attribute,
        ):
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
    value = appliance.get_target_temp(cavity)
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
        return self.entity_description.value_fn(self.appliance)

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        if not await self.entity_description.set_fn(self.appliance, value):
            raise HomeAssistantError("Whirlpool rejected the number command")
        await self.coordinator.async_request_refresh()

"""Binary sensor platform for Whirlpool Cooking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, _value


@dataclass(frozen=True, kw_only=True)
class WhirlpoolBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Whirlpool binary sensor."""

    value_fn: Callable[[Any], bool | None]


BINARY_SENSORS: tuple[WhirlpoolBinarySensorDescription, ...] = (
    WhirlpoolBinarySensorDescription(
        key="door",
        translation_key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda appliance: _as_bool(
            _value(appliance, "door_open", "is_door_open"),
        ),
    ),
    WhirlpoolBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda appliance: _as_bool(_value(appliance, "online", "is_online")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking binary sensors."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    async_add_entities(
        WhirlpoolCookingBinarySensor(coordinator, appliance, description)
        for appliance in coordinator.data
        for description in BINARY_SENSORS
    )


class WhirlpoolCookingBinarySensor(WhirlpoolCookingEntity, BinarySensorEntity):
    """Whirlpool Cooking binary sensor."""

    entity_description: WhirlpoolBinarySensorDescription

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        description: WhirlpoolBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, appliance, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.appliance)


def _as_bool(value: Any) -> bool | None:
    """Convert common API values to booleans."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on", "open", "online"}
    return bool(value)

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
    cavity: Any | None = None


BINARY_SENSORS: tuple[WhirlpoolBinarySensorDescription, ...] = (
    WhirlpoolBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda appliance: _as_bool(_value(appliance, "get_online")),
    ),
)


def _cavity_binary_sensor_descriptions(
    appliance: Any,
) -> list[WhirlpoolBinarySensorDescription]:
    """Build binary sensor descriptions for oven cavities that exist."""
    from whirlpool.oven import Cavity

    descriptions: list[WhirlpoolBinarySensorDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        exists = getattr(appliance, "get_oven_cavity_exists", None)
        if exists is None or not exists(cavity):
            continue

        cavity_key = cavity.name.lower()
        descriptions.append(
            WhirlpoolBinarySensorDescription(
                key=f"{cavity_key}_door",
                translation_key=f"{cavity_key}_door",
                cavity=cavity,
                device_class=BinarySensorDeviceClass.DOOR,
                value_fn=lambda item, oven_cavity=cavity: _as_bool(
                    item.get_door_opened(oven_cavity),
                ),
            ),
        )
    return descriptions


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
        for description in (
            *BINARY_SENSORS,
            *_cavity_binary_sensor_descriptions(appliance),
        )
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

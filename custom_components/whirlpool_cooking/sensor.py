"""Sensor platform for Whirlpool Cooking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, _value


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSensorDescription(SensorEntityDescription):
    """Describe a Whirlpool sensor."""

    value_fn: Callable[[Any], Any]


SENSORS: tuple[WhirlpoolSensorDescription, ...] = (
    WhirlpoolSensorDescription(
        key="state",
        translation_key="state",
        value_fn=lambda appliance: _value(appliance, "state", "status"),
    ),
    WhirlpoolSensorDescription(
        key="mode",
        translation_key="mode",
        value_fn=lambda appliance: _value(appliance, "mode", "current_mode"),
    ),
    WhirlpoolSensorDescription(
        key="target_temperature",
        translation_key="target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda appliance: _value(
            appliance,
            "target_temperature",
            "setpoint",
            "temperature",
        ),
    ),
    WhirlpoolSensorDescription(
        key="time_remaining",
        translation_key="time_remaining",
        value_fn=lambda appliance: _value(appliance, "time_remaining", "remaining_time"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking sensors."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    async_add_entities(
        WhirlpoolCookingSensor(coordinator, appliance, description)
        for appliance in coordinator.data
        for description in SENSORS
    )


class WhirlpoolCookingSensor(WhirlpoolCookingEntity, SensorEntity):
    """Whirlpool Cooking sensor."""

    entity_description: WhirlpoolSensorDescription

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        description: WhirlpoolSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, appliance, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the native value."""
        return self.entity_description.value_fn(self.appliance)

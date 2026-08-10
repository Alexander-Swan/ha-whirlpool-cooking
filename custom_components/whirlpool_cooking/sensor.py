"""Sensor platform for Whirlpool Cooking."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSensorDescription(SensorEntityDescription):
    """Describe a Whirlpool sensor."""

    value_fn: Callable[[Any], Any]
    cavity: Any | None = None


SENSORS: tuple[WhirlpoolSensorDescription, ...] = ()

RAW_ATTRIBUTE_KEYWORDS = (
    "alert",
    "cook",
    "cycle",
    "door",
    "error",
    "light",
    "mode",
    "online",
    "operation",
    "remote",
    "set",
    "state",
    "status",
    "temp",
    "time",
)


def _enum_name(value: Any) -> str | None:
    """Return a stable state string for Whirlpool enum values."""
    if value is None:
        return None
    return str(getattr(value, "name", value)).lower()


def _cavity_sensor_descriptions(appliance: Any) -> list[WhirlpoolSensorDescription]:
    """Build descriptions for oven cavities that exist on the appliance."""
    from whirlpool.oven import Cavity

    descriptions: list[WhirlpoolSensorDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        if not _cavity_exists(appliance, cavity):
            continue

        cavity_key = cavity.name.lower()
        descriptions.extend(
            (
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_state",
                    translation_key=f"{cavity_key}_state",
                    cavity=cavity,
                    value_fn=lambda item, oven_cavity=cavity: _enum_name(
                        item.get_cavity_state(oven_cavity),
                    ),
                ),
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_mode",
                    translation_key=f"{cavity_key}_mode",
                    cavity=cavity,
                    value_fn=lambda item, oven_cavity=cavity: _enum_name(
                        item.get_cook_mode(oven_cavity),
                    ),
                ),
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_temperature",
                    translation_key=f"{cavity_key}_temperature",
                    cavity=cavity,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    value_fn=lambda item, oven_cavity=cavity: item.get_temp(
                        oven_cavity,
                    ),
                ),
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_target_temperature",
                    translation_key=f"{cavity_key}_target_temperature",
                    cavity=cavity,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    value_fn=lambda item, oven_cavity=cavity: item.get_target_temp(
                        oven_cavity,
                    ),
                ),
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_cook_time",
                    translation_key=f"{cavity_key}_cook_time",
                    cavity=cavity,
                    value_fn=lambda item, oven_cavity=cavity: item.get_cook_time(
                        oven_cavity,
                    ),
                ),
            ),
        )
    return descriptions


def _cavity_exists(appliance: Any, cavity: Any) -> bool:
    """Return true when the Whirlpool API reports that an oven cavity exists."""
    from whirlpool.oven import ATTR_POSTFIX_STATUS_STATE, CAVITY_PREFIX_MAP

    if not _has_attribute(
        appliance,
        f"{CAVITY_PREFIX_MAP[cavity]}_{ATTR_POSTFIX_STATUS_STATE}",
    ):
        return False

    exists = getattr(appliance, "get_oven_cavity_exists", None)
    if exists is None:
        return False
    return bool(exists(cavity))


def _sensor_descriptions(appliance: Any) -> list[WhirlpoolSensorDescription]:
    """Build all sensor descriptions for an appliance."""
    descriptions = [*SENSORS, *_cavity_sensor_descriptions(appliance)]
    if len(descriptions) > len(SENSORS):
        return descriptions
    return [*descriptions, *_raw_attribute_sensor_descriptions(appliance)]


def _raw_attribute_sensor_descriptions(
    appliance: Any,
) -> list[WhirlpoolSensorDescription]:
    """Expose useful raw API attributes when no typed cooking API matches."""
    return [
        WhirlpoolSensorDescription(
            key=f"raw_{_slugify_attribute_key(attribute)}",
            name=_humanize_attribute_key(attribute),
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda item, attr=attribute: _raw_attribute_value(item, attr),
        )
        for attribute in _raw_attribute_keys(appliance)
        if _should_expose_raw_attribute(attribute)
    ]


def _raw_attribute_keys(appliance: Any) -> list[str]:
    """Return raw Whirlpool attribute keys from the fetched data payload."""
    attributes = getattr(appliance, "_data_dict", {}).get("attributes", {})
    if not isinstance(attributes, dict):
        return []
    return sorted(str(attribute) for attribute in attributes)


def _raw_attribute_value(appliance: Any, attribute: str) -> Any:
    """Return a raw Whirlpool attribute value."""
    value = getattr(appliance, "_get_attribute", lambda _: None)(attribute)
    if value == "":
        return None
    return value


def _should_expose_raw_attribute(attribute: str) -> bool:
    """Return true for raw attributes that are useful as HA entities."""
    normalized = attribute.lower()
    return any(keyword in normalized for keyword in RAW_ATTRIBUTE_KEYWORDS)


def _has_attribute(appliance: Any, attribute: str) -> bool:
    """Return true if an appliance reports a raw Whirlpool attribute."""
    has_attribute = getattr(appliance, "has_attribute", None)
    if has_attribute is None:
        return False
    return bool(has_attribute(attribute))


def _slugify_attribute_key(attribute: str) -> str:
    """Return a Home Assistant-safe key for a raw Whirlpool attribute."""
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", attribute.lower())).strip("_")


def _humanize_attribute_key(attribute: str) -> str:
    """Return a readable name for a raw Whirlpool attribute."""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", attribute.replace("_", " "))
    return " ".join(spaced.split())


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
        for description in _sensor_descriptions(appliance)
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

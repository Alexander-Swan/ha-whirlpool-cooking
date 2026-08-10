"""Binary sensor platform for Whirlpool Cooking."""

from __future__ import annotations

import logging
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

from .cavity import cavity_device_key, cavity_device_name
from .cooking import cavity_attribute
from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, _value, appliance_label, has_callable
from .sensor import _cavity_exists, _has_attribute, _raw_attribute_value

_LOGGER = logging.getLogger(__name__)


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
    try:
        from whirlpool.oven import Cavity
    except ModuleNotFoundError:
        _LOGGER.warning(
            "Whirlpool oven support is unavailable; skipping oven binary sensors",
            exc_info=True,
        )
        return []

    descriptions: list[WhirlpoolBinarySensorDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        if not _cavity_exists(appliance, cavity):
            continue

        cavity_key = cavity.name.lower()
        if has_callable(appliance, "get_door_opened"):
            descriptions.append(
                WhirlpoolBinarySensorDescription(
                    key=f"{cavity_key}_door",
                    translation_key=f"{cavity_key}_door",
                    cavity=cavity,
                    device_class=BinarySensorDeviceClass.DOOR,
                    value_fn=lambda item, oven_cavity=cavity: _as_bool_cavity_method(
                        item,
                        "get_door_opened",
                        oven_cavity,
                    ),
                ),
            )
        else:
            _LOGGER.debug(
                "Whirlpool appliance %s does not expose get_door_opened; "
                "skipping %s_door",
                appliance_label(appliance),
                cavity_key,
            )

        if _has_attribute(
            appliance,
            cavity_attribute(cavity, "OpStatusDoorLocked"),
        ):
            descriptions.append(
                WhirlpoolBinarySensorDescription(
                    key=f"{cavity_key}_door_locked",
                    translation_key=f"{cavity_key}_door_locked",
                    cavity=cavity,
                    device_class=BinarySensorDeviceClass.LOCK,
                    value_fn=lambda item, oven_cavity=cavity: _as_bool(
                        _raw_attribute_value(
                            item,
                            cavity_attribute(oven_cavity, "OpStatusDoorLocked"),
                        ),
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
    entities: list[WhirlpoolCookingBinarySensor] = []
    for appliance in coordinator.data:
        try:
            descriptions = (
                *BINARY_SENSORS,
                *_cavity_binary_sensor_descriptions(appliance),
            )
        except Exception:
            _LOGGER.warning(
                "Unable to build Whirlpool Cooking binary sensor entities for %s; "
                "skipping this appliance",
                appliance_label(appliance),
                exc_info=True,
            )
            continue
        entities.extend(
            WhirlpoolCookingBinarySensor(coordinator, appliance, description)
            for description in descriptions
        )
    async_add_entities(entities)


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
        super().__init__(
            coordinator,
            appliance,
            description.key,
            device_key=cavity_device_key(appliance, description.cavity),
            device_name=cavity_device_name(appliance, description.cavity),
        )
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


def _as_bool_cavity_method(
    appliance: Any,
    method_name: str,
    cavity: Any,
) -> bool | None:
    """Read a Whirlpool boolean cavity method without raising into Home Assistant."""
    method = getattr(appliance, method_name, None)
    if not callable(method):
        return None
    try:
        return _as_bool(method(cavity))
    except Exception:
        _LOGGER.warning(
            "Unable to read Whirlpool %s for %s; returning no value",
            method_name,
            appliance_label(appliance),
            exc_info=True,
        )
        return None

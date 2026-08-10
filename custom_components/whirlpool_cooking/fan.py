"""Fan platform for Whirlpool Cooking."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, appliance_label, has_callable
from .sensor import _has_attribute, _raw_attribute_value

_LOGGER = logging.getLogger(__name__)

ATTR_HOOD_FAN_SPEED = "Hood_OperationSetExhaustFanSpeed"
HOOD_FAN_MAX_SPEED = 6

PERCENTAGE_TO_SPEED = tuple(
    (round(speed * 100 / HOOD_FAN_MAX_SPEED), str(speed))
    for speed in range(HOOD_FAN_MAX_SPEED + 1)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking fans."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    entities: list[WhirlpoolCookingHoodFan] = []
    for appliance in coordinator.data:
        try:
            if not _hood_fan_supported(appliance):
                continue
            entities.append(WhirlpoolCookingHoodFan(coordinator, appliance))
        except Exception:
            _LOGGER.warning(
                "Unable to build Whirlpool Cooking fan entities for %s; "
                "skipping this appliance",
                appliance_label(appliance),
                exc_info=True,
            )
    async_add_entities(entities)


def _hood_fan_supported(appliance: Any) -> bool:
    """Return true when a hood fan entity can be read and controlled."""
    if not _has_attribute(appliance, ATTR_HOOD_FAN_SPEED):
        return False
    if not has_callable(appliance, "send_attributes"):
        _LOGGER.debug(
            "Whirlpool appliance %s reports hood fan speed but does not "
            "expose send_attributes; skipping hood fan",
            appliance_label(appliance),
        )
        return False
    return True


class WhirlpoolCookingHoodFan(WhirlpoolCookingEntity, FanEntity):
    """Whirlpool Cooking hood fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_speed_count = HOOD_FAN_MAX_SPEED
    _attr_translation_key = "hood_fan"

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, appliance, "hood_fan")

    @property
    def is_on(self) -> bool | None:
        """Return true if the fan is on."""
        speed = _speed_value(self.appliance)
        return None if speed is None else speed > 0

    @property
    def percentage(self) -> int | None:
        """Return current fan percentage."""
        speed = _speed_value(self.appliance)
        if speed is None:
            return None
        if speed <= 0:
            return 0
        return round(min(speed, HOOD_FAN_MAX_SPEED) * 100 / HOOD_FAN_MAX_SPEED)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        await self.async_set_percentage(percentage or 100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.async_set_percentage(0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by percentage."""
        if not await self.appliance.send_attributes(
            {ATTR_HOOD_FAN_SPEED: _speed_for_percentage(percentage)},
        ):
            raise HomeAssistantError("Whirlpool rejected the fan command")
        await self.coordinator.async_request_refresh()


def _speed_value(appliance: Any) -> int | None:
    """Return raw hood fan speed as an integer."""
    value = _raw_attribute_value(appliance, ATTR_HOOD_FAN_SPEED)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _speed_for_percentage(percentage: int) -> str:
    """Return the nearest Whirlpool hood fan speed for a percentage."""
    return min(
        PERCENTAGE_TO_SPEED,
        key=lambda item: abs(item[0] - percentage),
    )[1]

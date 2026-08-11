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
HOOD_FAN_MAX_SPEED = 4

SPEED_TO_PRESET_MODE = {
    2: "Low",
    4: "Medium",
    5: "Medium-high",
    6: "High",
}
PRESET_MODE_TO_SPEED = {
    preset_mode: str(speed)
    for speed, preset_mode in SPEED_TO_PRESET_MODE.items()
}
PRESET_MODES = ("Low", "Medium", "Medium-high", "High")
PERCENTAGE_TO_SPEED = (
    (0, "0"),
    (25, PRESET_MODE_TO_SPEED["Low"]),
    (50, PRESET_MODE_TO_SPEED["Medium"]),
    (75, PRESET_MODE_TO_SPEED["Medium-high"]),
    (100, PRESET_MODE_TO_SPEED["High"]),
)
SPEED_TO_PERCENTAGE = {
    0: 0,
    **{
        int(speed): percentage
        for percentage, speed in PERCENTAGE_TO_SPEED
        if int(speed) > 0
    },
}


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
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = list(PRESET_MODES)
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
        return SPEED_TO_PERCENTAGE.get(speed, 0 if speed <= 0 else None)

    @property
    def preset_mode(self) -> str | None:
        """Return current fan preset mode."""
        speed = _speed_value(self.appliance)
        if speed is None or speed <= 0:
            return None
        return SPEED_TO_PRESET_MODE.get(speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
        await self.async_set_percentage(percentage or 100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.async_set_percentage(0)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set fan speed by Whirlpool preset mode."""
        speed = PRESET_MODE_TO_SPEED.get(preset_mode)
        if speed is None:
            raise HomeAssistantError(f"Unsupported Whirlpool fan mode: {preset_mode}")
        await self._async_set_speed(speed)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by percentage."""
        await self._async_set_speed(_speed_for_percentage(percentage))

    async def _async_set_speed(self, speed: str) -> None:
        """Set raw Whirlpool fan speed and refresh appliance data."""
        if not await self.appliance.send_attributes(
            {ATTR_HOOD_FAN_SPEED: speed},
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

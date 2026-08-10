"""Light platform for Whirlpool Cooking."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .cavity import cavity_device_key, cavity_device_name
from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, appliance_label, has_callable
from .sensor import _cavity_exists, _has_attribute, _raw_attribute_value

_LOGGER = logging.getLogger(__name__)

ATTR_HOOD_SURFACE_LIGHT = "Hood_OperationSetSurfaceLight"
ATTR_MICROWAVE_LIGHT = "Mwo_DisplaySetLightOn"
HOOD_LIGHT_MAX_LEVEL = 2
HOOD_LIGHT_LOW_LEVEL = 2
HOOD_LIGHT_HIGH_LEVEL = 4


@dataclass(frozen=True, kw_only=True)
class WhirlpoolLightDescription(LightEntityDescription):
    """Describe a Whirlpool light."""

    value_fn: Callable[[Any], bool | None]
    set_fn: Callable[[Any, bool], Awaitable[bool]]
    brightness_fn: Callable[[Any], int | None] | None = None
    set_brightness_fn: Callable[[Any, int], Awaitable[bool]] | None = None
    max_level: int | None = None
    cavity: Any | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking lights."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    entities: list[WhirlpoolCookingLight] = []
    for appliance in coordinator.data:
        try:
            descriptions = _light_descriptions(appliance)
        except Exception:
            _LOGGER.warning(
                "Unable to build Whirlpool Cooking light entities for %s; "
                "skipping this appliance",
                appliance_label(appliance),
                exc_info=True,
            )
            continue
        entities.extend(
            WhirlpoolCookingLight(coordinator, appliance, description)
            for description in descriptions
        )
    async_add_entities(entities)


def _light_descriptions(appliance: Any) -> list[WhirlpoolLightDescription]:
    """Build light descriptions supported by an appliance."""
    return [
        *_cavity_light_descriptions(appliance),
        *_microwave_light_descriptions(appliance),
    ]


def _cavity_light_descriptions(appliance: Any) -> list[WhirlpoolLightDescription]:
    """Build oven cavity light descriptions."""
    try:
        from whirlpool.oven import ATTR_POSTFIX_LIGHT_STATUS, CAVITY_PREFIX_MAP, Cavity
    except ModuleNotFoundError:
        return []

    descriptions: list[WhirlpoolLightDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        attribute = f"{CAVITY_PREFIX_MAP[cavity]}_{ATTR_POSTFIX_LIGHT_STATUS}"
        if not _cavity_exists(appliance, cavity) or not _has_attribute(
            appliance,
            attribute,
        ):
            continue
        if not has_callable(appliance, "set_light"):
            _LOGGER.debug(
                "Whirlpool appliance %s does not expose set_light; skipping %s light",
                appliance_label(appliance),
                cavity.name.lower(),
            )
            continue

        cavity_key = cavity.name.lower()
        descriptions.append(
            WhirlpoolLightDescription(
                key=f"{cavity_key}_light",
                translation_key=f"{cavity_key}_light",
                cavity=cavity,
                value_fn=lambda item, attr=attribute: _raw_bool(item, attr),
                set_fn=lambda item, on, oven_cavity=cavity: item.set_light(
                    on,
                    oven_cavity,
                ),
            ),
        )
    return descriptions


def _microwave_light_descriptions(
    appliance: Any,
) -> list[WhirlpoolLightDescription]:
    """Build microwave and hood light descriptions."""
    descriptions: list[WhirlpoolLightDescription] = []
    if not has_callable(appliance, "send_attributes"):
        if _has_attribute(appliance, ATTR_MICROWAVE_LIGHT) or _has_attribute(
            appliance,
            ATTR_HOOD_SURFACE_LIGHT,
        ):
            _LOGGER.debug(
                "Whirlpool appliance %s reports microwave or hood light "
                "attributes but does not expose send_attributes; skipping lights",
                appliance_label(appliance),
            )
        return descriptions

    if _has_attribute(appliance, ATTR_MICROWAVE_LIGHT):
        descriptions.append(
            WhirlpoolLightDescription(
                key="microwave_light",
                translation_key="microwave_light",
                value_fn=lambda item: _raw_bool(item, ATTR_MICROWAVE_LIGHT),
                set_fn=lambda item, on: _send_bool(item, ATTR_MICROWAVE_LIGHT, on),
            ),
        )

    if _has_attribute(appliance, ATTR_HOOD_SURFACE_LIGHT):
        descriptions.append(
            WhirlpoolLightDescription(
                key="hood_light",
                translation_key="hood_light",
                value_fn=lambda item: _raw_level(item, ATTR_HOOD_SURFACE_LIGHT) > 0,
                set_fn=lambda item, on: _send_level(
                    item,
                    ATTR_HOOD_SURFACE_LIGHT,
                    HOOD_LIGHT_HIGH_LEVEL if on else 0,
                ),
                brightness_fn=lambda item: _brightness_for_level(
                    _raw_level(item, ATTR_HOOD_SURFACE_LIGHT),
                    HOOD_LIGHT_LOW_LEVEL,
                    high_level=HOOD_LIGHT_HIGH_LEVEL,
                ),
                set_brightness_fn=lambda item, brightness: _send_level(
                    item,
                    ATTR_HOOD_SURFACE_LIGHT,
                    _level_for_brightness(
                        brightness,
                        HOOD_LIGHT_LOW_LEVEL,
                        high_level=HOOD_LIGHT_HIGH_LEVEL,
                    ),
                ),
                max_level=HOOD_LIGHT_MAX_LEVEL,
            ),
        )
    return descriptions


def _raw_bool(appliance: Any, attribute: str) -> bool | None:
    """Return a raw Whirlpool boolean attribute."""
    value = _raw_attribute_value(appliance, attribute)
    if value is None:
        return None
    return str(value) == "1"


def _raw_level(appliance: Any, attribute: str) -> int:
    """Return a raw Whirlpool level attribute."""
    value = _raw_attribute_value(appliance, attribute)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _brightness_for_level(
    level: int,
    max_level: int,
    *,
    high_level: int | None = None,
) -> int | None:
    """Return Home Assistant brightness for a raw Whirlpool level."""
    if level <= 0:
        return None
    if high_level is not None:
        return 255 if level == high_level else 128
    return round(min(level, max_level) * 255 / max_level)


def _level_for_brightness(
    brightness: int,
    max_level: int,
    *,
    high_level: int | None = None,
) -> int:
    """Return a raw Whirlpool level for Home Assistant brightness."""
    if high_level is not None:
        return high_level if brightness > 128 else max_level
    return min(max(round(brightness * max_level / 255), 1), max_level)


async def _send_bool(appliance: Any, attribute: str, on: bool) -> bool:
    """Send a raw Whirlpool boolean attribute."""
    return await appliance.send_attributes({attribute: "1" if on else "0"})


async def _send_level(appliance: Any, attribute: str, level: int) -> bool:
    """Send a raw Whirlpool level attribute."""
    return await appliance.send_attributes({attribute: str(level)})


class WhirlpoolCookingLight(WhirlpoolCookingEntity, LightEntity):
    """Whirlpool Cooking light."""

    entity_description: WhirlpoolLightDescription

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        description: WhirlpoolLightDescription,
    ) -> None:
        """Initialize the light."""
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
        """Return true if the light is on."""
        return self.entity_description.value_fn(self.appliance)

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the current color mode."""
        if not self.is_on:
            return None
        if self.entity_description.max_level is not None:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return supported color modes."""
        if self.entity_description.max_level is not None:
            return {ColorMode.BRIGHTNESS}
        return {ColorMode.ONOFF}

    @property
    def brightness(self) -> int | None:
        """Return current brightness for level-capable lights."""
        if self.entity_description.brightness_fn is None:
            return None
        return self.entity_description.brightness_fn(self.appliance)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if (
            brightness is not None
            and self.entity_description.set_brightness_fn is not None
        ):
            if not await self.entity_description.set_brightness_fn(
                self.appliance,
                int(brightness),
            ):
                raise HomeAssistantError("Whirlpool rejected the light command")
            await self.coordinator.async_request_refresh()
            return
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_set(False)

    async def _async_set(self, on: bool) -> None:
        """Set the light and refresh appliance data."""
        if not await self.entity_description.set_fn(self.appliance, on):
            raise HomeAssistantError("Whirlpool rejected the light command")
        await self.coordinator.async_request_refresh()

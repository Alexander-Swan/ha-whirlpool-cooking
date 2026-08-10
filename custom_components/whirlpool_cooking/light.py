"""Light platform for Whirlpool Cooking."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.light import (
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
from .entity import WhirlpoolCookingEntity
from .sensor import _cavity_exists, _has_attribute, _raw_attribute_value

ATTR_HOOD_SURFACE_LIGHT = "Hood_OperationSetSurfaceLight"
ATTR_MICROWAVE_LIGHT = "Mwo_DisplaySetLightOn"


@dataclass(frozen=True, kw_only=True)
class WhirlpoolLightDescription(LightEntityDescription):
    """Describe a Whirlpool light."""

    value_fn: Callable[[Any], bool | None]
    set_fn: Callable[[Any, bool], Awaitable[bool]]
    cavity: Any | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking lights."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    async_add_entities(
        WhirlpoolCookingLight(coordinator, appliance, description)
        for appliance in coordinator.data
        for description in _light_descriptions(appliance)
    )


def _light_descriptions(appliance: Any) -> list[WhirlpoolLightDescription]:
    """Build light descriptions supported by an appliance."""
    return [
        *_cavity_light_descriptions(appliance),
        *_microwave_light_descriptions(appliance),
    ]


def _cavity_light_descriptions(appliance: Any) -> list[WhirlpoolLightDescription]:
    """Build oven cavity light descriptions."""
    from whirlpool.oven import ATTR_POSTFIX_LIGHT_STATUS, CAVITY_PREFIX_MAP, Cavity

    descriptions: list[WhirlpoolLightDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        attribute = f"{CAVITY_PREFIX_MAP[cavity]}_{ATTR_POSTFIX_LIGHT_STATUS}"
        if not _cavity_exists(appliance, cavity) or not _has_attribute(
            appliance,
            attribute,
        ):
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
    for key, translation_key, attribute in (
        ("microwave_light", "microwave_light", ATTR_MICROWAVE_LIGHT),
        ("hood_light", "hood_light", ATTR_HOOD_SURFACE_LIGHT),
    ):
        if not _has_attribute(appliance, attribute):
            continue
        descriptions.append(
            WhirlpoolLightDescription(
                key=key,
                translation_key=translation_key,
                value_fn=lambda item, attr=attribute: _raw_bool(item, attr),
                set_fn=lambda item, on, attr=attribute: _send_bool(item, attr, on),
            ),
        )
    return descriptions


def _raw_bool(appliance: Any, attribute: str) -> bool | None:
    """Return a raw Whirlpool boolean attribute."""
    value = _raw_attribute_value(appliance, attribute)
    if value is None:
        return None
    return str(value) == "1"


async def _send_bool(appliance: Any, attribute: str, on: bool) -> bool:
    """Send a raw Whirlpool boolean attribute."""
    return await appliance.send_attributes({attribute: "1" if on else "0"})


class WhirlpoolCookingLight(WhirlpoolCookingEntity, LightEntity):
    """Whirlpool Cooking light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_set(False)

    async def _async_set(self, on: bool) -> None:
        """Set the light and refresh appliance data."""
        if not await self.entity_description.set_fn(self.appliance, on):
            raise HomeAssistantError("Whirlpool rejected the light command")
        await self.coordinator.async_request_refresh()

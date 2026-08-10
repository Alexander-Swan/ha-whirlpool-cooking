"""Switch platform for Whirlpool Cooking."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity
from .sensor import _has_attribute


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSwitchDescription(SwitchEntityDescription):
    """Describe a Whirlpool switch."""

    value_fn: Callable[[Any], bool | None]
    set_fn: Callable[[Any, bool], Awaitable[bool]]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking switches."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    async_add_entities(
        WhirlpoolCookingSwitch(coordinator, appliance, description)
        for appliance in coordinator.data
        for description in _switch_descriptions(appliance)
    )


def _switch_descriptions(appliance: Any) -> list[WhirlpoolSwitchDescription]:
    """Build switch descriptions supported by an appliance."""
    return _global_switch_descriptions(appliance)


def _global_switch_descriptions(appliance: Any) -> list[WhirlpoolSwitchDescription]:
    """Build appliance-level switches."""
    descriptions: list[WhirlpoolSwitchDescription] = []
    if _has_attribute(appliance, "Sys_OperationSetControlLock"):
        descriptions.append(
            WhirlpoolSwitchDescription(
                key="control_lock",
                translation_key="control_lock",
                value_fn=lambda item: item.get_control_locked(),
                set_fn=lambda item, on: item.set_control_locked(on),
            ),
        )
    if _has_attribute(appliance, "Sys_OperationSetSabbathModeEnabled"):
        descriptions.append(
            WhirlpoolSwitchDescription(
                key="sabbath_mode",
                translation_key="sabbath_mode",
                value_fn=lambda item: item.get_sabbath_mode(),
                set_fn=lambda item, on: item.set_sabbath_mode(on),
            ),
        )
    return descriptions


class WhirlpoolCookingSwitch(WhirlpoolCookingEntity, SwitchEntity):
    """Whirlpool Cooking switch."""

    entity_description: WhirlpoolSwitchDescription

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        description: WhirlpoolSwitchDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, appliance, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self.entity_description.value_fn(self.appliance)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set(False)

    async def _async_set(self, on: bool) -> None:
        """Set the switch and refresh appliance data."""
        if not await self.entity_description.set_fn(self.appliance, on):
            raise HomeAssistantError("Whirlpool rejected the switch command")
        await self.coordinator.async_request_refresh()

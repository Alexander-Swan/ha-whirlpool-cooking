"""Select platform for Whirlpool Cooking."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .cavity import cavity_device_key, cavity_device_name
from .cooking import COOK_MODE_OPTIONS, cavity_attribute, cook_mode_attribute_value
from .cooking import cook_mode_option as _cook_mode_option
from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity
from .sensor import _cavity_exists, _has_attribute


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSelectDescription(SelectEntityDescription):
    """Describe a Whirlpool select."""

    current_fn: Callable[[Any], str | None]
    select_fn: Callable[[Any, str], Awaitable[bool]]
    cavity: Any | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking selects."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    async_add_entities(
        WhirlpoolCookingSelect(coordinator, appliance, description)
        for appliance in coordinator.data
        for description in _select_descriptions(appliance)
    )


def _select_descriptions(appliance: Any) -> list[WhirlpoolSelectDescription]:
    """Build select descriptions supported by an appliance."""
    return _cavity_select_descriptions(appliance)


def _cavity_select_descriptions(appliance: Any) -> list[WhirlpoolSelectDescription]:
    """Build oven cavity select controls."""
    from whirlpool.oven import ATTR_POSTFIX_COOK_MODE, Cavity

    descriptions: list[WhirlpoolSelectDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        attribute = cavity_attribute(cavity, ATTR_POSTFIX_COOK_MODE)
        if not _cavity_exists(appliance, cavity) or not _has_attribute(
            appliance,
            attribute,
        ):
            continue

        cavity_key = cavity.name.lower()
        descriptions.append(
            WhirlpoolSelectDescription(
                key=f"{cavity_key}_cook_mode_control",
                translation_key=f"{cavity_key}_cook_mode_control",
                cavity=cavity,
                options=list(COOK_MODE_OPTIONS),
                current_fn=lambda item, oven_cavity=cavity: _cook_mode_option(
                    item.get_cook_mode(oven_cavity),
                ),
                select_fn=lambda item, option, attr=attribute: _send_cook_mode(
                    item,
                    attr,
                    option,
                ),
            ),
        )
    return descriptions


async def _send_cook_mode(appliance: Any, attribute: str, option: str) -> bool:
    """Send a raw Whirlpool cook mode attribute."""
    return await appliance.send_attributes(
        {attribute: cook_mode_attribute_value(option)},
    )


class WhirlpoolCookingSelect(WhirlpoolCookingEntity, SelectEntity):
    """Whirlpool Cooking select."""

    entity_description: WhirlpoolSelectDescription

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        description: WhirlpoolSelectDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(
            coordinator,
            appliance,
            description.key,
            device_key=cavity_device_key(appliance, description.cavity),
            device_name=cavity_device_name(appliance, description.cavity),
        )
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.entity_description.current_fn(self.appliance)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option not in self.entity_description.options:
            raise HomeAssistantError(f"Unsupported Whirlpool option: {option}")
        if not await self.entity_description.select_fn(self.appliance, option):
            raise HomeAssistantError("Whirlpool rejected the select command")
        await self.coordinator.async_request_refresh()

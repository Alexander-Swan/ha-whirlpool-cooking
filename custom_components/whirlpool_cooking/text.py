"""Text platform for Whirlpool Cooking."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, appliance_label
from .timer import (
    format_duration,
    kitchen_timer_duration,
    kitchen_timer_supported,
    parse_duration,
    set_kitchen_timer_duration,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class WhirlpoolTextDescription(TextEntityDescription):
    """Describe a Whirlpool text entity."""

    value_fn: Callable[[Any], str | None]
    set_fn: Callable[[Any, str], Awaitable[bool]]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking text entities."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    entities: list[WhirlpoolCookingText] = []
    for appliance in coordinator.data:
        try:
            descriptions = _text_descriptions(appliance)
        except Exception:
            _LOGGER.warning(
                "Unable to build Whirlpool Cooking text entities for %s; "
                "skipping this appliance",
                appliance_label(appliance),
                exc_info=True,
            )
            continue
        entities.extend(
            WhirlpoolCookingText(coordinator, appliance, description)
            for description in descriptions
        )
    async_add_entities(entities)


def _text_descriptions(appliance: Any) -> list[WhirlpoolTextDescription]:
    """Build text descriptions supported by an appliance."""
    if not kitchen_timer_supported(appliance):
        return []
    return [
        WhirlpoolTextDescription(
            key="kitchen_timer_duration",
            translation_key="kitchen_timer_duration",
            value_fn=lambda item: format_duration(kitchen_timer_duration(item)),
            set_fn=_set_kitchen_timer_duration,
        ),
    ]


async def _set_kitchen_timer_duration(appliance: Any, value: str) -> bool:
    """Set the kitchen timer duration from a user-entered duration string."""
    try:
        seconds = parse_duration(value)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err
    return await set_kitchen_timer_duration(appliance, seconds)


class WhirlpoolCookingText(WhirlpoolCookingEntity, TextEntity):
    """Whirlpool Cooking text entity."""

    entity_description: WhirlpoolTextDescription

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        description: WhirlpoolTextDescription,
    ) -> None:
        """Initialize the text entity."""
        super().__init__(coordinator, appliance, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | None:
        """Return the current text value."""
        return self.entity_description.value_fn(self.appliance)

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        if not await self.entity_description.set_fn(self.appliance, value):
            raise HomeAssistantError("Whirlpool rejected the text command")
        await self.coordinator.async_request_refresh()

"""Button platform for Whirlpool Cooking."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity
from .sensor import _cavity_exists


@dataclass(frozen=True, kw_only=True)
class WhirlpoolButtonDescription(ButtonEntityDescription):
    """Describe a Whirlpool button."""

    press_fn: Callable[[Any, WhirlpoolCookingCoordinator], Awaitable[bool | None]]


BUTTONS: tuple[WhirlpoolButtonDescription, ...] = (
    WhirlpoolButtonDescription(
        key="refresh",
        translation_key="refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda appliance, coordinator: _async_refresh(coordinator),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking buttons."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    async_add_entities(
        WhirlpoolCookingButton(coordinator, appliance, description)
        for appliance in coordinator.data
        for description in _button_descriptions(appliance)
    )


def _button_descriptions(appliance: Any) -> list[WhirlpoolButtonDescription]:
    """Build button descriptions supported by an appliance."""
    return [*BUTTONS, *_cavity_button_descriptions(appliance)]


def _cavity_button_descriptions(appliance: Any) -> list[WhirlpoolButtonDescription]:
    """Build oven cavity command buttons."""
    from whirlpool.oven import Cavity

    descriptions: list[WhirlpoolButtonDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        if not _cavity_exists(appliance, cavity):
            continue

        cavity_key = cavity.name.lower()
        descriptions.append(
            WhirlpoolButtonDescription(
                key=f"{cavity_key}_stop_cook",
                translation_key=f"{cavity_key}_stop_cook",
                press_fn=lambda item, coordinator, oven_cavity=cavity: _async_stop_cook(
                    item,
                    coordinator,
                    oven_cavity,
                ),
            ),
        )
    return descriptions


async def _async_refresh(coordinator: WhirlpoolCookingCoordinator) -> None:
    """Refresh coordinator data."""
    await coordinator.async_request_refresh()


async def _async_stop_cook(
    appliance: Any,
    coordinator: WhirlpoolCookingCoordinator,
    cavity: Any,
) -> bool:
    """Stop cooking on an oven cavity."""
    result = await appliance.stop_cook(cavity)
    if result:
        await coordinator.async_request_refresh()
    return result


class WhirlpoolCookingButton(WhirlpoolCookingEntity, ButtonEntity):
    """Whirlpool Cooking button."""

    entity_description: WhirlpoolButtonDescription

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        description: WhirlpoolButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, appliance, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle the button press."""
        result = await self.entity_description.press_fn(
            self.appliance,
            self.coordinator,
        )
        if result is False:
            raise HomeAssistantError("Whirlpool rejected the button command")

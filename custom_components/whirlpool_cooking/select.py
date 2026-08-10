"""Select platform for Whirlpool Cooking."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .cavity import cavity_device_key, cavity_device_name
from .cooking import (
    cavity_attribute,
    cook_mode_attribute_value,
    cook_mode_option,
    set_pending_cook_mode_option,
    supported_cook_mode_options,
)
from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, appliance_label, has_callable
from .sensor import _cavity_exists, _has_attribute

_LOGGER = logging.getLogger(__name__)


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
    entities: list[WhirlpoolCookingSelect] = []
    for appliance in coordinator.data:
        try:
            descriptions = _select_descriptions(appliance)
        except Exception:
            _LOGGER.warning(
                "Unable to build Whirlpool Cooking select entities for %s; "
                "skipping this appliance",
                appliance_label(appliance),
                exc_info=True,
            )
            continue
        entities.extend(
            WhirlpoolCookingSelect(coordinator, appliance, description)
            for description in descriptions
        )
    async_add_entities(entities)


def _select_descriptions(appliance: Any) -> list[WhirlpoolSelectDescription]:
    """Build select descriptions supported by an appliance."""
    return _cavity_select_descriptions(appliance)


def _cavity_select_descriptions(appliance: Any) -> list[WhirlpoolSelectDescription]:
    """Build oven cavity select controls."""
    try:
        from whirlpool.oven import ATTR_POSTFIX_COOK_MODE, Cavity
    except ModuleNotFoundError:
        _LOGGER.warning(
            "Whirlpool oven support is unavailable; skipping oven select controls",
            exc_info=True,
        )
        return []

    descriptions: list[WhirlpoolSelectDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        attribute = cavity_attribute(cavity, ATTR_POSTFIX_COOK_MODE)
        if not _cavity_exists(appliance, cavity) or not _has_attribute(
            appliance,
            attribute,
        ):
            continue
        if not has_callable(appliance, "get_cook_mode") or not has_callable(
            appliance,
            "send_attributes",
        ):
            _LOGGER.debug(
                "Whirlpool appliance %s reports cook mode but lacks the required "
                "cook mode API; skipping %s cook mode control",
                appliance_label(appliance),
                cavity.name.lower(),
            )
            continue
        try:
            options = supported_cook_mode_options(appliance, cavity)
        except Exception:
            _LOGGER.warning(
                "Unable to read supported Whirlpool cook modes for %s; skipping "
                "%s cook mode control",
                appliance_label(appliance),
                cavity.name.lower(),
                exc_info=True,
            )
            continue

        cavity_key = cavity.name.lower()
        descriptions.append(
            WhirlpoolSelectDescription(
                key=f"{cavity_key}_cook_mode_control",
                translation_key=f"{cavity_key}_cook_mode_control",
                cavity=cavity,
                options=options,
                current_fn=lambda item, oven_cavity=cavity: _current_cook_mode(
                    item,
                    oven_cavity,
                ),
                select_fn=lambda item, option, attr=attribute: _send_cook_mode(
                    item,
                    attr,
                    option,
                ),
            ),
        )
    return descriptions


def _current_cook_mode(appliance: Any, cavity: Any) -> str | None:
    """Return the current Whirlpool cook mode without raising into HA."""
    try:
        return cook_mode_option(appliance.get_cook_mode(cavity))
    except Exception:
        _LOGGER.warning(
            "Unable to read Whirlpool cook mode for %s; returning no value",
            appliance_label(appliance),
            exc_info=True,
        )
        return None


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
        normalized_option = cook_mode_option_from_alias(option)
        if normalized_option not in self.entity_description.options:
            raise HomeAssistantError(f"Unsupported Whirlpool option: {option}")
        if not await self.entity_description.select_fn(
            self.appliance,
            normalized_option,
        ):
            raise HomeAssistantError("Whirlpool rejected the select command")
        if self.entity_description.cavity is not None:
            set_pending_cook_mode_option(
                self.appliance,
                self.entity_description.cavity,
                normalized_option,
            )
        await self.coordinator.async_request_refresh()


def cook_mode_option_from_alias(option: str) -> str:
    """Return a canonical cook mode option from a display or legacy value."""
    from .cooking import cook_mode_from_option

    try:
        return cook_mode_option(cook_mode_from_option(option)) or option
    except ValueError:
        return option

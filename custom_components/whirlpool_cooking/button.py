"""Button platform for Whirlpool Cooking."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .cavity import cavity_device_key, cavity_device_name
from .cooking import (
    cavity_attribute,
    cook_mode_attribute_value,
    cook_mode_from_option,
    cook_mode_option,
    get_pending_cook_mode_option,
    get_pending_cook_time,
    get_pending_target_temperature,
)
from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, appliance_label, has_callable
from .sensor import _cavity_exists
from .timer import (
    cancel_kitchen_timer,
    kitchen_timer_supported,
    start_kitchen_timer,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class WhirlpoolButtonDescription(ButtonEntityDescription):
    """Describe a Whirlpool button."""

    press_fn: Callable[[Any, WhirlpoolCookingCoordinator], Awaitable[bool | None]]
    cavity: Any | None = None


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
    entities: list[WhirlpoolCookingButton] = []
    for appliance in coordinator.data:
        try:
            descriptions = _button_descriptions(appliance)
        except Exception:
            _LOGGER.warning(
                "Unable to build Whirlpool Cooking button entities for %s; "
                "skipping this appliance",
                appliance_label(appliance),
                exc_info=True,
            )
            continue
        entities.extend(
            WhirlpoolCookingButton(coordinator, appliance, description)
            for description in descriptions
        )
    async_add_entities(entities)


def _button_descriptions(appliance: Any) -> list[WhirlpoolButtonDescription]:
    """Build button descriptions supported by an appliance."""
    return [
        *BUTTONS,
        *_kitchen_timer_button_descriptions(appliance),
        *_cavity_button_descriptions(appliance),
    ]


def _kitchen_timer_button_descriptions(
    appliance: Any,
) -> list[WhirlpoolButtonDescription]:
    """Build kitchen timer command buttons."""
    if not kitchen_timer_supported(appliance):
        return []
    return [
        WhirlpoolButtonDescription(
            key="start_kitchen_timer",
            translation_key="start_kitchen_timer",
            press_fn=lambda item, coordinator: _async_start_kitchen_timer(
                item,
                coordinator,
            ),
        ),
        WhirlpoolButtonDescription(
            key="cancel_kitchen_timer",
            translation_key="cancel_kitchen_timer",
            press_fn=lambda item, coordinator: _async_cancel_kitchen_timer(
                item,
                coordinator,
            ),
        ),
    ]


def _cavity_button_descriptions(appliance: Any) -> list[WhirlpoolButtonDescription]:
    """Build oven cavity command buttons."""
    try:
        from whirlpool.oven import Cavity
    except ModuleNotFoundError:
        _LOGGER.warning(
            "Whirlpool oven support is unavailable; skipping oven command buttons",
            exc_info=True,
        )
        return []

    descriptions: list[WhirlpoolButtonDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        if not _cavity_exists(appliance, cavity):
            continue

        cavity_key = cavity.name.lower()
        if has_callable(appliance, "set_cook"):
            descriptions.append(
                WhirlpoolButtonDescription(
                    key=f"{cavity_key}_start_cook",
                    translation_key=f"{cavity_key}_start_cook",
                    cavity=cavity,
                    press_fn=(
                        lambda item, coordinator, oven_cavity=cavity: _async_start_cook(
                            item,
                            coordinator,
                            oven_cavity,
                        )
                    ),
                ),
            )
        else:
            _LOGGER.debug(
                "Whirlpool appliance %s does not expose set_cook; "
                "skipping %s start cook",
                appliance_label(appliance),
                cavity_key,
            )

        if has_callable(appliance, "stop_cook"):
            descriptions.append(
                WhirlpoolButtonDescription(
                    key=f"{cavity_key}_stop_cook",
                    translation_key=f"{cavity_key}_stop_cook",
                    cavity=cavity,
                    press_fn=lambda item, coordinator, oven_cavity=cavity: (
                        _async_stop_cook(
                            item,
                            coordinator,
                            oven_cavity,
                        )
                    ),
                ),
            )
        else:
            _LOGGER.debug(
                "Whirlpool appliance %s does not expose stop_cook; "
                "skipping %s stop cook",
                appliance_label(appliance),
                cavity_key,
            )
    return descriptions


async def _async_refresh(coordinator: WhirlpoolCookingCoordinator) -> None:
    """Refresh coordinator data."""
    await coordinator.async_request_refresh()


async def _async_start_kitchen_timer(
    appliance: Any,
    coordinator: WhirlpoolCookingCoordinator,
) -> bool:
    """Start the Whirlpool kitchen timer."""
    result = await start_kitchen_timer(appliance)
    if result:
        await coordinator.async_request_refresh()
    return result


async def _async_cancel_kitchen_timer(
    appliance: Any,
    coordinator: WhirlpoolCookingCoordinator,
) -> bool:
    """Cancel the Whirlpool kitchen timer."""
    result = await cancel_kitchen_timer(appliance)
    if result:
        await coordinator.async_request_refresh()
    return result


async def _async_stop_cook(
    appliance: Any,
    coordinator: WhirlpoolCookingCoordinator,
    cavity: Any,
) -> bool:
    """Stop cooking on an oven cavity."""
    try:
        result = await appliance.stop_cook(cavity)
    except Exception as err:
        raise HomeAssistantError("Whirlpool stop cook command failed") from err
    if result:
        await coordinator.async_request_refresh()
    return result


async def _async_start_cook(
    appliance: Any,
    coordinator: WhirlpoolCookingCoordinator,
    cavity: Any,
) -> bool:
    """Start cooking on an oven cavity using current mode and target temp."""
    mode_option = (
        get_pending_cook_mode_option(appliance, cavity)
        or _current_cook_mode_option(appliance, cavity)
        or "Bake"
    )
    target_temp = (
        get_pending_target_temperature(appliance, cavity)
        or _current_target_temperature(appliance, cavity)
        or 175
    )
    try:
        cook_time = get_pending_cook_time(appliance, cavity)
        if cook_time is not None and has_callable(appliance, "send_attributes"):
            result = await _send_start_cook_attributes(
                appliance,
                cavity,
                mode_option,
                target_temp,
                cook_time,
            )
        else:
            result = await appliance.set_cook(
                target_temp,
                cook_mode_from_option(mode_option),
                cavity,
            )
    except Exception as err:
        raise HomeAssistantError("Whirlpool start cook command failed") from err
    if result:
        await coordinator.async_request_refresh()
    return result


async def _send_start_cook_attributes(
    appliance: Any,
    cavity: Any,
    mode_option: str,
    target_temp: float,
    cook_time: int,
) -> bool:
    """Start cooking with cook time included in the raw attribute payload."""
    from whirlpool.oven import COOK_OPERATION_MAP, CookOperation

    return await appliance.send_attributes(
        {
            cavity_attribute(cavity, "CycleSetCommonMode"): cook_mode_attribute_value(
                mode_option,
            ),
            cavity_attribute(cavity, "CycleSetTargetTemp"): str(
                round(target_temp * 10),
            ),
            cavity_attribute(cavity, "TimeSetCookTimeSet"): str(cook_time),
            cavity_attribute(cavity, "OpSetOperations"): COOK_OPERATION_MAP[
                CookOperation.Start
            ],
        },
    )


def _current_cook_mode_option(appliance: Any, cavity: Any) -> str | None:
    """Return the current cook mode option without raising into HA."""
    if not has_callable(appliance, "get_cook_mode"):
        return None
    try:
        return cook_mode_option(appliance.get_cook_mode(cavity))
    except Exception:
        _LOGGER.warning(
            "Unable to read Whirlpool cook mode for %s; using default for start cook",
            appliance_label(appliance),
            exc_info=True,
        )
        return None


def _current_target_temperature(appliance: Any, cavity: Any) -> float | None:
    """Return the current target temperature without raising into HA."""
    if not has_callable(appliance, "get_target_temp"):
        return None
    try:
        return appliance.get_target_temp(cavity)
    except Exception:
        _LOGGER.warning(
            "Unable to read Whirlpool target temperature for %s; using default "
            "for start cook",
            appliance_label(appliance),
            exc_info=True,
        )
        return None


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
        super().__init__(
            coordinator,
            appliance,
            description.key,
            device_key=cavity_device_key(appliance, description.cavity),
            device_name=cavity_device_name(appliance, description.cavity),
        )
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle the button press."""
        result = await self.entity_description.press_fn(
            self.appliance,
            self.coordinator,
        )
        if result is False:
            raise HomeAssistantError("Whirlpool rejected the button command")

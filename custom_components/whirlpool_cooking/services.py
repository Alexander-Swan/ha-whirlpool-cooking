"""Services for Whirlpool Cooking."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .cooking import cavity_attribute, cook_mode_attribute_value
from .coordinator import WhirlpoolCookingCoordinator
from .timer import parse_duration

SERVICE_SET_COOK = "set_cook"
SERVICE_STOP_COOK = "stop_cook"

ATTR_CAVITY = "cavity"
ATTR_MODE = "mode"
ATTR_TARGET_TEMPERATURE_CELSIUS = "target_temperature_celsius"
ATTR_COOK_TIME = "cook_time"

CAVITY_OPTIONS = ("upper", "lower")
COOK_MODE_OPTIONS = (
    "air_fry",
    "bake",
    "broil",
    "convect_bake",
    "convect_broil",
    "convect_roast",
    "keep_warm",
)

SET_COOK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_CAVITY): vol.In(CAVITY_OPTIONS),
        vol.Required(ATTR_MODE, default="bake"): vol.In(COOK_MODE_OPTIONS),
        vol.Required(ATTR_TARGET_TEMPERATURE_CELSIUS): vol.Coerce(float),
        vol.Optional(ATTR_COOK_TIME): vol.Any(vol.Coerce(int), cv.string),
    },
)

STOP_COOK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_CAVITY): vol.In(CAVITY_OPTIONS),
    },
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Whirlpool Cooking services."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_COOK):
        return

    async def async_set_cook(call: ServiceCall) -> None:
        appliance, coordinator = _appliance_from_entity(
            hass,
            call.data[ATTR_ENTITY_ID],
        )
        cavity = _cavity(call.data[ATTR_CAVITY])
        mode = _cook_mode(call.data[ATTR_MODE])
        cook_time = _cook_time(call.data.get(ATTR_COOK_TIME))
        if cook_time is None:
            result = await appliance.set_cook(
                call.data[ATTR_TARGET_TEMPERATURE_CELSIUS],
                mode,
                cavity,
            )
        else:
            result = await _set_cook_with_time(
                appliance,
                call.data[ATTR_TARGET_TEMPERATURE_CELSIUS],
                call.data[ATTR_MODE],
                cavity,
                cook_time,
            )
        if not result:
            raise HomeAssistantError("Whirlpool rejected the set cook command")
        await coordinator.async_request_refresh()

    async def async_stop_cook(call: ServiceCall) -> None:
        appliance, coordinator = _appliance_from_entity(
            hass,
            call.data[ATTR_ENTITY_ID],
        )
        if not await appliance.stop_cook(_cavity(call.data[ATTR_CAVITY])):
            raise HomeAssistantError("Whirlpool rejected the stop cook command")
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_COOK,
        async_set_cook,
        schema=SET_COOK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_COOK,
        async_stop_cook,
        schema=STOP_COOK_SCHEMA,
    )


def _appliance_from_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> tuple[Any, WhirlpoolCookingCoordinator]:
    """Return the appliance and coordinator associated with an entity."""
    entity_entry = er.async_get(hass).async_get(entity_id)
    if entity_entry is None or entity_entry.device_id is None:
        raise HomeAssistantError(f"Unknown Whirlpool Cooking entity: {entity_id}")

    device = dr.async_get(hass).async_get(entity_entry.device_id)
    if device is None:
        raise HomeAssistantError(f"Entity has no Whirlpool device: {entity_id}")

    said = next(
        (
            identifier
            for domain, identifier in device.identifiers
            if domain == DOMAIN
        ),
        None,
    )
    if said is None:
        raise HomeAssistantError(f"Entity is not a Whirlpool device: {entity_id}")

    for entry in hass.config_entries.async_entries(DOMAIN):
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is None:
            continue
        for appliance in coordinator.data or []:
            if _appliance_matches_identifier(appliance, said):
                return appliance, coordinator

    raise HomeAssistantError(f"Whirlpool appliance is not loaded: {entity_id}")


def _appliance_matches_identifier(appliance: Any, identifier: str) -> bool:
    """Return true when a device identifier belongs to an appliance."""
    said = str(getattr(appliance, "said", ""))
    return bool(said) and (
        identifier == said or identifier.startswith(f"{said}_")
    )


def _cavity(value: str) -> Any:
    """Return a Whirlpool cavity enum."""
    from whirlpool.oven import Cavity

    return Cavity.Upper if value == "upper" else Cavity.Lower


def _cook_mode(value: str) -> Any:
    """Return a Whirlpool cook mode enum."""
    from whirlpool.oven import CookMode

    normalized = value.replace("_", "")
    for mode in CookMode:
        if mode.name.lower() == normalized:
            return mode
    raise HomeAssistantError(f"Unsupported Whirlpool cook mode: {value}")


def _cook_time(value: Any) -> int | None:
    """Return an optional cook time in seconds."""
    if value is None:
        return None
    try:
        return parse_duration(str(value))
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err


async def _set_cook_with_time(
    appliance: Any,
    target_temperature_celsius: float,
    mode: str,
    cavity: Any,
    cook_time: int,
) -> bool:
    """Start cooking with a cook time included in the command payload."""
    from whirlpool.oven import COOK_OPERATION_MAP, CookOperation

    return await appliance.send_attributes(
        {
            cavity_attribute(cavity, "CycleSetCommonMode"): cook_mode_attribute_value(
                mode,
            ),
            cavity_attribute(cavity, "CycleSetTargetTemp"): str(
                round(target_temperature_celsius * 10),
            ),
            cavity_attribute(cavity, "TimeSetCookTimeSet"): str(cook_time),
            cavity_attribute(cavity, "OpSetOperations"): COOK_OPERATION_MAP[
                CookOperation.Start
            ],
        },
    )

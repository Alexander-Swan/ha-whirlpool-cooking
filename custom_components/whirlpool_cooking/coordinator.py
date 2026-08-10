"""Data coordinator for Whirlpool Cooking."""

from __future__ import annotations

import logging
from datetime import timedelta
from inspect import isawaitable
from typing import Any

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BRAND, CONF_REGION, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

COOKING_DATA_MODELS = {
    "ddm_cooking_mhc76_v1",
}


def _enum_member(enum_type: Any, value: str) -> Any:
    """Return a Whirlpool enum member by common value spellings."""
    normalized = value.lower()
    for item in enum_type:
        if item.name.lower() == normalized or str(item.value).lower() == normalized:
            return item
    raise ValueError(f"Unsupported {enum_type.__name__}: {value}")


async def build_appliance_manager(
    session: ClientSession,
    data: dict[str, Any],
) -> Any:
    """Build an authenticated Whirlpool appliance manager."""
    from whirlpool.appliancesmanager import AppliancesManager
    from whirlpool.auth import Auth
    from whirlpool.backendselector import BackendSelector, Brand, Region

    backend_selector = BackendSelector(
        _enum_member(Brand, data[CONF_BRAND]),
        _enum_member(Region, data[CONF_REGION]),
    )
    auth = Auth(
        backend_selector,
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        session,
    )
    await auth.do_auth(store=False)
    manager = AppliancesManager(backend_selector, auth, session)
    _add_cooking_model_compat(manager)
    return manager


class WhirlpoolCookingCoordinator(DataUpdateCoordinator[list[Any]]):
    """Coordinate Whirlpool Cooking appliance updates."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._manager: Any | None = None
        self._push_connected = False

    async def _async_update_data(self) -> list[Any]:
        """Fetch cooking appliance data."""
        try:
            if self._manager is None:
                session = async_get_clientsession(self.hass)
                self._manager = await build_appliance_manager(
                    session,
                    self.config_entry.data,
                )

            if not await self._manager.fetch_appliances():
                raise UpdateFailed("Unable to fetch Whirlpool appliances")

            await self._manager.fetch_all_data()
            await self._async_connect_push_updates()

            appliances = [
                *getattr(self._manager, "ovens", []),
                *getattr(self._manager, "microwaves", []),
            ]
            _log_unsupported_models(self._manager)
        except Exception as err:
            raise UpdateFailed(str(err)) from err
        return appliances

    async def async_shutdown(self) -> None:
        """Disconnect push resources if the library created them."""
        if self._manager is not None:
            await async_disconnect_manager(self._manager)

    async def _async_connect_push_updates(self) -> None:
        """Connect Whirlpool push updates when the library supports them."""
        if self._manager is None or self._push_connected:
            return

        connect = getattr(self._manager, "connect", None)
        if connect is None:
            return

        try:
            result = connect()
            if isawaitable(result):
                await result
        except Exception:
            _LOGGER.warning(
                "Unable to connect Whirlpool push updates; falling back to polling",
                exc_info=True,
            )
            return

        self._push_connected = True
        self.update_interval = None


async def async_disconnect_manager(manager: Any) -> None:
    """Disconnect manager resources when supported by the library."""
    if _disconnect_is_noop(manager):
        return

    disconnect = getattr(manager, "disconnect", None)
    if disconnect is None:
        return

    result = disconnect()
    if isawaitable(result):
        await result


def _add_cooking_model_compat(manager: Any) -> None:
    """Teach older whirlpool-sixth-sense releases about known cooking models."""
    add_appliance = getattr(manager, "_add_appliance", None)
    if add_appliance is None:
        return

    def add_appliance_with_cooking_models(appliance: dict[str, Any]) -> None:
        data_model = str(appliance.get("DATA_MODEL_KEY", "")).lower()
        if data_model in COOKING_DATA_MODELS:
            _add_oven_appliance(manager, appliance)
            return

        add_appliance(appliance)

    manager._add_appliance = add_appliance_with_cooking_models


def _add_oven_appliance(manager: Any, appliance: dict[str, Any]) -> None:
    """Register an appliance as an oven using the upstream library types."""
    from whirlpool.oven import Oven
    from whirlpool.types import ApplianceInfo

    data_model = appliance["DATA_MODEL_KEY"]
    appliance_data = ApplianceInfo(
        said=appliance["SAID"],
        name=appliance["APPLIANCE_NAME"],
        data_model=data_model,
        category=appliance["CATEGORY_NAME"],
        model_number=appliance.get("MODEL_NO", ""),
        serial_number=appliance.get("SERIAL", ""),
    )
    manager._ovens[appliance_data.said] = Oven(
        manager._backend_selector,
        manager._auth,
        manager._session,
        appliance_data,
    )
    manager.__dict__.pop("all_appliances", None)
    _LOGGER.debug("Registered Whirlpool cooking appliance model %s", data_model)


def _disconnect_is_noop(manager: Any) -> bool:
    """Return true when the upstream manager has no push resources to close."""
    state = getattr(manager, "__dict__", {})
    has_push_state = "_event_socket" in state or "_keepalive_task" in state
    return (
        has_push_state
        and state.get("_event_socket") is None
        and state.get("_keepalive_task") is None
    )


def _log_unsupported_models(manager: Any) -> None:
    """Log raw appliance model keys for discovery-oriented debugging."""
    for appliance in getattr(manager, "appliances", []):
        data_model = _first_present(
            appliance,
            "data_model",
            "data_model_key",
            "DATA_MODEL_KEY",
        )
        if data_model:
            _LOGGER.debug("Whirlpool appliance data model discovered: %s", data_model)


def _first_present(source: Any, *names: str) -> Any:
    """Read the first present attribute or mapping key."""
    for name in names:
        if isinstance(source, dict) and name in source:
            return source[name]
        if hasattr(source, name):
            return getattr(source, name)
    return None

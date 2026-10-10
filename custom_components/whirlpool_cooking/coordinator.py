"""Data coordinator for Whirlpool Cooking."""

from __future__ import annotations

import logging
from datetime import timedelta
from importlib import import_module
from inspect import isawaitable, signature
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


async def async_prepare_manager(manager: Any) -> bool:
    """Fetch appliance data using the available upstream manager API."""
    fetch_appliances = getattr(manager, "fetch_appliances", None)
    if fetch_appliances is not None:
        if not await _maybe_await(fetch_appliances()):
            return False

        fetch_all_data = getattr(manager, "fetch_all_data", None)
        if fetch_all_data is not None:
            await _maybe_await(fetch_all_data())
        return True

    connect = getattr(manager, "connect", None)
    if connect is None:
        raise UpdateFailed("Whirlpool appliance manager has no supported fetch API")

    result = await _maybe_await(connect())
    return result is not False


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

            if not await async_prepare_manager(self._manager):
                raise UpdateFailed("Unable to fetch Whirlpool appliances")

            if hasattr(self._manager, "fetch_appliances"):
                await self._async_connect_push_updates()
            else:
                self._push_connected = True

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
                "Unable to connect Whirlpool push updates; continuing with polling",
                exc_info=True,
            )
            return

        self._push_connected = True


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


async def _maybe_await(value: Any) -> Any:
    """Await a value only when the upstream API returned an awaitable."""
    if isawaitable(value):
        return await value
    return value


def _add_cooking_model_compat(manager: Any) -> None:
    """Teach older whirlpool-sixth-sense releases about known cooking models."""
    for target in _manager_compat_targets(manager):
        _add_cooking_model_compat_to_manager(target)


def _manager_compat_targets(manager: Any) -> tuple[Any, ...]:
    """Return upstream managers that may classify HTTP appliance payloads."""
    targets = [manager]
    for name in ("_http_appliances_manager",):
        target = getattr(manager, name, None)
        if target is not None:
            targets.append(target)
    return tuple(targets)


def _add_cooking_model_compat_to_manager(manager: Any) -> None:
    """Teach one upstream manager about known cooking models."""
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
    data_model = appliance["DATA_MODEL_KEY"]
    appliance_data = _appliance_info(appliance, data_model)
    manager._ovens[appliance_data.said] = _oven_type(manager)(
        manager._backend_selector,
        manager._auth,
        manager._session,
        appliance_data,
    )
    manager.__dict__.pop("all_appliances", None)
    _LOGGER.debug("Registered Whirlpool cooking appliance model %s", data_model)


def _appliance_info(appliance: dict[str, Any], data_model: str) -> Any:
    """Build ApplianceInfo across whirlpool-sixth-sense versions."""
    from whirlpool.types import ApplianceInfo

    kwargs = {
        "said": appliance["SAID"],
        "name": appliance["APPLIANCE_NAME"],
        "category": appliance["CATEGORY_NAME"],
        "model_number": appliance.get("MODEL_NO", ""),
        "serial_number": appliance.get("SERIAL", ""),
    }
    if "data_model" in signature(ApplianceInfo).parameters:
        kwargs["data_model"] = data_model
    return ApplianceInfo(**kwargs)


def _oven_type(manager: Any) -> Any:
    """Return the Oven type that belongs to the upstream manager."""
    module_name = type(manager).__module__
    if ".appliancesmanager" in module_name:
        try:
            module = import_module(module_name.rsplit(".", 1)[0] + ".oven")
            return module.Oven
        except (ImportError, AttributeError):
            pass

    from whirlpool.oven import Oven

    return Oven


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

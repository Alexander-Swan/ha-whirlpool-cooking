"""Data coordinator for Whirlpool Cooking."""

from __future__ import annotations

from datetime import timedelta
import logging
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
    return AppliancesManager(backend_selector, auth, session)


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
        if self._manager is not None and hasattr(self._manager, "disconnect"):
            await self._manager.disconnect()


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

"""Whirlpool Cooking integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import WhirlpoolCookingCoordinator
from .services import async_setup_services

type WhirlpoolCookingConfigEntry = ConfigEntry[WhirlpoolCookingCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WhirlpoolCookingConfigEntry,
) -> bool:
    """Set up Whirlpool Cooking from a config entry."""
    await async_setup_services(hass)

    coordinator = WhirlpoolCookingCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(
        entry,
        [Platform(platform) for platform in PLATFORMS],
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: WhirlpoolCookingConfigEntry,
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        [Platform(platform) for platform in PLATFORMS],
    )
    if unload_ok:
        await entry.runtime_data.async_shutdown()
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant,
    entry: WhirlpoolCookingConfigEntry,
) -> None:
    """Reload Whirlpool Cooking when options change."""
    await hass.config_entries.async_reload(entry.entry_id)

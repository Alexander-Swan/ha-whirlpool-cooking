"""Coordinator tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import sys

import pytest


pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Home Assistant test runtime requires Python 3.14",
)


async def test_coordinator_combines_ovens_and_microwaves(hass) -> None:
    """Test coordinator returns cooking appliances."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.whirlpool_cooking.const import DOMAIN
    from custom_components.whirlpool_cooking.coordinator import (
        WhirlpoolCookingCoordinator,
    )

    oven = object()
    microwave = object()
    manager = AsyncMock()
    manager.fetch_appliances.return_value = True
    manager.ovens = [oven]
    manager.microwaves = [microwave]
    manager.appliances = []
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "cook@example.com",
            "password": "secret",
            "region": "US",
            "brand": "whirlpool",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.whirlpool_cooking.coordinator.build_appliance_manager",
        return_value=manager,
    ):
        coordinator = WhirlpoolCookingCoordinator(hass, entry)
        data = await coordinator._async_update_data()

    assert data == [oven, microwave]
    manager.fetch_appliances.assert_awaited_once()


async def test_coordinator_failed_fetch_raises_update_failed(hass) -> None:
    """Test coordinator surfaces fetch failures."""
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.whirlpool_cooking.const import DOMAIN
    from custom_components.whirlpool_cooking.coordinator import (
        WhirlpoolCookingCoordinator,
    )

    manager = AsyncMock()
    manager.fetch_appliances.return_value = False
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "cook@example.com",
            "password": "secret",
            "region": "US",
            "brand": "whirlpool",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.whirlpool_cooking.coordinator.build_appliance_manager",
        return_value=manager,
    ):
        coordinator = WhirlpoolCookingCoordinator(hass, entry)
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


async def test_disconnect_manager_handles_sync_and_async_disconnects() -> None:
    """Test manager cleanup supports both library shapes."""
    from custom_components.whirlpool_cooking.coordinator import async_disconnect_manager

    async_manager = AsyncMock()
    await async_disconnect_manager(async_manager)
    async_manager.disconnect.assert_awaited_once()

    class SyncManager:
        def __init__(self) -> None:
            self.disconnected = False

        def disconnect(self) -> None:
            self.disconnected = True

    sync_manager = SyncManager()
    await async_disconnect_manager(sync_manager)
    assert sync_manager.disconnected is True


async def test_coordinator_shutdown_disconnects_manager(hass) -> None:
    """Test coordinator shutdown cleans up the active manager."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.whirlpool_cooking.const import DOMAIN
    from custom_components.whirlpool_cooking.coordinator import (
        WhirlpoolCookingCoordinator,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "cook@example.com",
            "password": "secret",
            "region": "US",
            "brand": "whirlpool",
        },
    )
    entry.add_to_hass(hass)
    coordinator = WhirlpoolCookingCoordinator(hass, entry)
    coordinator._manager = AsyncMock()

    await coordinator.async_shutdown()

    coordinator._manager.disconnect.assert_awaited_once()

"""Coordinator tests."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, patch

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
    manager.fetch_all_data.assert_awaited_once()


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


async def test_disconnect_manager_skips_unstarted_library_socket() -> None:
    """Test unstarted push resources are not disconnected noisily."""
    from custom_components.whirlpool_cooking.coordinator import async_disconnect_manager

    class Manager:
        def __init__(self) -> None:
            self._event_socket = None
            self._keepalive_task = None

        def disconnect(self) -> None:
            raise AssertionError("disconnect should not be called")

    await async_disconnect_manager(Manager())


def test_known_cooking_model_is_registered_as_oven(monkeypatch) -> None:
    """Test local compatibility handles newly discovered cooking data models."""
    from custom_components.whirlpool_cooking.coordinator import (
        _add_cooking_model_compat,
    )

    class ApplianceInfo:
        def __init__(
            self,
            *,
            said,
            name,
            data_model,
            category,
            model_number,
            serial_number,
        ) -> None:
            self.said = said
            self.name = name
            self.data_model = data_model
            self.category = category
            self.model_number = model_number
            self.serial_number = serial_number

    class Oven:
        def __init__(self, backend_selector, auth, session, appliance_data) -> None:
            self.backend_selector = backend_selector
            self.auth = auth
            self.session = session
            self.appliance_data = appliance_data

    oven_module = types.ModuleType("whirlpool.oven")
    oven_module.Oven = Oven
    types_module = types.ModuleType("whirlpool.types")
    types_module.ApplianceInfo = ApplianceInfo
    whirlpool_module = types.ModuleType("whirlpool")
    whirlpool_module.oven = oven_module
    whirlpool_module.types = types_module
    monkeypatch.setitem(sys.modules, "whirlpool", whirlpool_module)
    monkeypatch.setitem(sys.modules, "whirlpool.oven", oven_module)
    monkeypatch.setitem(sys.modules, "whirlpool.types", types_module)

    class Manager:
        def __init__(self) -> None:
            self._backend_selector = object()
            self._auth = object()
            self._session = object()
            self._ovens = {}
            self.original_calls = []
            self.all_appliances = {}

        def _add_appliance(self, appliance) -> None:
            self.original_calls.append(appliance)

    manager = Manager()
    _add_cooking_model_compat(manager)

    appliance = {
        "SAID": "SAID123",
        "APPLIANCE_NAME": "Kitchen Oven",
        "DATA_MODEL_KEY": "ddm_cooking_mhc76_v1",
        "CATEGORY_NAME": "cooking",
        "MODEL_NO": "MHC76",
        "SERIAL": "SERIAL123",
    }
    manager._add_appliance(appliance)

    assert manager.original_calls == []
    assert manager.all_appliances == {}
    assert (
        manager._ovens["SAID123"].appliance_data.data_model
        == "ddm_cooking_mhc76_v1"
    )


def test_unknown_cooking_model_uses_library_handler() -> None:
    """Test unknown appliance models still flow through the library."""
    from custom_components.whirlpool_cooking.coordinator import (
        _add_cooking_model_compat,
    )

    class Manager:
        def __init__(self) -> None:
            self.original_calls = []

        def _add_appliance(self, appliance) -> None:
            self.original_calls.append(appliance)

    manager = Manager()
    _add_cooking_model_compat(manager)
    appliance = {"DATA_MODEL_KEY": "unknown_model"}

    manager._add_appliance(appliance)

    assert manager.original_calls == [appliance]


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

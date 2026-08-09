"""Config flow tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import sys

import pytest


pytestmark = [
    pytest.mark.skipif(
        sys.version_info < (3, 14),
        reason="Home Assistant test runtime requires Python 3.14",
    ),
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def test_config_flow_success(hass) -> None:
    """Test successful config flow."""
    from homeassistant import data_entry_flow

    from custom_components.whirlpool_cooking.const import (
        CONF_BRAND,
        CONF_REGION,
        DOMAIN,
    )

    user_input = {
        "username": "cook@example.com",
        "password": "secret",
        CONF_REGION: "US",
        CONF_BRAND: "whirlpool",
    }
    manager = AsyncMock()
    manager.fetch_appliances.return_value = [object()]

    with patch(
        "custom_components.whirlpool_cooking.config_flow.build_appliance_manager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=user_input,
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Whirlpool Cooking"
    assert result["data"] == user_input
    manager.fetch_appliances.assert_awaited_once()
    manager.disconnect.assert_called_once()


async def test_config_flow_empty_appliances_returns_cannot_connect(hass) -> None:
    """Test empty discovery during config flow."""
    from homeassistant import data_entry_flow

    from custom_components.whirlpool_cooking.const import (
        CONF_BRAND,
        CONF_REGION,
        DOMAIN,
    )

    manager = AsyncMock()
    manager.fetch_appliances.return_value = []

    with patch(
        "custom_components.whirlpool_cooking.config_flow.build_appliance_manager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={
                "username": "cook@example.com",
                "password": "secret",
                CONF_REGION: "US",
                CONF_BRAND: "whirlpool",
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    manager.disconnect.assert_called_once()


async def test_config_flow_client_error_returns_cannot_connect(hass) -> None:
    """Test client errors during config flow."""
    from aiohttp import ClientError
    from homeassistant import data_entry_flow

    from custom_components.whirlpool_cooking.const import (
        CONF_BRAND,
        CONF_REGION,
        DOMAIN,
    )

    with patch(
        "custom_components.whirlpool_cooking.config_flow.build_appliance_manager",
        side_effect=ClientError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={
                "username": "cook@example.com",
                "password": "secret",
                CONF_REGION: "US",
                CONF_BRAND: "whirlpool",
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_unexpected_error_returns_unknown(hass) -> None:
    """Test unexpected errors during config flow."""
    from homeassistant import data_entry_flow

    from custom_components.whirlpool_cooking.const import (
        CONF_BRAND,
        CONF_REGION,
        DOMAIN,
    )

    with patch(
        "custom_components.whirlpool_cooking.config_flow.build_appliance_manager",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={
                "username": "cook@example.com",
                "password": "secret",
                CONF_REGION: "US",
                CONF_BRAND: "whirlpool",
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

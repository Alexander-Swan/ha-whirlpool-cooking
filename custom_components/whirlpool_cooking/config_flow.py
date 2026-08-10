"""Config flow for Whirlpool Cooking."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BRANDS,
    CONF_BRAND,
    CONF_REGION,
    CONF_TEMPERATURE_UNIT,
    DOMAIN,
    REGIONS,
    TEMP_UNIT_CELSIUS,
    TEMP_UNITS,
)
from .coordinator import async_disconnect_manager, build_appliance_manager

_LOGGER = logging.getLogger(__name__)

ERR_ACCOUNT_LOCKED = "account_locked"


class WhirlpoolCookingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Whirlpool Cooking config flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return WhirlpoolCookingOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_BRAND]}_{user_input[CONF_REGION]}_{user_input[CONF_USERNAME]}",
            )
            self._abort_if_unique_id_configured()

            manager: Any | None = None
            try:
                session = async_get_clientsession(self.hass)
                manager = await build_appliance_manager(session, user_input)
                if not await manager.fetch_appliances():
                    _LOGGER.warning(
                        "Whirlpool setup connected but could not fetch appliances "
                        "for brand=%s region=%s username=%s",
                        user_input[CONF_BRAND],
                        user_input[CONF_REGION],
                        user_input[CONF_USERNAME],
                    )
                    errors["base"] = "cannot_connect"
            except ClientError as err:
                _LOGGER.warning(
                    "Whirlpool setup failed while connecting for brand=%s "
                    "region=%s username=%s: %s",
                    user_input[CONF_BRAND],
                    user_input[CONF_REGION],
                    user_input[CONF_USERNAME],
                    err,
                )
                errors["base"] = "cannot_connect"
            except Exception as err:
                if type(err).__name__ == "AccountLockedError":
                    _LOGGER.warning(
                        "Whirlpool account is locked for brand=%s region=%s "
                        "username=%s",
                        user_input[CONF_BRAND],
                        user_input[CONF_REGION],
                        user_input[CONF_USERNAME],
                    )
                    errors["base"] = ERR_ACCOUNT_LOCKED
                else:
                    _LOGGER.exception("Unexpected Whirlpool Cooking setup failure")
                    errors["base"] = "unknown"
            else:
                if not errors:
                    return self.async_create_entry(
                        title=f"{user_input[CONF_BRAND].title()} Cooking",
                        data=user_input,
                    )
            finally:
                if manager is not None:
                    await async_disconnect_manager(manager)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_REGION, default=REGIONS[0]): vol.In(REGIONS),
                    vol.Required(CONF_BRAND, default=BRANDS[0]): vol.In(BRANDS),
                },
            ),
            errors=errors,
        )


class WhirlpoolCookingOptionsFlow(config_entries.OptionsFlow):
    """Handle Whirlpool Cooking options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage Whirlpool Cooking options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TEMPERATURE_UNIT,
                        default=self._config_entry.options.get(
                            CONF_TEMPERATURE_UNIT,
                            TEMP_UNIT_CELSIUS,
                        ),
                    ): vol.In(TEMP_UNITS),
                },
            ),
        )

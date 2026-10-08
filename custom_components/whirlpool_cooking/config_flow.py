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
            await self.async_set_unique_id(_unique_id(user_input))
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_BRAND].title()} Cooking",
                    data=user_input,
                )

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

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Handle a Whirlpool credential refresh."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Ask the user to re-enter Whirlpool credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}

            errors = await self._async_validate_input(new_data)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data=new_data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                },
            ),
            errors=errors,
        )

    async def _async_validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate Whirlpool credentials and appliance access."""
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
                return {"base": "cannot_connect"}
        except ClientError as err:
            _LOGGER.warning(
                "Whirlpool setup failed while connecting for brand=%s "
                "region=%s username=%s: %s",
                user_input[CONF_BRAND],
                user_input[CONF_REGION],
                user_input[CONF_USERNAME],
                err,
            )
            return {"base": "cannot_connect"}
        except Exception as err:
            if type(err).__name__ == "AccountLockedError":
                _LOGGER.warning(
                    "Whirlpool account is locked for brand=%s region=%s username=%s",
                    user_input[CONF_BRAND],
                    user_input[CONF_REGION],
                    user_input[CONF_USERNAME],
                )
                return {"base": ERR_ACCOUNT_LOCKED}

            _LOGGER.exception("Unexpected Whirlpool Cooking setup failure")
            return {"base": "unknown"}
        finally:
            if manager is not None:
                await async_disconnect_manager(manager)

        return {}


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


def _unique_id(data: dict[str, Any]) -> str:
    """Return the stable account unique ID."""
    return f"{data[CONF_BRAND]}_{data[CONF_REGION]}_{data[CONF_USERNAME]}"

"""Entity helpers for Whirlpool Cooking."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .cavity import default_cavity_device_key, default_cavity_device_name
from .const import DOMAIN
from .coordinator import WhirlpoolCookingCoordinator

_LOGGER = logging.getLogger(__name__)


class WhirlpoolCookingEntity(CoordinatorEntity[WhirlpoolCookingCoordinator]):
    """Base Whirlpool Cooking entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        key: str,
        *,
        device_key: str | None = None,
        device_name: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._appliance = appliance
        self._said = str(_value(appliance, "said", "SAID", default="unknown"))
        self._device_key = device_key or default_cavity_device_key(appliance)
        self._device_name = device_name or default_cavity_device_name(appliance)
        self.entity_key = key
        self._attr_unique_id = f"{self.said}_{key}"
        self._registered_appliance: Any | None = None
        self._attr_available = self._appliance_available(appliance)

    async def async_added_to_hass(self) -> None:
        """Register for Whirlpool push attribute updates."""
        await super().async_added_to_hass()
        self._register_attr_callback()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister Whirlpool push attribute updates."""
        self._unregister_attr_callback()
        await super().async_will_remove_from_hass()

    @property
    def appliance(self) -> Any:
        """Return the latest appliance object from coordinator data."""
        for appliance in self.coordinator.data or []:
            if str(_value(appliance, "said", "SAID", default="unknown")) == self._said:
                return appliance
        return self._appliance

    @property
    def said(self) -> str:
        """Return the appliance SAID."""
        return self._said

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._appliance_available(self.appliance)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        name = _value(self.appliance, "name", "appliance_name", default=self.said)
        model = _value(self.appliance, "model", "model_number", default=None)
        if self._device_key is not None:
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self.said}_{self._device_key}")},
                manufacturer="Whirlpool",
                name=f"{name} {self._device_name or self._device_key}",
                model=str(model) if model else None,
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self.said)},
            manufacturer="Whirlpool",
            name=str(name),
            model=str(model) if model else None,
        )

    def _register_attr_callback(self) -> None:
        """Register this entity for Whirlpool appliance attribute updates."""
        appliance = self.appliance
        register = getattr(appliance, "register_attr_callback", None)
        if not callable(register):
            return
        register(self._async_attr_callback)
        self._registered_appliance = appliance

    def _unregister_attr_callback(self) -> None:
        """Unregister this entity from Whirlpool appliance attribute updates."""
        if self._registered_appliance is None:
            return
        unregister = getattr(
            self._registered_appliance,
            "unregister_attr_callback",
            None,
        )
        if callable(unregister):
            unregister(self._async_attr_callback)
        self._registered_appliance = None

    @callback
    def _async_attr_callback(self) -> None:
        """Handle a pushed Whirlpool appliance attribute update."""
        self._attr_available = self._appliance_available(self.appliance)
        self.async_write_ha_state()

    @staticmethod
    def _appliance_available(appliance: Any) -> bool:
        """Return availability from the appliance online state."""
        online = _value(appliance, "get_online", default=True)
        if isinstance(online, str):
            return online.lower() not in {"0", "false", "no", "off", "offline"}
        return online is not False and online is not None


def _value(source: Any, *names: str, default: Any = None) -> Any:
    """Read a value from an object or mapping."""
    for name in names:
        if isinstance(source, dict) and name in source:
            return source[name]
        if hasattr(source, name):
            value = getattr(source, name)
            if callable(value) and not name.startswith("set_"):
                try:
                    return value()
                except TypeError:
                    return default
                except Exception:
                    _LOGGER.warning(
                        "Unable to read Whirlpool value %s; using default",
                        name,
                        exc_info=True,
                    )
                    return default
            return value
    return default


def appliance_label(appliance: Any) -> str:
    """Return a safe appliance label for logs."""
    return str(_value(appliance, "name", "appliance_name", "said", default="unknown"))


def has_callable(appliance: Any, name: str) -> bool:
    """Return true if an appliance exposes a callable API method."""
    return callable(getattr(appliance, name, None))

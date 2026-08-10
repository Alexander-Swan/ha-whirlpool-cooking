"""Entity helpers for Whirlpool Cooking."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .cavity import default_cavity_device_key, default_cavity_device_name
from .const import DOMAIN
from .coordinator import WhirlpoolCookingCoordinator


class WhirlpoolCookingEntity(CoordinatorEntity[WhirlpoolCookingCoordinator]):
    """Base Whirlpool Cooking entity."""

    _attr_has_entity_name = True

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
            return value
    return default

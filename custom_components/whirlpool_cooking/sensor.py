"""Sensor platform for Whirlpool Cooking."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .cavity import (
    cavity_device_key,
    cavity_device_name,
    existing_cavities,
    has_attribute,
)
from .cavity import cavity_exists as _cavity_exists
from .cooking import cavity_attribute, enum_label
from .coordinator import WhirlpoolCookingCoordinator
from .entity import WhirlpoolCookingEntity, appliance_label, has_callable
from .temperature import configured_temperature_unit, temperature_from_celsius

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSensorDescription(SensorEntityDescription):
    """Describe a Whirlpool sensor."""

    value_fn: Callable[[Any], Any]
    cavity: Any | None = None


SENSORS: tuple[WhirlpoolSensorDescription, ...] = ()

TIME_ATTRIBUTES = (
    ("kitchen_timer_time", "KitchenTimer01_SetTimeSet"),
    ("kitchen_timer_time_remaining", "KitchenTimer01_StatusTimeRemaining"),
)

STATUS_ATTRIBUTES = (
    ("kitchen_timer_state", "KitchenTimer01_StatusState"),
    ("fault_code", "Sys_AlertStatusCustomerFaultCode"),
    ("notification", "Sys_AlertStatusNotification"),
    ("customer_fault_notification", "CustomerFaultCodeNotification"),
    ("timezone", "TimeZoneId"),
    ("utc_offset", "UtcOffset"),
    ("date_time_mode", "DateTimeMode"),
    ("appliance_version", "ApplianceVersionNumber"),
    ("project_release", "ProjectReleaseNumber"),
    ("model_number", "ModelNumber"),
    ("xcat_model_number", "XCat_ApplianceInfoSetModelNumber"),
)

MEASUREMENT_ATTRIBUTES = (
    (
        "real_time_power",
        ("XCat_PowerStatusRealTimePower",),
        SensorDeviceClass.POWER,
        UnitOfPower.WATT,
    ),
    (
        "real_time_voltage",
        ("XCat_PowerStatusRealTimeVoltage",),
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
    ),
    (
        "real_time_current",
        ("XCat_PowerStatusRealTimeCurrent",),
        SensorDeviceClass.CURRENT,
        UnitOfElectricCurrent.AMPERE,
    ),
    (
        "energy_consumption",
        ("XCat_PowerStatusEnergyConsumption",),
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
    ),
    (
        "energy_measurement_results",
        ("XCat_PowerStatusEnergyMeasurementResults",),
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
    ),
    (
        "power_outage",
        ("XCat_PowerStatusPowerOutage",),
        None,
        None,
    ),
    (
        "cycle_count",
        ("XCat_OdometerStatusCycleCount", "Mwo_CycleStatusOdometer"),
        None,
        None,
    ),
    (
        "running_hours",
        ("XCat_OdometerStatusRunningHours",),
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
    ),
    (
        "total_hours",
        ("XCat_OdometerStatusTotalHours",),
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
    ),
    (
        "wifi_rssi",
        ("XCat_WifiStatusRssiAntennaDiversity", "WifiRssi"),
        SensorDeviceClass.SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
)

RAW_ATTRIBUTE_KEYWORDS = (
    "cook",
    "cycle",
    "microwave",
    "mwo",
)

MICROWAVE_SENSOR_SPECS = (
    (
        "state",
        (("status", "state"), ("cycle", "state")),
        ("door", "light", "timer"),
    ),
    (
        "mode",
        (("cook", "mode"), ("cycle", "mode"), ("mode",)),
        ("remote", "sabbath"),
    ),
    (
        "cook_time",
        (("cook", "time"), ("cycle", "set", "time")),
        ("elapsed", "remaining"),
    ),
    (
        "time_remaining",
        (("time", "remaining"), ("remaining", "time")),
        ("timer",),
    ),
    (
        "temperature",
        (("display", "temp"), ("status", "temp")),
        ("target", "set"),
    ),
    (
        "target_temperature",
        (("target", "temp"), ("set", "temp")),
        (),
    ),
)


def _enum_name(value: Any) -> str | None:
    """Return a stable state string for Whirlpool enum values."""
    return enum_label(value)


def _cavity_sensor_descriptions(appliance: Any) -> list[WhirlpoolSensorDescription]:
    """Build descriptions for oven cavities that exist on the appliance."""
    try:
        from whirlpool.oven import Cavity
    except ModuleNotFoundError:
        return []

    descriptions: list[WhirlpoolSensorDescription] = []
    for cavity in (Cavity.Upper, Cavity.Lower):
        if not _cavity_exists(appliance, cavity):
            continue

        cavity_key = cavity.name.lower()
        if has_callable(appliance, "get_cavity_state"):
            descriptions.append(
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_state",
                    translation_key=f"{cavity_key}_state",
                    cavity=cavity,
                    value_fn=lambda item, oven_cavity=cavity: _safe_cavity_value(
                        item,
                        "get_cavity_state",
                        oven_cavity,
                        transform=_enum_name,
                    ),
                ),
            )
        else:
            _log_missing_method(appliance, "get_cavity_state", f"{cavity_key}_state")

        if has_callable(appliance, "get_cook_mode"):
            descriptions.append(
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_mode",
                    translation_key=f"{cavity_key}_mode",
                    cavity=cavity,
                    value_fn=lambda item, oven_cavity=cavity: _safe_cavity_value(
                        item,
                        "get_cook_mode",
                        oven_cavity,
                        transform=_enum_name,
                    ),
                ),
            )
        else:
            _log_missing_method(appliance, "get_cook_mode", f"{cavity_key}_mode")

        if has_callable(appliance, "get_temp"):
            descriptions.append(
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_temperature",
                    translation_key=f"{cavity_key}_temperature",
                    cavity=cavity,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    value_fn=lambda item, oven_cavity=cavity: _safe_cavity_value(
                        item,
                        "get_temp",
                        oven_cavity,
                    ),
                ),
            )
        else:
            _log_missing_method(appliance, "get_temp", f"{cavity_key}_temperature")

        if has_callable(appliance, "get_target_temp"):
            descriptions.append(
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_target_temperature",
                    translation_key=f"{cavity_key}_target_temperature",
                    cavity=cavity,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    value_fn=lambda item, oven_cavity=cavity: _safe_cavity_value(
                        item,
                        "get_target_temp",
                        oven_cavity,
                    ),
                ),
            )
        else:
            _log_missing_method(
                appliance,
                "get_target_temp",
                f"{cavity_key}_target_temperature",
            )

        if has_callable(appliance, "get_cook_time") or _has_attribute(
            appliance,
            cavity_attribute(cavity, "TimeSetCookTimeSet"),
        ):
            descriptions.extend(
                (
                    WhirlpoolSensorDescription(
                        key=f"{cavity_key}_cook_time",
                        translation_key=f"{cavity_key}_cook_time",
                        cavity=cavity,
                        value_fn=lambda item, oven_cavity=cavity: _oven_cook_time(
                            item,
                            oven_cavity,
                        ),
                    ),
                    WhirlpoolSensorDescription(
                        key=f"{cavity_key}_cook_time_remaining",
                        translation_key=f"{cavity_key}_cook_time_remaining",
                        cavity=cavity,
                        value_fn=lambda item, oven_cavity=cavity: (
                            _formatted_cavity_time(
                                item,
                                oven_cavity,
                                "TimeStatusCookTimeRemaining",
                            )
                        ),
                    ),
                ),
            )
        descriptions.extend(
            (
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_delay_time_remaining",
                    translation_key=f"{cavity_key}_delay_time_remaining",
                    cavity=cavity,
                    value_fn=lambda item, oven_cavity=cavity: _formatted_cavity_time(
                        item,
                        oven_cavity,
                        "TimeStatusDelayTimeRemaining",
                    ),
                ),
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_recipe_cook_time",
                    translation_key=f"{cavity_key}_recipe_cook_time",
                    cavity=cavity,
                    value_fn=lambda item, oven_cavity=cavity: _formatted_cavity_time(
                        item,
                        oven_cavity,
                        "_RecipeSetFacadeCookTime",
                    ),
                ),
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_recipe_temperature",
                    translation_key=f"{cavity_key}_recipe_temperature",
                    cavity=cavity,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    value_fn=lambda item, oven_cavity=cavity: _cavity_raw_temperature(
                        item,
                        oven_cavity,
                        "_RecipeSetFacadeDisplayTemp",
                    ),
                ),
                WhirlpoolSensorDescription(
                    key=f"{cavity_key}_recipe_mode",
                    translation_key=f"{cavity_key}_recipe_mode",
                    cavity=cavity,
                    value_fn=lambda item, oven_cavity=cavity: _raw_attribute_value(
                        item,
                        cavity_attribute(oven_cavity, "_RecipeSetFacadeMode"),
                    ),
                ),
            ),
        )
    return [
        description
        for description in descriptions
        if description.cavity is None
        or _cavity_sensor_supported(appliance, description.cavity, description.key)
    ]


def _sensor_descriptions(appliance: Any) -> list[WhirlpoolSensorDescription]:
    """Build all sensor descriptions for an appliance."""
    global_descriptions = _global_sensor_descriptions(appliance)
    cavity_descriptions = _cavity_sensor_descriptions(appliance)
    if cavity_descriptions or existing_cavities(appliance):
        return [*SENSORS, *global_descriptions, *cavity_descriptions]
    return [*SENSORS, *global_descriptions, *_microwave_sensor_descriptions(appliance)]


def _global_sensor_descriptions(appliance: Any) -> list[WhirlpoolSensorDescription]:
    """Build global appliance sensor descriptions."""
    descriptions: list[WhirlpoolSensorDescription] = []

    for key, attribute in TIME_ATTRIBUTES:
        if _has_attribute(appliance, attribute):
            descriptions.append(
                WhirlpoolSensorDescription(
                    key=key,
                    translation_key=key,
                    value_fn=lambda item, attr=attribute: (
                        _formatted_raw_duration_attribute(item, attr)
                    ),
                ),
            )

    for key, attribute in STATUS_ATTRIBUTES:
        if _has_attribute(appliance, attribute):
            descriptions.append(
                WhirlpoolSensorDescription(
                    key=key,
                    translation_key=key,
                    value_fn=lambda item, attr=attribute: _raw_attribute_value(
                        item,
                        attr,
                    ),
                ),
            )

    for key, attributes, device_class, unit in MEASUREMENT_ATTRIBUTES:
        attribute = _first_existing_attribute(appliance, attributes)
        if attribute is None:
            continue
        descriptions.append(
            WhirlpoolSensorDescription(
                key=key,
                translation_key=key,
                device_class=device_class,
                native_unit_of_measurement=unit,
                value_fn=lambda item, attr=attribute: _raw_number_attribute(
                    item,
                    attr,
                ),
            ),
        )

    return descriptions


def _microwave_sensor_descriptions(
    appliance: Any,
) -> list[WhirlpoolSensorDescription]:
    """Build stable microwave sensors from known raw Whirlpool attributes."""
    descriptions: list[WhirlpoolSensorDescription] = []
    if not _is_microwave_like(appliance):
        return descriptions

    for key, token_groups, excluded_tokens in MICROWAVE_SENSOR_SPECS:
        attribute = _find_raw_attribute(appliance, token_groups, excluded_tokens)
        if attribute is None:
            continue

        descriptions.append(
            WhirlpoolSensorDescription(
                key=f"microwave_{key}",
                translation_key=f"microwave_{key}",
                value_fn=_microwave_value_fn(
                    attribute,
                    key in {"cook_time", "time_remaining"},
                ),
            ),
        )
    return descriptions


def _raw_attribute_keys(appliance: Any) -> list[str]:
    """Return raw Whirlpool attribute keys from the fetched data payload."""
    attributes = getattr(appliance, "_data_dict", {}).get("attributes", {})
    if not isinstance(attributes, dict):
        return []
    return sorted(str(attribute) for attribute in attributes)


def _raw_attribute_value(appliance: Any, attribute: str) -> Any:
    """Return a raw Whirlpool attribute value."""
    try:
        value = getattr(appliance, "_get_attribute", lambda _: None)(attribute)
    except Exception:
        _LOGGER.warning(
            "Unable to read Whirlpool attribute %s; returning no value",
            attribute,
            exc_info=True,
        )
        return None
    if value == "":
        return None
    return value


def _microwave_value_fn(
    attribute: str,
    is_duration: bool,
) -> Callable[[Any], Any]:
    """Return a value function for a raw microwave attribute."""

    def value_fn(appliance: Any) -> Any:
        if is_duration:
            return _formatted_raw_duration_attribute(appliance, attribute)
        return _raw_attribute_value(appliance, attribute)

    return value_fn


def _oven_cook_time(appliance: Any, cavity: Any) -> str | None:
    """Return configured oven cook time, falling back to elapsed time."""
    configured = _raw_int_attribute(
        appliance,
        cavity_attribute(cavity, "TimeSetCookTimeSet"),
    )
    if configured is not None:
        return _format_duration_seconds(configured)
    if not has_callable(appliance, "get_cook_time"):
        return None
    return _format_duration_seconds(
        _safe_cavity_value(appliance, "get_cook_time", cavity),
    )


def _formatted_cavity_time(appliance: Any, cavity: Any, postfix: str) -> str | None:
    """Return a cavity duration attribute as formatted time."""
    return _formatted_raw_duration_attribute(
        appliance,
        cavity_attribute(cavity, postfix),
    )


def _cavity_raw_temperature(appliance: Any, cavity: Any, postfix: str) -> float | None:
    """Return a cavity temperature stored in tenths of a degree Celsius."""
    value = _raw_number_attribute(appliance, cavity_attribute(cavity, postfix))
    if value in (None, 0):
        return None
    return value / 10


def _formatted_raw_duration_attribute(appliance: Any, attribute: str) -> str | None:
    """Return a raw Whirlpool duration attribute as a formatted time string."""
    return _format_duration_seconds(_raw_int_attribute(appliance, attribute))


def _raw_int_attribute(appliance: Any, attribute: str) -> int | None:
    """Return a raw Whirlpool attribute value as an integer."""
    value = _raw_attribute_value(appliance, attribute)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _raw_number_attribute(appliance: Any, attribute: str) -> int | float | None:
    """Return a raw Whirlpool attribute value as a number."""
    value = _raw_attribute_value(appliance, attribute)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def _format_duration_seconds(value: Any) -> str | None:
    """Return seconds formatted as H:MM:SS or M:SS."""
    if value is None:
        return None
    try:
        total_seconds = int(value)
    except (TypeError, ValueError):
        return None
    if total_seconds < 0:
        return None

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _has_attribute(appliance: Any, attribute: str) -> bool:
    """Return true if an appliance reports a raw Whirlpool attribute."""
    return has_attribute(appliance, attribute)


def _first_existing_attribute(
    appliance: Any,
    attributes: tuple[str, ...],
) -> str | None:
    """Return the first attribute exposed by an appliance."""
    for attribute in attributes:
        if _has_attribute(appliance, attribute):
            return attribute
    return None


def _cavity_sensor_supported(appliance: Any, cavity: Any, key: str) -> bool:
    """Return true when a cavity sensor has a backing Whirlpool attribute."""
    optional_postfixes = {
        "cook_time_remaining": "TimeStatusCookTimeRemaining",
        "delay_time_remaining": "TimeStatusDelayTimeRemaining",
        "recipe_cook_time": "_RecipeSetFacadeCookTime",
        "recipe_temperature": "_RecipeSetFacadeDisplayTemp",
        "recipe_mode": "_RecipeSetFacadeMode",
    }
    suffix = str(key).removeprefix(f"{str(getattr(cavity, 'name', cavity)).lower()}_")
    postfix = optional_postfixes.get(suffix)
    return postfix is None or _has_attribute(
        appliance,
        cavity_attribute(cavity, postfix),
    )


def _should_expose_raw_attribute(attribute: str) -> bool:
    """Return true for raw attributes that identify microwave-like payloads."""
    tokens = _attribute_tokens(attribute)
    return any(keyword in tokens for keyword in RAW_ATTRIBUTE_KEYWORDS)


def _is_microwave_like(appliance: Any) -> bool:
    """Return true when a non-cavity appliance looks like a microwave."""
    info = getattr(appliance, "appliance_info", None)
    values = (
        getattr(appliance, "name", ""),
        getattr(info, "data_model", ""),
        getattr(info, "category", ""),
    )
    if any(
        "microwave" in str(value).lower() or "mwo" in str(value).lower()
        for value in values
    ):
        return True
    return any(
        _should_expose_raw_attribute(attribute)
        for attribute in _raw_attribute_keys(appliance)
    )


def _find_raw_attribute(
    appliance: Any,
    token_groups: tuple[tuple[str, ...], ...],
    excluded_tokens: tuple[str, ...],
) -> str | None:
    """Return the first raw attribute matching all tokens in a group."""
    for attribute in _raw_attribute_keys(appliance):
        tokens = _attribute_tokens(attribute)
        if any(token in tokens for token in excluded_tokens):
            continue
        if any(all(token in tokens for token in group) for group in token_groups):
            return attribute
    return None


def _attribute_tokens(attribute: str) -> set[str]:
    """Split Whirlpool's raw camel-case attribute names into tokens."""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", attribute.replace("_", " "))
    return set(re.findall(r"[a-z0-9]+", spaced.lower()))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Whirlpool Cooking sensors."""
    coordinator: WhirlpoolCookingCoordinator = entry.runtime_data
    entities: list[WhirlpoolCookingSensor] = []
    for appliance in coordinator.data:
        try:
            descriptions = _sensor_descriptions(appliance)
        except Exception:
            _LOGGER.warning(
                "Unable to build Whirlpool Cooking sensor entities for %s; "
                "skipping this appliance",
                appliance_label(appliance),
                exc_info=True,
            )
            continue
        entities.extend(
            WhirlpoolCookingSensor(coordinator, appliance, description)
            for description in descriptions
        )
    async_add_entities(entities)


class WhirlpoolCookingSensor(WhirlpoolCookingEntity, SensorEntity):
    """Whirlpool Cooking sensor."""

    entity_description: WhirlpoolSensorDescription

    def __init__(
        self,
        coordinator: WhirlpoolCookingCoordinator,
        appliance: Any,
        description: WhirlpoolSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            appliance,
            description.key,
            device_key=cavity_device_key(appliance, description.cavity),
            device_name=cavity_device_name(appliance, description.cavity),
        )
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the native value."""
        value = self.entity_description.value_fn(self.appliance)
        if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE:
            return temperature_from_celsius(self.coordinator.config_entry, value)
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE:
            return configured_temperature_unit(self.coordinator.config_entry)
        return self.entity_description.native_unit_of_measurement


def _safe_cavity_value(
    appliance: Any,
    method_name: str,
    cavity: Any,
    *,
    transform: Callable[[Any], Any] | None = None,
) -> Any:
    """Read a Whirlpool cavity method without raising into Home Assistant."""
    method = getattr(appliance, method_name, None)
    if not callable(method):
        return None
    try:
        value = method(cavity)
    except Exception:
        _LOGGER.warning(
            "Unable to read Whirlpool %s for %s; returning no value",
            method_name,
            appliance_label(appliance),
            exc_info=True,
        )
        return None
    return transform(value) if transform is not None else value


def _log_missing_method(appliance: Any, method_name: str, entity_key: str) -> None:
    """Log a skipped entity caused by a missing Whirlpool library method."""
    _LOGGER.warning(
        "Whirlpool appliance %s does not expose %s; skipping %s",
        appliance_label(appliance),
        method_name,
        entity_key,
    )

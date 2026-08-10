"""Sensor helper tests."""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Home Assistant test runtime requires Python 3.14",
)


def test_non_cavity_microwave_attributes_get_stable_sensor_descriptions() -> None:
    """Microwave-style cooking payloads should create stable sensors."""
    from custom_components.whirlpool_cooking.sensor import _sensor_descriptions

    class ApplianceInfo:
        data_model = "ddm_cooking_mhc76_v1"
        category = "cooking"

    class Appliance:
        appliance_info = ApplianceInfo()
        name = "microwave"
        _data_dict = {
            "attributes": {
                "CookCycleMode": {"value": "8"},
                "CookCycleStatusState": {"value": "3"},
                "CookCycleSetTime": {"value": "5999"},
                "CookCycleTimeRemaining": {"value": "30"},
                "WifiRssi": {"value": "-50"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def _get_attribute(self, attribute: str) -> str:
            return self._data_dict["attributes"][attribute]["value"]

    descriptions = _sensor_descriptions(Appliance())

    assert [description.key for description in descriptions] == [
        "microwave_state",
        "microwave_mode",
        "microwave_cook_time",
        "microwave_time_remaining",
    ]
    assert descriptions[0].value_fn(Appliance()) == "3"
    assert descriptions[2].value_fn(Appliance()) == "1:39:59"
    assert descriptions[3].value_fn(Appliance()) == "0:30"


def test_diagnostics_reads_nested_appliance_info() -> None:
    """Diagnostics should report model details stored by the library."""
    from custom_components.whirlpool_cooking.diagnostics import _describe_appliance

    class ApplianceInfo:
        data_model = "ddm_cooking_mhc76_v1"

    class Appliance:
        appliance_info = ApplianceInfo()
        _data_dict = {
            "attributes": {
                "CookCycleStatusState": {"value": "3"},
                "Serial": {"value": "secret"},
            },
        }

        @property
        def name(self) -> str:
            return "microwave"

    diagnostics = _describe_appliance(Appliance())

    assert diagnostics["data_model"] == "ddm_cooking_mhc76_v1"
    assert diagnostics["raw_attribute_keys"] == ["CookCycleStatusState"]


def test_oven_cavities_get_light_entities(monkeypatch) -> None:
    """Oven cavity light attributes should create light entities."""
    from custom_components.whirlpool_cooking.light import _light_descriptions

    class Cavity:
        Upper = type("Upper", (), {"name": "Upper"})()
        Lower = type("Lower", (), {"name": "Lower"})()

    import types

    oven_module = types.ModuleType("whirlpool.oven")
    oven_module.ATTR_POSTFIX_LIGHT_STATUS = "DisplaySetLightOn"
    oven_module.ATTR_POSTFIX_STATUS_STATE = "OpStatusState"
    oven_module.CAVITY_PREFIX_MAP = {
        Cavity.Upper: "OvenUpperCavity",
        Cavity.Lower: "OvenLowerCavity",
    }
    oven_module.Cavity = Cavity
    monkeypatch.setitem(sys.modules, "whirlpool.oven", oven_module)

    class Appliance:
        _data_dict = {
            "attributes": {
                "OvenUpperCavity_OpStatusState": {"value": "0"},
                "OvenUpperCavity_DisplaySetLightOn": {"value": "1"},
                "OvenLowerCavity_OpStatusState": {"value": "0"},
                "OvenLowerCavity_DisplaySetLightOn": {"value": "0"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def _get_attribute(self, attribute: str) -> str:
            return self._data_dict["attributes"][attribute]["value"]

        def get_oven_cavity_exists(self, cavity) -> bool:
            return True

        def get_light(self, cavity) -> bool:
            return cavity is Cavity.Upper

    descriptions = _light_descriptions(Appliance())

    assert [description.key for description in descriptions] == [
        "upper_light",
        "lower_light",
    ]
    assert descriptions[0].value_fn(Appliance()) is True


def test_multi_cavity_oven_gets_cavity_device_keys(monkeypatch) -> None:
    """Two-cavity ovens should expose cavity entities on child devices."""
    from custom_components.whirlpool_cooking.cavity import (
        cavity_device_key,
        cavity_device_name,
        default_cavity_device_key,
        default_cavity_device_name,
    )

    class Cavity:
        Upper = type("Upper", (), {"name": "Upper"})()
        Lower = type("Lower", (), {"name": "Lower"})()

    import types

    oven_module = types.ModuleType("whirlpool.oven")
    oven_module.ATTR_POSTFIX_STATUS_STATE = "OpStatusState"
    oven_module.CAVITY_PREFIX_MAP = {
        Cavity.Upper: "OvenUpperCavity",
        Cavity.Lower: "OvenLowerCavity",
    }
    oven_module.Cavity = Cavity
    monkeypatch.setitem(sys.modules, "whirlpool.oven", oven_module)

    class Appliance:
        _data_dict = {
            "attributes": {
                "OvenUpperCavity_OpStatusState": {"value": "0"},
                "OvenLowerCavity_OpStatusState": {"value": "0"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def _get_attribute(self, attribute: str) -> str:
            return self._data_dict["attributes"][attribute]["value"]

        def get_oven_cavity_exists(self, cavity) -> bool:
            return True

    appliance = Appliance()

    assert cavity_device_key(appliance, Cavity.Upper) == "upper"
    assert cavity_device_name(appliance, Cavity.Lower) == "Lower"
    assert default_cavity_device_key(appliance) == "upper"
    assert default_cavity_device_name(appliance) == "Upper"


def test_single_cavity_oven_stays_on_base_device(monkeypatch) -> None:
    """Single-cavity ovens should not create a separate cavity device."""
    from custom_components.whirlpool_cooking.cavity import cavity_device_key

    class Cavity:
        Upper = type("Upper", (), {"name": "Upper"})()
        Lower = type("Lower", (), {"name": "Lower"})()

    import types

    oven_module = types.ModuleType("whirlpool.oven")
    oven_module.ATTR_POSTFIX_STATUS_STATE = "OpStatusState"
    oven_module.CAVITY_PREFIX_MAP = {
        Cavity.Upper: "OvenUpperCavity",
        Cavity.Lower: "OvenLowerCavity",
    }
    oven_module.Cavity = Cavity
    monkeypatch.setitem(sys.modules, "whirlpool.oven", oven_module)

    class Appliance:
        _data_dict = {
            "attributes": {
                "OvenUpperCavity_OpStatusState": {"value": "0"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def get_oven_cavity_exists(self, cavity) -> bool:
            return cavity is Cavity.Upper

    assert cavity_device_key(Appliance(), Cavity.Upper) is None


def test_oven_cavities_get_cook_control_entities(monkeypatch) -> None:
    """Oven cavities should create cook mode, target temp, and start buttons."""
    from enum import Enum

    from custom_components.whirlpool_cooking.button import _button_descriptions
    from custom_components.whirlpool_cooking.cooking import cook_mode_attribute_value
    from custom_components.whirlpool_cooking.number import _number_descriptions
    from custom_components.whirlpool_cooking.select import _select_descriptions
    from custom_components.whirlpool_cooking.sensor import _sensor_descriptions

    class Cavity:
        Upper = type("Upper", (), {"name": "Upper"})()
        Lower = type("Lower", (), {"name": "Lower"})()

    import types

    class CookMode(Enum):
        Bake = 2
        ConvectBake = 6
        Broil = 8
        ConvectBroil = 9
        ConvectRoast = 16
        KeepWarm = 24
        AirFry = 41

    oven_module = types.ModuleType("whirlpool.oven")
    oven_module.ATTR_POSTFIX_COOK_MODE = "CycleSetCommonMode"
    oven_module.ATTR_POSTFIX_STATUS_STATE = "OpStatusState"
    oven_module.ATTR_POSTFIX_TARGET_TEMP = "CycleSetTargetTemp"
    oven_module.CAVITY_PREFIX_MAP = {
        Cavity.Upper: "OvenUpperCavity",
        Cavity.Lower: "OvenLowerCavity",
    }
    oven_module.Cavity = Cavity
    oven_module.CookMode = CookMode
    oven_module.COOK_MODE_MAP = {
        CookMode.Bake: "2",
        CookMode.ConvectBake: "6",
        CookMode.Broil: "8",
        CookMode.ConvectBroil: "9",
        CookMode.ConvectRoast: "16",
        CookMode.KeepWarm: "24",
        CookMode.AirFry: "41",
    }
    monkeypatch.setitem(sys.modules, "whirlpool.oven", oven_module)

    class Appliance:
        _data_dict = {
            "attributes": {
                "OvenUpperCavity_OpStatusState": {"value": "0"},
                "OvenUpperCavity_CycleSetCommonMode": {"value": "2"},
                "OvenUpperCavity_CycleSetTargetTemp": {"value": "1750"},
                "OvenUpperCavity_TimeSetCookTimeSet": {"value": "3600"},
                "OvenLowerCavity_OpStatusState": {"value": "0"},
                "OvenLowerCavity_CycleSetCommonMode": {"value": "2"},
                "OvenLowerCavity_CycleSetTargetTemp": {"value": "1750"},
                "OvenLowerCavity_TimeSetCookTimeSet": {"value": "2700"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def _get_attribute(self, attribute: str) -> str:
            return self._data_dict["attributes"][attribute]["value"]

        def get_oven_cavity_exists(self, cavity) -> bool:
            return True

        def get_cook_mode(self, cavity):
            return CookMode.Bake

        def get_target_temp(self, cavity) -> float:
            return 175

        def get_cook_time(self, cavity) -> int:
            return 0

        def get_supported_cook_modes(self, cavity):
            if cavity is Cavity.Upper:
                return (CookMode.Bake, CookMode.Broil)
            return (CookMode.Bake, CookMode.ConvectBake, CookMode.KeepWarm)

    appliance = Appliance()

    assert [description.key for description in _select_descriptions(appliance)] == [
        "upper_cook_mode_control",
        "lower_cook_mode_control",
    ]
    assert [description.key for description in _number_descriptions(appliance)] == [
        "upper_target_temperature_control",
        "lower_target_temperature_control",
    ]
    cook_time_description = _sensor_descriptions(appliance)[4]
    assert cook_time_description.key == "upper_cook_time"
    assert cook_time_description.device_class is None
    assert cook_time_description.native_unit_of_measurement is None
    assert cook_time_description.value_fn(appliance) == "1:00:00"
    assert _select_descriptions(appliance)[0].options == [
        "Bake",
        "Broil",
    ]
    assert _select_descriptions(appliance)[1].options == [
        "Bake",
        "Convect Bake",
        "Keep Warm",
    ]
    assert _select_descriptions(appliance)[0].current_fn(appliance) == "Bake"
    assert "upper_start_cook" in [
        description.key for description in _button_descriptions(appliance)
    ]
    assert cook_mode_attribute_value("air_fry") == "41"
    assert cook_mode_attribute_value("Air Fry") == "41"


def test_cook_mode_options_use_capability_payload(monkeypatch) -> None:
    """Cook mode options should narrow from structured capability attributes."""
    from enum import Enum

    from custom_components.whirlpool_cooking.cooking import supported_cook_mode_options

    class Cavity:
        Upper = type("Upper", (), {"name": "Upper"})()

    import types

    class CookMode(Enum):
        Bake = 2
        Broil = 8
        AirFry = 41

    oven_module = types.ModuleType("whirlpool.oven")
    oven_module.CookMode = CookMode
    oven_module.COOK_MODE_MAP = {
        CookMode.Bake: "2",
        CookMode.Broil: "8",
        CookMode.AirFry: "41",
    }
    monkeypatch.setitem(sys.modules, "whirlpool.oven", oven_module)

    class Appliance:
        _data_dict = {
            "attributes": {
                "Relational_CapabilityModeTemperatures": {
                    "value": (
                        '[{"CycleSetCommonMode": "2"}, '
                        '{"cookModeId": 8}, {"mode": "41"}]'
                    ),
                },
            },
        }

        def get_cook_mode(self, cavity):
            return CookMode.Bake

    assert supported_cook_mode_options(Appliance(), Cavity.Upper) == [
        "Air Fry",
        "Bake",
        "Broil",
    ]


def test_microwave_gets_hood_light_and_fan_entities() -> None:
    """Microwave hood attributes should create light and fan entities."""
    from custom_components.whirlpool_cooking.fan import (
        ATTR_HOOD_FAN_SPEED,
        _speed_for_percentage,
        _speed_value,
    )
    from custom_components.whirlpool_cooking.light import (
        _brightness_for_level,
        _level_for_brightness,
        _light_descriptions,
    )

    class Appliance:
        _data_dict = {
            "attributes": {
                "Hood_OperationSetSurfaceLight": {"value": "2"},
                "Hood_OperationSetExhaustFanSpeed": {"value": "4"},
                "Mwo_DisplaySetLightOn": {"value": "0"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def _get_attribute(self, attribute: str) -> str:
            return self._data_dict["attributes"][attribute]["value"]

    appliance = Appliance()
    light_descriptions = _light_descriptions(appliance)

    assert [description.key for description in light_descriptions] == [
        "microwave_light",
        "hood_light",
    ]
    assert light_descriptions[1].value_fn(appliance) is True
    assert light_descriptions[1].brightness_fn(appliance) == 255
    assert _brightness_for_level(1, 2) == 128
    assert _level_for_brightness(128, 2) == 1
    assert _level_for_brightness(255, 2) == 2
    assert ATTR_HOOD_FAN_SPEED in appliance._data_dict["attributes"]
    assert _speed_value(appliance) == 4
    assert _speed_for_percentage(50) == "3"
    assert _speed_for_percentage(100) == "6"


def test_start_cook_uses_pending_ha_controls(monkeypatch) -> None:
    """Start cook should not overwrite a just-set target temperature."""
    import asyncio
    from enum import Enum

    from custom_components.whirlpool_cooking.button import _async_start_cook
    from custom_components.whirlpool_cooking.cooking import (
        set_pending_cook_mode_option,
        set_pending_target_temperature,
    )

    class Cavity:
        Upper = type("Upper", (), {"name": "Upper"})()

    class CookMode(Enum):
        Bake = 2

    import types

    oven_module = types.ModuleType("whirlpool.oven")
    oven_module.CookMode = CookMode
    monkeypatch.setitem(sys.modules, "whirlpool.oven", oven_module)

    class Appliance:
        sent = None

        def get_cook_mode(self, cavity):
            return CookMode.Bake

        def get_target_temp(self, cavity) -> float:
            return 175

        async def set_cook(self, target_temp, mode, cavity):
            self.sent = (target_temp, mode, cavity)
            return True

    class Coordinator:
        async def async_request_refresh(self) -> None:
            return None

    appliance = Appliance()
    set_pending_cook_mode_option(appliance, Cavity.Upper, "Bake")
    set_pending_target_temperature(appliance, Cavity.Upper, 204.4)

    result = asyncio.run(_async_start_cook(appliance, Coordinator(), Cavity.Upper))

    assert result is True
    assert appliance.sent == (204.4, CookMode.Bake, Cavity.Upper)

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
        "wifi_rssi",
        "microwave_state",
        "microwave_mode",
        "microwave_cook_time",
        "microwave_time_remaining",
    ]
    assert descriptions[0].value_fn(Appliance()) == -50
    assert descriptions[1].value_fn(Appliance()) == "3"
    assert descriptions[3].value_fn(Appliance()) == "1:39:59"
    assert descriptions[4].value_fn(Appliance()) == "0:30"


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

        async def set_light(self, on, cavity) -> bool:
            return True

    descriptions = _light_descriptions(Appliance())

    assert [description.key for description in descriptions] == [
        "upper_light",
        "lower_light",
    ]
    assert descriptions[0].value_fn(Appliance()) is True


def test_oven_cavities_get_door_lock_entities(monkeypatch) -> None:
    """Oven cavity door lock attributes should create binary sensors."""
    from custom_components.whirlpool_cooking.binary_sensor import (
        _cavity_binary_sensor_descriptions,
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
                "OvenUpperCavity_OpStatusDoorLocked": {"value": "1"},
                "OvenLowerCavity_OpStatusState": {"value": "0"},
                "OvenLowerCavity_OpStatusDoorLocked": {"value": "0"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def _get_attribute(self, attribute: str) -> str:
            return self._data_dict["attributes"][attribute]["value"]

        def get_oven_cavity_exists(self, cavity) -> bool:
            return True

        def get_door_opened(self, cavity) -> bool:
            return False

    descriptions = _cavity_binary_sensor_descriptions(Appliance())

    assert [description.key for description in descriptions] == [
        "upper_door",
        "upper_door_locked",
        "lower_door",
        "lower_door_locked",
    ]
    assert descriptions[1].value_fn(Appliance()) is True


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
                "OvenUpperCavity_TimeStatusCookTimeRemaining": {"value": "120"},
                "OvenUpperCavity_TimeStatusDelayTimeRemaining": {"value": "30"},
                "OvenUpperCavity__RecipeSetFacadeCookTime": {"value": "5400"},
                "OvenUpperCavity__RecipeSetFacadeDisplayTemp": {"value": "1770"},
                "OvenUpperCavity__RecipeSetFacadeMode": {"value": "2"},
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

        def get_cavity_state(self, cavity):
            return "Idle"

        def get_cook_mode(self, cavity):
            return CookMode.Bake

        def get_temp(self, cavity) -> float:
            return 177

        def get_target_temp(self, cavity) -> float:
            return 175

        def get_cook_time(self, cavity) -> int:
            return 0

        def get_supported_cook_modes(self, cavity):
            if cavity is Cavity.Upper:
                return (CookMode.Bake, CookMode.Broil)
            return (CookMode.Bake, CookMode.ConvectBake, CookMode.KeepWarm)

        async def send_attributes(self, attributes) -> bool:
            return True

        async def set_cook(self, target_temp, mode, cavity) -> bool:
            return True

        async def stop_cook(self, cavity) -> bool:
            return True

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
    assert [
        description.key for description in _sensor_descriptions(appliance)[:10]
    ] == [
        "upper_state",
        "upper_mode",
        "upper_temperature",
        "upper_target_temperature",
        "upper_cook_time",
        "upper_cook_time_remaining",
        "upper_delay_time_remaining",
        "upper_recipe_cook_time",
        "upper_recipe_temperature",
        "upper_recipe_mode",
    ]
    assert _sensor_descriptions(appliance)[5].value_fn(appliance) == "2:00"
    assert _sensor_descriptions(appliance)[7].value_fn(appliance) == "1:30:00"
    assert _sensor_descriptions(appliance)[8].value_fn(appliance) == 177
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


def test_cook_mode_select_defaults_to_bake_when_current_mode_is_unknown(
    monkeypatch,
) -> None:
    """Cook mode controls should not show HA's unknown state by default."""
    from enum import Enum

    from custom_components.whirlpool_cooking.select import _select_descriptions

    class Cavity:
        Upper = type("Upper", (), {"name": "Upper"})()
        Lower = type("Lower", (), {"name": "Lower"})()

    import types

    class CookMode(Enum):
        Unknown = 0
        Bake = 2
        Broil = 8

    oven_module = types.ModuleType("whirlpool.oven")
    oven_module.ATTR_POSTFIX_COOK_MODE = "CycleSetCommonMode"
    oven_module.ATTR_POSTFIX_STATUS_STATE = "OpStatusState"
    oven_module.CAVITY_PREFIX_MAP = {
        Cavity.Upper: "OvenUpperCavity",
        Cavity.Lower: "OvenLowerCavity",
    }
    oven_module.Cavity = Cavity
    oven_module.CookMode = CookMode
    oven_module.COOK_MODE_MAP = {
        CookMode.Bake: "2",
        CookMode.Broil: "8",
    }
    monkeypatch.setitem(sys.modules, "whirlpool.oven", oven_module)

    class Appliance:
        _data_dict = {
            "attributes": {
                "OvenUpperCavity_OpStatusState": {"value": "0"},
                "OvenUpperCavity_CycleSetCommonMode": {"value": "0"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def get_oven_cavity_exists(self, cavity) -> bool:
            return True

        def get_cook_mode(self, cavity):
            return CookMode.Unknown

        def get_supported_cook_modes(self, cavity):
            return (CookMode.Bake, CookMode.Broil)

        async def send_attributes(self, attributes) -> bool:
            return True

    description = _select_descriptions(Appliance())[0]

    assert description.options == ["Bake", "Broil"]
    assert description.current_fn(Appliance()) == "Bake"


def test_microwave_gets_hood_light_and_fan_entities() -> None:
    """Microwave hood attributes should create light and fan entities."""
    import asyncio

    from custom_components.whirlpool_cooking.fan import (
        ATTR_HOOD_FAN_SPEED,
        PRESET_MODE_TO_SPEED,
        SPEED_TO_PRESET_MODE,
        _speed_for_percentage,
        _speed_value,
    )
    from custom_components.whirlpool_cooking.light import (
        _brightness_for_level,
        _level_for_brightness,
        _light_descriptions,
    )
    from custom_components.whirlpool_cooking.select import _select_descriptions

    class Appliance:
        sent = None
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

        async def send_attributes(self, attributes) -> bool:
            self.sent = attributes
            return True

    appliance = Appliance()
    light_descriptions = _light_descriptions(appliance)
    select_descriptions = _select_descriptions(appliance)

    assert [description.key for description in light_descriptions] == [
        "microwave_light",
        "hood_light",
    ]
    assert [description.key for description in select_descriptions] == [
        "hood_fan_mode",
    ]
    assert select_descriptions[0].options == [
        "Off",
        "Low",
        "Medium",
        "Medium-high",
        "High",
    ]
    assert select_descriptions[0].current_fn(appliance) == "Medium"
    assert light_descriptions[1].value_fn(appliance) is True
    assert light_descriptions[1].brightness_fn(appliance) == 128
    assert _brightness_for_level(1, 2) == 128
    assert _level_for_brightness(128, 2) == 1
    assert _level_for_brightness(255, 2) == 2
    assert _brightness_for_level(2, 2, high_level=1) == 128
    assert _brightness_for_level(4, 2, high_level=4) == 255
    assert _level_for_brightness(128, 2, high_level=4) == 2
    assert _level_for_brightness(255, 2, high_level=4) == 4

    asyncio.run(light_descriptions[1].set_fn(appliance, True))
    assert appliance.sent == {"Hood_OperationSetSurfaceLight": "4"}
    asyncio.run(light_descriptions[1].set_brightness_fn(appliance, 128))
    assert appliance.sent == {"Hood_OperationSetSurfaceLight": "2"}
    assert ATTR_HOOD_FAN_SPEED in appliance._data_dict["attributes"]
    assert _speed_value(appliance) == 4
    assert SPEED_TO_PRESET_MODE[4] == "Medium"
    assert PRESET_MODE_TO_SPEED["Low"] == "2"
    assert PRESET_MODE_TO_SPEED["Medium-high"] == "5"
    assert PRESET_MODE_TO_SPEED["High"] == "6"
    assert _speed_for_percentage(50) == "4"
    assert _speed_for_percentage(100) == "6"

    asyncio.run(select_descriptions[0].select_fn(appliance, "Medium"))
    assert appliance.sent == {ATTR_HOOD_FAN_SPEED: "4"}
    asyncio.run(select_descriptions[0].select_fn(appliance, "Medium-high"))
    assert appliance.sent == {ATTR_HOOD_FAN_SPEED: "5"}
    asyncio.run(select_descriptions[0].select_fn(appliance, "High"))
    assert appliance.sent == {ATTR_HOOD_FAN_SPEED: "6"}
    asyncio.run(select_descriptions[0].select_fn(appliance, "Off"))
    assert appliance.sent == {ATTR_HOOD_FAN_SPEED: "0"}


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


def test_missing_library_methods_skip_entities_and_log(
    monkeypatch,
    caplog,
) -> None:
    """Raw attributes without matching library APIs should not create entities."""
    import logging
    import types

    from custom_components.whirlpool_cooking.binary_sensor import (
        _cavity_binary_sensor_descriptions,
    )
    from custom_components.whirlpool_cooking.button import _button_descriptions
    from custom_components.whirlpool_cooking.fan import _hood_fan_supported
    from custom_components.whirlpool_cooking.light import _light_descriptions
    from custom_components.whirlpool_cooking.number import _number_descriptions
    from custom_components.whirlpool_cooking.select import _select_descriptions
    from custom_components.whirlpool_cooking.sensor import _sensor_descriptions
    from custom_components.whirlpool_cooking.switch import _switch_descriptions

    class Cavity:
        Upper = type("Upper", (), {"name": "Upper"})()
        Lower = type("Lower", (), {"name": "Lower"})()

    oven_module = types.ModuleType("whirlpool.oven")
    oven_module.ATTR_POSTFIX_COOK_MODE = "CycleSetCommonMode"
    oven_module.ATTR_POSTFIX_LIGHT_STATUS = "DisplaySetLightOn"
    oven_module.ATTR_POSTFIX_STATUS_STATE = "OpStatusState"
    oven_module.ATTR_POSTFIX_TARGET_TEMP = "CycleSetTargetTemp"
    oven_module.CAVITY_PREFIX_MAP = {
        Cavity.Upper: "OvenUpperCavity",
        Cavity.Lower: "OvenLowerCavity",
    }
    oven_module.Cavity = Cavity
    monkeypatch.setitem(sys.modules, "whirlpool.oven", oven_module)

    class Appliance:
        name = "Kitchen Oven"
        _data_dict = {
            "attributes": {
                "OvenUpperCavity_OpStatusState": {"value": "0"},
                "OvenUpperCavity_CycleSetCommonMode": {"value": "2"},
                "OvenUpperCavity_CycleSetTargetTemp": {"value": "1750"},
                "OvenUpperCavity_DisplaySetLightOn": {"value": "1"},
                "OvenUpperCavity_OpStatusDoorLocked": {"value": "0"},
                "Hood_OperationSetExhaustFanSpeed": {"value": "3"},
                "Sys_OperationSetControlLock": {"value": "0"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def _get_attribute(self, attribute: str) -> str:
            return self._data_dict["attributes"][attribute]["value"]

        def get_oven_cavity_exists(self, cavity) -> bool:
            return cavity is Cavity.Upper

    appliance = Appliance()

    caplog.set_level(logging.DEBUG)

    assert _sensor_descriptions(appliance) == []
    assert [
        description.key
        for description in _cavity_binary_sensor_descriptions(appliance)
    ] == ["upper_door_locked"]
    assert _light_descriptions(appliance) == []
    assert _select_descriptions(appliance) == []
    assert _number_descriptions(appliance) == []
    assert [description.key for description in _button_descriptions(appliance)] == [
        "refresh",
    ]
    assert _switch_descriptions(appliance) == []
    assert _hood_fan_supported(appliance) is False
    assert "does not expose get_cavity_state" in caplog.text


def test_sensor_setup_skips_bad_appliance_and_adds_supported_entities() -> None:
    """A bad appliance should not prevent supported entities from loading."""
    import asyncio

    from custom_components.whirlpool_cooking.sensor import async_setup_entry

    class BadAppliance:
        name = "Bad payload"

        def has_attribute(self, attribute: str) -> bool:
            raise RuntimeError("broken has_attribute")

    class ApplianceInfo:
        data_model = "ddm_cooking_mhc76_v1"
        category = "cooking"

    class GoodAppliance:
        appliance_info = ApplianceInfo()
        name = "Good microwave"
        _data_dict = {
            "attributes": {
                "CookCycleStatusState": {"value": "3"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def _get_attribute(self, attribute: str) -> str:
            return self._data_dict["attributes"][attribute]["value"]

    class Coordinator:
        data = [BadAppliance(), GoodAppliance()]

    class Entry:
        runtime_data = Coordinator()

    entities = []

    def async_add_entities(new_entities) -> None:
        entities.extend(new_entities)

    asyncio.run(async_setup_entry(None, Entry(), async_add_entities))

    assert [entity.entity_description.key for entity in entities] == [
        "microwave_state",
    ]

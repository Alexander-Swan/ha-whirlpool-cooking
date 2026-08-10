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
                "CookCycleSetTime": {"value": "60"},
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

        def get_oven_cavity_exists(self, cavity) -> bool:
            return True

    appliance = Appliance()

    assert cavity_device_key(appliance, Cavity.Upper) == "upper"
    assert cavity_device_name(appliance, Cavity.Lower) == "Lower"


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


def test_microwave_gets_hood_light_and_fan_entities() -> None:
    """Microwave hood attributes should create light and fan entities."""
    from custom_components.whirlpool_cooking.fan import (
        ATTR_HOOD_FAN_SPEED,
        _speed_value,
    )
    from custom_components.whirlpool_cooking.light import _light_descriptions

    class Appliance:
        _data_dict = {
            "attributes": {
                "Hood_OperationSetSurfaceLight": {"value": "1"},
                "Hood_OperationSetExhaustFanSpeed": {"value": "2"},
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
    assert ATTR_HOOD_FAN_SPEED in appliance._data_dict["attributes"]
    assert _speed_value(appliance) == 2

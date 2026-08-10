"""Sensor helper tests."""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Home Assistant test runtime requires Python 3.14",
)


def test_non_cavity_raw_attributes_get_sensor_descriptions() -> None:
    """Microwave-style cooking payloads should still create useful sensors."""
    from custom_components.whirlpool_cooking.sensor import _sensor_descriptions

    class Appliance:
        _data_dict = {
            "attributes": {
                "CookCycleStatusState": {"value": "3"},
                "CookCycleSetTime": {"value": "60"},
                "WifiRssi": {"value": "-50"},
            },
        }

        def has_attribute(self, attribute: str) -> bool:
            return attribute in self._data_dict["attributes"]

        def _get_attribute(self, attribute: str) -> str:
            return self._data_dict["attributes"][attribute]["value"]

    descriptions = _sensor_descriptions(Appliance())

    assert [description.key for description in descriptions] == [
        "raw_cookcyclestatusstate",
        "raw_cookcyclesettime",
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

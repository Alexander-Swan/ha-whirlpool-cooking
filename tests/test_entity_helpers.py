"""Entity helper tests."""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Home Assistant test runtime requires Python 3.14",
)


class FakeAppliance:
    """Fake appliance with mixed attribute shapes."""

    model = "W123"

    def name(self) -> str:
        """Return a zero-argument callable value."""
        return "Wall Oven"

    def state(self, cavity: str) -> str:
        """Represent a library method requiring arguments."""
        return cavity


def test_entity_value_reads_mappings_attributes_and_zero_arg_callables() -> None:
    """Test generic entity value extraction."""
    from custom_components.whirlpool_cooking.entity import _value

    appliance = FakeAppliance()

    assert _value({"name": "Kitchen Oven"}, "name") == "Kitchen Oven"
    assert _value(appliance, "model") == "W123"
    assert _value(appliance, "name") == "Wall Oven"


def test_entity_value_returns_default_for_callables_requiring_args() -> None:
    """Test methods requiring arguments do not crash entity updates."""
    from custom_components.whirlpool_cooking.entity import _value

    assert _value(FakeAppliance(), "state", default="unknown") == "unknown"


def test_diagnostics_read_handles_callables_requiring_args() -> None:
    """Test diagnostics do not crash on callable library methods."""
    from custom_components.whirlpool_cooking.diagnostics import _read

    assert _read(FakeAppliance(), "state") is None


def test_temperature_helpers_convert_configured_units() -> None:
    """Test configured temperature unit conversion."""
    from custom_components.whirlpool_cooking.const import (
        CONF_TEMPERATURE_UNIT,
        TEMP_UNIT_FAHRENHEIT,
    )
    from custom_components.whirlpool_cooking.temperature import (
        temperature_from_celsius,
        temperature_to_celsius,
    )

    class Entry:
        options = {CONF_TEMPERATURE_UNIT: TEMP_UNIT_FAHRENHEIT}

    assert temperature_from_celsius(Entry(), 100) == 212
    assert round(temperature_to_celsius(Entry(), 350), 1) == 176.7

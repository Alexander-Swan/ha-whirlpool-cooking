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


def test_entity_availability_uses_online_state() -> None:
    """Test entity availability follows the appliance online state."""
    from custom_components.whirlpool_cooking.entity import WhirlpoolCookingEntity

    class Appliance:
        def __init__(self, online) -> None:
            self._online = online

        def get_online(self):
            return self._online

    assert WhirlpoolCookingEntity._appliance_available(Appliance(True)) is True
    assert WhirlpoolCookingEntity._appliance_available(Appliance(False)) is False
    assert WhirlpoolCookingEntity._appliance_available(Appliance(None)) is False
    assert WhirlpoolCookingEntity._appliance_available(Appliance("0")) is False


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


def test_service_lookup_matches_child_cavity_device_identifiers() -> None:
    """Test services can resolve child cavity device identifiers to appliances."""
    from custom_components.whirlpool_cooking.services import (
        _appliance_matches_identifier,
    )

    class Appliance:
        said = "SAID123"

    appliance = Appliance()

    assert _appliance_matches_identifier(appliance, "SAID123") is True
    assert _appliance_matches_identifier(appliance, "SAID123_upper") is True
    assert _appliance_matches_identifier(appliance, "SAID123_lower") is True
    assert _appliance_matches_identifier(appliance, "OTHER_upper") is False

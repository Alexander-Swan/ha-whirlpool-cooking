"""Import smoke tests for the integration modules."""

from __future__ import annotations

from importlib import import_module
import sys

import pytest


MODULES = (
    "custom_components.whirlpool_cooking",
    "custom_components.whirlpool_cooking.binary_sensor",
    "custom_components.whirlpool_cooking.button",
    "custom_components.whirlpool_cooking.config_flow",
    "custom_components.whirlpool_cooking.const",
    "custom_components.whirlpool_cooking.coordinator",
    "custom_components.whirlpool_cooking.diagnostics",
    "custom_components.whirlpool_cooking.entity",
    "custom_components.whirlpool_cooking.sensor",
)


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="integration uses Python 3.12 type alias syntax",
)
@pytest.mark.parametrize("module", MODULES)
def test_integration_modules_import(module: str) -> None:
    """Verify integration modules can be imported in a HA-capable environment."""
    pytest.importorskip("homeassistant")

    import_module(module)

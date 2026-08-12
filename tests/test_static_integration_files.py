"""Static integration file checks."""

from __future__ import annotations

from pathlib import Path

INTEGRATION_PATH = Path("custom_components/whirlpool_cooking")


def test_temperature_unit_uses_home_assistant_constant() -> None:
    """Guard against mojibake in the temperature unit."""
    sensor_source = (INTEGRATION_PATH / "sensor.py").read_text()

    assert "UnitOfTemperature.CELSIUS" in sensor_source
    assert "SensorDeviceClass.TEMPERATURE" in sensor_source
    assert "\u00c2\u00b0F" not in sensor_source


def test_refresh_button_is_diagnostic() -> None:
    """The refresh button should be grouped with diagnostic entities."""
    button_source = (INTEGRATION_PATH / "button.py").read_text()

    assert "EntityCategory.DIAGNOSTIC" in button_source


def test_services_file_matches_registered_services() -> None:
    """The integration should register services advertised in services.yaml."""
    init_source = (INTEGRATION_PATH / "__init__.py").read_text()
    services_source = (INTEGRATION_PATH / "services.py").read_text()
    services_yaml = (INTEGRATION_PATH / "services.yaml").read_text()

    assert "async_setup_services" in init_source
    assert "SERVICE_SET_COOK" in services_source
    assert "SERVICE_STOP_COOK" in services_source
    assert "set_cook:" in services_yaml
    assert "stop_cook:" in services_yaml


def test_release_workflow_validates_manifest_version() -> None:
    """Release workflow should only tag versions already in manifest.json."""
    workflow = Path(".github/workflows/release.yml").read_text()

    assert "workflow_dispatch:" in workflow
    assert "scripts/check_version.py" in workflow
    assert 'git tag "v${{ inputs.version }}"' in workflow
    assert 'gh release create "v${{ inputs.version }}"' in workflow


def test_hacs_validation_workflow_exists() -> None:
    """HACS publish docs recommend validating the repository with hacs/action."""
    workflow = Path(".github/workflows/validate.yml").read_text()

    assert "hacs/action@main" in workflow
    assert "category: integration" in workflow


def test_brand_icon_exists() -> None:
    """HACS publish docs require repository brand assets."""
    assert Path("brand/icon.png").is_file()

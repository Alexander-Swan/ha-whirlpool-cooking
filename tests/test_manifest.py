"""Manifest tests."""

from __future__ import annotations

import json
from pathlib import Path


def test_manifest_is_hacs_ready() -> None:
    """Verify required HACS manifest fields."""
    manifest = json.loads(
        Path("custom_components/whirlpool_cooking/manifest.json").read_text(),
    )

    assert manifest["domain"] == "whirlpool_cooking"
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_push"
    assert "whirlpool-sixth-sense" in manifest["requirements"][0]

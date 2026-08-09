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
    assert manifest["iot_class"] == "cloud_polling"
    assert "whirlpool-sixth-sense" in manifest["requirements"][0]


def test_manifest_urls_are_not_placeholders() -> None:
    """Verify user-facing manifest links point at the real repository."""
    manifest = json.loads(
        Path("custom_components/whirlpool_cooking/manifest.json").read_text(),
    )

    assert "your-user" not in manifest["documentation"]
    assert "your-user" not in manifest["issue_tracker"]

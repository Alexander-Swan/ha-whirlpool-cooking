"""Manifest tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$",
)


def test_manifest_is_hacs_ready() -> None:
    """Verify required HACS manifest fields."""
    manifest = json.loads(
        Path("custom_components/whirlpool_cooking/manifest.json").read_text(),
    )

    assert manifest["domain"] == "whirlpool_cooking"
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"
    assert manifest["codeowners"] == ["@Alexander-Swan"]
    assert "whirlpool-sixth-sense" in manifest["requirements"][0]
    assert SEMVER_RE.fullmatch(manifest["version"])


def test_manifest_urls_are_not_placeholders() -> None:
    """Verify user-facing manifest links point at the real repository."""
    manifest = json.loads(
        Path("custom_components/whirlpool_cooking/manifest.json").read_text(),
    )

    assert "your-user" not in manifest["documentation"]
    assert "your-user" not in manifest["issue_tracker"]


def test_project_version_matches_manifest() -> None:
    """Keep the release version consistent across project metadata."""
    manifest = json.loads(
        Path("custom_components/whirlpool_cooking/manifest.json").read_text(),
    )
    pyproject = Path("pyproject.toml").read_text()

    assert f'version = "{manifest["version"]}"' in pyproject


def test_hacs_metadata_is_present() -> None:
    """Verify the root HACS metadata stays available for custom repository use."""
    hacs = json.loads(Path("hacs.json").read_text())

    assert hacs["name"] == "Whirlpool Cooking"
    assert hacs["content_in_root"] is False
    assert hacs["render_readme"] is True

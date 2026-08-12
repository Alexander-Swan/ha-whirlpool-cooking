"""Validate the integration version before creating a release."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "custom_components" / "whirlpool_cooking" / "manifest.json"
PYPROJECT_PATH = ROOT / "pyproject.toml"

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$",
)


def _normalize(version: str) -> str:
    return version.removeprefix("v")


def _load_manifest_version() -> str:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return str(manifest["version"])


def _load_project_version() -> str:
    project = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    return str(project["project"]["version"])


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/check_version.py <version>")
        return 2

    requested = _normalize(sys.argv[1])
    if not SEMVER_RE.fullmatch(requested):
        print(f"Invalid version: {sys.argv[1]}")
        print("Use semantic versioning, for example 0.2.0 or 0.2.0-beta.1.")
        return 2

    manifest_version = _load_manifest_version()
    project_version = _load_project_version()

    if manifest_version != requested:
        print(
            f"Manifest version {manifest_version} does not match requested "
            f"version {requested}.",
        )
        return 1

    if project_version != requested:
        print(
            f"pyproject version {project_version} does not match requested "
            f"version {requested}.",
        )
        return 1

    print(f"Version {requested} is ready to release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

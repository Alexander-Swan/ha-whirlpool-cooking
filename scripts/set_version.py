"""Set the project version in files used by Home Assistant and tooling."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from check_version import SEMVER_RE

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "custom_components" / "whirlpool_cooking" / "manifest.json"
PYPROJECT_PATH = ROOT / "pyproject.toml"


def _normalize(version: str) -> str:
    return version.removeprefix("v")


def _update_manifest(version: str) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["version"] = version
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _update_pyproject(version: str) -> None:
    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
    pyproject = re.sub(
        r'(?m)^version = "[^"]+"$',
        f'version = "{version}"',
        pyproject,
        count=1,
    )
    PYPROJECT_PATH.write_text(pyproject, encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/set_version.py <version>")
        return 2

    version = _normalize(sys.argv[1])
    if not SEMVER_RE.fullmatch(version):
        print(f"Invalid version: {sys.argv[1]}")
        print("Use semantic versioning, for example 0.2.0 or 0.2.0-beta.1.")
        return 2

    _update_manifest(version)
    _update_pyproject(version)
    print(f"Set version to {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

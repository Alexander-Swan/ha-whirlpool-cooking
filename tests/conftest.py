"""Pytest configuration."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CUSTOM_COMPONENTS = ROOT / "custom_components"
CUSTOM_COMPONENTS_INIT = CUSTOM_COMPONENTS / "__init__.py"

spec = importlib.util.spec_from_file_location(
    "custom_components",
    CUSTOM_COMPONENTS_INIT,
    submodule_search_locations=[str(CUSTOM_COMPONENTS)],
)
if spec is not None and spec.loader is not None:
    module = importlib.util.module_from_spec(spec)
    sys.modules["custom_components"] = module
    spec.loader.exec_module(module)

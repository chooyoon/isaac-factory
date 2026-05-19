"""Test configuration for scene-integrity tests.

Adds the asset_validator extension package to sys.path so tests can
`from asset_validator import …` without an editable install. These tests
run in the `research` profile (conda env_isaaclab) — pure Python, no
pxr / omni / isaacsim imports anywhere.

Scope distinction:
  - tests/scene_integrity/  (here): scene-level integration tests, one
    file per validator. Each test composes a representative multi-prim
    scene and asserts the validator's behaviour against it.
  - isaac_factory/extensions/asset_validator/tests/unit/: per-validator
    unit tests covering every edge case in isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path


# /home/cap2/last/tests/scene_integrity/conftest.py
#   parents[0] = scene_integrity
#   parents[1] = tests
#   parents[2] = last  (workspace root)
_EXT_ROOT = Path(__file__).resolve().parents[2] / "isaac_factory" / "extensions" / "asset_validator"
if str(_EXT_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXT_ROOT))

"""Test configuration for the cell_01 sprint test suite.

Adds the ``cell_authoring`` and ``asset_validator`` extension packages to
``sys.path`` so tests can import them without an editable install. These
tests run in Runtime A (conda env_isaaclab, Python 3.10) — pure pxr +
pyyaml, no Kit / no PhysX.
"""

from __future__ import annotations

import sys
from pathlib import Path


# /home/cap2/last/tests/cell_01/conftest.py
#   parents[0] = cell_01
#   parents[1] = tests
#   parents[2] = last  (workspace root)
_WORKSPACE = Path(__file__).resolve().parents[2]
_EXTS = (
    _WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring",
    _WORKSPACE / "isaac_factory" / "extensions" / "asset_validator",
)
for ext in _EXTS:
    if str(ext) not in sys.path:
        sys.path.insert(0, str(ext))

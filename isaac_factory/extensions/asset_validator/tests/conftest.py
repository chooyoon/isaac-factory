"""Test configuration for asset_validator unit tests.

These tests are pure Python — they import nothing from `pxr`, `omni`, or
`isaacsim`. They can run in:

  - the `research` profile (conda env_isaaclab, Python 3.10), or
  - any Python 3.10+ environment where `pytest` is installed.

The package is added to sys.path by walking two directories up from this
file, so tests work without an editable install.
"""

from __future__ import annotations

import sys
from pathlib import Path


_EXT_ROOT = Path(__file__).resolve().parents[1]
if str(_EXT_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXT_ROOT))

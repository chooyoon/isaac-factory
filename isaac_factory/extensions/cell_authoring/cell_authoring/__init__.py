"""cell_authoring — programmatic USD authoring for cell_01 and successors.

Runtime: research profile (conda env_isaaclab, Python 3.10, usd-core 26.3,
pyyaml). No Kit Python, no PhysX, no Isaac Sim imports. Anything that
would couple this package to Runtime B belongs in a separate adapter.

Public API
----------

* :class:`CellConfig`  — frozen dataclass mirror of ``configs/cell_01.yaml``.
* :func:`load_config`  — strict YAML loader with schema-version check.
* :func:`build_cell`   — top-level entry point. Builds the cell stage from
                         a :class:`CellConfig` and writes a deterministic
                         ``.usda`` to the path declared in the config.

Determinism contract
--------------------

Every public function in this package is pure with respect to the
``CellConfig`` argument. Re-invoking ``build_cell(cfg)`` on an unchanged
config produces a byte-identical ``.usda`` (modulo a single
``# Authored by …`` comment line that the build CLI strips when the
``--strip-banner`` flag is set, which the validator-clean gate requires).
"""

from __future__ import annotations

from .config  import CellConfig, FloorConfig, GravityConfig, LightingConfig, RuntimeConfig, load_config
from .stage   import build_cell

__all__ = [
    "CellConfig",
    "FloorConfig",
    "GravityConfig",
    "LightingConfig",
    "RuntimeConfig",
    "build_cell",
    "load_config",
]

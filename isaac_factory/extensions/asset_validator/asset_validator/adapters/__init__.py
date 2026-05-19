"""Real adapters wiring validators to pxr / omni / isaacsim.

Each module here implements one of the Protocols defined in `core/` against
a concrete runtime. The Protocol layer keeps the validators Kit-free so
unit tests can exercise them with in-memory mocks.

Import policy: every module in this package may import `pxr`. None may
import `omni.*` or `isaacsim.*` unless its module docstring declares the
Kit dependency explicitly.
"""

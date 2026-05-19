"""Build-the-cell CLI.

Usage::

    python -m cell_authoring.cli build \\
        --config configs/cell_01.yaml \\
        --workspace /home/cap2/last

Exit codes
----------

* 0 — stage written successfully
* 1 — config or filesystem error
* 2 — bad command-line arguments
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .stage  import build_cell


def main(argv: list[str] | None = None) -> int:
    parser = _make_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        return _cmd_build(args)
    parser.error(f"unknown command: {args.command}")
    return 2


# =============================================================== build ==


def _cmd_build(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (workspace / config_path).resolve()

    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"[cell_authoring] config error: {e}", file=sys.stderr)
        return 1

    try:
        out_path = build_cell(cfg, workspace_root=workspace)
    except Exception as e:                                       # pragma: no cover
        print(f"[cell_authoring] build error: {e}", file=sys.stderr)
        return 1

    print(f"[cell_authoring] wrote {out_path}")
    return 0


# ============================================================== argparse ==


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cell_authoring",
        description="Build a deterministic cell stage from a YAML config.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="Build the cell stage.")
    b.add_argument("--config",    required=True, help="Path to cell config YAML.")
    b.add_argument("--workspace", required=True, help="Workspace root (paths in config are relative to this).")

    return p


if __name__ == "__main__":                                       # pragma: no cover
    sys.exit(main())

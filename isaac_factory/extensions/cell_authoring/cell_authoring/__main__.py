"""Allow ``python -m cell_authoring …`` to dispatch through the CLI."""

from __future__ import annotations

import sys

from .cli import main


if __name__ == "__main__":
    sys.exit(main())

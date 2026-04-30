"""Module entry point: ``python -m mine_sim``.

Delegates to :func:`mine_sim.cli.main`. Kept tiny so the heavy
import-time work happens inside :mod:`mine_sim.cli` and tests can drive
the CLI without invoking the interpreter as a subprocess.
"""

from __future__ import annotations

import sys

from mine_sim.cli import main


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    sys.exit(main())

"""Entry point for the frozen build.

PyInstaller executes its entry script as a top-level module named ``__main__``,
which has no parent package - so ``batterylimit/__main__.py`` cannot be used
directly there, because its relative import would fail with "attempted relative
import with no known parent package".

This launcher stands outside the package and imports it absolutely instead.
``python -m batterylimit`` continues to work through ``batterylimit/__main__.py``.
"""

from __future__ import annotations

import sys

from batterylimit.main import main

if __name__ == "__main__":
    sys.exit(main())

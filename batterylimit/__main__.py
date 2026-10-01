"""Allows ``python -m batterylimit`` to start the application."""

from __future__ import annotations

from .main import main

if __name__ == "__main__":
    raise SystemExit(main())

"""Battery Charge Notifier - a background battery charging limiter.

The application watches the battery and *notifies* the user when a
configurable charge threshold is crossed. It only ever reads battery status:
it never controls charging, never touches drivers or firmware and performs no
network communication.

``__version__`` is the single canonical version of the project
(``major.minor.patch``). ``pyproject`` reads it dynamically so the value is
defined in exactly one place. Bump **major** for incompatible changes,
**minor** for compatible features, and **patch** for bug fixes.
"""

from __future__ import annotations

__version__ = "1.1.0"

_parts = tuple(int(part) for part in __version__.split("."))
VERSION_INFO: tuple[int, int, int] = (_parts[0], _parts[1], _parts[2])

__all__ = ["VERSION_INFO", "__version__"]

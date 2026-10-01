"""BatteryLimit - a background battery charging limiter.

The application watches the battery and *notifies* the user when a
configurable charge threshold is crossed. It only ever reads battery status:
it never controls charging, never touches drivers or firmware and performs no
network communication.

``__version__`` is the single canonical version of the project; ``pyproject``
reads it dynamically so the value is defined in exactly one place.
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["__version__"]

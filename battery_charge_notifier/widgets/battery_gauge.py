"""A battery gauge: a charge bar with optional threshold markers.

The widget is purely a renderer. It is told the charge level, the accent to use
and where the configured limits sit, and it paints accordingly - it never sees a
:class:`~battery_charge_notifier.battery_service.BatteryState` or an ``AppConfig``.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import colors

BAR_HEIGHT = 18
CORNER_RADIUS = 9
MARKER_OVERHANG = 4
PERCENT_MAX = 100


class BatteryGauge(QWidget):
    """A horizontal charge bar with tick marks at the configured limits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty gauge.

        Args:
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._percent = 0
        self._accent = colors.ACCENT_PRIMARY
        self._upper: int | None = None
        self._lower: int | None = None
        self.setMinimumHeight(BAR_HEIGHT + 2 * MARKER_OVERHANG)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # -- input -------------------------------------------------------------
    def set_reading(
        self,
        percent: int,
        *,
        action: str | None = None,
        upper: int | None = None,
        lower: int | None = None,
    ) -> None:
        """Set everything needed to paint the gauge.

        Args:
            percent: Charge level, 0-100.
            action: ``"unplug"``, ``"plug_in"`` or ``None`` for the neutral accent.
            upper: Upper limit to mark, if known.
            lower: Lower limit to mark, if known.
        """
        self._percent = max(0, min(PERCENT_MAX, int(percent)))
        self._accent = colors.accent_for(action) if action else colors.ACCENT_PRIMARY
        self._upper = upper
        self._lower = lower
        self.update()

    # -- geometry ----------------------------------------------------------
    def sizeHint(self) -> QSize:
        """Preferred size."""
        return QSize(360, BAR_HEIGHT + 2 * MARKER_OVERHANG)

    def minimumSizeHint(self) -> QSize:
        """Smallest usable size."""
        return QSize(140, BAR_HEIGHT + 2 * MARKER_OVERHANG)

    # -- painting ----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: ANN001 - Qt signature
        """Paint the track, the charge fill and the threshold markers."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        track = QRectF(
            0,
            (self.height() - BAR_HEIGHT) / 2,
            self.width(),
            BAR_HEIGHT,
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors.GAUGE_TRACK))
        painter.drawRoundedRect(track, CORNER_RADIUS, CORNER_RADIUS)

        if self._percent > 0:
            filled = QRectF(track)
            filled.setWidth(track.width() * self._percent / PERCENT_MAX)
            # A very small fill would otherwise render as a sliver that ignores
            # the corner radius; keep it at least one diameter wide.
            filled.setWidth(max(filled.width(), CORNER_RADIUS * 2))
            painter.setBrush(QColor(self._accent))
            painter.drawRoundedRect(filled, CORNER_RADIUS, CORNER_RADIUS)

        self._paint_marker(painter, track, self._lower, colors.GAUGE_TICK)
        self._paint_marker(painter, track, self._upper, colors.GAUGE_TICK_MAJOR)
        painter.end()

    def _paint_marker(
        self,
        painter: QPainter,
        track: QRectF,
        percent: int | None,
        token: str,
    ) -> None:
        """Draw a vertical tick at *percent* across the track."""
        if percent is None:
            return
        x = track.left() + track.width() * max(0, min(PERCENT_MAX, percent)) / PERCENT_MAX
        pen = QPen(QColor(token), 1.5)
        painter.setPen(pen)
        painter.drawLine(
            int(x),
            int(track.top() - MARKER_OVERHANG),
            int(x),
            int(track.bottom() + MARKER_OVERHANG),
        )


__all__ = ["BatteryGauge"]

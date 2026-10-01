"""A battery gauge: charge bar with threshold markers.

The widget is purely a renderer. It is told the charge level, the accent to use
and where the configured limits sit, and it paints accordingly.

When the reading sits past the relevant threshold, the fill beyond that marker
uses the solid status accent; the portion before it uses the soft wash. Qt has
no stylesheet animation, so there is no pulse.
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
MARKER_WIDTH = 2
MARKER_HEIGHT = 14


class BatteryGauge(QWidget):
    """A horizontal charge bar with tick marks at the configured limits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty gauge."""
        super().__init__(parent)
        self._percent = 0
        self._action: str | None = None
        self._upper: int | None = None
        self._lower: int | None = None
        self.setMinimumHeight(BAR_HEIGHT + 2 * MARKER_OVERHANG)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

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
        self._action = action
        self._upper = upper
        self._lower = lower
        self.update()

    def sizeHint(self) -> QSize:
        """Preferred size."""
        return QSize(360, BAR_HEIGHT + 2 * MARKER_OVERHANG)

    def minimumSizeHint(self) -> QSize:
        """Smallest usable size."""
        return QSize(140, BAR_HEIGHT + 2 * MARKER_OVERHANG)

    def paintEvent(self, event) -> None:  # noqa: ANN001 - Qt signature
        """Paint the track, the split charge fill and the threshold markers."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        track = QRectF(
            0.5,
            (self.height() - BAR_HEIGHT) / 2,
            self.width() - 1,
            BAR_HEIGHT,
        )

        painter.setPen(QPen(QColor(colors.OUTLINE), 1))
        painter.setBrush(QColor(colors.GAUGE_TRACK))
        painter.drawRoundedRect(track, CORNER_RADIUS, CORNER_RADIUS)

        if self._percent > 0:
            self._paint_fill(painter, track)

        self._paint_marker(painter, track, self._lower, colors.GAUGE_TICK)
        self._paint_marker(painter, track, self._upper, colors.GAUGE_TICK_MAJOR)
        painter.end()

    def _paint_fill(self, painter: QPainter, track: QRectF) -> None:
        """Fill the track up to the current percent, splitting at the threshold."""
        wash = colors.accent_soft_for(self._action or "unplug") if self._action else colors.ACCENT_PRIMARY_SOFT
        solid = colors.accent_for(self._action) if self._action else colors.ACCENT_PRIMARY
        threshold = self._threshold_for_action()

        fill_width = max(track.width() * self._percent / PERCENT_MAX, CORNER_RADIUS * 2)
        painter.setPen(Qt.PenStyle.NoPen)

        if threshold is None or self._percent <= threshold:
            filled = QRectF(track)
            filled.setWidth(fill_width)
            painter.setBrush(QColor(wash))
            painter.drawRoundedRect(filled, CORNER_RADIUS, CORNER_RADIUS)
            return

        split = track.width() * threshold / PERCENT_MAX
        before = QRectF(track)
        before.setWidth(max(split, CORNER_RADIUS * 2))
        painter.setBrush(QColor(wash))
        painter.drawRoundedRect(before, CORNER_RADIUS, CORNER_RADIUS)

        after = QRectF(track)
        after.setLeft(track.left() + split)
        after.setWidth(fill_width - split)
        if after.width() > 1:
            painter.setBrush(QColor(solid))
            painter.drawRoundedRect(after, CORNER_RADIUS, CORNER_RADIUS)

    def _threshold_for_action(self) -> int | None:
        """The limit the current warning has crossed, if any."""
        if self._action == "unplug":
            return self._upper
        if self._action == "plug_in":
            return self._lower
        return None

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
        mid = track.center().y()
        pen = QPen(QColor(token), MARKER_WIDTH)
        painter.setPen(pen)
        painter.drawLine(
            int(x),
            int(mid - MARKER_HEIGHT / 2),
            int(x),
            int(mid + MARKER_HEIGHT / 2),
        )


__all__ = ["BatteryGauge"]

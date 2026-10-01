"""The warning popup - a Fluent frameless card.

Renders exactly what :class:`~battery_charge_notifier.viewmodels.warning.WarningViewModel`
gives it. Presentation:

* Frameless, always on top, translucent so the inner 8px card can round its
  corners. ``WA_ShowWithoutActivating`` plus ``Qt.Tool`` so it appears over a
  fullscreen application without stealing focus.
* A 3px status accent bar at the top of the card replaces the old full-border
  accent, so colour is not the only cue (headline, icon and gauge remain).
* One instance, updated in place, so repeated warnings never stack.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import colors, resources
from .viewmodels.warning import WarningContent, WarningViewModel
from .widgets import ActionButton, BatteryGauge, ButtonRole

CARD_MARGIN = 16
SCREEN_MARGIN = 28
ICON_SIZE = 24
POPUP_WIDTH = 440
ACCENT_BAR_HEIGHT = 3


class WarningWindow(QWidget):
    """Frameless always-on-top popup describing the required action."""

    def __init__(self, viewmodel: WarningViewModel, parent: QWidget | None = None) -> None:
        """Build the popup and bind it to *viewmodel*."""
        super().__init__(parent)
        self._viewmodel = viewmodel

        self.setWindowTitle("Battery Charge Notifier")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowIcon(resources.load_icon(resources.APP_ICON))
        self.setFixedWidth(POPUP_WIDTH)

        self._card = QFrame(self)
        self._card.setObjectName("card")

        self._build_ui()
        viewmodel.contentChanged.connect(self.apply_content)

    def _build_ui(self) -> None:
        """Create and lay out the child widgets."""
        self._accent_bar = QFrame()
        self._accent_bar.setObjectName("accentBar")
        self._accent_bar.setFixedHeight(ACCENT_BAR_HEIGHT)

        self._icon = QLabel()
        self._icon.setObjectName("icon")
        self._icon.setFixedSize(ICON_SIZE, ICON_SIZE)

        self._headline = QLabel()
        self._headline.setObjectName("headline")
        self._headline.setWordWrap(True)

        self._detail = QLabel()
        self._detail.setObjectName("detail")
        self._detail.setWordWrap(True)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(4)
        text_column.addWidget(self._headline)
        text_column.addWidget(self._detail)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(text_column, 1)

        self._gauge = BatteryGauge()
        self._gauge.setObjectName("gauge")
        self._gauge.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._snooze_button = ActionButton("Snooze", ButtonRole.ACCENT)
        self._settings_button = ActionButton("Settings", ButtonRole.NEUTRAL)
        self._dismiss_button = ActionButton("Dismiss", ButtonRole.OUTLINE)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self._snooze_button)
        buttons.addWidget(self._settings_button)
        buttons.addStretch(1)
        buttons.addWidget(self._dismiss_button)

        body = QVBoxLayout()
        body.setContentsMargins(CARD_MARGIN, 12, CARD_MARGIN, CARD_MARGIN)
        body.setSpacing(12)
        body.addLayout(header)
        body.addWidget(self._gauge)
        body.addLayout(buttons)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(self._accent_bar)
        card_layout.addLayout(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._card)

        self._snooze_button.clicked.connect(self._viewmodel.snooze)
        self._settings_button.clicked.connect(self._viewmodel.open_settings)
        self._dismiss_button.clicked.connect(self._viewmodel.dismiss)

    def apply_content(self, content: WarningContent) -> None:
        """Render *content*, restyling the window for the new accent."""
        accent = colors.accent_for(content.action)
        self._headline.setText(content.headline)
        self._detail.setText(content.detail)
        self._snooze_button.setText(content.snooze_label)
        self._snooze_button.set_action(content.action)

        pixmap = resources.load_pixmap(content.icon_name)
        if not pixmap.isNull():
            self._icon.setPixmap(
                pixmap.scaled(
                    ICON_SIZE,
                    ICON_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self._icon.clear()

        self._gauge.set_reading(
            content.percent,
            action=content.action,
            upper=self._viewmodel.upper_limit,
            lower=self._viewmodel.lower_limit,
        )

        self._card.setStyleSheet(
            f"""
            QFrame#card {{
                background-color: {colors.SCRIM};
                border: 1px solid {colors.OUTLINE};
                border-radius: 8px;
            }}
            QFrame#accentBar {{
                background-color: {accent};
                border: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QLabel {{
                color: {colors.TEXT_PRIMARY};
                background: {colors.TRANSPARENT};
            }}
            """
        )
        self._headline.setStyleSheet(
            f"color: {colors.TEXT_PRIMARY}; font-size: 20px; font-weight: 600;"
            f" background: {colors.TRANSPARENT};"
        )
        self._detail.setStyleSheet(
            f"color: {colors.TEXT_SECONDARY}; font-size: 13px;"
            f" background: {colors.TRANSPARENT};"
        )

        self.adjustSize()

    def show_at_bottom_right(self) -> None:
        """Show the window without activating it, near the notification area."""
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            x = available.right() - self.width() - SCREEN_MARGIN
            y = available.bottom() - self.height() - SCREEN_MARGIN
            self.move(max(available.left(), x), max(available.top(), y))
        self.show()
        self.raise_()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt signature
        """Close on ``Esc``."""
        if event.key() == Qt.Key.Key_Escape:
            self._viewmodel.dismiss()
            return
        super().keyPressEvent(event)


__all__ = ["WarningWindow"]

"""The warning popup - a pure View.

The window renders exactly what :class:`~batterylimit.viewmodels.warning.WarningViewModel`
gives it and reports button presses back as ViewModel calls. It holds no state of
its own beyond the widgets, and it never inspects the battery or the
configuration.

Presentation choices that matter:

* Frameless, always on top, translucent so the desktop shows through faintly.
* ``WA_ShowWithoutActivating`` plus ``Qt.Tool`` so it appears over a fullscreen
  application without pulling focus away from it. Clicking it still focuses it,
  which is what makes ``Esc`` work.
* One instance, updated in place, so repeated warnings never stack up.
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

CARD_MARGIN = 26
SCREEN_MARGIN = 28
ICON_SIZE = 44
PERCENT_POINT_SIZE = 46


class WarningWindow(QWidget):
    """Frameless always-on-top popup describing the required action."""

    def __init__(self, viewmodel: WarningViewModel, parent: QWidget | None = None) -> None:
        """Build the popup and bind it to *viewmodel*.

        Args:
            viewmodel: Supplies the content and receives the user's actions.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._viewmodel = viewmodel

        self.setWindowTitle("BatteryLimit")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowIcon(resources.load_icon(resources.APP_ICON))

        self._card = QFrame(self)
        self._card.setObjectName("card")

        self._build_ui()
        viewmodel.contentChanged.connect(self.apply_content)


    # -- construction ------------------------------------------------------
    def _build_ui(self) -> None:
        """Create and lay out the child widgets."""
        self._icon = QLabel()
        self._icon.setObjectName("icon")
        self._icon.setFixedSize(ICON_SIZE, ICON_SIZE)

        self._headline = QLabel()
        self._headline.setObjectName("headline")
        self._headline.setWordWrap(True)

        header = QHBoxLayout()
        header.setSpacing(14)
        header.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self._headline, 1)

        self._percent = QLabel()
        self._percent.setObjectName("percent")
        self._percent.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._gauge = BatteryGauge()
        self._gauge.setObjectName("gauge")
        self._gauge.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._detail = QLabel()
        self._detail.setObjectName("detail")
        self._detail.setWordWrap(True)

        self._snooze_button = ActionButton("Snooze", ButtonRole.ACCENT)
        self._settings_button = ActionButton("Settings", ButtonRole.NEUTRAL)
        self._dismiss_button = ActionButton("Dismiss", ButtonRole.OUTLINE)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addWidget(self._snooze_button)
        buttons.addWidget(self._settings_button)
        buttons.addStretch(1)
        buttons.addWidget(self._dismiss_button)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(CARD_MARGIN, CARD_MARGIN, CARD_MARGIN, CARD_MARGIN)
        card_layout.setSpacing(18)
        card_layout.addLayout(header)
        card_layout.addWidget(self._percent)
        card_layout.addWidget(self._gauge)
        card_layout.addWidget(self._detail)
        card_layout.addLayout(buttons)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._card)

        self.setMinimumWidth(420)
        self.setMaximumWidth(520)

        self._snooze_button.clicked.connect(self._viewmodel.snooze)
        self._settings_button.clicked.connect(self._viewmodel.open_settings)
        self._dismiss_button.clicked.connect(self._viewmodel.dismiss)

    # -- rendering ---------------------------------------------------------
    def apply_content(self, content: WarningContent) -> None:
        """Render *content*, restyling the window for the new accent.

        Args:
            content: The display-ready warning.
        """
        accent = colors.accent_for(content.action)
        self._headline.setText(content.headline)
        self._detail.setText(content.detail)
        self._percent.setText(f"{content.percent}%")
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
                border: 1px solid {accent};
                border-radius: 18px;
            }}
            QLabel {{
                color: {colors.TEXT_PRIMARY};
                background: {colors.TRANSPARENT};
            }}
            """
        )
        self._headline.setStyleSheet(
            f"color: {accent}; font-size: 19pt; font-weight: 700;"
            f" background: {colors.TRANSPARENT};"
        )
        self._percent.setStyleSheet(
            f"color: {colors.TEXT_PRIMARY}; font-size: {PERCENT_POINT_SIZE}px;"
            f" font-weight: 800; background: {colors.TRANSPARENT};"
        )
        self._detail.setStyleSheet(
            f"color: {colors.TEXT_SECONDARY}; font-size: 11pt;"
            f" background: {colors.TRANSPARENT};"
        )

        self.adjustSize()

    # -- placement ---------------------------------------------------------
    def show_at_bottom_right(self) -> None:
        """Show the window without activating it, near the notification area."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.adjustSize()
            self.move(
                available.right() - self.width() - SCREEN_MARGIN,
                available.bottom() - self.height() - SCREEN_MARGIN,
            )
        self.show()
        self.raise_()

    # -- events ------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt signature
        """Close on ``Esc``."""
        if event.key() == Qt.Key.Key_Escape:
            self._viewmodel.dismiss()
            return
        super().keyPressEvent(event)


__all__ = ["WarningWindow"]

"""A themed push button following Fluent 32px control metrics.

All colours come from :mod:`battery_charge_notifier.colors`. The ``ACCENT`` role
re-tints itself from the warning action so the popup's accent and its primary
button always agree.
"""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget

from .. import colors


class ButtonRole(StrEnum):
    """Visual weight of a button."""

    #: Filled with the primary accent (Close, primary actions).
    PRIMARY = "primary"
    #: Filled with the warning's status accent; needs :meth:`ActionButton.set_action`.
    ACCENT = "accent"
    #: Neutral fill with a 1px control stroke (Settings, standard actions).
    NEUTRAL = "neutral"
    #: Transparent, no border (Dismiss, Restore defaults).
    OUTLINE = "outline"


class ActionButton(QPushButton):
    """A push button styled from the Fluent design tokens."""

    def __init__(
        self,
        text: str = "",
        role: ButtonRole = ButtonRole.NEUTRAL,
        parent: QWidget | None = None,
    ) -> None:
        """Create the button.

        Args:
            text: Button caption.
            role: Visual weight.
            parent: Optional Qt parent.
        """
        super().__init__(text, parent)
        self._role = role
        self._action = "unplug"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(32)
        self.setMinimumWidth(80)
        self._apply_style()

    def set_role(self, role: ButtonRole) -> None:
        """Change the visual weight."""
        self._role = role
        self._apply_style()

    @property
    def role(self) -> ButtonRole:
        """The current visual weight."""
        return self._role

    def set_action(self, action: str) -> None:
        """Tint an ``ACCENT`` button to match the warning action.

        Args:
            action: ``"unplug"`` or ``"plug_in"``.
        """
        self._action = action
        if self._role is ButtonRole.ACCENT:
            self._apply_style()

    def _apply_style(self) -> None:
        """Rebuild the style sheet from the design tokens."""
        background, hover, pressed, text, border = self._palette()
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {background};
                color: {text};
                border: {border};
                border-radius: 4px;
                padding: 0px 12px;
                font-size: 13px;
                font-weight: 600;
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {pressed};
            }}
            QPushButton:focus {{
                outline: none;
                border: 1px solid {colors.FOCUS_OUTER};
            }}
            QPushButton:disabled {{
                background-color: {colors.CONTROL_FILL_DISABLED};
                color: {colors.TEXT_MUTED};
            }}
            """
        )

    def _palette(self) -> tuple[str, str, str, str, str]:
        """Return ``(background, hover, pressed, text, border)`` for the role."""
        if self._role is ButtonRole.PRIMARY:
            return (
                colors.ACCENT_PRIMARY,
                colors.ACCENT_PRIMARY_DIM,
                colors.ACCENT_PRIMARY_DIM,
                colors.TEXT_ON_ACCENT,
                "none",
            )
        if self._role is ButtonRole.ACCENT:
            return (
                colors.accent_for(self._action),
                colors.accent_dim_for(self._action),
                colors.accent_dim_for(self._action),
                colors.TEXT_ON_ACCENT,
                "none",
            )
        if self._role is ButtonRole.OUTLINE:
            return (
                colors.TRANSPARENT,
                colors.CONTROL_FILL_HOVER,
                colors.CONTROL_FILL_PRESSED,
                colors.TEXT_PRIMARY,
                "none",
            )
        return (
            colors.BUTTON_BACKGROUND,
            colors.BUTTON_BACKGROUND_HOVER,
            colors.BUTTON_BACKGROUND_PRESSED,
            colors.BUTTON_TEXT,
            f"1px solid {colors.OUTLINE_STRONG}",
        )


__all__ = ["ActionButton", "ButtonRole"]

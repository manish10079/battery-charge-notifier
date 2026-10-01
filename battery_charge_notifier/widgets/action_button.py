"""A themed push button.

All colours come from :mod:`battery_charge_notifier.colors`; the widget never hardcodes a
value. The ``ACCENT`` role re-tints itself from the warning action, so the
popup's accent colour and its primary button always agree.
"""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget

from .. import colors


class ButtonRole(StrEnum):
    """Visual weight of a button."""

    #: Filled with the neutral primary accent.
    PRIMARY = "primary"
    #: Filled with the warning's accent colour; needs :meth:`ActionButton.set_action`.
    ACCENT = "accent"
    #: Filled with the surface container colour.
    NEUTRAL = "neutral"
    #: Transparent with an outline.
    OUTLINE = "outline"


class ActionButton(QPushButton):
    """A push button styled from the design tokens."""

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
        self.setMinimumHeight(38)
        self.setMinimumWidth(96)
        self._apply_style()

    # -- configuration -----------------------------------------------------
    def set_role(self, role: ButtonRole) -> None:
        """Change the visual weight.

        Args:
            role: The new role.
        """
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

    # -- internals ---------------------------------------------------------
    def _apply_style(self) -> None:
        """Rebuild the style sheet from the design tokens."""
        background, hover, pressed, text = self._palette()
        border = "none"
        if self._role is ButtonRole.OUTLINE:
            border = f"1px solid {colors.OUTLINE_STRONG}"

        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {background};
                color: {text};
                border: {border};
                border-radius: 10px;
                padding: 9px 18px;
                font-size: 10.5pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {pressed};
            }}
            QPushButton:focus {{
                outline: none;
            }}
            """
        )

    def _palette(self) -> tuple[str, str, str, str]:
        """Return the ``(background, hover, pressed, text)`` tokens for the role."""
        if self._role is ButtonRole.PRIMARY:
            return (
                colors.ACCENT_PRIMARY,
                colors.ACCENT_PRIMARY,
                colors.ACCENT_PRIMARY_DIM,
                colors.TEXT_ON_ACCENT,
            )
        if self._role is ButtonRole.ACCENT:
            return (
                colors.accent_for(self._action),
                colors.accent_for(self._action),
                colors.accent_dim_for(self._action),
                colors.TEXT_ON_ACCENT,
            )
        if self._role is ButtonRole.OUTLINE:
            return (
                colors.TRANSPARENT,
                colors.BUTTON_BACKGROUND_HOVER,
                colors.BUTTON_BACKGROUND_PRESSED,
                colors.BUTTON_TEXT,
            )
        return (
            colors.BUTTON_BACKGROUND,
            colors.BUTTON_BACKGROUND_HOVER,
            colors.BUTTON_BACKGROUND_PRESSED,
            colors.BUTTON_TEXT,
        )


__all__ = ["ActionButton", "ButtonRole"]

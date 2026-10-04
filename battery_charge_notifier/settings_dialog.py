"""The settings dialog - a schema-driven Fluent view.

Every control is generated from :data:`~battery_charge_notifier.app_config.FIELDS`.
There is no OK/Cancel pair: a valid edit is persisted as soon as it is made.

The layout is two columns of setting cards: label and control on the first
row, help text on the second. The window is freely resizable.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import __version__, colors, resources
from .app_config import AppConfig, FieldSpec
from .viewmodels.settings import SettingsViewModel
from .widgets import ActionButton, ButtonRole

DIALOG_WIDTH = 720
COLUMN_GAP = 20
CARD_RADIUS = 6

#: Human-readable captions for the ``notification_mode`` values.
CHOICE_LABELS: dict[str, dict[str, str]] = {
    "notification_mode": {
        "popup": "Popup window",
        "tray": "Tray notification only",
    },
    "theme": {
        "system": "System",
        "light": "Light",
        "dark": "Dark",
    },
}

class _NoScrollSpinBox(QSpinBox):
    """A spin box whose value is not changed by the mouse wheel.

    Wheel events are ignored so they reach the settings scroller instead of
    nudging limits while the user is scrolling the dialog.
    """

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override
        event.ignore()


#: Fields split evenly across two columns, in schema order.
LEFT_KEYS = (
    "upper_limit",
    "lower_limit",
    "minimum_gap",
    "snooze_minutes",
    "poll_interval_seconds",
)
RIGHT_KEYS = (
    "popup_timeout_seconds",
    "monitoring_enabled",
    "launch_at_startup",
    "notification_mode",
    "sound_enabled",
    "theme",
)


class SettingsDialog(QDialog):
    """A modeless, live-applying settings window."""

    def __init__(self, viewmodel: SettingsViewModel, parent: QWidget | None = None) -> None:
        """Build the dialog from the schema."""
        super().__init__(parent)
        self._viewmodel = viewmodel
        self._loading = False
        self._editors: dict[str, QWidget] = {}
        self._errors: dict[str, QLabel] = {}
        self._cards: dict[str, QFrame] = {}

        self.setWindowTitle("Battery Charge Notifier")
        self.setWindowIcon(resources.load_icon(resources.APP_ICON))
        self.setModal(False)
        self.setMinimumSize(360, 280)
        self.resize(DIALOG_WIDTH, 560)
        self.setSizeGripEnabled(True)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        self._build_ui()
        self._load_values(viewmodel.config)

        viewmodel.accepted.connect(self._on_accepted)
        viewmodel.rejected.connect(self._on_rejected)
        viewmodel.reloaded.connect(self._load_values)

    def _build_ui(self) -> None:
        """Create the header, the two-column cards and the footer."""
        title = QLabel("Battery Charge Notifier")
        title.setObjectName("title")

        subtitle = QLabel(
            "Changes are saved and applied immediately \u2014 there is nothing to confirm."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        specs = {spec.key: spec for spec in self._viewmodel.fields}
        left = QVBoxLayout()
        left.setSpacing(8)
        right = QVBoxLayout()
        right.setSpacing(8)
        for key in LEFT_KEYS:
            left.addWidget(self._build_card(specs[key]))
        left.addStretch(1)
        for key in RIGHT_KEYS:
            right.addWidget(self._build_card(specs[key]))
        right.addStretch(1)

        columns = QGridLayout()
        columns.setHorizontalSpacing(COLUMN_GAP)
        columns.setVerticalSpacing(0)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.addLayout(left, 0, 0)
        columns.addLayout(right, 0, 1)
        columns.setColumnStretch(0, 1)
        columns.setColumnStretch(1, 1)

        body = QWidget()
        body.setObjectName("settingsBody")
        body.setLayout(columns)

        scroller = QScrollArea()
        scroller.setObjectName("settingsScroller")
        scroller.setWidget(body)
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.Shape.NoFrame)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroller.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        restore = ActionButton("Restore defaults", ButtonRole.OUTLINE)
        close = ActionButton("Close", ButtonRole.PRIMARY)
        restore.clicked.connect(self._viewmodel.reset_to_defaults)
        close.clicked.connect(self.accept)

        version = QLabel(f"Version {__version__}  by Mkn Labs")
        version.setObjectName("versionLabel")
        version.setToolTip("major.minor.patch")

        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addWidget(version)
        footer.addStretch(1)
        footer.addWidget(restore)
        footer.addWidget(close)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("separator")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(scroller, 1)
        layout.addSpacing(8)
        layout.addWidget(separator)
        layout.addSpacing(8)
        layout.addLayout(footer)

        self.setStyleSheet(self._style_sheet())

    def restyle(self) -> None:
        """Rebuild the style sheet after the theme tokens change."""
        self.setStyleSheet(self._style_sheet())
        for button in self.findChildren(ActionButton):
            button.set_role(button.role)

    def _build_card(self, spec: FieldSpec) -> QWidget:
        """Create a card: label + control on the first row, help text on the second."""
        card = QFrame()
        card.setObjectName("settingCard")
        self._cards[spec.key] = card

        label = QLabel(spec.label)
        label.setObjectName("fieldLabel")

        editor = self._build_editor(spec)
        self._editors[spec.key] = editor

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        top.addWidget(label, 1, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(editor, 0, Qt.AlignmentFlag.AlignVCenter)

        stack = QVBoxLayout(card)
        stack.setContentsMargins(16, 12, 16, 12)
        stack.setSpacing(4)
        stack.addLayout(top)
        if spec.help_text:
            help_label = QLabel(spec.help_text)
            help_label.setObjectName("fieldHelp")
            help_label.setWordWrap(True)
            stack.addWidget(help_label)

        error = QLabel()
        error.setObjectName("fieldError")
        error.setWordWrap(True)
        error.hide()
        self._errors[spec.key] = error
        stack.addWidget(error)
        return card

    def _build_editor(self, spec: FieldSpec) -> QWidget:
        """Create the input control matching the field's kind."""
        if spec.kind == "int":
            spin = _NoScrollSpinBox()
            spin.setRange(spec.minimum or 0, spec.maximum or 100)
            spin.setSuffix(spec.suffix)
            spin.setSingleStep(1)
            spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            spin.setMinimumWidth(110)
            spin.setFixedHeight(32)
            spin.valueChanged.connect(lambda value, key=spec.key: self._stage(key, value))
            return spin

        if spec.kind == "bool":
            check = QCheckBox("Enabled")
            check.toggled.connect(lambda value, key=spec.key: self._stage(key, value))
            return check

        combo = QComboBox()
        combo.setMinimumWidth(220)
        combo.setFixedHeight(32)
        labels = CHOICE_LABELS.get(spec.key, {})
        for choice in spec.choices:
            combo.addItem(labels.get(choice, choice), choice)
        combo.currentIndexChanged.connect(
            lambda _index, key=spec.key, box=combo: self._stage(key, box.currentData())
        )
        return combo

    def _load_values(self, config: AppConfig) -> None:
        """Write *config* into the controls without re-triggering validation."""
        self._loading = True
        try:
            for key, editor in self._editors.items():
                value = getattr(config, key)
                if isinstance(editor, QSpinBox):
                    editor.setValue(int(value))
                elif isinstance(editor, QCheckBox):
                    editor.setChecked(bool(value))
                elif isinstance(editor, QComboBox):
                    index = editor.findData(value)
                    if index >= 0:
                        editor.setCurrentIndex(index)
        finally:
            self._loading = False
        self._clear_errors()

    def _stage(self, key: str, value: object) -> None:
        """Forward an edit to the ViewModel, unless we are populating the form."""
        if self._loading:
            return
        self._viewmodel.stage(key, value)

    def _on_accepted(self, _config: AppConfig) -> None:
        """Clear any error state after a successful save."""
        self._clear_errors()

    def _on_rejected(self, issues: dict[str, str]) -> None:
        """Display the per-field rejection messages."""
        self._clear_errors()
        for key, message in issues.items():
            label = self._errors.get(key)
            if label is not None:
                label.setText(message)
                label.show()

    def _clear_errors(self) -> None:
        """Hide every inline error message."""
        for label in self._errors.values():
            label.clear()
            label.hide()

    def _style_sheet(self) -> str:
        """Return the dialog's style sheet, built from the design tokens."""
        arrow_up = resources.asset_path(resources.ARROW_UP).as_posix()
        arrow_down = resources.asset_path(resources.ARROW_DOWN).as_posix()
        return f"""
            QDialog {{
                background-color: {colors.SURFACE};
            }}
            QLabel {{
                color: {colors.TEXT_PRIMARY};
                background: {colors.TRANSPARENT};
            }}
            QLabel#title {{
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#subtitle {{
                color: {colors.TEXT_SECONDARY};
                font-size: 13px;
            }}
            QLabel#versionLabel {{
                color: {colors.TEXT_MUTED};
                font-size: 12px;
            }}
            QFrame#settingCard {{
                background-color: {colors.SURFACE_CONTAINER};
                border: 1px solid {colors.OUTLINE};
                border-radius: {CARD_RADIUS}px;
            }}
            QLabel#fieldLabel {{
                color: {colors.FIELD_LABEL};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#fieldHelp {{
                color: {colors.FIELD_HELP};
                font-size: 12px;
            }}
            QLabel#fieldError {{
                color: {colors.FIELD_ERROR};
                font-size: 12px;
                font-weight: 500;
            }}
            QFrame#separator {{
                color: {colors.OUTLINE};
                background-color: {colors.OUTLINE};
                max-height: 1px;
                border: none;
            }}
            QScrollArea#settingsScroller {{
                background: {colors.TRANSPARENT};
                border: none;
            }}
            QScrollArea#settingsScroller > QWidget > QWidget {{
                background: {colors.TRANSPARENT};
            }}
            QScrollBar:vertical {{
                background: {colors.TRANSPARENT};
                width: 10px;
                margin: 0;
            }}
            QScrollBar:horizontal {{
                background: {colors.TRANSPARENT};
                height: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {colors.SCROLLBAR_HANDLE};
                border-radius: 4px;
                min-height: 24px;
                min-width: 24px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background: {colors.SCROLLBAR_HANDLE_HOVER};
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                height: 0;
                width: 0;
            }}
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: {colors.TRANSPARENT};
            }}
            QSpinBox, QComboBox {{
                background-color: {colors.INPUT_BACKGROUND};
                color: {colors.TEXT_PRIMARY};
                border: 1px solid {colors.INPUT_BORDER};
                border-radius: 4px;
                padding: 0px 8px;
                min-height: 32px;
                font-size: 13px;
            }}
            QSpinBox:hover, QComboBox:hover {{
                border: 1px solid {colors.TEXT_SECONDARY};
            }}
            QSpinBox:focus, QComboBox:focus {{
                border: 1px solid {colors.INPUT_BORDER_FOCUS};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 18px;
                background-color: {colors.TRANSPARENT};
                border: none;
            }}
            QSpinBox::up-arrow {{
                image: url({arrow_up});
                width: 9px;
                height: 6px;
            }}
            QSpinBox::down-arrow {{
                image: url({arrow_down});
                width: 9px;
                height: 6px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 22px;
            }}
            QComboBox::down-arrow {{
                image: url({arrow_down});
                width: 9px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors.SURFACE_CONTAINER};
                color: {colors.TEXT_PRIMARY};
                selection-background-color: {colors.ACCENT_PRIMARY_SOFT};
                border: 1px solid {colors.OUTLINE};
                padding: 4px;
            }}
            QCheckBox {{
                color: {colors.TEXT_PRIMARY};
                font-size: 13px;
                spacing: 8px;
                padding: 4px 0;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 1px solid {colors.TEXT_SECONDARY};
                background-color: {colors.INPUT_BACKGROUND};
            }}
            QCheckBox::indicator:checked {{
                background-color: {colors.ACCENT_PRIMARY};
                border: 1px solid {colors.ACCENT_PRIMARY};
            }}
        """


__all__ = ["SettingsDialog"]

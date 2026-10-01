"""The settings dialog - a schema-driven View.

Every control is generated from :data:`~battery_charge_notifier.app_config.FIELDS`, so
adding a setting never requires touching this file. The dialog contains no
validation logic: it forwards edits to
:class:`~battery_charge_notifier.viewmodels.settings.SettingsViewModel` and renders the
per-field messages that come back.

There is no OK/Cancel pair: a valid edit is persisted - and therefore applied
across the running application - as soon as it is made.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import colors, resources
from .app_config import AppConfig, FieldSpec
from .viewmodels.settings import SettingsViewModel
from .widgets import ActionButton, ButtonRole

DIALOG_WIDTH = 470

#: Human-readable captions for the ``notification_mode`` values.
CHOICE_LABELS: dict[str, dict[str, str]] = {
    "notification_mode": {
        "popup": "Popup window (mirrored to the tray)",
        "tray": "Tray notification only",
    }
}


class SettingsDialog(QDialog):
    """A modeless, live-applying settings window."""

    def __init__(self, viewmodel: SettingsViewModel, parent: QWidget | None = None) -> None:
        """Build the dialog from the schema.

        Args:
            viewmodel: Validates and persists edits.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._viewmodel = viewmodel
        self._loading = False
        self._editors: dict[str, QWidget] = {}
        self._errors: dict[str, QLabel] = {}

        self.setWindowTitle("Battery Charge Notifier settings")
        self.setWindowIcon(resources.load_icon(resources.APP_ICON))
        self.setModal(False)
        self.setMinimumWidth(DIALOG_WIDTH)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._build_ui()
        self._load_values(viewmodel.config)

        viewmodel.accepted.connect(self._on_accepted)
        viewmodel.rejected.connect(self._on_rejected)
        viewmodel.reloaded.connect(self._load_values)

    # -- construction ------------------------------------------------------
    def _build_ui(self) -> None:
        """Create the header, the generated fields and the footer."""
        title = QLabel("Battery Charge Notifier settings")
        title.setObjectName("title")

        subtitle = QLabel(
            "Changes are saved and applied immediately \u2014 there is nothing to confirm."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        fields_layout = QVBoxLayout()
        fields_layout.setSpacing(16)
        for spec in self._viewmodel.fields:
            fields_layout.addWidget(self._build_field(spec))

        restore = ActionButton("Restore defaults", ButtonRole.OUTLINE)
        close = ActionButton("Close", ButtonRole.PRIMARY)
        restore.clicked.connect(self._viewmodel.reset_to_defaults)
        close.clicked.connect(self.accept)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(restore)
        footer.addStretch(1)
        footer.addWidget(close)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("separator")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(6)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addLayout(fields_layout)
        layout.addSpacing(10)
        layout.addWidget(separator)
        layout.addSpacing(10)
        layout.addLayout(footer)

        self.setStyleSheet(self._style_sheet())

    def _build_field(self, spec: FieldSpec) -> QWidget:
        """Create the label/control/help/error block for one schema field."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel(spec.label)
        label.setObjectName("fieldLabel")

        editor = self._build_editor(spec)
        self._editors[spec.key] = editor

        layout.addWidget(label)
        layout.addWidget(editor)

        if spec.help_text:
            help_label = QLabel(spec.help_text)
            help_label.setObjectName("fieldHelp")
            help_label.setWordWrap(True)
            layout.addWidget(help_label)

        error = QLabel()
        error.setObjectName("fieldError")
        error.setWordWrap(True)
        error.hide()
        self._errors[spec.key] = error
        layout.addWidget(error)

        return container

    def _build_editor(self, spec: FieldSpec) -> QWidget:
        """Create the input control matching the field's kind."""
        if spec.kind == "int":
            spin = QSpinBox()
            spin.setRange(spec.minimum or 0, spec.maximum or 100)
            spin.setSuffix(spec.suffix)
            spin.setSingleStep(1)
            spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            spin.valueChanged.connect(lambda value, key=spec.key: self._stage(key, value))
            return spin

        if spec.kind == "bool":
            check = QCheckBox("Enabled")
            check.toggled.connect(lambda value, key=spec.key: self._stage(key, value))
            return check

        combo = QComboBox()
        labels = CHOICE_LABELS.get(spec.key, {})
        for choice in spec.choices:
            combo.addItem(labels.get(choice, choice), choice)
        combo.currentIndexChanged.connect(
            lambda _index, key=spec.key, box=combo: self._stage(key, box.currentData())
        )
        return combo

    # -- model plumbing ----------------------------------------------------
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

    # -- theme -------------------------------------------------------------
    def _style_sheet(self) -> str:
        """Return the dialog's style sheet, built from the design tokens."""
        # Qt style sheets need a URL, and accept forward slashes on every platform.
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
                font-size: 16pt;
                font-weight: 700;
            }}
            QLabel#subtitle {{
                color: {colors.TEXT_SECONDARY};
                font-size: 10pt;
            }}
            QLabel#fieldLabel {{
                color: {colors.FIELD_LABEL};
                font-size: 10.5pt;
                font-weight: 600;
            }}
            QLabel#fieldHelp {{
                color: {colors.FIELD_HELP};
                font-size: 9.5pt;
            }}
            QLabel#fieldError {{
                color: {colors.FIELD_ERROR};
                font-size: 9.5pt;
                font-weight: 600;
            }}
            QFrame#separator {{
                color: {colors.OUTLINE};
                background-color: {colors.OUTLINE};
                max-height: 1px;
                border: none;
            }}
            QSpinBox, QComboBox {{
                background-color: {colors.INPUT_BACKGROUND};
                color: {colors.TEXT_PRIMARY};
                border: 1px solid {colors.INPUT_BORDER};
                border-radius: 8px;
                padding: 7px 10px;
                min-height: 22px;
                font-size: 10.5pt;
            }}
            QSpinBox:focus, QComboBox:focus {{
                border: 1px solid {colors.INPUT_BORDER_FOCUS};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 18px;
                background-color: {colors.SURFACE_CONTAINER};
                border: none;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {colors.SURFACE_CONTAINER_HIGH};
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
                selection-background-color: {colors.ACCENT_PRIMARY_DIM};
                border: 1px solid {colors.OUTLINE};
            }}
            QCheckBox {{
                color: {colors.TEXT_PRIMARY};
                font-size: 10.5pt;
                spacing: 9px;
                padding: 4px 0;
            }}
            QCheckBox::indicator {{
                width: 17px;
                height: 17px;
                border-radius: 5px;
                border: 1px solid {colors.INPUT_BORDER};
                background-color: {colors.INPUT_BACKGROUND};
            }}
            QCheckBox::indicator:checked {{
                background-color: {colors.ACCENT_PRIMARY};
                border: 1px solid {colors.ACCENT_PRIMARY};
            }}
        """


__all__ = ["SettingsDialog"]

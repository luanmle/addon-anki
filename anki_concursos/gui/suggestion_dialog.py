from typing import Dict, Optional

from aqt.operations import QueryOp
from aqt.qt import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import tooltip

from ..api.client import ApiClient
from ..api.models import NoteSuggestionRequest
from ..services.suggestions import diff_preview_text, filter_fields_for_suggestion


class SuggestionDialog(QDialog):
    def __init__(
        self,
        api: ApiClient,
        card_id: str,
        fields: Dict[str, str],
        original_fields: Optional[Dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._card_id = card_id
        self._fields = fields
        self._original_fields = original_fields or {}
        self._field_checkboxes: Dict[str, QCheckBox] = {}

        self.setWindowTitle("Sugerir alteração")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Sugerir alteração desta nota</b>"))
        layout.addWidget(self._field_selector())
        layout.addWidget(self._preview_widget())

        form = QFormLayout()
        self._comment_edit = QPlainTextEdit()
        self._comment_edit.setPlaceholderText("Descreva o que foi alterado e por quê.")
        self._comment_edit.setMinimumHeight(120)
        form.addRow("Comentário", self._comment_edit)

        self._source_edit = QLineEdit()
        self._source_edit.setPlaceholderText("Fonte, lei, edital ou referência")
        form.addRow("Fonte", self._source_edit)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Enviar sugestão")
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self._buttons.accepted.connect(self._submit)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def _field_selector(self) -> QGroupBox:
        group = QGroupBox("Campos a enviar")
        group_layout = QVBoxLayout(group)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(120)
        scroll.setMaximumHeight(220)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        for field_name in self._fields:
            checkbox = QCheckBox(field_name)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._update_preview)
            self._field_checkboxes[field_name] = checkbox
            content_layout.addWidget(checkbox)

        scroll.setWidget(content)
        group_layout.addWidget(scroll)
        return group

    def _preview_widget(self) -> QGroupBox:
        group = QGroupBox("Prévia antes/depois")
        layout = QVBoxLayout(group)
        self._preview_edit = QPlainTextEdit()
        self._preview_edit.setReadOnly(True)
        self._preview_edit.setMinimumHeight(140)
        self._preview_edit.setMaximumHeight(220)
        layout.addWidget(self._preview_edit)
        self._update_preview()
        return group

    def _selected_field_names(self) -> list[str]:
        return [
            field_name
            for field_name, checkbox in self._field_checkboxes.items()
            if checkbox.isChecked()
        ]

    def _selected_fields(self) -> Dict[str, str]:
        return filter_fields_for_suggestion(self._fields, self._selected_field_names())

    def _update_preview(self) -> None:
        if not hasattr(self, "_preview_edit"):
            return
        fields = self._selected_fields()
        self._preview_edit.setPlainText(
            diff_preview_text(self._original_fields, fields)
            if fields
            else "Nenhum campo selecionado."
        )

    def _submit(self) -> None:
        comment = self._comment_edit.toPlainText().strip()
        if not comment:
            tooltip("Informe um comentário para enviar a sugestão.", parent=self)
            return

        fields = self._selected_fields()
        if not fields:
            tooltip("Selecione pelo menos um campo para enviar.", parent=self)
            return

        payload = NoteSuggestionRequest(
            suggestion_type="updated_content",
            fields=fields,
            comment=comment,
            source=self._source_edit.text().strip() or None,
        )
        self._buttons.setEnabled(False)

        def on_success(_: object) -> None:
            tooltip("Sugestão enviada para revisão.", parent=self)
            self.accept()

        def on_failure(exc: Exception) -> None:
            self._buttons.setEnabled(True)
            tooltip(f"Falha ao enviar sugestão: {exc}", parent=self)

        op = QueryOp(
            parent=self,
            op=lambda _: self._api.create_card_suggestion(self._card_id, payload),
            success=on_success,
        )
        op.failure(on_failure)
        op.with_progress("Enviando sugestão...").run_in_background()

import logging
from aqt import mw
from aqt.qt import *
from aqt.operations import QueryOp
from ..api.client import ApiClient, ApiError
from ..services.deck_exporter import DeckExporter

logger = logging.getLogger("anki_concursos.gui.upload")

class UploadDialog(QDialog):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Anki Concursos - Enviar Baralho")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        
        # Resolve decks list
        self.decks = []
        try:
            raw_decks = mw.col.decks.all_names_and_ids()
            for d in raw_decks:
                name = getattr(d, "name", None)
                id = getattr(d, "id", None)
                if name is None or id is None:
                    name, id = d[0], d[1]
                self.decks.append((name, id))
        except Exception as e:
            logger.error(f"Failed to fetch decks: {e}")
            
        form = QFormLayout()
        
        self.deck_cb = QComboBox()
        for name, id in self.decks:
            self.deck_cb.addItem(name, id)
        form.addRow("Selecione o Baralho:", self.deck_cb)
        
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Descrição opcional do pacote...")
        form.addRow("Descrição:", self.description_input)
        
        self.publish_cb = QCheckBox("Publicar release automaticamente")
        self.publish_cb.setChecked(True)
        form.addRow("", self.publish_cb)
        
        layout.addLayout(form)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Enviar Baralho")
        button_box.accepted.connect(self.on_upload)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def on_upload(self):
        # 1. Check if authenticated
        token = self.api.auth_service.get_token()
        if not token:
            QMessageBox.warning(self, "Não Autenticado", "Usuário não autenticado. Por favor, realize o login antes de enviar.")
            return
            
        selected_index = self.deck_cb.currentIndex()
        if selected_index == -1:
            QMessageBox.warning(self, "Aviso", "Selecione um baralho para upload.")
            return
            
        deck_id = self.deck_cb.itemData(selected_index)
        description = self.description_input.text().strip()
        publish_release = self.publish_cb.isChecked()
        
        def background_job():
            exporter = DeckExporter()
            payload = exporter.export_deck(deck_id)
            payload["publish_release"] = publish_release
            if description:
                payload["description"] = description
            
            return self.api.upload_deck(payload)
            
        def on_success(resp):
            mw.progress.finish()
            
            deck_name = resp.get("deck_name", "")
            total_notes = resp.get("total_notes", 0)
            created_cards = resp.get("created_cards", 0)
            reused_cards = resp.get("reused_cards", 0)
            published = resp.get("published", False)
            
            msg = (
                f"Baralho '{deck_name}' enviado com sucesso!\n\n"
                f"ID do Baralho: {resp.get('deck_id')}\n"
                f"Total de Notas Enviadas: {total_notes}\n"
                f"Novos Cartões Criados: {created_cards}\n"
                f"Cartões Reutilizados: {reused_cards}\n"
            )
            if published:
                msg += "\nUma nova release foi publicada na plataforma."
            else:
                msg += "\nO pacote foi gravado, mas nenhuma release foi publicada."
                
            QMessageBox.information(self, "Sucesso", msg)
            self.accept()
            
        def on_failure(exc):
            mw.progress.finish()
            err_msg = str(exc)
            if isinstance(exc, ApiError):
                if exc.status_code == 401:
                    err_msg = "Sessão expirada ou não autenticado. Por favor, faça login novamente."
                elif exc.status_code == 403:
                    err_msg = "Você não possui permissão para realizar o upload de baralhos."
                elif exc.status_code == 409:
                    err_msg = "Conflito de dados no servidor. Verifique o baralho ou tente novamente."
                elif exc.status_code == 422:
                    err_msg = f"Erro de validação dos dados enviados:\n{exc}"
            
            QMessageBox.critical(self, "Erro no Upload", f"Não foi possível enviar o baralho:\n{err_msg}")
            
        mw.progress.start(label="Preparando e enviando pacote do baralho...", immediate=True)
        op = QueryOp(
            parent=self,
            op=lambda _: background_job(),
            success=on_success
        )
        op.failure(on_failure)
        op.run_in_background()

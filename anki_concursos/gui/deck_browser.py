from aqt import mw
from aqt.qt import *
from aqt.operations import QueryOp
from ..api.client import ApiClient, ApiError
from ..storage.database import DatabaseManager
from ..sync.installer import DeckInstaller
from ..services.subscription_manager import SubscriptionManager

class DeckBrowser(QDialog):
    def __init__(self, api: ApiClient, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.api = api
        self.db = db
        self.setWindowTitle("Anki Concursos - Explorar baralhos")
        self.resize(900, 420)
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Nome",
            "Cards",
            "Versão local",
            "Versão remota",
            "Status local",
            "Instalação",
            "Inscrição",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self.load_decks)
        btn_layout.addWidget(self.btn_refresh)
        
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        
        self.load_decks()
        
    def load_decks(self):
        self.btn_refresh.setEnabled(False)
        self.table.setRowCount(0)

        op = QueryOp(
            parent=self,
            op=lambda _: self.api.list_subscribable_decks(),
            success=self._on_decks_loaded,
        )
        op.failure(self._on_decks_failed)
        op.with_progress("Carregando baralhos...").run_in_background()

    def _on_decks_loaded(self, resp) -> None:
        self.btn_refresh.setEnabled(True)
        self.table.setRowCount(len(resp.items))
        for i, deck in enumerate(resp.items):
            self.table.setItem(i, 0, QTableWidgetItem(deck.name))
            self.table.setItem(i, 1, QTableWidgetItem(str(deck.active_card_count)))

            local_deck = self.db.get_deck(deck.deck_id)
            self.table.setItem(i, 2, QTableWidgetItem(str(local_deck.latest_release) if local_deck else "-"))
            self.table.setItem(i, 3, QTableWidgetItem(str(deck.latest_release)))
            self.table.setItem(
                i,
                4,
                QTableWidgetItem(self._format_local_status(local_deck, deck.latest_release)),
            )

            if deck.subscribed and not local_deck:
                btn_install = QPushButton("Instalar")
                btn_install.clicked.connect(lambda _, d=deck.deck_id: self.on_install(d))
                self.table.setCellWidget(i, 5, btn_install)
            elif deck.subscribed:
                self.table.setCellWidget(i, 5, QLabel("Instalado"))
            else:
                self.table.setCellWidget(i, 5, QLabel("-"))

            if deck.subscribed:
                btn_unsubscribe = QPushButton("Cancelar inscrição")
                btn_unsubscribe.clicked.connect(
                    lambda _, d=deck.deck_id, n=deck.name: self.on_unsubscribe(d, n)
                )
                self.table.setCellWidget(i, 6, btn_unsubscribe)
            else:
                btn_sub = QPushButton("Inscrever")
                btn_sub.clicked.connect(lambda _, d=deck.deck_id: self.on_subscribe(d))
                self.table.setCellWidget(i, 6, btn_sub)

    def _on_decks_failed(self, exc: Exception) -> None:
        self.btn_refresh.setEnabled(True)
        if isinstance(exc, ApiError):
            message = str(exc)
        else:
            message = f"Falha ao carregar baralhos: {exc}"
        QMessageBox.critical(self, "Erro", message)
            
    def on_subscribe(self, deck_id: str):
        op = QueryOp(
            parent=self,
            op=lambda _: self.api.subscribe(deck_id),
            success=lambda _: self._on_subscribed(),
        )
        op.failure(self._on_subscribe_failed)
        op.with_progress("Inscrevendo...").run_in_background()

    def _on_subscribed(self) -> None:
        QMessageBox.information(self, "Sucesso", "Inscrição realizada com sucesso.")
        self.load_decks()

    def _on_subscribe_failed(self, exc: Exception) -> None:
        if isinstance(exc, ApiError):
            message = str(exc)
        else:
            message = f"Falha ao inscrever: {exc}"
        QMessageBox.critical(self, "Erro", message)
            
    def on_install(self, deck_id: str):
        installer = DeckInstaller(self.api, self.db)
        
        def callback(success: bool, msg: str):
            if success:
                QMessageBox.information(self, "Instalação concluída", msg)
                self.load_decks()
            else:
                QMessageBox.critical(self, "Falha na instalação", msg)
                
        installer.install_deck(deck_id, callback)

    def on_unsubscribe(self, deck_id: str, deck_name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Confirmar",
            (
                f"Cancelar inscrição em {deck_name}? Os cards existentes no Anki "
                "continuarão na coleção, mas o add-on deixará de sincronizar este baralho."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        op = QueryOp(
            parent=self,
            op=lambda _: self._unsubscribe_and_forget(deck_id),
            success=lambda _: self._on_unsubscribed(),
        )
        op.failure(self._on_unsubscribe_failed)
        op.with_progress("Cancelando inscrição...").run_in_background()

    def _unsubscribe_and_forget(self, deck_id: str) -> None:
        SubscriptionManager(self.api, self.db).unsubscribe_and_forget(deck_id)

    def _on_unsubscribed(self) -> None:
        QMessageBox.information(
            self,
            "Sucesso",
            "Inscrição cancelada com sucesso. Os cards existentes no Anki foram mantidos.",
        )
        self.load_decks()

    def _on_unsubscribe_failed(self, exc: Exception) -> None:
        if isinstance(exc, ApiError):
            message = str(exc)
        else:
            message = f"Falha ao cancelar inscrição: {exc}"
        QMessageBox.critical(self, "Erro", message)

    def _format_local_status(self, local_deck, remote_release: int) -> str:
        if not local_deck:
            return "Não instalado"
        if local_deck.latest_release < remote_release:
            return "Atualização disponível"
        if local_deck.latest_release > remote_release:
            return "Local à frente"
        return "Atualizado"

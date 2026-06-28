from aqt import mw
from aqt.qt import *
from aqt.operations import QueryOp
from typing import Optional

from ..api.client import ApiClient, ApiError
from ..storage.database import DatabaseManager
from ..sync.installer import DeckInstaller
from ..services.subscription_manager import SubscriptionManager

class StatusDialog(QDialog):
    def __init__(self, api: ApiClient, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.api = api
        self.db = db
        self.setWindowTitle("Anki Concursos - Minhas inscrições")
        self.resize(1080, 420)
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Nome",
            "Cards",
            "Versão local",
            "Versão remota",
            "Status local",
            "Última sync",
            "Instalação",
            "Inscrição",
            "Histórico",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self.load_status)
        btn_layout.addWidget(self.btn_refresh)

        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        
        self.load_status()
        
    def load_status(self):
        self.btn_refresh.setEnabled(False)
        self.table.setRowCount(0)
        
        op = QueryOp(
            parent=self,
            op=lambda _: self.api.list_subscriptions(),
            success=self._on_subscriptions_loaded,
        )
        op.failure(self._on_subscriptions_failed)
        op.with_progress("Carregando inscrições...").run_in_background()

    def _on_subscriptions_loaded(self, response) -> None:
        self.btn_refresh.setEnabled(True)
        subscriptions = [
            sub for sub in response.items
            if getattr(sub, "unsubscribed_at", None) is None
        ]
        self._forget_missing_local_decks({sub.deck_id for sub in subscriptions})
        self.table.setRowCount(len(subscriptions))
        for row, sub in enumerate(subscriptions):
            local_deck = self.db.get_deck(sub.deck_id)
            local_release = str(local_deck.latest_release) if local_deck else "-"
            remote_release = str(sub.latest_release)
            status = self._format_local_status(local_deck, sub.latest_release)
            last_sync = self._format_sync_time(local_deck.last_sync) if local_deck else "Nunca"

            self.table.setItem(row, 0, QTableWidgetItem(sub.deck_name))
            self.table.setItem(row, 1, QTableWidgetItem(str(sub.active_card_count)))
            self.table.setItem(row, 2, QTableWidgetItem(local_release))
            self.table.setItem(row, 3, QTableWidgetItem(remote_release))
            self.table.setItem(row, 4, QTableWidgetItem(status))
            self.table.setItem(row, 5, QTableWidgetItem(last_sync))

            if local_deck:
                self.table.setCellWidget(row, 6, QLabel("Instalado"))
            else:
                btn_install = QPushButton("Instalar")
                btn_install.clicked.connect(lambda _, d=sub.deck_id: self.on_install(d))
                self.table.setCellWidget(row, 6, btn_install)

            btn_unsubscribe = QPushButton("Cancelar inscrição")
            btn_unsubscribe.clicked.connect(
                lambda _, d=sub.deck_id, n=sub.deck_name: self.on_unsubscribe(d, n)
            )
            self.table.setCellWidget(row, 7, btn_unsubscribe)

            btn_history = QPushButton("Ver")
            btn_history.clicked.connect(
                lambda _, d=sub.deck_id, n=sub.deck_name: self.on_history(d, n)
            )
            self.table.setCellWidget(row, 8, btn_history)

    def _on_subscriptions_failed(self, exc: Exception) -> None:
        self.btn_refresh.setEnabled(True)
        if isinstance(exc, ApiError):
            message = str(exc)
        else:
            message = f"Falha ao carregar inscrições: {exc}"
        QMessageBox.critical(self, "Erro", message)

    def on_install(self, deck_id: str) -> None:
        installer = DeckInstaller(self.api, self.db)

        def callback(success: bool, msg: str) -> None:
            if success:
                QMessageBox.information(self, "Instalação concluída", msg)
                self.load_status()
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
        self.load_status()

    def _on_unsubscribe_failed(self, exc: Exception) -> None:
        if isinstance(exc, ApiError):
            message = str(exc)
        else:
            message = f"Falha ao cancelar inscrição: {exc}"
        QMessageBox.critical(self, "Erro", message)

    def on_history(self, deck_id: str, deck_name: str) -> None:
        op = QueryOp(
            parent=self,
            op=lambda _: self.api.get_deck_releases(deck_id),
            success=lambda releases: self._on_remote_history_loaded(deck_id, deck_name, releases),
        )
        op.failure(lambda exc: self._show_local_history(deck_id, deck_name, remote_error=exc))
        op.with_progress("Carregando histórico...").run_in_background()

    def _on_remote_history_loaded(self, deck_id: str, deck_name: str, releases) -> None:
        if not releases.items:
            self._show_local_history(deck_id, deck_name)
            return

        lines = [
            deck_name,
            f"Release mais recente: {releases.latest_release}",
            "",
        ]
        for release in releases.items:
            summary = release.summary or "Sem descrição."
            lines.append(
                f"Release {release.release_number} | {self._format_sync_time(release.published_at)}"
            )
            lines.append(f"  {summary}")
            lines.append(
                f"  +{release.cards_added} ~{release.cards_updated} "
                f"-{release.cards_removed} dep.{release.cards_deprecated}"
            )
        QMessageBox.information(self, "Histórico do baralho", "\n".join(lines))

    def _show_local_history(
        self,
        deck_id: str,
        deck_name: str,
        remote_error: Optional[Exception] = None,
    ) -> None:
        local_deck = self.db.get_deck(deck_id)
        prefix = ""
        if remote_error is not None:
            prefix = "Histórico remoto indisponível. Exibindo histórico local.\n\n"
        if not local_deck:
            QMessageBox.information(
                self,
                "Histórico do baralho",
                prefix + "Histórico disponível apenas para baralhos instalados.",
            )
            return

        logs = self.db.get_sync_logs(deck_id)
        if not logs:
            QMessageBox.information(
                self,
                "Histórico do baralho",
                prefix + f"{deck_name}\n\nNenhum histórico local de sincronização encontrado.",
            )
            return

        lines = [prefix + deck_name, ""]
        for log in logs:
            status = "sucesso" if log.success else f"falha: {log.error_message or 'erro desconhecido'}"
            lines.append(
                f"{self._format_sync_time(log.synced_at)} | release {log.from_release} -> {log.to_release} | "
                f"+{log.cards_added} ~{log.cards_updated} -{log.cards_removed} dep.{log.cards_deprecated} | {status}"
            )
        QMessageBox.information(self, "Histórico do baralho", "\n".join(lines))

    def _forget_missing_local_decks(self, active_subscription_ids: set[str]) -> None:
        for deck in self.db.get_all_decks():
            if deck.deck_id not in active_subscription_ids:
                self.db.delete_deck(deck.deck_id)

    def _format_sync_time(self, sync_time: Optional[str]) -> str:
        if not sync_time:
            return "Nunca"
        if "T" in sync_time:
            return sync_time.split("T")[0] + " " + sync_time.split("T")[1][:5]
        return sync_time

    def _format_local_status(self, local_deck, remote_release: int) -> str:
        if not local_deck:
            return "Não instalado"
        if local_deck.latest_release < remote_release:
            return "Atualização disponível"
        if local_deck.latest_release > remote_release:
            return "Local à frente"
        return "Atualizado"

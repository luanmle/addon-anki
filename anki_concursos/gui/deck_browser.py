from aqt import mw
from aqt.qt import *
from ..api.client import ApiClient, ApiError
from ..storage.database import DatabaseManager
from ..sync.installer import DeckInstaller

class DeckBrowser(QDialog):
    def __init__(self, api: ApiClient, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.api = api
        self.db = db
        self.setWindowTitle("Anki Concursos - Browse Decks")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Cards", "Latest Release", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.load_decks)
        btn_layout.addWidget(btn_refresh)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        
        self.load_decks()
        
    def load_decks(self):
        try:
            resp = self.api.list_subscribable_decks()
            self.table.setRowCount(len(resp.items))
            for i, deck in enumerate(resp.items):
                self.table.setItem(i, 0, QTableWidgetItem(deck.name))
                self.table.setItem(i, 1, QTableWidgetItem(str(deck.active_card_count)))
                self.table.setItem(i, 2, QTableWidgetItem(str(deck.latest_release)))
                
                # Check local status
                local_deck = self.db.get_deck(deck.deck_id)
                
                widget = QWidget()
                l = QHBoxLayout(widget)
                l.setContentsMargins(0, 0, 0, 0)
                
                if not deck.subscribed:
                    btn_sub = QPushButton("Subscribe")
                    btn_sub.clicked.connect(lambda _, d=deck.deck_id: self.on_subscribe(d))
                    l.addWidget(btn_sub)
                elif not local_deck:
                    btn_install = QPushButton("Install")
                    btn_install.clicked.connect(lambda _, d=deck.deck_id: self.on_install(d))
                    l.addWidget(btn_install)
                else:
                    lbl = QLabel("Installed")
                    l.addWidget(lbl)
                    
                self.table.setCellWidget(i, 3, widget)
                
        except ApiError as e:
            QMessageBox.critical(self, "Error", f"Failed to load decks: {e}")
            
    def on_subscribe(self, deck_id: str):
        try:
            self.api.subscribe(deck_id)
            QMessageBox.information(self, "Success", "Subscribed successfully!")
            self.load_decks()
        except ApiError as e:
            QMessageBox.critical(self, "Error", f"Subscription failed: {e}")
            
    def on_install(self, deck_id: str):
        installer = DeckInstaller(self.api, self.db)
        
        def callback(success: bool, msg: str):
            if success:
                QMessageBox.information(self, "Installation Complete", msg)
                self.load_decks()
            else:
                QMessageBox.critical(self, "Installation Failed", msg)
                
        installer.install_deck(deck_id, callback)

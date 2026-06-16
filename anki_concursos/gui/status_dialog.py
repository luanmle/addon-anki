from aqt import mw
from aqt.qt import *
from ..storage.database import DatabaseManager

class StatusDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Anki Concursos - My Subscriptions")
        self.resize(600, 300)
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Cards", "Local Release", "Last Sync"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        
        self.load_status()
        
    def load_status(self):
        decks = self.db.get_all_decks()
        self.table.setRowCount(len(decks))
        for i, deck in enumerate(decks):
            self.table.setItem(i, 0, QTableWidgetItem(deck.deck_name))
            
            # Count local cards
            with self.db.transaction() as c:
                c.execute("SELECT count(*) FROM remote_cards WHERE deck_id = ? AND status != 'removed'", (deck.deck_id,))
                count = c.fetchone()[0]
                
            self.table.setItem(i, 1, QTableWidgetItem(str(count)))
            self.table.setItem(i, 2, QTableWidgetItem(str(deck.latest_release)))
            
            sync_time = deck.last_sync or "Never"
            if "T" in sync_time:
                sync_time = sync_time.split("T")[0] + " " + sync_time.split("T")[1][:5]
                
            self.table.setItem(i, 3, QTableWidgetItem(sync_time))

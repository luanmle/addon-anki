from aqt import mw
from aqt.qt import *
from ..api.client import ApiClient

class SettingsDialog(QDialog):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Anki Concursos - Settings")
        self.setMinimumWidth(400)
        
        self.addon_folder = __name__.split('.')[0]
        self.config = mw.addonManager.getConfig(self.addon_folder) or {}
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.api_url_input = QLineEdit(self.config.get("api_url", "http://localhost:8000"))
        form.addRow("API URL:", self.api_url_input)
        
        self.auto_sync_cb = QCheckBox()
        self.auto_sync_cb.setChecked(self.config.get("auto_sync", False))
        form.addRow("Auto-sync on startup:", self.auto_sync_cb)
        
        self.log_level_cb = QComboBox()
        self.log_level_cb.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_cb.setCurrentText(self.config.get("log_level", "INFO"))
        form.addRow("Log Level:", self.log_level_cb)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        btn_test = QPushButton("Test Connection")
        btn_test.clicked.connect(self.on_test)
        btn_layout.addWidget(btn_test)
        
        btn_clear = QPushButton("Clear Data")
        btn_clear.clicked.connect(self.on_clear)
        btn_layout.addWidget(btn_clear)
        
        layout.addLayout(btn_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def on_test(self):
        # Temporarily change API URL
        old_url = self.api.base_url
        self.api.base_url = self.api_url_input.text().strip().rstrip("/")
        try:
            try:
                self.api.get_current_user()
                QMessageBox.information(self, "Success", "Connection and Authentication successful!")
            except Exception as e:
                # If we get 401, server is there but we aren't logged in.
                if hasattr(e, 'status_code') and e.status_code == 401:
                    QMessageBox.information(self, "Success", "Connected to API (Authentication required).")
                else:
                    QMessageBox.critical(self, "Error", f"Connection failed: {e}")
        finally:
            self.api.base_url = old_url
            
    def on_clear(self):
        reply = QMessageBox.question(self, "Confirm", "Clear local database and token? This will force a full resync.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.api.auth_service.clear_token()
            db_path = mw.anki_concursos_db.db_path
            import os
            try:
                os.remove(db_path)
                QMessageBox.information(self, "Success", "Data cleared. Please restart Anki.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete DB: {e}")

    def on_accept(self):
        self.config["api_url"] = self.api_url_input.text().strip().rstrip("/")
        self.config["auto_sync"] = self.auto_sync_cb.isChecked()
        self.config["log_level"] = self.log_level_cb.currentText()
        mw.addonManager.writeConfig(self.addon_folder, self.config)
        
        self.api.base_url = self.config["api_url"]
        
        QMessageBox.information(self, "Success", "Settings saved.")
        self.accept()

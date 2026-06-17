from aqt import mw
from aqt.qt import *
from ..api.client import ApiClient

class SettingsDialog(QDialog):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Anki Concursos - Settings")
        self.setMinimumWidth(450)
        
        self.addon_folder = __name__.split('.')[0]
        self.config = mw.addonManager.getConfig(self.addon_folder) or {}
        
        layout = QVBoxLayout(self)
        
        # Resolve initial environment and display URL
        from ..consts import API_ENVIRONMENTS, DEFAULT_API_ENVIRONMENT, DEFAULT_API_URL
        self.env = self.config.get("api_environment", DEFAULT_API_ENVIRONMENT)
        self.url = self.config.get("api_url", "").strip()
        
        if self.url:
            self.display_url = self.url
            # Match preset environments if custom URL equals one of them
            matched_env = "custom"
            for env_name, env_url in API_ENVIRONMENTS.items():
                if env_url.rstrip("/") == self.url.rstrip("/"):
                    matched_env = env_name
                    break
            self.env = matched_env
        else:
            self.display_url = API_ENVIRONMENTS.get(self.env, DEFAULT_API_URL)
            
        form = QFormLayout()
        
        self.env_cb = QComboBox()
        self.env_cb.addItem("Staging", "staging")
        self.env_cb.addItem("Production", "production")
        self.env_cb.addItem("Local (Development)", "local")
        self.env_cb.addItem("Custom URL", "custom")
        
        # Select active environment in combo box
        index = self.env_cb.findData(self.env)
        if index != -1:
            self.env_cb.setCurrentIndex(index)
        else:
            self.env_cb.setCurrentIndex(self.env_cb.findData("custom"))
            
        form.addRow("Environment:", self.env_cb)
        
        self.api_url_input = QLineEdit(self.display_url)
        form.addRow("API URL:", self.api_url_input)
        
        # Connect change event
        self.env_cb.currentIndexChanged.connect(self.on_env_changed)
        
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
        
        # Set initial enabling/text state
        self.on_env_changed()
        
    def on_env_changed(self):
        from ..consts import API_ENVIRONMENTS
        selected_env = self.env_cb.currentData()
        if selected_env == "custom":
            self.api_url_input.setEnabled(True)
        else:
            self.api_url_input.setEnabled(False)
            preset_url = API_ENVIRONMENTS.get(selected_env, "")
            self.api_url_input.setText(preset_url)
            
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
        selected_env = self.env_cb.currentData()
        self.config["api_environment"] = selected_env
        
        if selected_env == "custom":
            self.config["api_url"] = self.api_url_input.text().strip().rstrip("/")
        else:
            self.config["api_url"] = ""
            
        self.config["auto_sync"] = self.auto_sync_cb.isChecked()
        self.config["log_level"] = self.log_level_cb.currentText()
        mw.addonManager.writeConfig(self.addon_folder, self.config)
        
        # Update active client base_url
        from ..consts import API_ENVIRONMENTS, DEFAULT_API_URL
        if self.config["api_url"]:
            self.api.base_url = self.config["api_url"]
        else:
            self.api.base_url = API_ENVIRONMENTS.get(selected_env, DEFAULT_API_URL).rstrip("/")
            
        QMessageBox.information(self, "Success", "Settings saved.")
        self.accept()

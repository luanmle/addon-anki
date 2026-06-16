from aqt.qt import *
from ..api.client import ApiClient, ApiError

class LoginDialog(QDialog):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Anki Concursos - Login")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        # Check current status
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        form = QFormLayout()
        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        form.addRow("Email:", self.email_input)
        form.addRow("Password:", self.password_input)
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("Login")
        self.btn_login.clicked.connect(self.on_login)
        self.btn_logout = QPushButton("Logout")
        self.btn_logout.clicked.connect(self.on_logout)
        
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_logout)
        layout.addLayout(btn_layout)
        
        self.update_ui()
        
    def update_ui(self):
        token = self.api.auth_service.get_token()
        if token:
            self.status_label.setText("Status: Logged in")
            self.btn_login.setEnabled(False)
            self.btn_logout.setEnabled(True)
        else:
            self.status_label.setText("Status: Not logged in")
            self.btn_login.setEnabled(True)
            self.btn_logout.setEnabled(False)
            
    def on_login(self):
        email = self.email_input.text().strip()
        pwd = self.password_input.text()
        
        if not email or not pwd:
            QMessageBox.warning(self, "Error", "Email and password required.")
            return
            
        try:
            self.api.login(email, pwd)
            QMessageBox.information(self, "Success", "Logged in successfully!")
            self.update_ui()
            self.accept()
        except ApiError as e:
            QMessageBox.critical(self, "Login Failed", str(e))
            
    def on_logout(self):
        self.api.auth_service.clear_token()
        QMessageBox.information(self, "Success", "Logged out.")
        self.update_ui()

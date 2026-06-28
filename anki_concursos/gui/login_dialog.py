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
        self.email_label = QLabel("Email:")
        self.email_input = QLineEdit()
        self.password_label = QLabel("Senha:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        form.addRow(self.email_label, self.email_input)
        form.addRow(self.password_label, self.password_input)
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("Entrar")
        self.btn_login.clicked.connect(self.on_login)
        self.btn_logout = QPushButton("Sair")
        self.btn_logout.clicked.connect(self.on_logout)
        
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_logout)
        layout.addLayout(btn_layout)
        
        self.update_ui()
        
    def update_ui(self):
        token = self.api.auth_service.get_token()
        if token:
            email = self.api.auth_service.get_email()
            if email:
                self.status_label.setText(f"Login ativo: {email}")
            else:
                self.status_label.setText("Login ativo. Email indisponível; saia e entre novamente para atualizar.")
            self.email_label.setVisible(False)
            self.email_input.setVisible(False)
            self.password_label.setVisible(False)
            self.password_input.setVisible(False)
            self.btn_login.setEnabled(False)
            self.btn_login.setVisible(False)
            self.btn_logout.setEnabled(True)
            self.btn_logout.setVisible(True)
        else:
            self.status_label.setText("Informe email e senha para entrar.")
            self.email_label.setVisible(True)
            self.email_input.setVisible(True)
            self.password_label.setVisible(True)
            self.password_input.setVisible(True)
            self.btn_login.setEnabled(True)
            self.btn_login.setVisible(True)
            self.btn_logout.setEnabled(False)
            self.btn_logout.setVisible(False)
            self.email_input.setFocus()
            
    def on_login(self):
        email = self.email_input.text().strip()
        pwd = self.password_input.text()
        
        if not email or not pwd:
            QMessageBox.warning(self, "Erro", "Email e senha são obrigatórios.")
            return
            
        try:
            self.api.login(email, pwd)
            QMessageBox.information(self, "Sucesso", "Login realizado com sucesso.")
            self.update_ui()
            self.accept()
        except ApiError as e:
            QMessageBox.critical(self, "Falha no login", str(e))
            
    def on_logout(self):
        self.api.auth_service.clear_token()
        self.password_input.clear()
        self.update_ui()

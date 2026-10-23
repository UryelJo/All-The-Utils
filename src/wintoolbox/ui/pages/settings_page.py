"""
Página de Configurações da Aplicação (Settings Page).
Gerencia tema, comportamento da bandeja, atalho global, SendTo, backup/restauração e tokens de API centralizados.
"""
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.context_menu import install_sendto, is_sendto_installed, uninstall_sendto
from wintoolbox.core.history import clear_history
from wintoolbox.core.settings import (
    export_settings, get_all_api_tokens, import_settings,
    load_settings, save_settings, set_api_token
)
from wintoolbox.ui.theme import apply_theme

PREDEFINED_SERVICES = [
    ("virustotal", "VirusTotal (Varredura e Reputação de Arquivos)"),
    ("openai", "OpenAI / ChatGPT (Modelos de Linguagem)"),
    ("anthropic", "Anthropic Claude (Modelos de Linguagem)"),
    ("gemini", "Google Gemini (Modelos de Linguagem)"),
    ("github", "GitHub (Personal Access Token)"),
    ("huggingface", "Hugging Face (Modelos e Embeddings)"),
    ("weather", "OpenWeatherMap (Previsão do Tempo)")
]

class SettingsPage(QWidget):
    """Página de configurações do sistema."""
    settings_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.token_inputs: Dict[str, QLineEdit] = {}
        self.token_rows_container: Optional[QVBoxLayout] = None
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Cabeçalho
        lbl_title = QLabel("Configurações do All the Utils")
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel("Preferências de inicialização, comportamento da bandeja, atalhos, tokens de API e backup.")
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # 1. Cartão: Aparência
        card_theme = QFrame()
        card_theme.setProperty("class", "card")
        l_theme = QVBoxLayout(card_theme)
        l_theme.setContentsMargins(14, 12, 14, 12)
        l_theme.setSpacing(8)

        lbl_sec1 = QLabel("Aparência")
        lbl_sec1.setStyleSheet("font-weight: 600; font-size: 13px;")
        l_theme.addWidget(lbl_sec1)

        row_theme = QHBoxLayout()
        row_theme.addWidget(QLabel("Tema visual:"))
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(["Escuro", "Claro"])
        self.cmb_theme.currentTextChanged.connect(self._on_theme_changed)
        row_theme.addWidget(self.cmb_theme)
        row_theme.addStretch()
        l_theme.addLayout(row_theme)
        layout.addWidget(card_theme)

        # 2. Cartão: Comportamento do Sistema
        card_sys = QFrame()
        card_sys.setProperty("class", "card")
        l_sys = QVBoxLayout(card_sys)
        l_sys.setContentsMargins(14, 12, 14, 12)
        l_sys.setSpacing(10)

        lbl_sec2 = QLabel("Comportamento e Integração")
        lbl_sec2.setStyleSheet("font-weight: 600; font-size: 13px;")
        l_sys.addWidget(lbl_sec2)

        self.chk_tray = QCheckBox("Minimizar para a bandeja do sistema ao fechar a janela")
        self.chk_tray.toggled.connect(self._save_checkboxes)
        l_sys.addWidget(self.chk_tray)

        self.chk_notif = QCheckBox("Exibir notificações no Windows ao finalizar tarefas longas")
        self.chk_notif.toggled.connect(self._save_checkboxes)
        l_sys.addWidget(self.chk_notif)

        self.chk_hotkey = QCheckBox("Ativar atalho global do Windows (Ctrl+Alt+T) para abrir a toolbox de qualquer lugar")
        self.chk_hotkey.toggled.connect(self._save_checkboxes)
        l_sys.addWidget(self.chk_hotkey)

        # Botão SendTo
        row_sendto = QHBoxLayout()
        self.lbl_sendto_status = QLabel("Menu 'Enviar para' do Windows:")
        row_sendto.addWidget(self.lbl_sendto_status)

        self.btn_sendto = QPushButton("Integrar ao Menu Enviar Para")
        self.btn_sendto.clicked.connect(self._toggle_sendto)
        row_sendto.addWidget(self.btn_sendto)
        row_sendto.addStretch()
        l_sys.addLayout(row_sendto)

        layout.addWidget(card_sys)

        # 3. Cartão: Chaves de API e Tokens de Serviços (NOVO)
        card_tokens = QFrame()
        card_tokens.setProperty("class", "card")
        l_tok = QVBoxLayout(card_tokens)
        l_tok.setContentsMargins(14, 12, 14, 12)
        l_tok.setSpacing(10)

        lbl_sec_tok = QLabel("Chaves de API e Tokens de Serviços")
        lbl_sec_tok.setStyleSheet("font-weight: 600; font-size: 13px;")
        l_tok.addWidget(lbl_sec_tok)

        lbl_tok_sub = QLabel(
            "Centralize aqui suas chaves de API e tokens para desbloquear ferramentas integradas com serviços externos.\n"
            "As chaves são salvas localmente nas preferências da sua máquina."
        )
        lbl_tok_sub.setProperty("class", "secondary")
        l_tok.addWidget(lbl_tok_sub)

        # Container dos campos de tokens
        self.token_rows_container = QVBoxLayout()
        self.token_rows_container.setSpacing(8)
        l_tok.addLayout(self.token_rows_container)

        # Ações de Tokens
        row_tok_acts = QHBoxLayout()
        btn_add_tok = QPushButton("Adicionar Outro Serviço...")
        btn_add_tok.clicked.connect(self._add_custom_token_dialog)
        row_tok_acts.addWidget(btn_add_tok)

        btn_save_toks = QPushButton("Salvar Chaves e Tokens")
        btn_save_toks.setProperty("class", "primary")
        btn_save_toks.clicked.connect(self._save_tokens)
        row_tok_acts.addWidget(btn_save_toks)
        row_tok_acts.addStretch()
        l_tok.addLayout(row_tok_acts)

        layout.addWidget(card_tokens)

        # 4. Cartão: Backup e Restauração
        card_backup = QFrame()
        card_backup.setProperty("class", "card")
        l_bak = QVBoxLayout(card_backup)
        l_bak.setContentsMargins(14, 12, 14, 12)
        l_bak.setSpacing(10)

        lbl_sec3 = QLabel("Backup, Restauração e Dados")
        lbl_sec3.setStyleSheet("font-weight: 600; font-size: 13px;")
        l_bak.addWidget(lbl_sec3)

        row_bak = QHBoxLayout()
        btn_export = QPushButton("Fazer Backup das Configurações (JSON)...")
        btn_export.clicked.connect(self._on_export)
        row_bak.addWidget(btn_export)

        btn_import = QPushButton("Restaurar Configurações...")
        btn_import.clicked.connect(self._on_import)
        row_bak.addWidget(btn_import)

        btn_clear_hist = QPushButton("Limpar Histórico de Tarefas")
        btn_clear_hist.clicked.connect(self._on_clear_history)
        row_bak.addWidget(btn_clear_hist)

        row_bak.addStretch()
        l_bak.addLayout(row_bak)
        layout.addWidget(card_backup)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _render_token_fields(self):
        """Renderiza os campos de tokens cadastrados e pré-definidos."""
        # Limpa layout anterior
        while self.token_rows_container.count():
            item = self.token_rows_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_sub_layout(item.layout())

        self.token_inputs.clear()
        saved_tokens = get_all_api_tokens()

        # Mapeamento para exibir os pré-definidos primeiro
        seen = set()
        for svc_id, label in PREDEFINED_SERVICES:
            seen.add(svc_id)
            val = saved_tokens.get(svc_id, "")
            self._create_token_row(svc_id, label, val)

        # Adiciona tokens customizados adicionados pelo usuário
        for svc_id, val in saved_tokens.items():
            if svc_id not in seen:
                self._create_token_row(svc_id, f"Personalizado ({svc_id})", val)

    def _clear_sub_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_sub_layout(item.layout())

    def _create_token_row(self, service_id: str, label_text: str, initial_value: str = ""):
        row = QHBoxLayout()
        lbl = QLabel(f"{label_text}:")
        lbl.setFixedWidth(260)
        lbl.setStyleSheet("font-weight: 500;")
        row.addWidget(lbl)

        txt = QLineEdit(initial_value)
        txt.setEchoMode(QLineEdit.Password)
        txt.setPlaceholderText("Cole o token ou chave de API aqui...")
        row.addWidget(txt, stretch=1)

        btn_eye = QPushButton("Mostrar")
        btn_eye.setFixedWidth(65)
        btn_eye.clicked.connect(lambda _, f=txt, b=btn_eye: self._toggle_echo(f, b))
        row.addWidget(btn_eye)

        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(txt.clear)
        row.addWidget(btn_clear)

        self.token_inputs[service_id] = txt
        self.token_rows_container.addLayout(row)

    def _toggle_echo(self, line_edit: QLineEdit, button: QPushButton):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            button.setText("Ocultar")
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            button.setText("Mostrar")

    def _add_custom_token_dialog(self):
        svc_name, ok = QInputDialog.getText(
            self,
            "Adicionar Chave de API",
            "Informe o identificador ou nome do serviço (ex: shodan, deepl, gemini):"
        )
        if ok and svc_name.strip():
            clean_id = svc_name.strip().lower()
            if clean_id in self.token_inputs:
                QMessageBox.warning(self, "Aviso", f"O serviço '{clean_id}' já está presente na lista.")
                return
            self._create_token_row(clean_id, f"Personalizado ({clean_id})", "")

    def _save_tokens(self):
        for svc_id, line_edit in self.token_inputs.items():
            set_api_token(svc_id, line_edit.text())
        QMessageBox.information(
            self,
            "Tokens Salvos",
            "Chaves de API e tokens salvos com sucesso nas preferências do sistema!"
        )

    def _load_values(self):
        st = load_settings()
        self.cmb_theme.setCurrentText("Escuro" if st.get("theme", "dark") == "dark" else "Claro")
        self.chk_tray.setChecked(st.get("minimize_to_tray", True))
        self.chk_notif.setChecked(st.get("notifications_enabled", True))
        self.chk_hotkey.setChecked(st.get("global_hotkey_enabled", True))
        self._update_sendto_ui()
        self._render_token_fields()

    def _update_sendto_ui(self):
        installed = is_sendto_installed()
        if installed:
            self.lbl_sendto_status.setText("Menu 'Enviar para' do Windows: Ativado")
            self.btn_sendto.setText("Remover do Menu Enviar Para")
        else:
            self.lbl_sendto_status.setText("Menu 'Enviar para' do Windows: Desativado")
            self.btn_sendto.setText("Adicionar ao Menu Enviar Para")

    def _toggle_sendto(self):
        if is_sendto_installed():
            uninstall_sendto()
            QMessageBox.information(self, "Menu de Contexto", "Atalho removido da pasta 'Enviar para'.")
        else:
            install_sendto()
            QMessageBox.information(self, "Menu de Contexto", "WinToolbox adicionado à pasta 'Enviar para' com sucesso!")
        self._update_sendto_ui()

    def _save_checkboxes(self):
        st = load_settings()
        st["minimize_to_tray"] = self.chk_tray.isChecked()
        st["notifications_enabled"] = self.chk_notif.isChecked()
        st["global_hotkey_enabled"] = self.chk_hotkey.isChecked()
        save_settings(st)
        self.settings_changed.emit()

    def _on_theme_changed(self, text: str):
        mode = "dark" if text == "Escuro" else "light"
        from PySide6.QtWidgets import QApplication
        apply_theme(QApplication.instance(), mode)
        st = load_settings()
        st["theme"] = mode
        save_settings(st)

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Configurações", "wintoolbox_config.json", "Arquivo JSON (*.json)")
        if path:
            if export_settings(Path(path)):
                QMessageBox.information(self, "Sucesso", "Backup das configurações exportado com sucesso!")
            else:
                QMessageBox.critical(self, "Erro", "Falha ao exportar backup.")

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restaurar Configurações", "", "Arquivo JSON (*.json)")
        if path:
            if import_settings(Path(path)):
                self._load_values()
                self.settings_changed.emit()
                QMessageBox.information(self, "Sucesso", "Configurações restauradas com sucesso!")
            else:
                QMessageBox.critical(self, "Erro", "Arquivo de configurações inválido.")

    def _on_clear_history(self):
        res = QMessageBox.question(self, "Confirmar", "Deseja realmente limpar todo o histórico de execuções?", QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            clear_history()
            QMessageBox.information(self, "Histórico", "Histórico de execuções limpo com sucesso.")

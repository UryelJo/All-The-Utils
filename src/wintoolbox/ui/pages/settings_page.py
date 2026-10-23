"""
Página de Configurações da Aplicação (Settings Page) — Padrão WinUI 3 / PowerToys.
Gerencia tema (Escuro/Claro/Sistema), cor de destaque, personalização da tela inicial,
comportamento da bandeja, atalho global, SendTo, backup/restauração e cofre de tokens de API.
"""
from pathlib import Path
from typing import Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.context_menu import install_sendto, is_sendto_installed, uninstall_sendto
from wintoolbox.core.history import clear_history
from wintoolbox.core.settings import (
    export_settings, get_all_api_tokens, import_settings,
    load_settings, save_settings, set_api_token
)
from wintoolbox.ui.pages.home_page import HomeCustomizationDialog
from wintoolbox.ui.theme import ACCENT_PRESETS, apply_theme
from wintoolbox.ui.widgets.setting_card import SettingCard
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.toggle_switch import ToggleSwitch

PREDEFINED_SERVICES = [
    ("virustotal", "VirusTotal (Varredura e Reputação de Arquivos)"),
    ("openai", "OpenAI / ChatGPT (Modelos de Linguagem)"),
    ("anthropic", "Anthropic Claude (Modelos de Linguagem)"),
    ("gemini", "Google Gemini (Modelos de Linguagem)"),
    ("github", "GitHub (Personal Access Token)"),
    ("huggingface", "Hugging Face (Modelos e Embeddings)"),
    ("weather", "OpenWeatherMap (Previsão do Tempo)"),
]


class SettingsPage(QWidget):
    """Página de configurações do sistema em cartões Fluent."""
    settings_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.token_inputs: Dict[str, QLineEdit] = {}
        self.token_rows_container: Optional[QVBoxLayout] = None
        self._loading = False
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 28)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel("Configurações do All the Utils")
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "Personalize a aparência, a tela inicial, integrações com o Windows, chaves de API e backup."
        )
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # ── SEÇÃO 1: Aparência e Personalização ──
        lbl_sec1 = QLabel("Aparência e Tela Inicial")
        lbl_sec1.setProperty("class", "section-title")
        layout.addWidget(lbl_sec1)

        # Tema Visual
        self.cmb_theme = QComboBox()
        self.cmb_theme.setMinimumWidth(210)
        self.cmb_theme.addItems(["Escuro", "Claro", "Automático (Sistema)"])
        self.cmb_theme.currentTextChanged.connect(self._on_appearance_changed)
        layout.addWidget(SettingCard(
            "eye",
            "Tema Visual da Aplicação",
            "Alterne entre o modo escuro, modo claro ou acompanhe automaticamente o tema do Windows.",
            self.cmb_theme,
        ))

        # Cor de Destaque
        self.cmb_accent = QComboBox()
        self.cmb_accent.setMinimumWidth(210)
        for hex_val, label in ACCENT_PRESETS:
            self.cmb_accent.addItem(label, hex_val)
        self.cmb_accent.currentIndexChanged.connect(self._on_appearance_changed)
        layout.addWidget(SettingCard(
            "customize",
            "Cor de Destaque (Accent Color)",
            "Utilize a cor de destaque nativa do Windows 11 (DWM) ou escolha uma paleta própria.",
            self.cmb_accent,
        ))

        # Personalização da Tela Inicial
        btn_home_cfg = QPushButton("Personalizar Tela Inicial...")
        btn_home_cfg.clicked.connect(self._open_home_customization)
        layout.addWidget(SettingCard(
            "home",
            "Layout da Tela Inicial (Dashboard)",
            "Configure a exibição da Smart Dropzone, Mini-Monitor de Hardware, Favoritos e densidade dos cards.",
            btn_home_cfg,
        ))

        # ── SEÇÃO 2: Comportamento e Integração ──
        lbl_sec2 = QLabel("Comportamento e Integração com o Windows")
        lbl_sec2.setProperty("class", "section-title")
        layout.addWidget(lbl_sec2)

        self.chk_tray = ToggleSwitch()
        self.chk_tray.toggled.connect(self._save_checkboxes)
        layout.addWidget(SettingCard(
            "pin",
            "Minimizar para a Bandeja do Sistema",
            "Mantém o All the Utils ativo em segundo plano na bandeja ao fechar a janela principal.",
            self.chk_tray,
        ))

        self.chk_notif = ToggleSwitch()
        self.chk_notif.toggled.connect(self._save_checkboxes)
        layout.addWidget(SettingCard(
            "info",
            "Notificações Nativas do Windows",
            "Exibe alertas na área de notificação ao concluir lotes ou tarefas demoradas.",
            self.chk_notif,
        ))

        self.chk_hotkey = ToggleSwitch()
        self.chk_hotkey.toggled.connect(self._save_checkboxes)
        layout.addWidget(SettingCard(
            "bolt",
            "Atalho Global (Ctrl+Alt+T)",
            "Permite trazer a janela do All the Utils para a frente a partir de qualquer aplicativo.",
            self.chk_hotkey,
        ))

        self.btn_sendto = QPushButton("Integrar ao Menu Enviar Para")
        self.btn_sendto.clicked.connect(self._toggle_sendto)
        self.card_sendto = SettingCard(
            "folder_open",
            "Menu de Contexto 'Enviar para' do Windows Explorer",
            "Adiciona um atalho no menu de botão direito do Explorer para enviar arquivos direto ao app.",
            self.btn_sendto,
        )
        self.lbl_sendto_status = self.card_sendto.lbl_title
        layout.addWidget(self.card_sendto)

        # ── SEÇÃO 3: Chaves de API e Tokens de Serviços ──
        lbl_sec3 = QLabel("Cofre de Chaves de API e Tokens")
        lbl_sec3.setProperty("class", "section-title")
        layout.addWidget(lbl_sec3)

        card_tokens = QFrame()
        card_tokens.setProperty("class", "card")
        l_tok = QVBoxLayout(card_tokens)
        l_tok.setContentsMargins(16, 14, 16, 14)
        l_tok.setSpacing(10)

        lbl_tok_sub = QLabel(
            "Centralize suas chaves de API para ferramentas integradas com serviços externos. "
            "Armazenadas localmente em %APPDATA%."
        )
        lbl_tok_sub.setProperty("class", "secondary")
        lbl_tok_sub.setWordWrap(True)
        l_tok.addWidget(lbl_tok_sub)

        self.token_rows_container = QVBoxLayout()
        self.token_rows_container.setSpacing(8)
        l_tok.addLayout(self.token_rows_container)

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

        # ── SEÇÃO 4: Backup, Restauração e Dados ──
        lbl_sec4 = QLabel("Backup, Restauração e Histórico")
        lbl_sec4.setProperty("class", "section-title")
        layout.addWidget(lbl_sec4)

        card_backup = QFrame()
        card_backup.setProperty("class", "card")
        l_bak = QHBoxLayout(card_backup)
        l_bak.setContentsMargins(16, 12, 16, 12)
        l_bak.setSpacing(10)

        btn_export = QPushButton("Exportar Backup (JSON)...")
        btn_export.clicked.connect(self._on_export)
        l_bak.addWidget(btn_export)

        btn_import = QPushButton("Restaurar Backup...")
        btn_import.clicked.connect(self._on_import)
        l_bak.addWidget(btn_import)

        btn_clear_hist = QPushButton("Limpar Histórico de Tarefas")
        btn_clear_hist.clicked.connect(self._on_clear_history)
        l_bak.addWidget(btn_clear_hist)

        l_bak.addStretch()
        layout.addWidget(card_backup)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _open_home_customization(self) -> None:
        dlg = HomeCustomizationDialog(self)
        dlg.layout_updated.connect(self.settings_changed.emit)
        dlg.exec()

    def _render_token_fields(self) -> None:
        while self.token_rows_container.count():
            item = self.token_rows_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_sub_layout(item.layout())

        self.token_inputs.clear()
        saved_tokens = get_all_api_tokens()

        seen = set()
        for svc_id, label in PREDEFINED_SERVICES:
            seen.add(svc_id)
            val = saved_tokens.get(svc_id, "")
            self._create_token_row(svc_id, label, val)

        for svc_id, val in saved_tokens.items():
            if svc_id not in seen:
                self._create_token_row(svc_id, f"Personalizado ({svc_id})", val)

    def _clear_sub_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_sub_layout(item.layout())

    def _create_token_row(self, service_id: str, label_text: str, initial_value: str = "") -> None:
        row = QHBoxLayout()
        lbl = QLabel(f"{label_text}:")
        lbl.setFixedWidth(310)
        lbl.setStyleSheet("font-weight: 500;")
        row.addWidget(lbl)

        txt = QLineEdit(initial_value)
        txt.setEchoMode(QLineEdit.Password)
        txt.setPlaceholderText("Cole o token ou chave de API aqui...")
        row.addWidget(txt, stretch=1)

        btn_eye = QPushButton("Mostrar")
        btn_eye.setMinimumWidth(80)
        btn_eye.clicked.connect(lambda _, f=txt, b=btn_eye: self._toggle_echo(f, b))
        row.addWidget(btn_eye)

        btn_clear = QPushButton("Limpar")
        btn_clear.setMinimumWidth(75)
        btn_clear.clicked.connect(txt.clear)
        row.addWidget(btn_clear)

        self.token_inputs[service_id] = txt
        self.token_rows_container.addLayout(row)

    def _toggle_echo(self, line_edit: QLineEdit, button: QPushButton) -> None:
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            button.setText("Ocultar")
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            button.setText("Mostrar")

    def _add_custom_token_dialog(self) -> None:
        svc_name, ok = QInputDialog.getText(
            self,
            "Adicionar Chave de API",
            "Informe o identificador ou nome do serviço (ex: shodan, deepl, gemini):",
        )
        if ok and svc_name.strip():
            clean_id = svc_name.strip().lower()
            if clean_id in self.token_inputs:
                show_toast(self, "Serviço Existente", f"O serviço '{clean_id}' já está na lista.", kind="warning")
                return
            self._create_token_row(clean_id, f"Personalizado ({clean_id})", "")

    def _save_tokens(self) -> None:
        for svc_id, line_edit in self.token_inputs.items():
            set_api_token(svc_id, line_edit.text())
        show_toast(
            self,
            "Tokens Salvos",
            "Chaves de API e tokens salvos com segurança nas preferências locais.",
            kind="success",
        )

    def _load_values(self) -> None:
        self._loading = True
        st = load_settings()
        theme_val = st.get("theme", "dark")
        if theme_val == "light":
            self.cmb_theme.setCurrentText("Claro")
        elif theme_val == "system":
            self.cmb_theme.setCurrentText("Automático (Sistema)")
        else:
            self.cmb_theme.setCurrentText("Escuro")

        accent_val = st.get("accent_override", "")
        idx_acc = self.cmb_accent.findData(accent_val)
        self.cmb_accent.setCurrentIndex(idx_acc if idx_acc >= 0 else 0)

        self.chk_tray.setChecked(st.get("minimize_to_tray", True))
        self.chk_notif.setChecked(st.get("notifications_enabled", True))
        self.chk_hotkey.setChecked(st.get("global_hotkey_enabled", True))
        self._update_sendto_ui()
        self._render_token_fields()
        self._loading = False

    def _update_sendto_ui(self) -> None:
        installed = is_sendto_installed()
        if installed:
            self.card_sendto.set_title("Menu 'Enviar para' do Windows: Ativado")
            self.btn_sendto.setText("Remover do Menu Enviar Para")
        else:
            self.card_sendto.set_title("Menu 'Enviar para' do Windows: Desativado")
            self.btn_sendto.setText("Adicionar ao Menu Enviar Para")

    def _toggle_sendto(self) -> None:
        if is_sendto_installed():
            uninstall_sendto()
            show_toast(self, "Menu Enviar Para", "Atalho removido da pasta 'Enviar para'.", kind="info")
        else:
            install_sendto()
            show_toast(self, "Menu Enviar Para", "Atalho adicionado ao menu 'Enviar para' com sucesso!", kind="success")
        self._update_sendto_ui()

    def _save_checkboxes(self) -> None:
        if self._loading:
            return
        st = load_settings()
        st["minimize_to_tray"] = self.chk_tray.isChecked()
        st["notifications_enabled"] = self.chk_notif.isChecked()
        st["global_hotkey_enabled"] = self.chk_hotkey.isChecked()
        save_settings(st)
        self.settings_changed.emit()

    def _on_appearance_changed(self, *args) -> None:
        if self._loading:
            return
        theme_text = self.cmb_theme.currentText()
        if theme_text == "Claro":
            mode = "light"
        elif "Automático" in theme_text:
            mode = "system"
        else:
            mode = "dark"

        accent_override = self.cmb_accent.currentData() or ""
        st = load_settings()
        st["theme"] = mode
        st["accent_override"] = accent_override
        save_settings(st)

        apply_theme(QApplication.instance(), mode=mode, accent_override=accent_override)
        self.settings_changed.emit()
        show_toast(self, "Aparência Atualizada", "Tema e paleta aplicados com sucesso.", kind="success", duration_ms=2200)

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Configurações", "wintoolbox_config.json", "Arquivo JSON (*.json)"
        )
        if path:
            if export_settings(Path(path)):
                show_toast(self, "Backup Concluído", "Configurações exportadas com sucesso.", kind="success")
            else:
                show_toast(self, "Erro no Backup", "Falha ao exportar arquivo JSON.", kind="error")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Restaurar Configurações", "", "Arquivo JSON (*.json)"
        )
        if path:
            if import_settings(Path(path)):
                self._load_values()
                st = load_settings()
                apply_theme(QApplication.instance(), mode=st.get("theme", "dark"), accent_override=st.get("accent_override", ""))
                self.settings_changed.emit()
                show_toast(self, "Configurações Restauradas", "Preferências importadas com sucesso!", kind="success")
            else:
                show_toast(self, "Erro na Restauração", "Arquivo de configurações inválido.", kind="error")

    def _on_clear_history(self) -> None:
        res = QMessageBox.question(
            self,
            "Confirmar",
            "Deseja realmente limpar todo o histórico de execuções?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            clear_history()
            show_toast(self, "Histórico Limpo", "Todos os registros de tarefas foram removidos.", kind="info")

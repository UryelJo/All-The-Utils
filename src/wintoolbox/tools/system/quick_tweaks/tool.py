"""
Ferramenta: Ajustes Rápidos do Windows (Quick Tweaks).
Interface para alternar opções frequentes do sistema com um clique (arquivos ocultos, extensões, modo escuro, etc.).
"""
from typing import Optional
from PySide6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.quick_tweaks.logic import (
    apply_quick_tweak, get_quick_tweaks_state, restart_windows_explorer
)


@register
class QuickTweaksTool(Tool):
    id = "system.quick_tweaks"
    name = "Ajustes Rápidos do Windows"
    category = "Sistema"
    description = "Alternância em 1 clique de arquivos ocultos, extensões de arquivos, modo escuro e ícones do sistema"
    keywords = ["tweaks", "ajustes", "ocultos", "extensão", "escuro", "dark", "explorer", "personalização"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return QuickTweaksView(self, parent)


class QuickTweaksView(QWidget):
    def __init__(self, tool: QuickTweaksTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()
        self._load_current_states()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # 1. Opções do Explorador de Arquivos
        grp_explorer = QGroupBox("Explorador de Arquivos e Área de Trabalho")
        exp_layout = QVBoxLayout(grp_explorer)
        exp_layout.setSpacing(10)

        self.chk_hidden = QCheckBox("Exibir arquivos, pastas e unidades ocultas no Windows")
        exp_layout.addWidget(self.chk_hidden)

        self.chk_extensions = QCheckBox("Exibir extensões de tipos de arquivo conhecidos (.exe, .txt, .pdf, etc.)")
        exp_layout.addWidget(self.chk_extensions)

        self.chk_this_pc = QCheckBox("Exibir o ícone 'Este Computador' na Área de Trabalho")
        exp_layout.addWidget(self.chk_this_pc)

        self.chk_recent = QCheckBox("Ocultar arquivos recentes e pastas frequentes no Acesso Rápido")
        exp_layout.addWidget(self.chk_recent)

        layout.addWidget(grp_explorer)

        # 2. Personalização Visual
        grp_theme = QGroupBox("Aparência e Cores do Sistema")
        thm_layout = QVBoxLayout(grp_theme)
        thm_layout.setSpacing(10)

        self.chk_dark_apps = QCheckBox("Modo Escuro para Aplicativos do Windows")
        thm_layout.addWidget(self.chk_dark_apps)

        self.chk_dark_sys = QCheckBox("Modo Escuro para o Sistema Operacional (Barra de Tarefas e Menu Iniciar)")
        thm_layout.addWidget(self.chk_dark_sys)

        layout.addWidget(grp_theme)

        # Barra de Ações
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        self.btn_apply = QPushButton("Aplicar Ajustes Selecionados")
        self.btn_apply.setProperty("class", "primary")
        self.btn_apply.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_apply.clicked.connect(self._on_apply_tweaks)
        btn_bar.addWidget(self.btn_apply)

        self.btn_restart_exp = QPushButton("Reiniciar Windows Explorer")
        self.btn_restart_exp.clicked.connect(self._on_restart_explorer)
        btn_bar.addWidget(self.btn_restart_exp)

        btn_bar.addStretch()

        self.btn_refresh = QPushButton("Recarregar do Sistema")
        self.btn_refresh.clicked.connect(self._load_current_states)
        btn_bar.addWidget(self.btn_refresh)

        layout.addLayout(btn_bar)

        info_lbl = QLabel("Nota: Algumas alterações visuais de pastas requerem reiniciar o Windows Explorer para entrar em vigor imediatamente.")
        info_lbl.setStyleSheet("color: #888890; font-size: 11px;")
        layout.addWidget(info_lbl)

        layout.addStretch()

    def _load_current_states(self):
        st = get_quick_tweaks_state()
        self.chk_hidden.setChecked(st.get("show_hidden_files", False))
        self.chk_extensions.setChecked(st.get("show_file_extensions", False))
        self.chk_this_pc.setChecked(st.get("show_this_pc_desktop", False))
        self.chk_recent.setChecked(st.get("hide_quick_access_recent", False))
        self.chk_dark_apps.setChecked(st.get("dark_mode_apps", True))
        self.chk_dark_sys.setChecked(st.get("dark_mode_system", True))

    def _on_apply_tweaks(self):
        targets = [
            ("show_hidden_files", self.chk_hidden.isChecked()),
            ("show_file_extensions", self.chk_extensions.isChecked()),
            ("show_this_pc_desktop", self.chk_this_pc.isChecked()),
            ("hide_quick_access_recent", self.chk_recent.isChecked()),
            ("dark_mode_apps", self.chk_dark_apps.isChecked()),
            ("dark_mode_system", self.chk_dark_sys.isChecked()),
        ]

        errors = []
        for tweak_id, val in targets:
            ok, msg = apply_quick_tweak(tweak_id, val)
            if not ok:
                errors.append(msg)

        if not errors:
            ans = QMessageBox.question(
                self,
                "Ajustes Aplicados",
                "Todos os ajustes selecionados foram gravados com sucesso no registro!\n\nDeseja reiniciar o Windows Explorer agora para atualizar as janelas?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ans == QMessageBox.Yes:
                self._on_restart_explorer()
        else:
            QMessageBox.warning(self, "Aviso", f"Alguns ajustes falharam:\n" + "\n".join(errors))

    def _on_restart_explorer(self):
        ok, msg = restart_windows_explorer()
        if ok:
            QMessageBox.information(self, "Explorer", msg)
        else:
            QMessageBox.critical(self, "Erro", msg)

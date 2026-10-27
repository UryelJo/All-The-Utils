"""
Interface de usuário para a ferramenta Gerador de .gitignore e Licenças Open Source.
"""
import datetime
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.gitignore_license.logic import (
    GITIGNORE_TEMPLATES,
    compose_gitignore,
    generate_license,
)


@register
class GitignoreLicenseTool(Tool):
    """Assistente de geração rápida de arquivos .gitignore multicamada e licenças de software."""

    id = "dev.gitignore_license"
    name = "Gerador de .gitignore e Licenças Open Source"
    description = "Cria arquivos .gitignore combinados por tecnologia e templates oficiais de licenças (MIT, Apache, GPL, BSD)."
    category = "Desenvolvimento"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Gerador de .gitignore e Licenças Open Source")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Configure a base de novos repositórios com regras especializadas de exclusão de artefatos "
            "e termos de licença de código aberto prontos para publicação."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        tabs = QTabWidget()

        # Aba 1: .gitignore
        tab_gi = QWidget()
        v_gi = QVBoxLayout(tab_gi)

        spl_gi = QSplitter(Qt.Orientation.Horizontal)

        # Coluna de Opções
        w_gi_opts = QWidget()
        v_gi_opts = QVBoxLayout(w_gi_opts)
        v_gi_opts.setContentsMargins(0, 0, 0, 0)

        v_gi_opts.addWidget(QLabel("Selecione as Tecnologias do Projeto:"))
        self.gi_checkboxes: List[QCheckBox] = []
        for name in GITIGNORE_TEMPLATES.keys():
            chk = QCheckBox(name)
            if name in ["Python", "Windows / SO"]:
                chk.setChecked(True)
            chk.toggled.connect(self._update_gitignore)
            self.gi_checkboxes.append(chk)
            v_gi_opts.addWidget(chk)

        v_gi_opts.addSpacing(10)
        v_gi_opts.addWidget(QLabel("Regras Adicionais Personalizadas:"))
        self.txt_gi_custom = QTextEdit()
        self.txt_gi_custom.setPlaceholderText("Ex:\nsecrets.json\n*.sqlite3")
        self.txt_gi_custom.textChanged.connect(self._update_gitignore)
        v_gi_opts.addWidget(self.txt_gi_custom)

        spl_gi.addWidget(w_gi_opts)

        # Coluna de Pré-visualização
        w_gi_prev = QWidget()
        v_gi_prev = QVBoxLayout(w_gi_prev)
        v_gi_prev.setContentsMargins(0, 0, 0, 0)
        v_gi_prev.addWidget(QLabel("Pré-visualização do .gitignore:"))

        self.txt_gi_output = QTextEdit()
        self.txt_gi_output.setFont(QFont("Consolas", 10))
        v_gi_prev.addWidget(self.txt_gi_output)

        h_gi_btns = QHBoxLayout()
        btn_copy_gi = QPushButton("Copiar para Área de Transferência")
        btn_copy_gi.clicked.connect(lambda: self._copy_text(self.txt_gi_output.toPlainText()))
        btn_save_gi = QPushButton("Salvar Arquivo .gitignore...")
        btn_save_gi.clicked.connect(self._save_gitignore)

        h_gi_btns.addStretch()
        h_gi_btns.addWidget(btn_copy_gi)
        h_gi_btns.addWidget(btn_save_gi)
        v_gi_prev.addLayout(h_gi_btns)

        spl_gi.addWidget(w_gi_prev)
        v_gi.addWidget(spl_gi)
        tabs.addTab(tab_gi, "Gerador de .gitignore")

        # Aba 2: Licença Open Source
        tab_lic = QWidget()
        v_lic = QVBoxLayout(tab_lic)

        lic_form = QFrame()
        lic_form.setFrameShape(QFrame.Shape.StyledPanel)
        grid_lic = QGridLayout(lic_form)

        grid_lic.addWidget(QLabel("Modelo de Licença:"), 0, 0)
        self.combo_lic = QComboBox()
        self.combo_lic.addItem("MIT License (Mais Popular e Permissiva)", "MIT")
        self.combo_lic.addItem("Apache License 2.0 (Proteção de Patentes)", "Apache-2.0")
        self.combo_lic.addItem("GNU GPL v3.0 (Copyleft Estrito)", "GPL-3.0")
        self.combo_lic.addItem("BSD 3-Clause (Permissiva sem Endosso)", "BSD-3-Clause")
        self.combo_lic.addItem("The Unlicense (Domínio Público)", "Unlicense")
        self.combo_lic.currentIndexChanged.connect(self._update_license)
        grid_lic.addWidget(self.combo_lic, 0, 1)

        grid_lic.addWidget(QLabel("Ano dos Direitos:"), 0, 2)
        self.spin_year = QSpinBox()
        self.spin_year.setRange(1990, 2100)
        self.spin_year.setValue(datetime.datetime.now().year)
        self.spin_year.valueChanged.connect(self._update_license)
        grid_lic.addWidget(self.spin_year, 0, 3)

        grid_lic.addWidget(QLabel("Nome do Titular / Autor:"), 1, 0)
        self.txt_holder = QLineEdit(Path.home().name)
        self.txt_holder.textChanged.connect(self._update_license)
        grid_lic.addWidget(self.txt_holder, 1, 1, 1, 3)

        v_lic.addWidget(lic_form)

        v_lic.addWidget(QLabel("Texto Oficial da Licença (LICENSE):"))
        self.txt_lic_output = QTextEdit()
        self.txt_lic_output.setFont(QFont("Consolas", 10))
        v_lic.addWidget(self.txt_lic_output, 1)

        h_lic_btns = QHBoxLayout()
        btn_copy_lic = QPushButton("Copiar Licença")
        btn_copy_lic.clicked.connect(lambda: self._copy_text(self.txt_lic_output.toPlainText()))
        btn_save_lic = QPushButton("Salvar Arquivo LICENSE...")
        btn_save_lic.clicked.connect(self._save_license)

        h_lic_btns.addStretch()
        h_lic_btns.addWidget(btn_copy_lic)
        h_lic_btns.addWidget(btn_save_lic)
        v_lic.addLayout(h_lic_btns)

        tabs.addTab(tab_lic, "Licenças de Código Aberto")

        layout.addWidget(tabs, 1)

        self._update_gitignore()
        self._update_license()
        return widget

    def _update_gitignore(self):
        selected = [chk.text() for chk in self.gi_checkboxes if chk.isChecked()]
        custom = self.txt_gi_custom.toPlainText()
        composed = compose_gitignore(selected, custom)
        self.txt_gi_output.setText(composed)

    def _update_license(self):
        lic_type = self.combo_lic.currentData()
        year = self.spin_year.value()
        holder = self.txt_holder.text().strip()
        text = generate_license(lic_type, year, holder)
        self.txt_lic_output.setText(text)

    def _copy_text(self, text: str):
        if text:
            QGuiApplication.clipboard().setText(text)
            QMessageBox.information(None, "Copiado", "Texto copiado para a área de transferência!")

    def _save_gitignore(self):
        dest, _ = QFileDialog.getSaveFileName(
            None, "Salvar Arquivo .gitignore", ".gitignore", "Arquivo Gitignore (*.gitignore)"
        )
        if dest:
            try:
                Path(dest).write_text(self.txt_gi_output.toPlainText(), encoding="utf-8")
                QMessageBox.information(None, "Salvo", f"Arquivo salvo com sucesso em:\n{dest}")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao salvar: {e}")

    def _save_license(self):
        dest, _ = QFileDialog.getSaveFileName(
            None, "Salvar Arquivo LICENSE", "LICENSE", "Arquivo de Licença (LICENSE*);;Todos (*.*)"
        )
        if dest:
            try:
                Path(dest).write_text(self.txt_lic_output.toPlainText(), encoding="utf-8")
                QMessageBox.information(None, "Salvo", f"Arquivo salvo com sucesso em:\n{dest}")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao salvar: {e}")

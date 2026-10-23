"""
Interface gráfica do Scaffold e Gerador de Templates de Repositórios.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.project_scaffold.logic import (
    EDITORCONFIG_TEMPLATE, generate_scaffold_files, get_available_languages,
    get_available_licenses, get_gitignore_content, get_license_content,
    get_readme_content
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("dev.project_scaffold.ui")


@register
class ProjectScaffoldTool(Tool):
    id = "dev.project_scaffold"
    name = "Scaffold de Projetos"
    category = "Desenvolvimento"
    description = "Geração de estruturas iniciais de repositórios: .gitignore, licenças (MIT, Apache, GPL), README e .editorconfig"
    keywords = ["scaffold", "template", "gitignore", "license", "readme", "editorconfig", "git", "repo", "dev", "projeto"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ProjectScaffoldView(self, parent)


class ProjectScaffoldView(QWidget):
    def __init__(self, tool: ProjectScaffoldTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()
        self._update_previews()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Scaffold de Projetos e Repositórios",
            "Criação padronizada de arquivos base para novos projetos (.gitignore profissional, licenças Open Source, README e convenções)."
        ))

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Coluna Esquerda: Formulário de Configuração
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # 1. Pasta de Destino
        dest_box = QGroupBox("Destino do Projeto")
        dest_layout = QHBoxLayout(dest_box)
        self.edit_target_dir = QLineEdit()
        self.edit_target_dir.setPlaceholderText("Selecione a pasta onde os arquivos serão criados...")
        dest_layout.addWidget(self.edit_target_dir, stretch=1)

        btn_browse_dir = QPushButton("Procurar...")
        btn_browse_dir.clicked.connect(self._browse_dir)
        dest_layout.addWidget(btn_browse_dir)
        left_col.addWidget(dest_box)

        # 2. Informações Gerais
        info_box = QGroupBox("Metadados do Projeto")
        grid_info = QGridLayout(info_box)
        grid_info.setSpacing(8)

        grid_info.addWidget(QLabel("Nome do Projeto:"), 0, 0)
        self.edit_name = QLineEdit("MeuProjeto")
        self.edit_name.textChanged.connect(self._update_previews)
        grid_info.addWidget(self.edit_name, 0, 1)

        grid_info.addWidget(QLabel("Descrição:"), 1, 0)
        self.edit_desc = QLineEdit("Uma aplicação moderna e de alta produtividade.")
        self.edit_desc.textChanged.connect(self._update_previews)
        grid_info.addWidget(self.edit_desc, 1, 1)

        grid_info.addWidget(QLabel("Autor / Empresa:"), 2, 0)
        self.edit_author = QLineEdit("Seu Nome")
        self.edit_author.textChanged.connect(self._update_previews)
        grid_info.addWidget(self.edit_author, 2, 1)

        grid_info.addWidget(QLabel("Linguagem (.gitignore):"), 3, 0)
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(get_available_languages())
        self.combo_lang.currentIndexChanged.connect(self._update_previews)
        grid_info.addWidget(self.combo_lang, 3, 1)

        grid_info.addWidget(QLabel("Licença de Software:"), 4, 0)
        self.combo_license = QComboBox()
        self.combo_license.addItems(get_available_licenses())
        self.combo_license.currentIndexChanged.connect(self._update_previews)
        grid_info.addWidget(self.combo_license, 4, 1)

        left_col.addWidget(info_box)

        # 3. Arquivos a Criar
        files_box = QGroupBox("Arquivos para Gerar")
        files_layout = QVBoxLayout(files_box)
        files_layout.setSpacing(6)

        self.chk_gitignore = QCheckBox("Arquivo .gitignore (com regras da linguagem e do SO)")
        self.chk_gitignore.setChecked(True)
        files_layout.addWidget(self.chk_gitignore)

        self.chk_license = QCheckBox("Arquivo LICENSE (com ano e autor preenchidos)")
        self.chk_license.setChecked(True)
        files_layout.addWidget(self.chk_license)

        self.chk_readme = QCheckBox("Arquivo README.md estruturado e formatado")
        self.chk_readme.setChecked(True)
        files_layout.addWidget(self.chk_readme)

        self.chk_editorconfig = QCheckBox("Arquivo .editorconfig (padronização de linhas e espaços)")
        self.chk_editorconfig.setChecked(True)
        files_layout.addWidget(self.chk_editorconfig)

        self.chk_env = QCheckBox("Arquivo .env.example (variáveis de ambiente modelo)")
        self.chk_env.setChecked(True)
        files_layout.addWidget(self.chk_env)

        left_col.addWidget(files_box)

        # Botão Gerar
        self.btn_generate = QPushButton("Gerar Arquivos no Diretório")
        self.btn_generate.setProperty("class", "primary")
        self.btn_generate.setFixedHeight(38)
        self.btn_generate.clicked.connect(self._on_generate)
        left_col.addWidget(self.btn_generate)

        left_col.addStretch(1)
        content_layout.addLayout(left_col, stretch=1)

        # Coluna Direita: Abas de Pré-visualização
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        prev_header = QHBoxLayout()
        prev_header.addWidget(QLabel("Pré-visualização do Conteúdo"))
        prev_header.addStretch(1)

        btn_copy_prev = QPushButton("Copiar Conteúdo da Aba Atual")
        btn_copy_prev.clicked.connect(self._copy_current_tab)
        prev_header.addWidget(btn_copy_prev)
        right_col.addLayout(prev_header)

        self.preview_tabs = QTabWidget()

        self.txt_prev_gitignore = QTextEdit()
        self.txt_prev_gitignore.setReadOnly(True)
        self.txt_prev_gitignore.setFont(QFont("Cascadia Mono", 9))
        self.preview_tabs.addTab(self.txt_prev_gitignore, ".gitignore")

        self.txt_prev_license = QTextEdit()
        self.txt_prev_license.setReadOnly(True)
        self.txt_prev_license.setFont(QFont("Cascadia Mono", 9))
        self.preview_tabs.addTab(self.txt_prev_license, "LICENSE")

        self.txt_prev_readme = QTextEdit()
        self.txt_prev_readme.setReadOnly(True)
        self.txt_prev_readme.setFont(QFont("Cascadia Mono", 9))
        self.preview_tabs.addTab(self.txt_prev_readme, "README.md")

        self.txt_prev_editorconfig = QTextEdit()
        self.txt_prev_editorconfig.setReadOnly(True)
        self.txt_prev_editorconfig.setFont(QFont("Cascadia Mono", 9))
        self.txt_prev_editorconfig.setPlainText(EDITORCONFIG_TEMPLATE.strip() + "\n")
        self.preview_tabs.addTab(self.txt_prev_editorconfig, ".editorconfig")

        right_col.addWidget(self.preview_tabs, stretch=1)
        content_layout.addLayout(right_col, stretch=1)

        root.addLayout(content_layout, stretch=1)

    def _browse_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Diretório do Projeto")
        if folder:
            self.edit_target_dir.setText(folder)
            if not self.edit_name.text() or self.edit_name.text() == "MeuProjeto":
                self.edit_name.setText(Path(folder).name)

    def _update_previews(self) -> None:
        lang = self.combo_lang.currentText()
        lic = self.combo_license.currentText()
        name = self.edit_name.text()
        desc = self.edit_desc.text()
        author = self.edit_author.text()

        self.txt_prev_gitignore.setPlainText(get_gitignore_content(lang, include_general=True))
        self.txt_prev_license.setPlainText(get_license_content(lic, author))
        self.txt_prev_readme.setPlainText(get_readme_content(name, desc, author, lic))

    def _copy_current_tab(self) -> None:
        current_widget = self.preview_tabs.currentWidget()
        if isinstance(current_widget, QTextEdit):
            text = current_widget.toPlainText()
            if text:
                QApplication.clipboard().setText(text)
                tab_title = self.preview_tabs.tabText(self.preview_tabs.currentIndex())
                show_toast(self, f"Conteúdo de {tab_title} copiado!")

    def _on_generate(self) -> None:
        target_path_str = self.edit_target_dir.text().strip()
        if not target_path_str:
            show_toast(self, "Por favor, selecione a pasta de destino do projeto.", duration_ms=2500)
            return

        target_dir = Path(target_path_str)
        try:
            results = generate_scaffold_files(
                target_dir=target_dir,
                project_name=self.edit_name.text(),
                description=self.edit_desc.text(),
                author=self.edit_author.text(),
                language=self.combo_lang.currentText(),
                license_type=self.combo_license.currentText(),
                create_gitignore=self.chk_gitignore.isChecked(),
                create_license=self.chk_license.isChecked(),
                create_readme=self.chk_readme.isChecked(),
                create_editorconfig=self.chk_editorconfig.isChecked(),
                create_env_example=self.chk_env.isChecked()
            )

            file_names = [f[0] for f in results]
            show_toast(self, f"{len(file_names)} arquivos criados com sucesso em {target_dir.name}!", duration_ms=3000)

        except Exception as exc:
            _log.error("Erro ao gerar scaffold: %s", exc)
            show_toast(self, f"Erro ao gerar arquivos: {exc}", duration_ms=3500)

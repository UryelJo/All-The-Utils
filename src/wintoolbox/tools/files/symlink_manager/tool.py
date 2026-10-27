"""
Interface gráfica da ferramenta Gerenciador de Links Simbólicos e Junções (files.symlink_manager).
Permite criar Directory Junctions (mklink /J), Symlinks e Hardlinks com segurança,
inspecionar links existentes em pastas e detectar links quebrados/órfãos.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.files.symlink_manager.logic import (
    create_link,
    remove_link_safely,
    scan_links_in_directory,
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class SymlinkManagerTool(Tool):
    id = "files.symlink_manager"
    name = "Gerenciador de Symlinks e Junções"
    category = "Arquivos e Pastas"
    description = (
        "Cria e audita Links Simbólicos, Junções de Diretório (mklink /J) e Hard Links no Windows, "
        "com detecção de links órfãos/quebrados e remoção segura sem apagar alvos."
    )
    keywords = ["symlink", "junction", "mklink", "hardlink", "atalho", "diretorio", "ntfs", "link"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SymlinkManagerView(self, parent)


class SymlinkManagerView(QWidget):
    def __init__(self, tool: SymlinkManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Abas
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_inspect_tab(), "Inspecionar e Listar Links")
        self._tabs.addTab(self._build_create_tab(), "Criar Novo Link ou Junção")
        root_layout.addWidget(self._tabs)

    def _build_inspect_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        # Barra de Busca
        search_bar = QHBoxLayout()
        self._txt_scan_dir = QLineEdit()
        self._txt_scan_dir.setPlaceholderText("Selecione uma pasta para buscar symlinks e junções...")
        search_bar.addWidget(self._txt_scan_dir)

        btn_browse = QPushButton("Selecionar Pasta...")
        btn_browse.clicked.connect(self._on_browse_scan_dir)
        search_bar.addWidget(btn_browse)

        btn_scan = QPushButton("Buscar Links")
        btn_scan.setStyleSheet("font-weight: bold;")
        btn_scan.clicked.connect(self._run_scan)
        search_bar.addWidget(btn_scan)

        layout.addLayout(search_bar)

        self._lbl_scan_status = QLabel("Nenhuma pasta examinada.")
        self._lbl_scan_status.setStyleSheet("color: #4b5563; font-size: 11px;")
        layout.addWidget(self._lbl_scan_status)

        # Tabela com DataTableView
        cols = [
            Column("status", "Status", width=90),
            Column("name", "Nome do Link", width=140),
            Column("type", "Tipo", width=140),
            Column("target", "Alvo Apontado", width=260),
            Column("path", "Caminho do Link", width=260),
        ]
        self._table = DataTableView(cols, key="path", parent=self)
        layout.addWidget(self._table)

        # Barra de Ações
        act_bar = QHBoxLayout()
        btn_delete_link = QPushButton("Remover Link Selecionado (Seguro)")
        btn_delete_link.clicked.connect(self._delete_selected_link)
        act_bar.addWidget(btn_delete_link)
        act_bar.addStretch()
        layout.addLayout(act_bar)

        return widget

    def _build_create_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        form_group = QGroupBox("Parâmetros do Link")
        form_layout = QVBoxLayout(form_group)

        # Tipo de Link
        type_box = QHBoxLayout()
        type_box.addWidget(QLabel("Tipo de Link:"))
        self._combo_type = QComboBox()
        self._combo_type.addItem("Junção de Diretório - mklink /J (Recomendado para pastas, sem UAC)", "junction")
        self._combo_type.addItem("Link Simbólico de Pasta - mklink /D (Requer modo dev/UAC)", "symlink_dir")
        self._combo_type.addItem("Link Simbólico de Arquivo - mklink (Requer modo dev/UAC)", "symlink_file")
        self._combo_type.addItem("Hard Link de Arquivo - mklink /H", "hardlink")
        type_box.addWidget(self._combo_type)
        form_layout.addLayout(type_box)

        # Caminho do Link (Onde será criado)
        link_box = QHBoxLayout()
        link_box.addWidget(QLabel("Caminho do Link (Origem):"))
        self._txt_new_link = QLineEdit()
        self._txt_new_link.setPlaceholderText("Caminho onde o atalho/junção será criado...")
        link_box.addWidget(self._txt_new_link)
        btn_b_link = QPushButton("Escolher Local...")
        btn_b_link.clicked.connect(self._choose_link_destination)
        link_box.addWidget(btn_b_link)
        form_layout.addLayout(link_box)

        # Caminho do Alvo (Target real)
        target_box = QHBoxLayout()
        target_box.addWidget(QLabel("Pasta ou Arquivo Real (Alvo):"))
        self._txt_target = QLineEdit()
        self._txt_target.setPlaceholderText("Caminho real que receberá os dados...")
        target_box.addWidget(self._txt_target)
        btn_b_target = QPushButton("Procurar Alvo...")
        btn_b_target.clicked.connect(self._choose_target_path)
        target_box.addWidget(btn_b_target)
        form_layout.addLayout(target_box)

        layout.addWidget(form_group)

        # Botão Criar
        btn_create = QPushButton("Criar Link / Junção")
        btn_create.setStyleSheet("font-weight: bold; padding: 10px 20px;")
        btn_create.clicked.connect(self._create_link)
        layout.addWidget(btn_create)

        self._lbl_create_status = QLabel("")
        self._lbl_create_status.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._lbl_create_status)

        layout.addStretch()
        return widget

    def _on_browse_scan_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Diretório para Varrer")
        if folder:
            self._txt_scan_dir.setText(folder)
            self._run_scan()

    def _run_scan(self):
        dir_str = self._txt_scan_dir.text().strip()
        if not dir_str or not Path(dir_str).is_dir():
            return

        self._lbl_scan_status.setText("Examinando sistema de arquivos...")
        self._runner.run(
            scan_links_in_directory,
            Path(dir_str),
            on_success=self._on_scan_success,
            on_error=self._on_scan_error,
        )

    def _on_scan_success(self, links: list):
        self._table.set_records(links)
        self._lbl_scan_status.setText(f"{len(links)} link(s) / junção(ões) encontrados.")

    def _on_scan_error(self, exc: Exception):
        QMessageBox.critical(self, "Erro", f"Falha na varredura: {exc}")
        self._lbl_scan_status.setText("Erro ao varrer diretório.")

    def _delete_selected_link(self):
        rec = self._table.current_record()
        if not rec:
            QMessageBox.warning(self, "Aviso", "Selecione um link na tabela para remover.")
            return

        link_path = Path(rec["path"])
        reply = QMessageBox.question(
            self,
            "Confirmar Remoção de Link",
            f"Deseja remover o link:\n{link_path}\n\nNota: Isso removerá apenas o link; o diretório ou arquivo alvo NÃO será apagado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                remove_link_safely(link_path)
                QMessageBox.information(self, "Sucesso", "Link removido com sucesso!")
                self._run_scan()
            except Exception as exc:
                QMessageBox.critical(self, "Erro", f"Falha ao remover link: {exc}")

    def _choose_link_destination(self):
        # Permite ao usuário escolher o local onde o link será colocado
        folder = QFileDialog.getExistingDirectory(self, "Selecione o diretório onde criar o link")
        if folder:
            self._txt_new_link.setText(str(Path(folder) / "NovoLink"))

    def _choose_target_path(self):
        ltype = self._combo_type.currentData()
        if "file" in ltype or ltype == "hardlink":
            fpath, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo Alvo")
            if fpath:
                self._txt_target.setText(fpath)
        else:
            folder = QFileDialog.getExistingDirectory(self, "Selecionar Diretório Alvo")
            if folder:
                self._txt_target.setText(folder)

    def _create_link(self):
        link_str = self._txt_new_link.text().strip()
        target_str = self._txt_target.text().strip()
        ltype = self._combo_type.currentData()

        if not link_str or not target_str:
            QMessageBox.warning(self, "Aviso", "Por favor, preencha os caminhos de origem e alvo.")
            return

        try:
            res = create_link(Path(link_str), Path(target_str), link_type=ltype)
            self._lbl_create_status.setStyleSheet("color: #047857;")
            self._lbl_create_status.setText(f"Link criado com sucesso! ({ltype})")
            QMessageBox.information(self, "Sucesso", f"Link criado com sucesso em:\n{res['link_path']}")
        except Exception as exc:
            self._lbl_create_status.setStyleSheet("color: #b91c1c;")
            self._lbl_create_status.setText(f"Erro: {exc}")
            QMessageBox.critical(self, "Erro ao Criar Link", f"Não foi possível criar o link: {exc}")

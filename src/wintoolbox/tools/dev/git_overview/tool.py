"""
Interface de usuário para a ferramenta Painel Agregador de Repositórios Git.
"""
import os
import subprocess
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.git_overview.logic import GitRepoInfo, scan_git_repositories


@register
class GitOverviewTool(Tool):
    """Visão panorâmica e monitoramento de múltiplos repositórios Git locais."""

    id = "dev.git_overview"
    name = "Painel Agregador de Repositórios Git"
    description = "Visão panorâmica de múltiplos repositórios Git locais: branches ativas, arquivos modificados e sincronização remota."
    category = "dev"

    def __init__(self):
        super().__init__()
        self.repos: List[GitRepoInfo] = []

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Painel Agregador de Repositórios Git")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Monitore o estado de branches, commits pendentes e alterações não salvas "
            "em todos os seus repositórios de código em uma única visão unificada."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Barra de Busca e Escaneamento
        top_frame = QFrame()
        top_frame.setFrameShape(QFrame.Shape.StyledPanel)
        top_layout = QHBoxLayout(top_frame)

        self.txt_dir = QLineEdit(str(Path.home() / "source" / "repos"))
        self.btn_browse = QPushButton("Procurar...")
        self.btn_browse.clicked.connect(self._browse)

        self.btn_scan = QPushButton("Escanear Repositórios")
        self.btn_scan.setStyleSheet("font-weight: bold;")
        self.btn_scan.clicked.connect(self._scan)

        top_layout.addWidget(QLabel("Pasta Raiz:"))
        top_layout.addWidget(self.txt_dir, 1)
        top_layout.addWidget(self.btn_browse)
        top_layout.addWidget(self.btn_scan)
        layout.addWidget(top_frame)

        # Tabela de Repositórios
        self.table_repos = QTableWidget()
        self.table_repos.setColumnCount(6)
        self.table_repos.setHorizontalHeaderLabels([
            "Repositório", "Branch Atual", "Status", "Pendências", "Sincronização", "Último Commit"
        ])
        self.table_repos.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_repos.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table_repos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_repos, 1)

        # Barra de Ações Inferior
        bot_frame = QFrame()
        bot_layout = QHBoxLayout(bot_frame)
        bot_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_summary = QLabel("Nenhum repositório escaneado.")
        self.lbl_summary.setStyleSheet("color: #2196f3; font-weight: bold;")

        self.btn_open_folder = QPushButton("Abrir no Explorador")
        self.btn_open_folder.clicked.connect(self._open_in_explorer)

        self.btn_open_term = QPushButton("Abrir no Terminal")
        self.btn_open_term.clicked.connect(self._open_in_terminal)

        bot_layout.addWidget(self.lbl_summary)
        bot_layout.addStretch()
        bot_layout.addWidget(self.btn_open_folder)
        bot_layout.addWidget(self.btn_open_term)
        layout.addWidget(bot_frame)

        return widget

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(None, "Selecionar Diretório de Projetos")
        if folder:
            self.txt_dir.setText(folder)

    def _scan(self):
        raw = self.txt_dir.text().strip()
        if not raw:
            QMessageBox.warning(None, "Aviso", "Informe um diretório válido.")
            return

        root_path = Path(raw)
        if not root_path.is_dir():
            QMessageBox.critical(None, "Erro", "O caminho especificado não existe.")
            return

        self.btn_scan.setEnabled(False)
        self.lbl_summary.setText("Localizando repositórios Git...")

        try:
            repos = scan_git_repositories(root_path)
            self.repos = repos
            self._populate_table(repos)
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha na varredura: {e}")
            self.lbl_summary.setText("Erro ao escanear.")
        finally:
            self.btn_scan.setEnabled(True)

    def _populate_table(self, repos: List[GitRepoInfo]):
        self.table_repos.setRowCount(len(repos))

        dirty_count = sum(1 for r in repos if r.is_dirty)

        for row, r in enumerate(repos):
            # 1. Nome
            self.table_repos.setItem(row, 0, QTableWidgetItem(r.name))

            # 2. Branch
            self.table_repos.setItem(row, 1, QTableWidgetItem(r.current_branch))

            # 3. Status
            status_text = "Modificado" if r.is_dirty else "Limpo"
            status_color = QColor(244, 67, 54) if r.is_dirty else QColor(76, 175, 80)
            it_status = QTableWidgetItem(status_text)
            it_status.setForeground(status_color)
            self.table_repos.setItem(row, 2, it_status)

            # 4. Pendências
            pending_str = f"{r.modified_count} modif., {r.untracked_count} novos" if r.is_dirty else "Nenhuma"
            self.table_repos.setItem(row, 3, QTableWidgetItem(pending_str))

            # 5. Sincronização
            sync_str = f"↑ {r.ahead_count}  ↓ {r.behind_count}"
            self.table_repos.setItem(row, 4, QTableWidgetItem(sync_str))

            # 6. Último Commit
            last_msg = f"{r.last_commit_date} - {r.last_commit_message}" if r.last_commit_message else ""
            self.table_repos.setItem(row, 5, QTableWidgetItem(last_msg))

        self.lbl_summary.setText(
            f"{len(repos)} repositórios encontrados | {dirty_count} com alterações pendentes"
        )

    def _get_selected_repo(self) -> Path:
        row = self.table_repos.currentRow()
        if 0 <= row < len(self.repos):
            return self.repos[row].path
        return None

    def _open_in_explorer(self):
        repo_path = self._get_selected_repo()
        if repo_path and repo_path.is_dir():
            os.startfile(str(repo_path))

    def _open_in_terminal(self):
        repo_path = self._get_selected_repo()
        if repo_path and repo_path.is_dir():
            subprocess.Popen(["wt.exe", "-d", str(repo_path)], shell=True)

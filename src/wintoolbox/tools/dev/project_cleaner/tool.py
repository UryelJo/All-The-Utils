"""
Interface de usuário para a ferramenta Limpador de Projetos de Código.
"""
from pathlib import Path
from typing import List, Set

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
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
from wintoolbox.tools.dev.project_cleaner.logic import (
    CleanableItem,
    delete_cleanable_items,
    scan_cleanable_items,
)


@register
class ProjectCleanerTool(Tool):
    """Localizador e limpador em massa de pastas de build e dependências de código."""

    id = "dev.project_cleaner"
    name = "Limpador de Projetos de Código"
    description = "Localiza e remove em massa pastas pesadas de compilação (node_modules, target, __pycache__, bin/obj, .venv) liberando espaço em disco."
    category = "dev"

    def __init__(self):
        super().__init__()
        self.scanned_items: List[CleanableItem] = []

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Limpador de Projetos de Código (Build Cleaner)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Recupere dezenas de gigabytes em seu disco localizando e excluindo pastas de compilação, "
            "caches de frameworks e dependências temporárias de repositórios antigos."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Seleção de Diretório e Categorias
        ctrl_frame = QFrame()
        ctrl_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(ctrl_frame)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Diretório Raiz dos Projetos:"), 0, 0)
        self.txt_root_dir = QLineEdit(str(Path.home() / "source" / "repos"))
        self.btn_browse = QPushButton("Procurar...")
        self.btn_browse.clicked.connect(self._browse_dir)

        grid.addWidget(self.txt_root_dir, 0, 1)
        grid.addWidget(self.btn_browse, 0, 2)

        # Checkboxes de ecossistemas
        cats_layout = QHBoxLayout()
        self.chk_node = QCheckBox("Node.js (node_modules, .next)")
        self.chk_node.setChecked(True)
        self.chk_python = QCheckBox("Python (__pycache__, .venv)")
        self.chk_python.setChecked(True)
        self.chk_rust = QCheckBox("Rust (target)")
        self.chk_rust.setChecked(True)
        self.chk_dotnet = QCheckBox(".NET (bin, obj)")
        self.chk_dotnet.setChecked(True)
        self.chk_java = QCheckBox("Java/Gradle (.gradle)")
        self.chk_java.setChecked(True)

        cats_layout.addWidget(self.chk_node)
        cats_layout.addWidget(self.chk_python)
        cats_layout.addWidget(self.chk_rust)
        cats_layout.addWidget(self.chk_dotnet)
        cats_layout.addWidget(self.chk_java)
        cats_layout.addStretch()

        grid.addLayout(cats_layout, 1, 0, 1, 3)

        # Botão de Varredura
        self.btn_scan = QPushButton("Escanear Diretório")
        self.btn_scan.setFixedHeight(35)
        self.btn_scan.clicked.connect(self._start_scan)
        grid.addWidget(self.btn_scan, 2, 0, 1, 3)

        layout.addWidget(ctrl_frame)

        # Tabela de Resultados
        self.table_items = QTableWidget()
        self.table_items.setColumnCount(5)
        self.table_items.setHorizontalHeaderLabels([
            "Selecionar", "Tipo / Descrição", "Arquivos", "Tamanho Estimado", "Caminho no Disco"
        ])
        self.table_items.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_items, 1)

        # Barra de Resumo e Ações
        bottom_frame = QFrame()
        b_layout = QHBoxLayout(bottom_frame)
        b_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_select_all = QPushButton("Selecionar Todos")
        self.btn_select_all.clicked.connect(lambda: self._set_all_checks(True))
        self.btn_deselect_all = QPushButton("Desmarcar Todos")
        self.btn_deselect_all.clicked.connect(lambda: self._set_all_checks(False))

        self.lbl_total_savings = QLabel("Nenhum item escaneado.")
        self.lbl_total_savings.setStyleSheet("font-weight: bold; color: #2196f3;")

        self.btn_delete = QPushButton("Excluir Selecionados")
        self.btn_delete.setFixedHeight(40)
        self.btn_delete.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_selected)

        b_layout.addWidget(self.btn_select_all)
        b_layout.addWidget(self.btn_deselect_all)
        b_layout.addSpacing(20)
        b_layout.addWidget(self.lbl_total_savings)
        b_layout.addStretch()
        b_layout.addWidget(self.btn_delete)

        layout.addWidget(bottom_frame)
        return widget

    def _browse_dir(self):
        folder = QFileDialog.getExistingDirectory(None, "Selecionar Diretório de Projetos")
        if folder:
            self.txt_root_dir.setText(folder)

    def _get_enabled_categories(self) -> Set[str]:
        cats: Set[str] = set()
        if self.chk_node.isChecked():
            cats.add("node")
        if self.chk_python.isChecked():
            cats.add("python")
        if self.chk_rust.isChecked():
            cats.add("rust")
        if self.chk_dotnet.isChecked():
            cats.add("dotnet")
        if self.chk_java.isChecked():
            cats.add("java")
        return cats

    def _start_scan(self):
        raw_path = self.txt_root_dir.text().strip()
        if not raw_path:
            QMessageBox.warning(None, "Aviso", "Informe um diretório válido para escanear.")
            return

        root_path = Path(raw_path)
        if not root_path.is_dir():
            QMessageBox.critical(None, "Erro", "O caminho especificado não existe ou não é uma pasta.")
            return

        cats = self._get_enabled_categories()
        self.btn_scan.setEnabled(False)
        self.lbl_total_savings.setText("Varrendo diretório... Por favor aguarde.")

        try:
            items = scan_cleanable_items(root_dir=root_path, enabled_categories=cats)
            self.scanned_items = items
            self._populate_table(items)
        except Exception as e:
            QMessageBox.critical(None, "Erro no Escaneamento", f"Falha ao varrer diretório: {e}")
        finally:
            self.btn_scan.setEnabled(True)

    def _populate_table(self, items: List[CleanableItem]):
        self.table_items.setRowCount(len(items))
        total_bytes = sum(i.size_bytes for i in items)

        for row, item in enumerate(items):
            # Checkbox
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked)
            self.table_items.setItem(row, 0, chk)

            # Descrição
            self.table_items.setItem(row, 1, QTableWidgetItem(item.description))

            # Quantidade de Arquivos
            self.table_items.setItem(row, 2, QTableWidgetItem(f"{item.file_count:,}"))

            # Tamanho Formatado
            size_mb = item.size_bytes / (1024 * 1024)
            size_str = f"{size_mb / 1024:.2f} GB" if size_mb >= 1024 else f"{size_mb:.1f} MB"
            self.table_items.setItem(row, 3, QTableWidgetItem(size_str))

            # Caminho
            self.table_items.setItem(row, 4, QTableWidgetItem(str(item.path)))

        mb_total = total_bytes / (1024 * 1024)
        total_str = f"{mb_total / 1024:.2f} GB" if mb_total >= 1024 else f"{mb_total:.1f} MB"
        self.lbl_total_savings.setText(f"{len(items)} itens encontrados. Espaço recuperável: {total_str}")
        self.btn_delete.setEnabled(len(items) > 0)

    def _set_all_checks(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for r in range(self.table_items.rowCount()):
            item = self.table_items.item(r, 0)
            if item:
                item.setCheckState(state)

    def _delete_selected(self):
        to_delete: List[Path] = []
        for r in range(self.table_items.rowCount()):
            chk = self.table_items.item(r, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                path_str = self.table_items.item(r, 4).text()
                to_delete.append(Path(path_str))

        if not to_delete:
            QMessageBox.information(None, "Aviso", "Nenhum item selecionado para exclusão.")
            return

        reply = QMessageBox.question(
            None,
            "Confirmar Limpeza",
            f"Tem certeza que deseja excluir permanentemente {len(to_delete)} pastas selecionadas?\n"
            "Essa ação removerá dependências e caches que precisarão ser recompilados/baixados novamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.btn_delete.setEnabled(False)
        try:
            count, freed = delete_cleanable_items(to_delete, dry_run=False)
            freed_mb = freed / (1024 * 1024)
            freed_str = f"{freed_mb / 1024:.2f} GB" if freed_mb >= 1024 else f"{freed_mb:.1f} MB"
            QMessageBox.information(
                None, "Limpeza Concluída", f"{count} itens foram excluídos!\nEspaço liberado: {freed_str}"
            )
            self._start_scan()
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha na exclusão: {e}")
        finally:
            self.btn_delete.setEnabled(True)

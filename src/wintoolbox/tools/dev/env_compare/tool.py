"""
Interface de usuário para a ferramenta Comparador de Ambientes (.env vs .env.example).
"""
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.env_compare.logic import (
    EnvDiffItem,
    compare_env_files,
    generate_missing_env_snippet,
    parse_env_file,
)


@register
class EnvCompareTool(Tool):
    """Comparador e auditor de variáveis de ambiente entre modelos de exemplo e arquivos reais."""

    id = "dev.env_compare"
    name = "Comparador de Ambientes (.env vs .env.example)"
    description = "Compara arquivos .env reais contra modelos de exemplo, alertando sobre variáveis ausentes com mascaramento de segredos."
    category = "dev"

    def __init__(self):
        super().__init__()
        self.diff_results: List[EnvDiffItem] = []

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Comparador de Ambientes (.env vs .env.example)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Audite parâmetros de configuração antes de deploys em produção. "
            "Identifique variáveis não declaradas, chaves ausentes e evite quebras de ambiente."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Seleção de Arquivos
        file_frame = QFrame()
        file_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(file_frame)
        grid.setSpacing(10)

        # Modelo (.env.example)
        grid.addWidget(QLabel("Arquivo Modelo (.env.example):"), 0, 0)
        self.txt_template = QLineEdit()
        self.txt_template.setPlaceholderText("Selecione o arquivo .env.example...")
        self.btn_browse_template = QPushButton("Procurar...")
        self.btn_browse_template.clicked.connect(lambda: self._browse_file(self.txt_template))
        grid.addWidget(self.txt_template, 0, 1)
        grid.addWidget(self.btn_browse_template, 0, 2)

        # Arquivo Real (.env)
        grid.addWidget(QLabel("Arquivo Real (.env):"), 1, 0)
        self.txt_target = QLineEdit()
        self.txt_target.setPlaceholderText("Selecione o arquivo .env real...")
        self.btn_browse_target = QPushButton("Procurar...")
        self.btn_browse_target.clicked.connect(lambda: self._browse_file(self.txt_target))
        grid.addWidget(self.txt_target, 1, 1)
        grid.addWidget(self.btn_browse_target, 1, 2)

        # Opções
        opts_layout = QHBoxLayout()
        self.chk_mask = QCheckBox("Mascarar credenciais sensíveis (chaves, senhas, tokens)")
        self.chk_mask.setChecked(True)
        opts_layout.addWidget(self.chk_mask)
        opts_layout.addStretch()

        self.btn_compare = QPushButton("Comparar Ambientes")
        self.btn_compare.setStyleSheet("font-weight: bold;")
        self.btn_compare.clicked.connect(self._compare)
        opts_layout.addWidget(self.btn_compare)

        grid.addLayout(opts_layout, 2, 0, 1, 3)
        layout.addWidget(file_frame)

        # Tabela Comparativa
        self.table_diff = QTableWidget()
        self.table_diff.setColumnCount(5)
        self.table_diff.setHorizontalHeaderLabels([
            "Status", "Variável (Chave)", "Valor no Modelo", "Valor no Ambiente Real", "Sensível"
        ])
        self.table_diff.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table_diff.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_diff.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_diff, 1)

        # Barra Inferior de Resumo e Ações
        b_frame = QFrame()
        b_layout = QHBoxLayout(b_frame)
        b_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_summary = QLabel("Nenhuma comparação efetuada.")
        self.lbl_summary.setStyleSheet("font-weight: bold; color: #2196f3;")

        self.btn_generate_missing = QPushButton("Gerar Trecho de Variáveis Faltantes")
        self.btn_generate_missing.setEnabled(False)
        self.btn_generate_missing.clicked.connect(self._show_missing_dialog)

        b_layout.addWidget(self.lbl_summary)
        b_layout.addStretch()
        b_layout.addWidget(self.btn_generate_missing)
        layout.addWidget(b_frame)

        return widget

    def _browse_file(self, target_line_edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            None, "Selecionar Arquivo de Ambiente", "",
            "Arquivos de Ambiente (*.env* *local* *example* *template*);;Todos os Arquivos (*.*)"
        )
        if path:
            target_line_edit.setText(path)

    def _compare(self):
        t_raw = self.txt_template.text().strip()
        target_raw = self.txt_target.text().strip()

        if not t_raw or not target_raw:
            QMessageBox.warning(None, "Aviso", "Selecione tanto o arquivo modelo quanto o arquivo real.")
            return

        t_path = Path(t_raw)
        target_path = Path(target_raw)

        if not t_path.is_file() or not target_path.is_file():
            QMessageBox.critical(None, "Erro", "Um ou ambos os arquivos selecionados não existem no disco.")
            return

        mask = self.chk_mask.isChecked()
        try:
            diffs = compare_env_files(t_path, target_path, mask_secrets=mask)
            self.diff_results = diffs
            self._populate_table(diffs)
        except Exception as e:
            QMessageBox.critical(None, "Erro na Comparação", f"Falha ao comparar arquivos: {e}")

    def _populate_table(self, diffs: List[EnvDiffItem]):
        self.table_diff.setRowCount(len(diffs))

        missing_count = 0
        empty_count = 0
        undoc_count = 0
        matched_count = 0

        status_labels = {
            "missing_in_target": ("Ausente no Real", QColor(244, 67, 54)),
            "empty_in_target": ("Vazio no Real", QColor(255, 152, 0)),
            "missing_in_template": ("Não Documentado", QColor(33, 150, 243)),
            "matched": ("OK / Preenchido", QColor(76, 175, 80))
        }

        for row, item in enumerate(diffs):
            label_text, color = status_labels.get(item.status, ("Desconhecido", QColor(150, 150, 150)))

            if item.status == "missing_in_target":
                missing_count += 1
            elif item.status == "empty_in_target":
                empty_count += 1
            elif item.status == "missing_in_template":
                undoc_count += 1
            elif item.status == "matched":
                matched_count += 1

            # Status
            it_status = QTableWidgetItem(label_text)
            it_status.setForeground(color)
            self.table_diff.setItem(row, 0, it_status)

            # Chave
            self.table_diff.setItem(row, 1, QTableWidgetItem(item.key))

            # Modelo
            self.table_diff.setItem(row, 2, QTableWidgetItem(item.template_value))

            # Alvo
            self.table_diff.setItem(row, 3, QTableWidgetItem(item.target_value))

            # Sensível
            self.table_diff.setItem(row, 4, QTableWidgetItem("Sim" if item.is_secret else "Não"))

        self.lbl_summary.setText(
            f"Total: {len(diffs)} chaves | {missing_count} ausentes | {empty_count} vazias | "
            f"{undoc_count} não documentadas | {matched_count} preenchidas"
        )
        self.btn_generate_missing.setEnabled(missing_count > 0 or empty_count > 0)

    def _show_missing_dialog(self):
        t_path = Path(self.txt_template.text().strip())
        raw_template = parse_env_file(t_path) if t_path.is_file() else None
        snippet = generate_missing_env_snippet(self.diff_results, raw_template)

        dlg = QDialog()
        dlg.setWindowTitle("Variáveis Faltantes")
        dlg.resize(600, 400)
        v = QVBoxLayout(dlg)

        v.addWidget(QLabel("Cole as variáveis abaixo no final do seu arquivo .env:"))
        txt = QTextEdit()
        txt.setText(snippet)
        v.addWidget(txt)

        h = QHBoxLayout()
        btn_copy = QPushButton("Copiar para Área de Transferência")
        btn_copy.clicked.connect(lambda: [QGuiApplication.clipboard().setText(snippet), dlg.accept()])
        h.addStretch()
        h.addWidget(btn_copy)
        v.addLayout(h)

        dlg.exec()

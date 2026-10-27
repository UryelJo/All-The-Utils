"""
Interface gráfica Fluent da ferramenta Formatador de Nomes Próprios.
"""
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.name_formatter.logic import (
    FormattedName,
    process_names_batch,
)


@register
class NameFormatterTool(Tool):
    """Ferramenta para capitalização gramatical de nomes próprios em português e citações ABNT."""
    id = "text.name_formatter"
    title = "Formatador de Nomes Próprios"
    category = "Texto e Redação"
    description = (
        "Padroniza e capitaliza nomes próprios conforme a gramática brasileira: "
        "mantém partículas de ligação minúsculas ('da', 'de', 'dos', 'e'), numerais romanos "
        "e gera citações ABNT em lote."
    )
    icon = "Contact"

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._on_format)
        self._results: list[FormattedName] = []

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Formatador Gramatical de Nomes Próprios e ABNT")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Digite ou cole nomes próprios (um por linha) em qualquer formato (ex: tudo maiúsculo). "
            "A ferramenta aplicará as regras ortográficas corretas (preservando 'da', 'de', 'do', 'dos', 'e'), "
            "além de gerar citações ABNT automáticas."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: Entrada
        left_widget = QWidget()
        v_left = QVBoxLayout(left_widget)
        v_left.setContentsMargins(0, 0, 0, 0)
        v_left.setSpacing(8)

        lbl_input = QLabel("Nomes de Entrada (um por linha):")
        lbl_input.setStyleSheet("font-weight: 600;")
        v_left.addWidget(lbl_input)

        self.edit_input = QTextEdit()
        self.edit_input.setPlaceholderText(
            "Exemplo:\n"
            "JOAO DA SILVA\n"
            "MARIA DE FATIMA DOS SANTOS\n"
            "CARLOS EDUARDO D'AVILA\n"
            "PEDRO ALVARES CABRAL NETO\n"
            "LUIZ INACIO LULA DA SILVA\n"
            "HENRIQUE VIII"
        )
        self.edit_input.textChanged.connect(self._trigger_debounce)
        v_left.addWidget(self.edit_input)

        bar_left = QHBoxLayout()
        btn_open = QPushButton("Abrir Arquivo...")
        btn_open.clicked.connect(self._on_open_file)
        bar_left.addWidget(btn_open)

        btn_sample = QPushButton("Carregar Exemplo")
        btn_sample.clicked.connect(self._load_sample)
        bar_left.addWidget(btn_sample)

        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(self.edit_input.clear)
        bar_left.addWidget(btn_clear)
        v_left.addLayout(bar_left)

        splitter.addWidget(left_widget)

        # Painel Direito: Resultados
        right_widget = QWidget()
        v_right = QVBoxLayout(right_widget)
        v_right.setContentsMargins(0, 0, 0, 0)
        v_right.setSpacing(8)

        self.lbl_count = QLabel("0 nome(s) formatado(s)")
        self.lbl_count.setStyleSheet("font-weight: bold; color: #0078D4;")
        v_right.addWidget(self.lbl_count)

        self.table_results = QTableWidget(0, 4)
        self.table_results.setHorizontalHeaderLabels([
            "Nome Capitalizado",
            "Citação ABNT",
            "Primeiro e Último",
            "Iniciais",
        ])
        self.table_results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_results.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        v_right.addWidget(self.table_results)

        bar_actions = QHBoxLayout()
        btn_copy_cap = QPushButton("Copiar Nomes")
        btn_copy_cap.setStyleSheet("font-weight: bold;")
        btn_copy_cap.clicked.connect(lambda: self._copy_column(0))
        bar_actions.addWidget(btn_copy_cap)

        btn_copy_abnt = QPushButton("Copiar Citações ABNT")
        btn_copy_abnt.clicked.connect(lambda: self._copy_column(1))
        bar_actions.addWidget(btn_copy_abnt)

        btn_export_csv = QPushButton("Exportar CSV...")
        btn_export_csv.clicked.connect(self._on_export_csv)
        bar_actions.addWidget(btn_export_csv)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #107C41; font-weight: bold;")
        bar_actions.addWidget(self.lbl_status)
        bar_actions.addStretch()

        v_right.addLayout(bar_actions)
        splitter.addWidget(right_widget)

        splitter.setSizes([380, 520])
        layout.addWidget(splitter, 1)

        self._load_sample()
        return container

    def _trigger_debounce(self) -> None:
        self._debounce_timer.start()

    def _load_sample(self) -> None:
        sample = (
            "JOAO DA SILVA\n"
            "MARIA DE FATIMA DOS SANTOS\n"
            "CARLOS EDUARDO D'AVILA\n"
            "PEDRO ALVARES CABRAL NETO\n"
            "LUIZ INACIO LULA DA SILVA\n"
            "HENRIQUE VIII"
        )
        self.edit_input.setPlainText(sample)

    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Abrir Arquivo de Nomes", "", "Arquivos de Texto (*.txt *.csv);;Todos (*.*)")
        if path:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            self.edit_input.setPlainText(text)

    def _on_format(self) -> None:
        text = self.edit_input.toPlainText()
        self._results = process_names_batch(text)
        self.table_results.setRowCount(len(self._results))
        self.lbl_count.setText(f"{len(self._results)} nome(s) formatado(s)")
        self.lbl_status.setText("")

        for row, res in enumerate(self._results):
            item_cap = QTableWidgetItem(res.capitalized)
            item_abnt = QTableWidgetItem(res.abnt)
            item_short = QTableWidgetItem(res.short_name)
            item_ini = QTableWidgetItem(res.initials)

            self.table_results.setItem(row, 0, item_cap)
            self.table_results.setItem(row, 1, item_abnt)
            self.table_results.setItem(row, 2, item_short)
            self.table_results.setItem(row, 3, item_ini)

    def _copy_column(self, col: int) -> None:
        if not self._results:
            return
        lines = []
        for r in range(self.table_results.rowCount()):
            item = self.table_results.item(r, col)
            if item:
                lines.append(item.text())
        cb = QApplication.clipboard()
        if cb:
            cb.setText("\n".join(lines))
            self.lbl_status.setText("Coluna copiada!")

    def _on_export_csv(self) -> None:
        if not self._results:
            return
        dest, _ = QFileDialog.getSaveFileName(None, "Salvar Tabela de Nomes", "nomes_formatados.csv", "CSV (*.csv);;Todos (*.*)")
        if dest:
            lines = ["Original;Capitalizado;ABNT;Primeiro_Ultimo;Iniciais"]
            for r in self._results:
                lines.append(f'"{r.original}";"{r.capitalized}";"{r.abnt}";"{r.short_name}";"{r.initials}"')
            Path(dest).write_text("\n".join(lines), encoding="utf-8-sig")
            self.lbl_status.setText(f"Exportado com sucesso para {Path(dest).name}")

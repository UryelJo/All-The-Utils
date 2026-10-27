"""
Interface gráfica Fluent da ferramenta de manipulação de planilhas CSV.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QSpinBox,
    QWidget,
)

from wintoolbox.core.registry import FileTool, TaskContext, register
from wintoolbox.tools.data.csv_tools.logic import (
    convert_csv_delimiter,
    merge_csv_files,
    remove_csv_duplicates,
    split_csv_by_rows,
)


@register
class CsvToolsTool(FileTool):
    """Utilitário em lote para divisão, conversão e higienização de arquivos CSV."""
    id = "data.csv_tools"
    title = "Ferramentas de CSV"
    category = "Dados e Estruturas"
    description = (
        "Utilitário de manipulação de planilhas CSV em lote: divisão por linhas, "
        "fusão de múltiplos arquivos com mesmo cabeçalho, conversão de delimitadores e remoção de duplicatas."
    )
    icon = "Table"
    supported_extensions = [".csv", ".tsv", ".txt"]
    output_extension = ".csv"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.combo_op = QComboBox()
        self.combo_op.addItem("Dividir em Partes Menores", "split")
        self.combo_op.addItem("Converter Delimitador", "convert_delim")
        self.combo_op.addItem("Remover Linhas Duplicadas", "dedup")
        layout.addRow("Operação Desejada:", self.combo_op)

        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(10, 1_000_000)
        self.spin_rows.setValue(1000)
        self.spin_rows.setSingleStep(500)
        layout.addRow("Linhas por Arquivo (Modo Dividir):", self.spin_rows)

        self.combo_target_delim = QComboBox()
        self.combo_target_delim.addItem("Ponto-e-vírgula ( ; ) - Padrão Excel BR", ";")
        self.combo_target_delim.addItem("Vírgula ( , ) - Padrão Internacional", ",")
        self.combo_target_delim.addItem("Tabulação ( \\t ) - Formato TSV", "\t")
        self.combo_target_delim.addItem("Pipe ( | )", "|")
        layout.addRow("Delimitador de Destino:", self.combo_target_delim)

        self.combo_encoding = QComboBox()
        self.combo_encoding.addItem("UTF-8 (Recomendado)", "utf-8")
        self.combo_encoding.addItem("Windows-1252 / Latin-1 (Excel Legado)", "cp1252")
        layout.addRow("Codificação dos Arquivos:", self.combo_encoding)

        return widget

    def get_options(self) -> dict:
        op = "split"
        rows = 1000
        target_delim = ";"
        enc = "utf-8"

        if hasattr(self, "combo_op"):
            op = self.combo_op.currentData() or "split"
        if hasattr(self, "spin_rows"):
            rows = self.spin_rows.value()
        if hasattr(self, "combo_target_delim"):
            target_delim = self.combo_target_delim.currentData() or ";"
        if hasattr(self, "combo_encoding"):
            enc = self.combo_encoding.currentData() or "utf-8"

        return {
            "operation": op,
            "rows_per_file": rows,
            "target_delimiter": target_delim,
            "encoding": enc,
        }

    def process(
        self,
        file_path: str,
        output_dir: str,
        options: dict,
        context: Optional[TaskContext] = None,
    ) -> list[str]:
        p = Path(file_path)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        op = options.get("operation", "split")
        encoding = options.get("encoding", "utf-8")

        if op == "split":
            rows = int(options.get("rows_per_file", 1000))
            return split_csv_by_rows(file_path, str(out_dir), rows, encoding=encoding)

        elif op == "convert_delim":
            target_delim = options.get("target_delimiter", ";")
            delim_suffix = "_convertido.csv"
            out_file = out_dir / f"{p.stem}{delim_suffix}"
            convert_csv_delimiter(file_path, str(out_file), target_delimiter=target_delim, encoding=encoding)
            return [str(out_file)]

        elif op == "dedup":
            out_file = out_dir / f"{p.stem}_sem_duplicatas.csv"
            remove_csv_duplicates(file_path, str(out_file), encoding=encoding)
            return [str(out_file)]

        return []

"""
Interface gráfica Fluent da ferramenta de manipulação de planilhas Excel.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, TaskContext, register
from wintoolbox.tools.data.excel_tools.logic import (
    export_sheets_to_csv,
    split_sheets_to_workbooks,
)


@register
class ExcelToolsTool(FileTool):
    """Utilitário em lote para processamento e divisão de arquivos Excel (.xlsx, .xlsm)."""
    id = "data.excel_tools"
    title = "Ferramentas de Excel"
    category = "Dados e Estruturas"
    description = (
        "Utilitários para arquivos Excel: dividir abas em pastas de trabalho separadas, "
        "consolidar planilhas e exportar abas para formato CSV."
    )
    icon = "DocumentExcel"
    supported_extensions = [".xlsx", ".xlsm"]
    output_extension = ".xlsx"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.combo_op = QComboBox()
        self.combo_op.addItem("Dividir Abas em Arquivos Individuais (.xlsx)", "split_sheets")
        self.combo_op.addItem("Exportar Todas as Abas para CSV (.csv)", "export_csv")
        layout.addRow("Operação Desejada:", self.combo_op)

        self.combo_csv_delim = QComboBox()
        self.combo_csv_delim.addItem("Ponto-e-vírgula ( ; ) - Padrão Excel Brasil", ";")
        self.combo_csv_delim.addItem("Vírgula ( , ) - Padrão Internacional", ",")
        self.combo_csv_delim.addItem("Tabulação ( \\t ) - TSV", "\t")
        layout.addRow("Delimitador (Modo CSV):", self.combo_csv_delim)

        return widget

    def get_options(self) -> dict:
        op = "split_sheets"
        delim = ";"
        if hasattr(self, "combo_op"):
            op = self.combo_op.currentData() or "split_sheets"
        if hasattr(self, "combo_csv_delim"):
            delim = self.combo_csv_delim.currentData() or ";"

        return {
            "operation": op,
            "csv_delimiter": delim,
        }

    def process(
        self,
        file_path: str,
        output_dir: str,
        options: dict,
        context: Optional[TaskContext] = None,
    ) -> list[str]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        op = options.get("operation", "split_sheets")

        if op == "split_sheets":
            return split_sheets_to_workbooks(file_path, str(out_dir))
        elif op == "export_csv":
            delim = options.get("csv_delimiter", ";")
            return export_sheets_to_csv(file_path, str(out_dir), delimiter=delim)

        return []

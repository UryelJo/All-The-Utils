"""
Ferramenta: Conversor Universal de Dados em Lote (JSON ↔ YAML ↔ CSV ↔ XML).
Processamento recursivo em lote com controle de saída, espelhamento e resolução de conflitos.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.data.converter.logic import load_data, save_data

@register
class DataConverterTool(FileTool):
    id = "data.converter"
    name = "Conversor de Dados em Lote"
    category = "Dados e Estruturas"
    description = "Converte arquivos de dados entre JSON, YAML, CSV e XML em lote com recursão"
    keywords = ["json", "yaml", "csv", "xml", "converter", "dados", "lote", "tabela"]
    accepts = [".json", ".yaml", ".yml", ".csv", ".xml"]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.addWidget(QLabel("Formato de Saída Desejado:"))
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(["JSON", "YAML", "CSV", "XML"])
        row.addWidget(self.cmb_format)
        row.addStretch()
        layout.addLayout(row)

        return panel

    def get_options(self) -> Dict[str, Any]:
        return {
            "format": self.cmb_format.currentText()
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        fmt = params.get("format", "JSON").lower()
        return f".{fmt}"

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            target_format = params.get("format", "JSON")
            data = load_data(src)
            save_data(data, dst, target_format)
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                bytes_in=src.stat().st_size,
                bytes_out=dst.stat().st_size if dst.exists() else 0
            )
        except Exception as e:
            return ItemResult(
                success=False,
                source_path=src,
                error=str(e)
            )

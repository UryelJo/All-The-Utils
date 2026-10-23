"""
Ferramenta: Compressor de Arquivos PDF em Lote.
Implementação completa herdando de FileTool com automação de pastas e espelhamento.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QLabel, QSlider, QVBoxLayout, QWidget
)
from PySide6.QtCore import Qt

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.pdf.compress.logic import compress_pdf_file


@register
class PdfCompressTool(FileTool):
    id = "pdf.compress"
    name = "Compressor de PDF"
    category = "PDF"
    description = "Comprima e reduza o tamanho de arquivos PDF em lote através de otimização de fluxos de dados"
    keywords = ["pdf", "comprimir", "compressor", "reduzir", "otimizar", "tamanho", "leves", "lote"]
    accepts = [".pdf"]
    batch_kind = "per_file"
    parallel_mode = "thread"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Compressão e Otimização")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        self.chk_compress_streams = QCheckBox("Comprimir fluxos de texto e vetores internos (Content Streams)")
        self.chk_compress_streams.setChecked(True)
        grid.addWidget(self.chk_compress_streams, 0, 0, 1, 2)

        self.chk_remove_meta = QCheckBox("Remover metadados e histórico interno para economia máxima")
        self.chk_remove_meta.setChecked(False)
        grid.addWidget(self.chk_remove_meta, 1, 0, 1, 2)

        layout.addLayout(grid)
        return panel

    def get_params(self) -> Dict[str, Any]:
        return {
            "compress_streams": self.chk_compress_streams.isChecked(),
            "remove_metadata": self.chk_remove_meta.isChecked(),
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ".pdf"

    def process(
        self,
        src: Path,
        dst: Path,
        params: Dict[str, Any],
        ctx: TaskContext
    ) -> ItemResult:
        try:
            res = compress_pdf_file(
                src,
                dst,
                compress_streams=params.get("compress_streams", True),
                remove_metadata=params.get("remove_metadata", False)
            )

            src_kb = res["src_size"] / 1024
            dst_kb = res["dst_size"] / 1024
            pct = res["saved_pct"]

            return ItemResult(
                success=True,
                output_path=dst,
                message=f"Reduzido de {src_kb:.1f} KB para {dst_kb:.1f} KB ({pct:.1f}% economia)"
            )
        except Exception as e:
            return ItemResult(
                success=False,
                error=f"Falha ao comprimir {src.name}: {e}"
            )

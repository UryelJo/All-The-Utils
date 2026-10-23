"""
Ferramenta: Conversor de Documentos do Office para PDF em Lote.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.pdf.office_convert.logic import convert_office_doc_to_pdf


@register
class OfficeToPdfTool(FileTool):
    id = "pdf.office_convert"
    name = "Conversor de Office para PDF"
    category = "PDF"
    description = "Converta arquivos Word (.docx), Excel (.xlsx) e PowerPoint (.pptx) para PDF de alta fidelidade"
    keywords = ["office", "word", "excel", "powerpoint", "pdf", "docx", "xlsx", "pptx", "converter", "lote"]
    accepts = [".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"]
    batch_kind = "per_file"
    parallel_mode = "serial"  # Automação COM do Office requer processamento sequencial estável

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        lbl_header = QLabel("Opções de Conversão Office")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        lbl_info = QLabel(
            "A conversão utiliza a engine nativa do Microsoft Office instalada no computador, "
            "garantindo 100% de precisão de layout, fontes e tabelas originais."
        )
        lbl_info.setStyleSheet("color: gray; font-size: 11px;")
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        return panel

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
            ctx.log("INFO", f"Convertendo {src.name} via Office COM...")
            convert_office_doc_to_pdf(src, dst)
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=f"Convertido com sucesso: {dst.name}"
            )
        except Exception as e:
            return ItemResult(
                success=False,
                source_path=src,
                error=f"Falha ao converter {src.name}: {e}"
            )

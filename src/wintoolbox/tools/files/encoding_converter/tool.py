"""
Interface e integração com Batch Engine do Conversor de Codificação de Texto em Lote.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.files.encoding_converter.logic import convert_text_content

_log = get_logger("files.encoding_converter.ui")


@register
class EncodingConverterTool(FileTool):
    id = "files.encoding_converter"
    name = "Conversor de Codificação de Texto"
    category = "Arquivos e Pastas"
    description = "Conversão em lote de codificação de arquivos de texto (UTF-8, ANSI, UTF-16) e normalização de quebras de linha (CRLF/LF)"
    keywords = ["codificacao", "encoding", "utf-8", "ansi", "windows-1252", "crlf", "lf", "bom", "texto", "lote"]

    accepts = [
        ".txt", ".csv", ".json", ".xml", ".html", ".css", ".js",
        ".py", ".md", ".sql", ".ini", ".log", ".bat", ".cmd", ".ps1", ".tsv"
    ]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        lay = QFormLayout(container)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        self.combo_target_enc = QComboBox()
        self.combo_target_enc.addItem("UTF-8 (Padrão Web / Sem BOM)", "utf-8")
        self.combo_target_enc.addItem("UTF-8 com BOM (Compatibilidade Windows / Excel)", "utf-8-sig")
        self.combo_target_enc.addItem("Windows-1252 / ANSI (Padrão Windows Antigo)", "windows-1252")
        self.combo_target_enc.addItem("ISO-8859-1 (Latin-1)", "iso-8859-1")
        self.combo_target_enc.addItem("UTF-16 LE (Unicode Windows)", "utf-16-le")
        self.combo_target_enc.addItem("ASCII Puro (7 bits)", "ascii")
        lay.addRow(QLabel("Codificação de Destino:"), self.combo_target_enc)

        self.combo_line_ending = QComboBox()
        self.combo_line_ending.addItem("Manter Quebras Originais", "keep")
        self.combo_line_ending.addItem("Windows (CRLF - \\r\\n)", "crlf")
        self.combo_line_ending.addItem("Linux / macOS (LF - \\n)", "lf")
        lay.addRow(QLabel("Finais de Linha:"), self.combo_line_ending)

        return container

    def get_options(self) -> Dict[str, Any]:
        return {
            "target_encoding": self.combo_target_enc.currentData() if hasattr(self, "combo_target_enc") else "utf-8",
            "line_ending": self.combo_line_ending.currentData() if hasattr(self, "combo_line_ending") else "keep"
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        # Preserva a extensão original do arquivo
        return ""

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            target_enc = params.get("target_encoding", "utf-8")
            line_ending = params.get("line_ending", "keep")

            raw_bytes = src.read_bytes()
            bytes_in = len(raw_bytes)

            converted_bytes, detail = convert_text_content(raw_bytes, target_enc, line_ending)

            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(converted_bytes)

            bytes_out = len(converted_bytes)
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=f"Convertido: {detail}",
                bytes_in=bytes_in,
                bytes_out=bytes_out
            )
        except Exception as exc:
            _log.warning("Falha ao converter %s: %s", src.name, exc)
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc)
            )

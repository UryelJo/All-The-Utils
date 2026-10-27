"""
Interface gráfica Fluent para o Limpador de Metadados de Documentos.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, TaskContext, register
from wintoolbox.tools.files.doc_metadata.logic import (
    clean_document,
    inspect_document,
)


@register
class FilesDocMetadataTool(FileTool):
    """Utilitário em lote para inspeção e higienização de metadados de documentos Office e PDF."""
    id = "files.doc_metadata"
    name = "Limpador de Metadados de Documentos"
    title = "Limpador de Metadados de Documentos"
    category = "Arquivos e Pastas"
    description = (
        "Inspetor e limpador em lote de metadados de privacidade em documentos "
        "Word (.docx), Excel (.xlsx), PowerPoint (.pptx) e PDF."
    )
    icon = "Shield"
    supported_extensions = [".docx", ".xlsx", ".pptx", ".pdf"]
    output_extension = ".docx"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Higienizar e Salvar Cópia Limpa", "clean")
        self.combo_mode.addItem("Gerar Relatório de Metadados (.txt)", "report")
        layout.addRow("Ação do Processamento:", self.combo_mode)

        return widget

    def get_options(self) -> dict:
        mode = "clean"
        if hasattr(self, "combo_mode"):
            mode = self.combo_mode.currentData() or "clean"
        return {"mode": mode}

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

        mode = options.get("mode", "clean")

        if mode == "clean":
            out_file = out_dir / f"{p.stem}_limpo{p.suffix}"
            clean_document(file_path, str(out_file))
            return [str(out_file)]

        elif mode == "report":
            out_file = out_dir / f"{p.name}_metadados.txt"
            info = inspect_document(file_path)
            lines = [
                f"Relatório de Metadados: {p.name}",
                f"Formato: {info.get('format', 'N/D')}",
                f"Autor / Criador: {info.get('author') or '(vazio)'}",
                f"Última Modificação Por: {info.get('last_modified_by') or '(vazio)'}",
                f"Título: {info.get('title') or '(vazio)'}",
                f"Empresa: {info.get('company') or '(vazio)'}",
                f"Data de Criação: {info.get('created') or info.get('creation_date') or '(vazio)'}",
            ]
            with open(out_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return [str(out_file)]

        return []

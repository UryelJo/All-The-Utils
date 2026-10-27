"""
Interface gráfica Fluent para o Detector de Tipo Real de Arquivos por Magic Bytes.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, TaskContext, register
from wintoolbox.tools.files.type_detector.logic import (
    correct_file_extension,
    detect_file_type,
)


@register
class FilesTypeDetectorTool(FileTool):
    """Utilitário em lote para identificação de assinaturas binárias e detecção de extensões falsas."""
    id = "files.type_detector"
    title = "Detector de Tipo Real de Arquivo"
    category = "Arquivos e Pastas"
    description = (
        "Identifica o tipo real de arquivos baseado em assinaturas binárias (Magic Bytes), "
        "detectando extensões mascaradas ou incorretas."
    )
    icon = "Search"
    supported_extensions = ["*.*"]
    output_extension = ".txt"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Gerar Relatório de Diagnóstico (.txt)", "report")
        self.combo_mode.addItem("Corrigir e Renomear para a Extensão Correta", "fix_extension")
        layout.addRow("Ação ao Detectar:", self.combo_mode)

        return widget

    def get_options(self) -> dict:
        mode = "report"
        if hasattr(self, "combo_mode"):
            mode = self.combo_mode.currentData() or "report"
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

        mode = options.get("mode", "report")
        info = detect_file_type(file_path)

        if mode == "fix_extension":
            if info["is_mismatch"]:
                fixed_path = correct_file_extension(file_path, info["recommended_ext"], str(out_dir))
                return [fixed_path]
            else:
                # Extensão já coincide, apenas gera relatório informativo
                pass

        # Modo report
        out_report = out_dir / f"{p.name}_tipo_real.txt"
        mismatch_str = "SIM (EXTENSÃO MASCARADA OU INCORRETA!)" if info["is_mismatch"] else "Não (Extensão compatível)"

        lines = [
            f"Relatório de Identificação de Tipo Real de Arquivo",
            f"==================================================",
            f"Arquivo: {info['file_name']}",
            f"Caminho original: {info['file_path']}",
            f"Tamanho: {info['file_size']} bytes",
            f"Extensão declarada: {info['declared_ext'] or '(sem extensão)'}",
            f"Tipo real detectado: {info['real_type']}",
            f"MIME Type: {info['mime_type']}",
            f"Extensão recomendada: {info['recommended_ext']}",
            f"Divergência detectada: {mismatch_str}",
            f"Magic Bytes (Hex): {info['magic_hex']}",
        ]

        with open(out_report, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return [str(out_report)]

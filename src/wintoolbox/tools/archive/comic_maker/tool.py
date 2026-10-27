"""
Interface gráfica do Criador e Conversor de Quadrinhos CBZ (archive.comic_maker).
Herda de FileTool com suporte a lote, ordenação natural e metadados ComicInfo.xml.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, register
from wintoolbox.tools.archive.comic_maker.logic import (
    create_cbz_archive,
    extract_cbz_archive,
)


@register
class ComicMakerTool(FileTool):
    id = "archive.comic_maker"
    name = "Conversor de Quadrinhos CBZ"
    description = "Converte pastas de imagens para quadrinhos CBZ com ordenação numérica natural e extrai CBZ para imagens."
    category = "Compactação"
    extensions = [
        ".cbz",
        ".zip",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    ]

    def build_options(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._combo_mode = QComboBox()
        self._combo_mode.addItem("Imagens/Pasta -> Arquivo CBZ", "TO_CBZ")
        self._combo_mode.addItem("Arquivo CBZ -> Pasta com Imagens", "TO_IMAGES")
        form.addRow("Modo de Operação:", self._combo_mode)

        self._combo_comp = QComboBox()
        self._combo_comp.addItem("DEFLATE (Comprimido - Menor tamanho)", True)
        self._combo_comp.addItem("STORE (Sem compressão - Mais rápido)", False)
        form.addRow("Compressão:", self._combo_comp)

        self._edit_title = QLineEdit()
        self._edit_title.setPlaceholderText("Deixe em branco para usar o nome da pasta")
        form.addRow("Título (ComicInfo.xml):", self._edit_title)

        self._edit_issue = QLineEdit()
        self._edit_issue.setPlaceholderText("Ex: 1, 01, Especial")
        form.addRow("Edição/Número:", self._edit_issue)

        layout.addLayout(form)

        self._chk_xml = QCheckBox("Incluir manifesto de metadados ComicInfo.xml padrão")
        self._chk_xml.setChecked(True)
        layout.addWidget(self._chk_xml)

        return widget

    def get_options(self) -> Dict[str, Any]:
        return {
            "mode": self._combo_mode.currentData(),
            "compress": self._combo_comp.currentData(),
            "title": self._edit_title.text().strip() or None,
            "issue": self._edit_issue.text().strip() or "1",
            "generate_xml": self._chk_xml.isChecked(),
        }

    def process(self, input_path: Path, output_dir: Path, options: Dict[str, Any]) -> Path:
        mode = options.get("mode", "TO_CBZ")
        lower_name = input_path.name.lower()

        # Detecção automática inteligente se o usuário soltar arquivo .cbz
        if lower_name.endswith((".cbz", ".zip")) or mode == "TO_IMAGES":
            return extract_cbz_archive(cbz_path=input_path, output_dir=output_dir)

        # Caso contrário, converte pasta ou imagem para CBZ
        out_cbz = output_dir / f"{input_path.stem}.cbz"
        return create_cbz_archive(
            source_folder_or_files=[input_path],
            output_cbz_path=out_cbz,
            title=options.get("title"),
            issue=options.get("issue"),
            compress=options.get("compress", True),
            generate_xml=options.get("generate_xml", True),
        )

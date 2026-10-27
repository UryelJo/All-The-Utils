"""
Interface gráfica do Descompactador em Lote (archive.batch_extract).
Herda de FileTool com suporte a múltiplos arquivos compactados,
criação automática de subpastas, detecção de raiz duplicada e exclusão pós-extração.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, register
from wintoolbox.tools.archive.batch_extract.logic import extract_archive_item


@register
class BatchExtractTool(FileTool):
    id = "archive.batch_extract"
    name = "Descompactador em Lote"
    description = "Descompacta múltiplos arquivos compactados simultâneos (ZIP, TAR, 7Z, RAR) com subpastas organizadas."
    category = "Compactação"
    extensions = [
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
    ]

    def build_options(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._chk_subfolder = QCheckBox("Criar subpasta individual com o nome de cada arquivo compactado")
        self._chk_subfolder.setChecked(True)
        layout.addWidget(self._chk_subfolder)

        self._chk_avoid_dup = QCheckBox("Evitar pasta raiz duplicada (se o arquivo já contém uma única pasta com o mesmo nome)")
        self._chk_avoid_dup.setChecked(True)
        layout.addWidget(self._chk_avoid_dup)

        self._chk_delete_source = QCheckBox("Excluir arquivo compactado original após extração com sucesso")
        self._chk_delete_source.setChecked(False)
        layout.addWidget(self._chk_delete_source)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 4, 0, 0)
        self._edit_password = QLineEdit()
        self._edit_password.setEchoMode(QLineEdit.Password)
        self._edit_password.setPlaceholderText("Senha (opcional, para arquivos protegidos)")
        form_layout.addRow("Senha:", self._edit_password)
        layout.addLayout(form_layout)

        return widget

    def get_options(self) -> Dict[str, Any]:
        return {
            "create_subfolder": self._chk_subfolder.isChecked(),
            "avoid_duplicate_root": self._chk_avoid_dup.isChecked(),
            "delete_source_after": self._chk_delete_source.isChecked(),
            "password": self._edit_password.text().strip() or None,
        }

    def process(self, input_path: Path, output_dir: Path, options: Dict[str, Any]) -> Path:
        res = extract_archive_item(
            archive_path=input_path,
            output_dir=output_dir,
            create_subfolder=options.get("create_subfolder", True),
            avoid_duplicate_root=options.get("avoid_duplicate_root", True),
            delete_source_after=options.get("delete_source_after", False),
            password=options.get("password"),
        )
        return Path(res["dest_folder"])

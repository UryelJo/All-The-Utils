"""
Interface e integração com Batch Engine do Desbloqueador de Arquivos em Lote.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.files.unblock.logic import unblock_file

_log = get_logger("files.unblock.ui")


@register
class UnblockTool(FileTool):
    id = "files.unblock"
    name = "Desbloquear Arquivos (Mark of the Web)"
    category = "Arquivos e Pastas"
    description = "Remove em lote a restrição de segurança Zone.Identifier aplicada pelo Windows a arquivos baixados da internet"
    keywords = ["desbloquear", "mark of the web", "zone identifier", "bloqueado", "smartscreen", "internet", "segurança", "lote"]

    # Aceita todas as extensões de arquivo
    accepts = []
    batch_kind = "per_file"
    parallel_mode = "thread"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(8, 8, 8, 8)
        lbl = QLabel(
            "Esta ferramenta remove o fluxo alternativo NTFS (Zone.Identifier) que causa avisos de 'Arquivo Bloqueado'\n"
            "ao abrir planilhas, macros do Office, arquivos compactados ou executáveis transferidos da internet.\n\n"
            "Arraste arquivos ou pastas inteiras acima e clique em 'Executar em Lote'."
        )
        lbl.setStyleSheet("color: #888888;")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        from PySide6.QtWidgets import QCheckBox
        self._chk_unblock = QCheckBox("Remover marca de segurança da Web (Zone.Identifier)", container)
        self._chk_unblock.setChecked(True)
        lay.addWidget(self._chk_unblock)

        return container

    def get_options(self) -> Dict[str, Any]:
        checked = getattr(self, "_chk_unblock", None)
        return {"remove_motw": checked.isChecked() if checked else True}

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ""

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            ok, msg = unblock_file(src)
            return ItemResult(
                success=ok,
                source_path=src,
                output_path=src,
                message=msg,
                error=None if ok else msg
            )
        except Exception as exc:
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc)
            )

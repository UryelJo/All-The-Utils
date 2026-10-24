"""Cabeçalho padrão (título + descrição) para telas de ferramentas do tipo painel."""
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wintoolbox.core.registry import BaseTool


def make_tool_header(tool: BaseTool) -> QWidget:
    """Título e descrição no mesmo estilo das ferramentas de lote (FileToolPage)."""
    return ToolHeader(tool.name, tool.description)


class ToolHeader(QWidget):
    """Componente reutilizável de cabeçalho com título e descrição."""

    def __init__(
        self,
        title: str,
        description: str = "",
        category_or_parent: QWidget | str | None = None,
        parent: QWidget | None = None,
    ):
        actual_parent = parent if parent is not None else (category_or_parent if isinstance(category_or_parent, QWidget) else None)
        super().__init__(actual_parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setProperty("class", "title")
        lay.addWidget(lbl_title)

        if description:
            lbl_desc = QLabel(description)
            lbl_desc.setProperty("class", "secondary")
            lbl_desc.setWordWrap(True)
            lay.addWidget(lbl_desc)


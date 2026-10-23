"""Cabeçalho padrão (título + descrição) para telas de ferramentas do tipo painel."""
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wintoolbox.core.registry import BaseTool


def make_tool_header(tool: BaseTool) -> QWidget:
    """Título e descrição no mesmo estilo das ferramentas de lote (FileToolPage)."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 4)
    lay.setSpacing(4)

    title = QLabel(tool.name)
    title.setProperty("class", "title")
    lay.addWidget(title)

    if tool.description:
        desc = QLabel(tool.description)
        desc.setProperty("class", "secondary")
        desc.setWordWrap(True)
        lay.addWidget(desc)
    return box

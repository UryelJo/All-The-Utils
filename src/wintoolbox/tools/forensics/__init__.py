"""Pacote de ferramentas forenses do WinToolbox.

Importa os sete módulos para que cada ferramenta seja registrada pelo decorador
``@register`` ao carregar ``wintoolbox.tools.forensics``.
"""
from wintoolbox.tools.forensics import (
    artifact_timeline,
    browser_extract,
    file_recovery,
    lnk_analyzer,
    memory_dump,
    registry_parser,
    usb_history,
)

__all__ = [
    "memory_dump",
    "file_recovery",
    "registry_parser",
    "browser_extract",
    "usb_history",
    "lnk_analyzer",
    "artifact_timeline",
]

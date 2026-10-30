"""Ferramentas de Engenharia Reversa do WinToolbox.

Cada módulo registra a própria ferramenta no `registry` ao ser importado. A lista
abaixo é a única fonte de importação da categoria Reverse Engineering.
"""
import wintoolbox.tools.rev.pe_analyzer  # noqa: F401
import wintoolbox.tools.rev.strings_extract  # noqa: F401
import wintoolbox.tools.rev.disassembler  # noqa: F401
import wintoolbox.tools.rev.js_deobfuscator  # noqa: F401
import wintoolbox.tools.rev.pyc_decompiler  # noqa: F401

__all__ = [
    "pe_analyzer",
    "strings_extract",
    "disassembler",
    "js_deobfuscator",
    "pyc_decompiler",
]

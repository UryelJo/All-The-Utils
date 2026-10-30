"""Ferramentas de OSINT (inteligência de fontes abertas) do WinToolbox.

Cada módulo registra a própria ferramenta no `registry` ao ser importado. A lista
abaixo é a única fonte de importação da categoria OSINT.
"""
import wintoolbox.tools.osint.username_enum  # noqa: F401
import wintoolbox.tools.osint.domain_intel  # noqa: F401
import wintoolbox.tools.osint.email_breach  # noqa: F401
import wintoolbox.tools.osint.metadata_extract  # noqa: F401

__all__ = [
    "username_enum",
    "domain_intel",
    "email_breach",
    "metadata_extract",
]

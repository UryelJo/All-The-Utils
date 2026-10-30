"""Ferramentas de segurança web do WinToolbox.

O simples ato de importar este pacote registra as cinco ferramentas na categoria
"Web" por meio do decorador ``@register`` de cada módulo.
"""
import wintoolbox.tools.web.dir_bruteforce
import wintoolbox.tools.web.subdomain_enum
import wintoolbox.tools.web.vuln_scanner
import wintoolbox.tools.web.jwt_toolkit
import wintoolbox.tools.web.csrf_poc

__all__ = [
    "dir_bruteforce",
    "subdomain_enum",
    "vuln_scanner",
    "jwt_toolkit",
    "csrf_poc",
]

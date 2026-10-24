"""
Lógica pura de verificação de senhas comprometidas via Have I Been Pwned com k-anonimato.
Totalmente desacoplada de bibliotecas de interface visual.
Garante privacidade absoluta: a senha ou hash completo NUNCA são transmitidos pela rede.
"""
import hashlib
from typing import Tuple
import urllib.request

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("security.pwned_check")


def check_password_pwned(password: str) -> Tuple[bool, int, str]:
    """
    Verifica se a senha consta em bancos de dados de vazamentos públicos conhecidos
    utilizando a API oficial do 'Have I Been Pwned' via modelo de k-anonimato (SHA-1).

    Retorna:
        (is_pwned: bool, leak_count: int, message: str)
    """
    if not password:
        return False, 0, "A senha fornecida está vazia."

    # 1. Gera o hash SHA-1 em maiúsculas
    sha1_hash = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix = sha1_hash[:5]
    suffix = sha1_hash[5:]

    url = f"https://api.pwnedpasswords.com/range/{prefix}"
    headers = {"User-Agent": "WinToolbox-Security-Audit/1.0"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")

        # 2. Busca localmente pelo sufixo na resposta
        for line in data.splitlines():
            line_str = line.strip()
            if ":" in line_str:
                h_suffix, count_str = line_str.split(":", 1)
                if h_suffix.upper() == suffix:
                    count = int(count_str.strip())
                    return True, count, f"Esta senha apareceu em {count:,} vazamento(s) de dados conhecidos na internet. Recomendamos trocá-la imediatamente."

        return False, 0, "Boa notícia: esta senha não foi encontrada em nenhum banco de dados público de vazamentos monitorado pelo Have I Been Pwned."

    except Exception as exc:
        _log.warning("Falha ao consultar API HIBP: %s", exc)
        return False, 0, f"Falha na conexão com o serviço Have I Been Pwned: {exc}"

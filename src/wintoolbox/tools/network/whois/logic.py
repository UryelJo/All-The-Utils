"""
Lógica pura para consulta WHOIS defensiva e pública de domínios e IPs.

Realiza consultas RFC 3912 via socket TCP na porta 43 com descoberta automática
de servidor TLD (ex.: whois.verisign-grs.com, whois.registro.br) e parser estruturado.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from dataclasses import asdict, dataclass
import re
import socket
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("network.whois.logic")

TLD_WHOIS_SERVERS: Dict[str, str] = {
    "br": "whois.registro.br",
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "org": "whois.pir.org",
    "io": "whois.nic.io",
    "dev": "whois.nic.google",
    "app": "whois.nic.google",
    "info": "whois.afilias.net",
    "me": "whois.nic.me",
    "co": "whois.nic.co",
}


@dataclass
class WhoisResult:
    domain: str
    registrar: str
    registrant: str
    creation_date: str
    expiration_date: str
    name_servers: List[str]
    status: str
    raw_text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_domain(domain_input: str) -> str:
    """Normaliza o nome de domínio removendo esquemas http://, portas e barras."""
    d = domain_input.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].split(":")[0]
    return d


def get_whois_server_for_domain(domain: str) -> str:
    """Identifica o servidor WHOIS padrão para o TLD do domínio."""
    parts = domain.strip().lower().split(".")
    if len(parts) >= 2:
        tld = parts[-1]
        if tld in TLD_WHOIS_SERVERS:
            return TLD_WHOIS_SERVERS[tld]
        if len(parts) >= 3 and parts[-2] == "com" and tld == "br":
            return "whois.registro.br"
    return "whois.iana.org"


def parse_whois_text(domain: str, raw_text: str) -> WhoisResult:
    """
    Analisa o texto retornado pelo servidor WHOIS e extrai os campos estruturados.
    """
    registrar = "Não informado"
    registrant = "Não informado / Privacidade Ativa"
    created = "Não informado"
    expires = "Não informado"
    status_list: List[str] = []
    name_servers: List[str] = []

    for line in raw_text.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("%") or line_clean.startswith("#"):
            continue

        # Registrar
        m_reg = re.match(r"^(?:Registrar|Registrar Name|provedor)\s*:\s*(.+)$", line_clean, re.IGNORECASE)
        if m_reg and registrar == "Não informado":
            registrar = m_reg.group(1).strip()
            continue

        # Registrant / Titular
        m_owner = re.match(r"^(?:Registrant Organization|Registrant Name|titular|owner)\s*:\s*(.+)$", line_clean, re.IGNORECASE)
        if m_owner and registrant.startswith("Não informado"):
            registrant = m_owner.group(1).strip()
            continue

        # Creation Date
        m_created = re.match(r"^(?:Creation Date|Created|Registration Time|criado)\s*:\s*(.+)$", line_clean, re.IGNORECASE)
        if m_created and created == "Não informado":
            created = m_created.group(1).strip()
            continue

        # Expiry Date
        m_exp = re.match(r"^(?:Registry Expiry Date|Registrar Registration Expiration Date|Expiration Date|Expires|expiração)\s*:\s*(.+)$", line_clean, re.IGNORECASE)
        if m_exp and expires == "Não informado":
            expires = m_exp.group(1).strip()
            continue

        # Name Servers
        m_ns = re.match(r"^(?:Name Server|nserver|nameserver)\s*:\s*(.+)$", line_clean, re.IGNORECASE)
        if m_ns:
            ns_val = m_ns.group(1).strip().split()[0].lower()
            if ns_val not in name_servers:
                name_servers.append(ns_val)
            continue

        # Status
        m_st = re.match(r"^(?:Domain Status|status)\s*:\s*(.+)$", line_clean, re.IGNORECASE)
        if m_st:
            st_val = m_st.group(1).strip().split()[0]
            if st_val not in status_list:
                status_list.append(st_val)

    # Formata datas simplificadas se contiverem formato ISO (ex.: 2026-05-12T00:00:00Z)
    if "T" in created:
        created = created.split("T")[0]
    if "T" in expires:
        expires = expires.split("T")[0]

    return WhoisResult(
        domain=domain,
        registrar=registrar,
        registrant=registrant,
        creation_date=created,
        expiration_date=expires,
        name_servers=name_servers,
        status=", ".join(status_list) if status_list else "Ativo",
        raw_text=raw_text
    )


def query_whois_socket(
    domain: str,
    server: Optional[str] = None,
    port: int = 43,
    timeout_sec: float = 8.0
) -> WhoisResult:
    """
    Executa consulta socket na porta 43 (ou porta especificada).
    """
    norm_dom = normalize_domain(domain)
    target_server = server or get_whois_server_for_domain(norm_dom)

    raw_response = ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout_sec)
            s.connect((target_server, port))
            s.sendall(f"{norm_dom}\r\n".encode("utf-8"))

            buffer = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buffer.append(chunk)

            raw_bytes = b"".join(buffer)
            try:
                raw_response = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raw_response = raw_bytes.decode("latin1", errors="replace")

        # Se o servidor responder com redirecionamento de WHOIS server (típico da IANA/Verisign)
        m_redirect = re.search(r"whois\s*server\s*:\s*([a-zA-Z0-9.-]+)", raw_response, re.IGNORECASE)
        if m_redirect and target_server in ("whois.iana.org", "whois.verisign-grs.com"):
            next_server = m_redirect.group(1).strip()
            if next_server != target_server:
                return query_whois_socket(norm_dom, server=next_server, port=43, timeout_sec=timeout_sec)

    except Exception as e:
        raw_response = f"Não foi possível consultar {target_server}: {e}"

    return parse_whois_text(norm_dom, raw_response)

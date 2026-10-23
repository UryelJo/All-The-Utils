"""
Lógica pura da ferramenta Diagnóstico de Rede e Domínios.
Inspeção SSL, Whois e verificação de disponibilidade HTTP sem acoplamento ao Qt.
"""
from dataclasses import dataclass
import datetime
import socket
import ssl
import time
from typing import Dict, Optional, Tuple
import urllib.error
import urllib.request


@dataclass
class SslInspectionResult:
    dominio: str
    emissor: str
    sujeito: str
    valido_de: str
    valido_ate: str
    dias_restantes: str
    sans: str


@dataclass
class SiteCheckResult:
    is_online: bool
    status_code: Optional[int]
    elapsed_ms: float
    message: str


def inspect_ssl_certificate(hostname: str, port: int = 443) -> SslInspectionResult:
    """Inspeciona o certificado SSL/TLS de um domínio usando o módulo ssl nativo."""
    hostname = hostname.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    ctx = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=6) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()

    not_after_str = cert.get("notAfter", "")
    not_before_str = cert.get("notBefore", "")

    fmt = "%b %d %H:%M:%S %Y %Z"
    exp_date = datetime.datetime.strptime(not_after_str, fmt)
    start_date = datetime.datetime.strptime(not_before_str, fmt)
    days_left = (exp_date - datetime.datetime.utcnow()).days

    issuer_dict = dict(x[0] for x in cert.get("issuer", ()))
    subject_dict = dict(x[0] for x in cert.get("subject", ()))
    sans = [val for key, val in cert.get("subjectAltName", ()) if key == "DNS"]

    return SslInspectionResult(
        dominio=hostname,
        emissor=issuer_dict.get("organizationName") or issuer_dict.get("commonName", "Desconhecido"),
        sujeito=subject_dict.get("commonName", hostname),
        valido_de=start_date.strftime("%d/%m/%Y %H:%M UTC"),
        valido_ate=exp_date.strftime("%d/%m/%Y %H:%M UTC"),
        dias_restantes=f"{days_left} dias ({'Válido' if days_left > 0 else 'EXPIRADO'})",
        sans=", ".join(sans[:8]) + ("..." if len(sans) > 8 else ""),
    )


def perform_whois_query(domain: str) -> str:
    """Executa consulta WHOIS via socket na porta 43."""
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0].strip()
    server = "whois.registro.br" if domain.endswith(".br") else "whois.iana.org"

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(6)
        s.connect((server, 43))
        s.send(f"{domain}\r\n".encode("utf-8"))
        response = b""
        while True:
            data = s.recv(4096)
            if not data:
                break
            response += data
        s.close()
        text = response.decode("utf-8", errors="replace")

        # Se for iana e indicar servidor específico (ex: verisign)
        if "whois:" in text.lower():
            for line in text.splitlines():
                if line.lower().startswith("whois:"):
                    sub_server = line.split(":", 1)[1].strip()
                    if sub_server and sub_server != server:
                        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s2.settimeout(6)
                        s2.connect((sub_server, 43))
                        s2.send(f"{domain}\r\n".encode("utf-8"))
                        resp2 = b""
                        while True:
                            d2 = s2.recv(4096)
                            if not d2:
                                break
                            resp2 += d2
                        s2.close()
                        return resp2.decode("utf-8", errors="replace")
        return text
    except Exception as e:
        return f"Erro ao consultar WHOIS em {server}: {str(e)}"


def check_site_availability(url: str) -> SiteCheckResult:
    """Verifica a disponibilidade de uma URL via requisição HTTP/HTTPS."""
    if not url.startswith("http"):
        url = f"https://{url}"

    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            elapsed = (time.time() - t0) * 1000
            code = resp.getcode()
            return SiteCheckResult(
                is_online=True,
                status_code=code,
                elapsed_ms=elapsed,
                message=f"Status: {code} OK | Tempo de resposta: {elapsed:.0f} ms | Servidor Online!",
            )
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - t0) * 1000
        return SiteCheckResult(
            is_online=True,
            status_code=e.code,
            elapsed_ms=elapsed,
            message=f"Status HTTP: {e.code} ({e.reason}) | Tempo: {elapsed:.0f} ms",
        )
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        return SiteCheckResult(
            is_online=False,
            status_code=None,
            elapsed_ms=elapsed,
            message=f"Site Inacessível ou Offline: {str(e)}",
        )

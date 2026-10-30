"""Inteligência de domínio: WHOIS nativo, DNS, TLS/SSL, tecnologias e dorks.

O WHOIS é consultado diretamente por socket na porta 43 (sem a biblioteca
`whois`), o DNS usa `dnspython` quando instalado e, na ausência dele, um cliente
UDP/TCP mínimo escrito apenas com a biblioteca padrão. O certificado TLS é lido
com `ssl` e as tecnologias são inferidas por cabeçalhos, cookies e marcas no HTML.
"""
from __future__ import annotations

import json
import random
import re
import socket
import ssl
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import dependencia_disponivel, truncar
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    botao_copiar,
    criar_card,
    criar_saida_texto,
    criar_tabela,
    executar_assincrono,
    mostrar_erro,
    preencher_tabela,
)

_log = get_logger("osint.domain_intel")

DNS_PADRAO = "1.1.1.1"

SERVIDORES_WHOIS = {
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "org": "whois.pir.org",
    "info": "whois.afilias.net",
    "biz": "whois.biz",
    "io": "whois.nic.io",
    "co": "whois.nic.co",
    "dev": "whois.nic.google",
    "app": "whois.nic.google",
    "xyz": "whois.nic.xyz",
    "online": "whois.nic.online",
    "site": "whois.nic.site",
    "me": "whois.nic.me",
    "tv": "whois.nic.tv",
    "cc": "ccwhois.verisign-grs.com",
    "br": "whois.registro.br",
    "pt": "whois.dns.pt",
    "uk": "whois.nic.uk",
    "de": "whois.denic.de",
    "fr": "whois.nic.fr",
    "it": "whois.nic.it",
    "es": "whois.nic.es",
    "nl": "whois.domain-registry.nl",
    "ru": "whois.tcinet.ru",
    "jp": "whois.jprs.jp",
    "au": "whois.auda.org.au",
    "ca": "whois.cira.ca",
    "mx": "whois.mx",
    "ar": "whois.nic.ar",
}

TIPOS_DNS = {
    "A": 1,
    "NS": 2,
    "CNAME": 5,
    "SOA": 6,
    "MX": 15,
    "TXT": 16,
    "AAAA": 28,
    "CAA": 257,
}

TIPOS_DNS_PADRAO: Tuple[str, ...] = ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "CAA")


# --------------------------------------------------------------------- domínio
def normalizar_dominio(valor: str) -> str:
    """Aceita domínio, URL ou host e devolve apenas o domínio normalizado."""
    texto = str(valor or "").strip().lower()
    if not texto:
        raise ValueError("Informe um domínio.")
    if "://" in texto:
        texto = urlparse(texto).hostname or ""
    texto = texto.split("/")[0].split("?")[0].split("#")[0].strip(".")
    if texto.startswith("www."):
        texto = texto[4:]
    if not texto:
        raise ValueError("Domínio inválido.")
    if len(texto) > 253:
        raise ValueError("Domínio longo demais.")
    rotulo = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if not re.fullmatch(rf"{rotulo}(?:\.{rotulo})+", texto):
        raise ValueError("Formato de domínio inválido. Exemplo: exemplo.com.br")
    return texto


def _tld(dominio: str) -> str:
    return dominio.rsplit(".", 1)[-1]


# ------------------------------------------------------------------------ DNS
class _RespostaTruncada(RuntimeError):
    """Sinaliza que a resposta UDP veio truncada e exige nova tentativa em TCP."""


def _montar_consulta(nome: str, tipo: str) -> Tuple[int, bytes]:
    identificador = random.randint(0, 0xFFFF)
    cabecalho = struct.pack(">HHHHHH", identificador, 0x0100, 1, 0, 0, 0)
    pergunta = b""
    for parte in nome.rstrip(".").split("."):
        codificado = parte.encode("idna")
        pergunta += bytes([len(codificado)]) + codificado
    pergunta += b"\x00" + struct.pack(">HH", TIPOS_DNS[tipo], 1)
    return identificador, cabecalho + pergunta


def _ler_nome(dados: bytes, deslocamento: int) -> Tuple[str, int]:
    partes: List[str] = []
    while deslocamento < len(dados):
        tamanho = dados[deslocamento]
        if tamanho == 0:
            deslocamento += 1
            break
        if tamanho & 0xC0 == 0xC0:
            if deslocamento + 1 >= len(dados):
                break
            ponteiro = ((tamanho & 0x3F) << 8) | dados[deslocamento + 1]
            sub, _ = _ler_nome(dados, ponteiro)
            if sub:
                partes.append(sub)
            deslocamento += 2
            return ".".join(partes), deslocamento
        deslocamento += 1
        partes.append(dados[deslocamento : deslocamento + tamanho].decode("latin-1", errors="replace"))
        deslocamento += tamanho
    return ".".join(p for p in partes if p), deslocamento


def _decodificar_rdata(dados: bytes, tipo: int, inicio: int, tamanho: int) -> Any:
    trecho = dados[inicio : inicio + tamanho]
    if tipo == 1 and len(trecho) == 4:
        return socket.inet_ntoa(trecho)
    if tipo == 28 and len(trecho) == 16:
        return socket.inet_ntop(socket.AF_INET6, trecho)
    if tipo in (2, 5):
        nome, _ = _ler_nome(dados, inicio)
        return nome
    if tipo == 15 and len(trecho) >= 3:
        preferencia = struct.unpack(">H", trecho[:2])[0]
        nome, _ = _ler_nome(dados, inicio + 2)
        return f"{preferencia} {nome}"
    if tipo == 16:
        textos: List[str] = []
        posicao = 0
        while posicao < len(trecho):
            tamanho_texto = trecho[posicao]
            posicao += 1
            textos.append(trecho[posicao : posicao + tamanho_texto].decode("utf-8", errors="replace"))
            posicao += tamanho_texto
        return " ".join(textos)
    if tipo == 6:
        mname, pos = _ler_nome(dados, inicio)
        rname, pos = _ler_nome(dados, pos)
        if pos + 20 <= len(dados):
            serial, refresh, retry, expire, minimo = struct.unpack(">IIIII", dados[pos : pos + 20])
            return f"{mname} {rname} serial={serial} refresh={refresh} retry={retry} expire={expire} minimum={minimo}"
        return f"{mname} {rname}"
    if tipo == 257 and len(trecho) >= 2:
        flags = trecho[0]
        tamanho_tag = trecho[1]
        tag = trecho[2 : 2 + tamanho_tag].decode("latin-1", errors="replace")
        valor = trecho[2 + tamanho_tag :].decode("latin-1", errors="replace")
        return f"flags={flags} {tag}={valor}"
    return trecho.hex()


def _consultar_dns_udp(nome: str, tipo: str, servidor: str, timeout: float) -> Dict[str, Any]:
    identificador, pacote = _montar_consulta(nome, tipo)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(pacote, (servidor, 53))
        dados, _ = sock.recvfrom(4096)
    if len(dados) < 12:
        raise RuntimeError("Resposta DNS truncada.")
    resposta_id, flags, qdcount, ancount, _, _ = struct.unpack(">HHHHHH", dados[:12])
    if resposta_id != identificador:
        raise RuntimeError("Identificador DNS não corresponde à consulta.")
    if flags & 0x0200:
        raise _RespostaTruncada("Resposta DNS truncada; repetindo em TCP.")
    deslocamento = 12
    for _ in range(qdcount):
        _, deslocamento = _ler_nome(dados, deslocamento)
        deslocamento += 4
    registros: List[Dict[str, Any]] = []
    for _ in range(ancount):
        nome_resposta, deslocamento = _ler_nome(dados, deslocamento)
        if deslocamento + 10 > len(dados):
            break
        tipo_reg, classe, ttl, tamanho = struct.unpack(">HHIH", dados[deslocamento : deslocamento + 10])
        deslocamento += 10
        valor = _decodificar_rdata(dados, tipo_reg, deslocamento, tamanho)
        deslocamento += tamanho
        registros.append(
            {
                "tipo": tipo,
                "nome": nome_resposta or nome,
                "valor": valor if isinstance(valor, str) else str(valor),
                "ttl": ttl,
                "classe": classe,
            }
        )
    return {"resposta": flags & 0x000F, "registros": registros}


def _consultar_dns_tcp(nome: str, tipo: str, servidor: str, timeout: float) -> Dict[str, Any]:
    identificador, pacote = _montar_consulta(nome, tipo)
    with socket.create_connection((servidor, 53), timeout=timeout) as sock:
        sock.sendall(struct.pack(">H", len(pacote)) + pacote)
        tamanho = struct.unpack(">H", sock.recv(2))[0]
        dados = b""
        while len(dados) < tamanho:
            pedaco = sock.recv(tamanho - len(dados))
            if not pedaco:
                break
            dados += pedaco
    if len(dados) < 12:
        raise RuntimeError("Resposta DNS/TCP vazia.")
    _, flags, qdcount, ancount, _, _ = struct.unpack(">HHHHHH", dados[:12])
    deslocamento = 12
    for _ in range(qdcount):
        _, deslocamento = _ler_nome(dados, deslocamento)
        deslocamento += 4
    registros: List[Dict[str, Any]] = []
    for _ in range(ancount):
        nome_resposta, deslocamento = _ler_nome(dados, deslocamento)
        if deslocamento + 10 > len(dados):
            break
        tipo_reg, classe, ttl, tamanho_reg = struct.unpack(">HHIH", dados[deslocamento : deslocamento + 10])
        deslocamento += 10
        valor = _decodificar_rdata(dados, tipo_reg, deslocamento, tamanho_reg)
        deslocamento += tamanho_reg
        registros.append(
            {
                "tipo": tipo,
                "nome": nome_resposta or nome,
                "valor": valor if isinstance(valor, str) else str(valor),
                "ttl": ttl,
                "classe": classe,
            }
        )
    return {"resposta": flags & 0x000F, "registros": registros}


def _consultar_dns_nativo(nome: str, tipo: str, servidor: str, timeout: float) -> List[Dict[str, Any]]:
    try:
        resultado = _consultar_dns_udp(nome, tipo, servidor, timeout)
    except _RespostaTruncada:
        resultado = _consultar_dns_tcp(nome, tipo, servidor, timeout)
    if resultado["resposta"] == 3:
        return []
    return resultado["registros"]


def consultar_dns(
    dominio: str,
    tipos: Sequence[str] = TIPOS_DNS_PADRAO,
    timeout: float = 5.0,
    servidor: str = DNS_PADRAO,
    ao_log: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """Consulta registros DNS e devolve ``{tipo: [registros]}`` com o motor usado."""
    dominio = normalizar_dominio(dominio)
    usar_dnspython = dependencia_disponivel("dns")
    motor = "dnspython" if usar_dnspython else "socket"
    saida: Dict[str, List[Dict[str, Any]]] = {tipo: [] for tipo in tipos}
    erros: Dict[str, str] = {}

    resolvedor = None
    if usar_dnspython:
        try:
            import dns.resolver

            resolvedor = dns.resolver.Resolver(configure=True)
            resolvedor.lifetime = timeout
            resolvedor.timeout = timeout
        except Exception as exc:  # noqa: BLE001
            if ao_log is not None:
                ao_log("WARN", f"dnspython indisponível na prática ({exc}); usando socket.")
            usar_dnspython = False
            motor = "socket"

    for tipo in tipos:
        try:
            if usar_dnspython and resolvedor is not None:
                import dns.resolver

                registros: List[Dict[str, Any]] = []
                try:
                    resposta = resolvedor.resolve(dominio, tipo, raise_on_no_answer=False)
                except dns.resolver.NXDOMAIN:
                    continue
                except dns.resolver.NoAnswer:
                    continue
                for item in resposta or []:
                    registros.append(
                        {
                            "tipo": tipo,
                            "nome": dominio,
                            "valor": item.to_text().strip('"') if hasattr(item, "to_text") else str(item),
                            "ttl": getattr(resposta, "rrset", None).ttl if getattr(resposta, "rrset", None) else 0,
                            "classe": 1,
                        }
                    )
                saida[tipo] = registros
            else:
                saida[tipo] = _consultar_dns_nativo(dominio, tipo, servidor, timeout)
        except Exception as exc:  # noqa: BLE001 - cada tipo é independente
            erros[tipo] = str(exc)
            if ao_log is not None:
                ao_log("DEBUG", f"DNS {tipo} sem resposta para {dominio}: {exc}")
    return {"dominio": dominio, "motor": motor, "registros": saida, "erros": erros}


# ---------------------------------------------------------------------- WHOIS
def _consultar_whois_bruto(servidor: str, consulta: str, timeout: float = 10.0) -> str:
    with socket.create_connection((servidor, 43), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall((consulta + "\r\n").encode("idna", errors="ignore"))
        partes: List[bytes] = []
        while True:
            try:
                pedaco = sock.recv(4096)
            except socket.timeout:
                break
            if not pedaco:
                break
            partes.append(pedaco)
    return b"".join(partes).decode("utf-8", errors="replace")


def _servidor_whois(dominio: str, timeout: float) -> str:
    try:
        resposta = _consultar_whois_bruto("whois.iana.org", f"domain {dominio}", timeout)
        for linha in resposta.splitlines():
            if linha.lower().startswith("refer:"):
                return linha.split(":", 1)[1].strip()
            if linha.lower().startswith("whois:"):
                return linha.split(":", 1)[1].strip()
    except OSError:
        pass
    return SERVIDORES_WHOIS.get(_tld(dominio), "")


def _parsear_whois(texto: str) -> Dict[str, str]:
    campos: Dict[str, str] = {}
    for linha in texto.splitlines():
        if not linha or linha.startswith("%") or linha.startswith("#") or ":" not in linha:
            continue
        chave, valor = linha.split(":", 1)
        chave = chave.strip()
        valor = " ".join(valor.split())
        if not chave or not valor:
            continue
        if chave in campos and len(campos[chave]) > len(valor):
            continue
        campos[chave] = valor
    return campos


def consultar_whois(dominio: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Consulta o WHOIS na porta 43 e devolve texto bruto, servidor e campos."""
    dominio = normalizar_dominio(dominio)
    servidor = _servidor_whois(dominio, timeout)
    if not servidor:
        return {
            "dominio": dominio,
            "servidor": "",
            "texto": "",
            "campos": {},
            "disponivel": None,
            "erro": f"Nenhum servidor WHOIS conhecido para o TLD .{_tld(dominio)}.",
        }
    try:
        texto = _consultar_whois_bruto(servidor, dominio, timeout)
    except OSError as exc:
        return {
            "dominio": dominio,
            "servidor": servidor,
            "texto": "",
            "campos": {},
            "disponivel": None,
            "erro": f"Falha ao consultar {servidor}: {exc}",
        }

    minusculo = texto.lower()
    disponivel = any(
        marca in minusculo
        for marca in ("no match", "not found", "no entries found", "no data found", "domain not found")
    )
    if disponivel:
        disponivel = True
    elif texto.strip():
        disponivel = False

    return {
        "dominio": dominio,
        "servidor": servidor,
        "texto": texto,
        "campos": _parsear_whois(texto),
        "disponivel": disponivel,
        "erro": "",
    }


# ------------------------------------------------------------------ TLS / SSL
def _certificado_para_dict(cert: Dict[str, Any]) -> Dict[str, Any]:
    def _achatar(entradas) -> Dict[str, str]:
        saida: Dict[str, str] = {}
        for grupo in entradas or ():
            for chave, valor in grupo:
                saida.setdefault(chave, valor)
        return saida

    def _data(valor: str) -> Optional[datetime]:
        try:
            return datetime.strptime(valor, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

    inicio = _data(str(cert.get("notBefore", "")))
    fim = _data(str(cert.get("notAfter", "")))
    agora = datetime.now(timezone.utc)
    return {
        "assunto": _achatar(cert.get("subject")),
        "emissor": _achatar(cert.get("issuer")),
        "valido_de": inicio.isoformat() if inicio else str(cert.get("notBefore", "")),
        "valido_ate": fim.isoformat() if fim else str(cert.get("notAfter", "")),
        "dias_restantes": (fim - agora).days if fim else None,
        "expirado": bool(fim and fim < agora),
        "san": [valor for tipo, valor in cert.get("subjectAltName", ()) if tipo in ("DNS", "IP Address")],
        "versao": cert.get("version"),
        "serial": str(cert.get("serialNumber", "")),
    }


def analisar_ssl(dominio: str, porta: int = 443, timeout: float = 8.0) -> Dict[str, Any]:
    """Lê o certificado e os parâmetros TLS do host, marcando falhas de validação."""
    dominio = normalizar_dominio(dominio)
    base: Dict[str, Any] = {
        "dominio": dominio,
        "porta": porta,
        "alcancavel": False,
        "validacao": "não verificada",
        "erro": "",
        "certificado": {},
        "protocolo": "",
        "cifra": "",
    }

    def _conectar(contexto: ssl.SSLContext):
        bruto = socket.create_connection((dominio, porta), timeout=timeout)
        return contexto.wrap_socket(bruto, server_hostname=dominio)

    try:
        contexto = ssl.create_default_context()
        with _conectar(contexto) as tls:
            cert = tls.getpeercert() or {}
            base.update(
                {
                    "alcancavel": True,
                    "validacao": "válida",
                    "certificado": _certificado_para_dict(cert),
                    "protocolo": tls.version() or "",
                    "cifra": (tls.cipher() or ("", "", 0))[0],
                }
            )
            return base
    except ssl.SSLCertVerificationError as exc:
        base["validacao"] = f"inválida ou incompleta: {exc.verify_message or exc}"
    except (ssl.SSLError, OSError) as exc:
        base["erro"] = str(exc)
        return base

    try:
        contexto_permissivo = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        contexto_permissivo.check_hostname = False
        contexto_permissivo.verify_mode = ssl.CERT_NONE
        with _conectar(contexto_permissivo) as tls:
            der = tls.getpeercert(binary_form=True) or b""
            base.update(
                {
                    "alcancavel": True,
                    "protocolo": tls.version() or "",
                    "cifra": (tls.cipher() or ("", "", 0))[0],
                    "certificado_der_bytes": len(der),
                }
            )
            base["certificado"] = {"aviso": "Certificado não confiável; dados completos exigem validação."}
    except (ssl.SSLError, OSError) as exc:
        base["erro"] = str(exc)
    return base


# ------------------------------------------------------- tecnologias e dorks
_REGRAS_CABECALHO: Tuple[Tuple[str, str, str, str], ...] = (
    ("server", r"cloudflare", "Cloudflare", "CDN / WAF"),
    ("server", r"nginx", "Nginx", "Servidor web"),
    ("server", r"apache", "Apache HTTP Server", "Servidor web"),
    ("server", r"microsoft-iis", "Microsoft IIS", "Servidor web"),
    ("server", r"litespeed", "LiteSpeed", "Servidor web"),
    ("server", r"caddy", "Caddy", "Servidor web"),
    ("server", r"gunicorn", "Gunicorn", "Servidor de aplicação"),
    ("server", r"openresty", "OpenResty", "Servidor web"),
    ("server", r"amazon", "Amazon CloudFront", "CDN / WAF"),
    ("x-powered-by", r"php", "PHP", "Linguagem"),
    ("x-powered-by", r"asp\.net", "ASP.NET", "Framework"),
    ("x-powered-by", r"express", "Express", "Framework"),
    ("x-powered-by", r"next\.js", "Next.js", "Framework"),
    ("x-powered-by", r"nuxt", "Nuxt", "Framework"),
    ("x-powered-by", r"servlet", "Java Servlet", "Plataforma"),
    ("x-generator", r"drupal", "Drupal", "CMS"),
    ("x-drupal-cache", r".", "Drupal", "CMS"),
    ("x-shopify-stage", r".", "Shopify", "E-commerce"),
    ("x-vercel-id", r".", "Vercel", "Hospedagem"),
    ("x-nextjs-cache", r".", "Next.js", "Framework"),
    ("cf-ray", r".", "Cloudflare", "CDN / WAF"),
    ("x-amz-cf-id", r".", "Amazon CloudFront", "CDN / WAF"),
    ("x-akamai-transformed", r".", "Akamai", "CDN / WAF"),
    ("x-litespeed-cache", r".", "LiteSpeed", "Servidor web"),
    ("x-github-request-id", r".", "GitHub Pages", "Hospedagem"),
    ("x-fastly-request-id", r".", "Fastly", "CDN / WAF"),
)

_REGRAS_CORPO: Tuple[Tuple[str, str, str], ...] = (
    (r"wp-content|wp-includes", "WordPress", "CMS"),
    (r"/_next/static|__NEXT_DATA__", "Next.js", "Framework"),
    (r"__NUXT__|/_nuxt/", "Nuxt", "Framework"),
    (r"ng-version=|ng-app", "Angular", "Framework"),
    (r"data-reactroot|react-dom", "React", "Biblioteca"),
    (r"vue(?:\.min)?\.js|data-v-[0-9a-f]{8}", "Vue.js", "Biblioteca"),
    (r"svelte-[a-z0-9]{6}", "Svelte", "Framework"),
    (r"astro-island|astro-slot", "Astro", "Framework"),
    (r"drupal-settings-json|/sites/default/files", "Drupal", "CMS"),
    (r"joomla", "Joomla", "CMS"),
    (r"magento|mage/cookies", "Magento", "E-commerce"),
    (r"cdn\.shopify\.com|shopify-section", "Shopify", "E-commerce"),
    (r"woocommerce", "WooCommerce", "E-commerce"),
    (r"prestashop", "PrestaShop", "E-commerce"),
    (r"elementor", "Elementor", "Construtor de páginas"),
    (r"squarespace", "Squarespace", "CMS"),
    (r"static\.wixstatic\.com", "Wix", "CMS"),
    (r"ghost-url|content=\"ghost", "Ghost", "CMS"),
    (r"bootstrap(?:\.min)?\.(?:css|js)", "Bootstrap", "CSS"),
    (r"tailwind", "Tailwind CSS", "CSS"),
    (r"jquery(?:-[\d.]+)?(?:\.min)?\.js", "jQuery", "Biblioteca"),
    (r"lodash(?:\.min)?\.js", "Lodash", "Biblioteca"),
    (r"font-awesome|fontawesome", "Font Awesome", "Ícones"),
    (r"googletagmanager\.com", "Google Tag Manager", "Analytics"),
    (r"google-analytics\.com|gtag\(", "Google Analytics", "Analytics"),
    (r"hotjar", "Hotjar", "Analytics"),
    (r"cloudflare", "Cloudflare", "CDN / WAF"),
    (r"recaptcha", "Google reCAPTCHA", "Segurança"),
    (r"stripe\.com/v3|js\.stripe\.com", "Stripe", "Pagamentos"),
    (r"paypal\.com/sdk", "PayPal", "Pagamentos"),
    (r"disqus\.com", "Disqus", "Comentários"),
)

_REGRAS_COOKIE: Tuple[Tuple[str, str, str], ...] = (
    ("phpsessid", "PHP", "Linguagem"),
    ("jsessionid", "Java", "Plataforma"),
    ("asp.net_sessionid", "ASP.NET", "Framework"),
    ("csrftoken", "Django", "Framework"),
    ("laravel_session", "Laravel", "Framework"),
    ("wp-settings", "WordPress", "CMS"),
    ("_shopify_s", "Shopify", "E-commerce"),
    ("_ga", "Google Analytics", "Analytics"),
    ("__cfduid", "Cloudflare", "CDN / WAF"),
    ("incap_ses", "Imperva", "CDN / WAF"),
)

_META_GENERATOR = re.compile(
    r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']([^\"']+)[\"']", re.IGNORECASE
)


def detectar_tecnologias(
    cabecalhos: Dict[str, str],
    html: str = "",
    cookies: str = "",
) -> List[Dict[str, str]]:
    """Infere tecnologias a partir de cabeçalhos, cookies e marcas no HTML."""
    encontrados: Dict[str, Dict[str, str]] = {}
    cabecalhos_min = {str(chave).lower(): str(valor) for chave, valor in (cabecalhos or {}).items()}

    for chave, padrao, nome, categoria in _REGRAS_CABECALHO:
        valor = cabecalhos_min.get(chave, "")
        if valor and re.search(padrao, valor, re.IGNORECASE):
            encontrados.setdefault(
                nome,
                {"nome": nome, "categoria": categoria, "evidencia": f"Cabeçalho {chave}: {truncar(valor, 80)}"},
            )

    for padrao, nome, categoria in _REGRAS_CORPO:
        if html and re.search(padrao, html, re.IGNORECASE):
            encontrados.setdefault(
                nome,
                {"nome": nome, "categoria": categoria, "evidencia": f"Marca no HTML: {padrao}"},
            )

    achado_generator = _META_GENERATOR.search(html or "")
    if achado_generator:
        conteudo = achado_generator.group(1).strip()
        nome = conteudo.split()[0] if conteudo else "Desconhecido"
        encontrados.setdefault(
            nome,
            {"nome": conteudo, "categoria": "Gerador declarado", "evidencia": "Meta tag generator"},
        )

    for chave, nome, categoria in _REGRAS_COOKIE:
        if cookies and chave in cookies.lower():
            encontrados.setdefault(
                nome,
                {"nome": nome, "categoria": categoria, "evidencia": f"Cookie {chave}"},
            )

    return sorted(encontrados.values(), key=lambda item: (item["categoria"], item["nome"]))


def coletar_web(dominio: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Baixa cabeçalhos e o início do HTML para inferir tecnologias."""
    import requests

    url = f"https://{dominio}/"
    saida: Dict[str, Any] = {
        "url": url,
        "status": None,
        "cabecalhos": {},
        "cookies": "",
        "html": "",
        "redirecionado_para": "",
        "erro": "",
    }
    try:
        resposta = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WinToolbox-OSINT",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            },
        )
        saida["status"] = resposta.status_code
        saida["cabecalhos"] = dict(resposta.headers)
        saida["cookies"] = "; ".join(f"{k}={v}" for k, v in resposta.cookies.items())
        saida["html"] = resposta.text[:300_000]
        if resposta.history:
            saida["redirecionado_para"] = resposta.url
    except Exception as exc:  # noqa: BLE001
        saida["erro"] = str(exc)
    return saida


def gerar_dorks(dominio: str) -> List[Dict[str, str]]:
    """Gera dorks de reconhecimento para mecanismos de busca públicos."""
    dominio = normalizar_dominio(dominio)
    modelos: List[Tuple[str, str, str]] = (
        ("Páginas indexadas", "site:{d}", "Mapeia o que já está indexado publicamente."),
        ("Documentos e planilhas", "site:{d} (filetype:pdf OR filetype:doc OR filetype:xlsx OR filetype:csv)", "Localiza documentos com possível dado sensível."),
        ("Painéis administrativos", "site:{d} (inurl:admin OR inurl:painel OR inurl:login OR inurl:dashboard)", "Aponta superfícies administrativas expostas."),
        ("Diretórios abertos", "site:{d} intitle:\"index of\"", "Procura listagem de diretórios habilitada."),
        ("Arquivos de configuração", "site:{d} (ext:env OR ext:ini OR ext:conf OR ext:yml OR ext:json)", "Busca artefatos de configuração vazados."),
        ("Chaves e credenciais", "site:{d} (intext:api_key OR intext:password OR intext:secret)", "Detecta vazamento de segredos em texto indexado."),
        ("Mensagens de erro", "site:{d} (intext:\"SQL syntax\" OR intext:\"stack trace\" OR intext:\"Warning: mysql\")", "Revela erros que expõem stack tecnológico."),
        ("Backups", "site:{d} (ext:bak OR ext:old OR ext:backup OR ext:sql OR ext:zip)", "Encontra arquivos de backup publicados por engano."),
        ("Subdomínios citados", "site:{d} -site:www.{d}", "Descobre subdomínios indexados fora do host principal."),
        ("Menções externas", "\"{d}\" -site:{d}", "Localiza menções ao domínio em outros sites."),
        ("Câmeras e dispositivos", "site:{d} inurl:\"view.shtml\" OR inurl:\"axis-cgi\"", "Verifica dispositivos de rede indexados."),
        ("Documentos do Office", "site:{d} (filetype:docx OR filetype:pptx OR filetype:xls)", "Amplia a busca em formatos do Office."),
        ("Pastas de upload", "site:{d} (inurl:upload OR inurl:uploads OR inurl:files)", "Identifica repositórios de upload expostos."),
        ("Parâmetros de erro", "site:{d} inurl:\"error\" OR inurl:\"debug\"", "Sinaliza páginas de depuração."),
    )
    return [
        {"titulo": titulo, "dork": modelo.format(d=dominio), "objetivo": objetivo}
        for titulo, modelo, objetivo in modelos
    ]


def coletar_inteligencia(
    dominio: str,
    incluir_whois: bool = True,
    incluir_dns: bool = True,
    incluir_ssl: bool = True,
    incluir_web: bool = True,
    timeout: float = 10.0,
    ao_log: Optional[Callable[[str, str], None]] = None,
    ao_progresso: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """Executa as etapas selecionadas e consolida o dossiê do domínio."""
    dominio = normalizar_dominio(dominio)
    etapas = [
        nome
        for nome, ativo in (
            ("whois", incluir_whois),
            ("dns", incluir_dns),
            ("ssl", incluir_ssl),
            ("web", incluir_web),
            ("dorks", True),
        )
        if ativo
    ]
    total = len(etapas)
    feitos = 0
    dossie: Dict[str, Any] = {
        "dominio": dominio,
        "consultado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "whois": {},
        "dns": {},
        "ssl": {},
        "web": {},
        "tecnologias": [],
        "dorks": [],
        "erros": [],
    }

    def _passo(nome: str) -> None:
        nonlocal feitos
        feitos += 1
        if ao_progresso is not None:
            ao_progresso(feitos, total, nome)

    if incluir_whois:
        if ao_log is not None:
            ao_log("INFO", f"Consultando WHOIS de {dominio}.")
        try:
            dossie["whois"] = consultar_whois(dominio, timeout)
            if dossie["whois"].get("erro"):
                dossie["erros"].append(f"WHOIS: {dossie['whois']['erro']}")
        except Exception as exc:  # noqa: BLE001
            dossie["erros"].append(f"WHOIS: {exc}")
        _passo("WHOIS")

    if incluir_dns:
        if ao_log is not None:
            ao_log("INFO", f"Consultando registros DNS de {dominio}.")
        try:
            dossie["dns"] = consultar_dns(dominio, timeout=min(timeout, 6.0), ao_log=ao_log)
        except Exception as exc:  # noqa: BLE001
            dossie["erros"].append(f"DNS: {exc}")
        _passo("DNS")

    if incluir_ssl:
        if ao_log is not None:
            ao_log("INFO", f"Negociando TLS com {dominio}:443.")
        try:
            dossie["ssl"] = analisar_ssl(dominio, timeout=min(timeout, 8.0))
            if dossie["ssl"].get("erro"):
                dossie["erros"].append(f"TLS: {dossie['ssl']['erro']}")
        except Exception as exc:  # noqa: BLE001
            dossie["erros"].append(f"TLS: {exc}")
        _passo("TLS/SSL")

    if incluir_web:
        if ao_log is not None:
            ao_log("INFO", f"Coletando cabeçalhos e HTML de {dominio}.")
        try:
            dossie["web"] = coletar_web(dominio, timeout)
            dossie["tecnologias"] = detectar_tecnologias(
                dossie["web"].get("cabecalhos", {}),
                dossie["web"].get("html", ""),
                dossie["web"].get("cookies", ""),
            )
            if dossie["web"].get("erro"):
                dossie["erros"].append(f"HTTP: {dossie['web']['erro']}")
        except Exception as exc:  # noqa: BLE001
            dossie["erros"].append(f"HTTP: {exc}")
        _passo("Tecnologias")

    dossie["dorks"] = gerar_dorks(dominio)
    _passo("Dorks")
    return dossie


def resumo_dossie(dossie: Dict[str, Any]) -> str:
    """Monta um laudo textual em pt-BR a partir do dossiê."""
    linhas: List[str] = [
        f"Dossiê de {dossie.get('dominio', '')}",
        f"Consultado em: {dossie.get('consultado_em', '')}",
        "",
    ]
    whois = dossie.get("whois") or {}
    if whois:
        linhas.append("WHOIS")
        linhas.append(f"  Servidor: {whois.get('servidor') or '-'}")
        if whois.get("disponivel"):
            linhas.append("  Situação: domínio aparentemente disponível para registro")
        campos = whois.get("campos") or {}
        for chave in (
            "Domain Name", "domain", "Registrar", "registrar", "Creation Date", "created",
            "Registry Expiry Date", "expires", "Name Server", "nserver", "Registrant Organization",
        ):
            if chave in campos:
                linhas.append(f"  {chave}: {campos[chave]}")
        linhas.append("")

    dns = dossie.get("dns") or {}
    if dns:
        linhas.append(f"DNS (motor: {dns.get('motor', '-')})")
        for tipo, registros in (dns.get("registros") or {}).items():
            if not registros:
                continue
            valores = "; ".join(str(r.get("valor", "")) for r in registros)
            linhas.append(f"  {tipo}: {valores}")
        for tipo, erro in (dns.get("erros") or {}).items():
            linhas.append(f"  {tipo}: sem resposta ({truncar(erro, 80)})")
        linhas.append("")

    ssl_info = dossie.get("ssl") or {}
    if ssl_info:
        linhas.append("TLS/SSL")
        linhas.append(f"  Alcançável: {'sim' if ssl_info.get('alcancavel') else 'não'}")
        linhas.append(f"  Validação: {ssl_info.get('validacao', '-')}")
        linhas.append(f"  Protocolo: {ssl_info.get('protocolo') or '-'}")
        linhas.append(f"  Cifra: {ssl_info.get('cifra') or '-'}")
        cert = ssl_info.get("certificado") or {}
        if cert.get("assunto"):
            assunto = cert["assunto"]
            linhas.append(f"  Emissor: {cert.get('emissor', {}).get('commonName', '-')}")
            linhas.append(f"  Titular: {assunto.get('commonName', '-')}")
            linhas.append(f"  Válido até: {cert.get('valido_ate', '-')}")
            if cert.get("dias_restantes") is not None:
                linhas.append(f"  Dias restantes: {cert['dias_restantes']}")
            if cert.get("san"):
                linhas.append(f"  SAN: {', '.join(cert['san'][:12])}")
        linhas.append("")

    web = dossie.get("web") or {}
    if web:
        linhas.append("HTTP")
        linhas.append(f"  URL: {web.get('url', '-')}")
        linhas.append(f"  Status: {web.get('status') if web.get('status') is not None else '-'}")
        if web.get("redirecionado_para"):
            linhas.append(f"  Redirecionado para: {web['redirecionado_para']}")
        for chave in ("server", "x-powered-by", "content-type", "strict-transport-security", "content-security-policy"):
            valor = (web.get("cabecalhos") or {}).get(chave)
            if valor:
                linhas.append(f"  {chave}: {truncar(str(valor), 100)}")
        linhas.append("")

    tecnologias = dossie.get("tecnologias") or []
    if tecnologias:
        linhas.append(f"Tecnologias ({len(tecnologias)})")
        for item in tecnologias:
            linhas.append(f"  {item['nome']} [{item['categoria']}]: {item['evidencia']}")
        linhas.append("")

    dorks = dossie.get("dorks") or []
    if dorks:
        linhas.append(f"Dorks sugeridos ({len(dorks)})")
        for item in dorks:
            linhas.append(f"  {item['titulo']}: {item['dork']}")
        linhas.append("")

    erros = dossie.get("erros") or []
    if erros:
        linhas.append("Ocorrências")
        for erro in erros:
            linhas.append(f"  {erro}")
    return "\n".join(linhas)


@register
class DomainIntelTool(Tool):
    """Ferramenta de inteligência de domínio com fontes abertas."""

    id = "osint.domain_intel"
    name = "Inteligência de Domínio"
    category = "OSINT"
    description = (
        "Consolida WHOIS nativo (porta 43), registros DNS, certificado TLS, tecnologias "
        "detectadas nos cabeçalhos e HTML e dorks de reconhecimento em um único laudo"
    )
    keywords = [
        "osint", "domínio", "dominio", "whois", "dns", "ssl", "tls", "certificado",
        "tecnologias", "fingerprint", "dorks", "reconhecimento", "pegada digital",
    ]
    optional_deps = ["dnspython"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DomainIntelView(self, parent)


class DomainIntelView(PainelFerramenta):
    """Painel interativo da inteligência de domínio."""

    def __init__(self, tool: DomainIntelTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._dossie: Dict[str, Any] = {}
        self._executando = False

        self.adicionar_aviso(
            "Use apenas em domínios próprios ou para os quais você possui autorização. "
            "O WHOIS e o DNS consultam servidores públicos de registro e resolução; "
            "a coleta não contorna autenticação nem realiza varredura de portas.",
            destaque=False,
        )
        motor_dns = "dnspython instalado" if dependencia_disponivel("dns") else "cliente DNS nativo (socket)"
        self.adicionar_aviso(f"Motor de resolução DNS desta execução: {motor_dns}.", destaque=False)

        card_entrada, layout_entrada = self.adicionar_card("Alvo e etapas")
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Domínio:"))
        self.txt_dominio = QLineEdit()
        self.txt_dominio.setPlaceholderText("Ex.: exemplo.com.br")
        self.txt_dominio.returnPressed.connect(self._executar)
        linha.addWidget(self.txt_dominio, stretch=1)
        self.btn_executar = QPushButton("Executar Inteligência")
        self.btn_executar.setProperty("class", "primary")
        self.btn_executar.clicked.connect(self._executar)
        linha.addWidget(self.btn_executar)
        layout_entrada.addLayout(linha)

        linha_opcoes = QHBoxLayout()
        self.chk_whois = QCheckBox("WHOIS")
        self.chk_whois.setChecked(True)
        self.chk_dns = QCheckBox("DNS")
        self.chk_dns.setChecked(True)
        self.chk_ssl = QCheckBox("TLS/SSL")
        self.chk_ssl.setChecked(True)
        self.chk_web = QCheckBox("Tecnologias")
        self.chk_web.setChecked(True)
        for caixa in (self.chk_whois, self.chk_dns, self.chk_ssl, self.chk_web):
            linha_opcoes.addWidget(caixa)
        linha_opcoes.addWidget(QLabel("Tempo limite (s):"))
        self.spn_timeout = QSpinBox()
        self.spn_timeout.setRange(3, 60)
        self.spn_timeout.setValue(10)
        linha_opcoes.addWidget(self.spn_timeout)
        linha_opcoes.addStretch()
        layout_entrada.addLayout(linha_opcoes)

        linha_acoes = QHBoxLayout()
        self.btn_exportar = QPushButton("Exportar JSON...")
        self.btn_exportar.clicked.connect(self._exportar)
        linha_acoes.addWidget(self.btn_exportar)
        self.btn_copiar = botao_copiar(self._texto_laudo, self, "Copiar laudo")
        linha_acoes.addWidget(self.btn_copiar)
        self.lbl_status = QLabel("Nenhuma consulta executada.")
        self.lbl_status.setWordWrap(True)
        linha_acoes.addWidget(self.lbl_status, stretch=1)
        layout_entrada.addLayout(linha_acoes)

        card_dns, layout_dns = self.adicionar_card("Registros DNS")
        self.tabela_dns = criar_tabela(["Tipo", "Nome", "Valor", "TTL"], self)
        self.tabela_dns.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela_dns.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabela_dns.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabela_dns.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout_dns.addWidget(self.tabela_dns)

        card_whois, layout_whois = self.adicionar_card("WHOIS")
        self.tabela_whois = criar_tabela(["Campo", "Valor"], self)
        self.tabela_whois.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela_whois.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout_whois.addWidget(self.tabela_whois)

        card_tec, layout_tec = self.adicionar_card("Tecnologias detectadas")
        self.tabela_tec = criar_tabela(["Tecnologia", "Categoria", "Evidência"], self)
        self.tabela_tec.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela_tec.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabela_tec.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout_tec.addWidget(self.tabela_tec)

        card_dorks, layout_dorks = self.adicionar_card("Dorks sugeridos")
        self.tabela_dorks = criar_tabela(["Título", "Dork", "Objetivo"], self)
        self.tabela_dorks.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela_dorks.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabela_dorks.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout_dorks.addWidget(self.tabela_dorks)

        card_laudo, layout_laudo = self.adicionar_card("Laudo consolidado")
        self.saida = criar_saida_texto(260, self)
        layout_laudo.addWidget(self.saida)

        self.log = adicionar_log_painel(self, "Log da consulta")
        self.adicionar_espaco()

    def _texto_laudo(self) -> str:
        return self.saida.toPlainText()

    def _definir_execucao(self, ativa: bool) -> None:
        self._executando = ativa
        for botao in (self.btn_executar, self.btn_exportar):
            botao.setEnabled(not ativa)

    def _executar(self) -> None:
        if self._executando:
            return
        try:
            dominio = normalizar_dominio(self.txt_dominio.text())
        except ValueError as exc:
            mostrar_erro(self, "Domínio inválido", exc)
            return

        self._definir_execucao(True)
        self.lbl_status.setText(f"Consultando {dominio}...")
        for tabela in (self.tabela_dns, self.tabela_whois, self.tabela_tec, self.tabela_dorks):
            tabela.setRowCount(0)
        self.saida.clear()
        self.log.append_log("INFO", f"Iniciando dossiê de {dominio}.")

        def tarefa(ctx):
            return coletar_inteligencia(
                dominio,
                incluir_whois=self.chk_whois.isChecked(),
                incluir_dns=self.chk_dns.isChecked(),
                incluir_ssl=self.chk_ssl.isChecked(),
                incluir_web=self.chk_web.isChecked(),
                timeout=float(self.spn_timeout.value()),
                ao_log=ctx.log,
                ao_progresso=lambda feitos, total, etapa: ctx.progress(feitos, total, etapa),
            )

        def concluiu(dossie) -> None:
            self._definir_execucao(False)
            self._dossie = dossie or {}
            self._preencher()
            self.lbl_status.setText(
                f"Dossiê de {self._dossie.get('dominio', dominio)} concluído com "
                f"{len(self._dossie.get('tecnologias', []))} tecnologia(s) e "
                f"{len(self._dossie.get('dorks', []))} dork(s)."
            )
            self.log.append_log("INFO", "Dossiê concluído.")

        def falhou(erro: Exception) -> None:
            self._definir_execucao(False)
            self.lbl_status.setText("Falha na consulta.")
            self.log.append_log("ERROR", str(erro))
            mostrar_erro(self, "Falha na inteligência de domínio", erro)

        executar_assincrono(self, tarefa, concluiu, falhou)

    def _preencher(self) -> None:
        dossie = self._dossie
        linhas_dns: List[List[Any]] = []
        for tipo, registros in (dossie.get("dns", {}).get("registros") or {}).items():
            for registro in registros:
                linhas_dns.append(
                    [
                        registro.get("tipo", tipo),
                        registro.get("nome", ""),
                        registro.get("valor", ""),
                        registro.get("ttl", 0),
                    ]
                )
        preencher_tabela(self.tabela_dns, linhas_dns)

        campos = (dossie.get("whois") or {}).get("campos") or {}
        preencher_tabela(
            self.tabela_whois,
            [[chave, valor] for chave, valor in campos.items()],
        )

        preencher_tabela(
            self.tabela_tec,
            [
                [item.get("nome", ""), item.get("categoria", ""), item.get("evidencia", "")]
                for item in dossie.get("tecnologias", [])
            ],
        )

        preencher_tabela(
            self.tabela_dorks,
            [
                [item.get("titulo", ""), item.get("dork", ""), item.get("objetivo", "")]
                for item in dossie.get("dorks", [])
            ],
        )

        self.saida.setPlainText(resumo_dossie(dossie))

    def _exportar(self) -> None:
        if not self._dossie:
            mostrar_erro(self, "Nada para exportar", "Execute uma consulta antes de exportar.")
            return
        sugestao = f"dominio_{self._dossie.get('dominio', 'resultado')}.json"
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar dossiê", sugestao, "JSON (*.json)")
        if not destino:
            return
        try:
            dados = dict(self._dossie)
            web = dict(dados.get("web") or {})
            web.pop("html", None)
            dados["web"] = web
            Path(destino).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            self.lbl_status.setText(f"Dossiê exportado para {destino}.")
            self.log.append_log("INFO", f"Dossiê gravado em {destino}.")
        except OSError as exc:
            mostrar_erro(self, "Falha ao exportar", exc)

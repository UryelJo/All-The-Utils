"""
Lógica pura para auditoria defensiva de cabeçalhos HTTP de segurança.

Analisa cabeçalhos HTTP retornados por uma URL pública e avalia a conformidade
com boas práticas de segurança defensiva da OWASP e padrões web modernos.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from http.client import HTTPResponse
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("security.http_headers.logic")

# Cabeçalhos de segurança avaliados
SECURITY_HEADERS = [
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
    "Cross-Origin-Opener-Policy",
    "Cross-Origin-Embedder-Policy",
    "Cross-Origin-Resource-Policy",
]

# Cabeçalhos com potencial vazamento de versão/informação tecnológica
INFO_LEAK_HEADERS = [
    "Server",
    "X-Powered-By",
    "X-AspNet-Version",
    "X-AspNetMvc-Version",
    "X-Generator",
]


@dataclass
class HeaderFinding:
    """Representa a análise de um cabeçalho específico."""
    header: str
    value: str
    status: str  # "OK" | "Aviso" | "Ausente" | "Informativo"
    severity: str  # "Baixa" | "Média" | "Alta" | "Informativa"
    recommendation: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HeaderAuditResult:
    """Resultado consolidado da auditoria de cabeçalhos."""
    target_url: str
    effective_url: str
    status_code: int
    is_https: bool
    score: int
    grade: str  # "A+", "A", "B", "C", "D", "F"
    summary: str
    findings: List[HeaderFinding] = field(default_factory=list)
    raw_headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["findings"] = [f.to_dict() for f in self.findings]
        return data


def normalize_url(url: str) -> str:
    """
    Normaliza a URL fornecida pelo usuário, adicionando protocolo padrão caso omitido.

    Args:
        url: URL digitada (ex: "exemplo.com.br" ou "https://exemplo.com.br")

    Returns:
        URL normalizada com esquema HTTP ou HTTPS.
    """
    clean = url.strip()
    if not clean:
        raise ValueError("A URL informada não pode estar vazia.")

    if not re.match(r"^https?://", clean, re.IGNORECASE):
        clean = f"https://{clean}"

    parsed = urllib.parse.urlsplit(clean)
    if not parsed.netloc:
        raise ValueError(f"URL inválida ou sem nome de domínio: {url}")

    return clean


def _parse_directives(header_value: str) -> Dict[str, str]:
    """Extrai diretivas separadas por ponto-e-vírgula em dicionário minúsculo."""
    directives = {}
    for part in header_value.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            directives[k.strip().lower()] = v.strip().strip("\"'")
        elif " " in part:
            k, v = part.split(" ", 1)
            directives[k.strip().lower()] = v.strip().strip("\"'")
        else:
            directives[part.lower()] = ""
    return directives


def _evaluate_hsts(value: Optional[str], is_https: bool) -> Tuple[HeaderFinding, int]:
    """Avalia o cabeçalho Strict-Transport-Security."""
    if not is_https:
        return HeaderFinding(
            header="Strict-Transport-Security",
            value=value or "Não configurado",
            status="Aviso",
            severity="Média",
            recommendation="Migre o site para HTTPS para poder ativar HSTS.",
            description="HSTS só tem efeito e é aceito pelos navegadores através de conexões HTTPS."
        ), 0

    if not value:
        return HeaderFinding(
            header="Strict-Transport-Security",
            value="Ausente",
            status="Ausente",
            severity="Alta",
            recommendation="Configure 'Strict-Transport-Security: max-age=31536000; includeSubDomains; preload'.",
            description="Força navegadores a se comunicarem exclusivamente via HTTPS, prevenindo ataques de downgrade (SSL Stripping)."
        ), 0

    directives = _parse_directives(value)
    max_age_val = None
    for k, v in directives.items():
        if k == "max-age" and v.isdigit():
            max_age_val = int(v)
            break
        if k.startswith("max-age="):
            part = k.split("=", 1)[1]
            if part.isdigit():
                max_age_val = int(part)
                break

    has_subdomains = "includesubdomains" in directives
    has_preload = "preload" in directives

    if max_age_val is None or max_age_val <= 0:
        return HeaderFinding(
            header="Strict-Transport-Security",
            value=value,
            status="Aviso",
            severity="Alta",
            recommendation="Defina um max-age numérico válido (ex: 31536000 segundos = 1 ano).",
            description="O valor de max-age não é um número positivo válido."
        ), 5

    if max_age_val < 10368000:  # Menor que ~120 dias
        return HeaderFinding(
            header="Strict-Transport-Security",
            value=value,
            status="Aviso",
            severity="Média",
            recommendation="Aumente o max-age para no mínimo 31536000 segundos (1 ano).",
            description=f"max-age atual ({max_age_val}s) é considerado curto para proteção a longo prazo."
        ), 15

    # max-age >= 10368000
    points = 25
    if has_subdomains and has_preload:
        rec = "Configuração exemplar com includeSubDomains e preload habilitados."
    elif has_subdomains:
        rec = "Recomendado adicionar a diretiva 'preload' caso queira submeter ao HSTS Preload List."
    else:
        rec = "Recomendado adicionar 'includeSubDomains' para proteger todos os subdomínios."

    return HeaderFinding(
        header="Strict-Transport-Security",
        value=value,
        status="OK",
        severity="Baixa",
        recommendation=rec,
        description="Força a conexão exclusivamente via HTTPS, mitigando ataques de interceptação."
    ), points


def _evaluate_csp(value: Optional[str]) -> Tuple[HeaderFinding, int]:
    """Avalia o cabeçalho Content-Security-Policy."""
    if not value:
        return HeaderFinding(
            header="Content-Security-Policy",
            value="Ausente",
            status="Ausente",
            severity="Alta",
            recommendation="Defina uma política CSP (ex: default-src 'self'; script-src 'self'; object-src 'none').",
            description="O CSP restringe as origens de scripts, estilos e recursos, sendo a principal defesa contra Cross-Site Scripting (XSS)."
        ), 0

    val_lower = value.lower()
    has_unsafe_inline = "'unsafe-inline'" in val_lower
    has_unsafe_eval = "'unsafe-eval'" in val_lower

    if has_unsafe_inline and has_unsafe_eval:
        return HeaderFinding(
            header="Content-Security-Policy",
            value=value,
            status="Aviso",
            severity="Média",
            recommendation="Substitua 'unsafe-inline' e 'unsafe-eval' por nonces criptográficos ou hashes SHA-256.",
            description="O uso de unsafe-inline e unsafe-eval enfraquece substancialmente a proteção contra ataques de injeção XSS."
        ), 15

    if has_unsafe_inline:
        return HeaderFinding(
            header="Content-Security-Policy",
            value=value,
            status="Aviso",
            severity="Média",
            recommendation="Prefira o uso de hashes ou nonces em vez de 'unsafe-inline'.",
            description="A permissão de scripts inline reduz a eficácia do CSP contra injeções de script malicioso."
        ), 20

    return HeaderFinding(
        header="Content-Security-Policy",
        value=value,
        status="OK",
        severity="Baixa",
        recommendation="Política CSP ativa sem diretivas inseguras genéricas.",
        description="Mitiga injeções de scripts maliciosos, iframes não autorizados e ataques de XSS."
    ), 30


def _evaluate_xfo(value: Optional[str], csp_value: Optional[str]) -> Tuple[HeaderFinding, int]:
    """Avalia o cabeçalho X-Frame-Options."""
    csp_has_frame_ancestors = "frame-ancestors" in (csp_value or "").lower()

    if not value:
        if csp_has_frame_ancestors:
            return HeaderFinding(
                header="X-Frame-Options",
                value="Ausente (Protegido por CSP frame-ancestors)",
                status="OK",
                severity="Baixa",
                recommendation="Recomendado incluir 'X-Frame-Options: DENY' por compatibilidade com navegadores legados.",
                description="O navegador moderno usa a diretiva frame-ancestors do CSP para bloquear Clickjacking."
            ), 15

        return HeaderFinding(
            header="X-Frame-Options",
            value="Ausente",
            status="Ausente",
            severity="Média",
            recommendation="Configure 'X-Frame-Options: DENY' ou 'SAMEORIGIN'.",
            description="Permite que a página seja embutida em iframes de outros sites, tornando-a vulnerável a Clickjacking."
        ), 0

    val_clean = value.strip().upper()
    if val_clean in ("DENY", "SAMEORIGIN"):
        return HeaderFinding(
            header="X-Frame-Options",
            value=value,
            status="OK",
            severity="Baixa",
            recommendation=f"Configurado corretamente com '{val_clean}'.",
            description="Impede o enquadramento em iframes por páginas de terceiros, prevenindo ataques de Clickjacking."
        ), 15

    if val_clean.startswith("ALLOW-FROM"):
        return HeaderFinding(
            header="X-Frame-Options",
            value=value,
            status="Aviso",
            severity="Média",
            recommendation="A diretiva ALLOW-FROM é obsoleta. Substitua pela diretiva 'frame-ancestors' do CSP.",
            description="A diretiva ALLOW-FROM não é mais suportada na maioria dos navegadores modernos."
        ), 5

    return HeaderFinding(
        header="X-Frame-Options",
        value=value,
        status="Aviso",
        severity="Média",
        recommendation="Use 'DENY' ou 'SAMEORIGIN'.",
        description=f"Valor não padrão encontrado: {value}"
    ), 5


def _evaluate_xcto(value: Optional[str]) -> Tuple[HeaderFinding, int]:
    """Avalia o cabeçalho X-Content-Type-Options."""
    if not value:
        return HeaderFinding(
            header="X-Content-Type-Options",
            value="Ausente",
            status="Ausente",
            severity="Média",
            recommendation="Configure 'X-Content-Type-Options: nosniff'.",
            description="Sem esse cabeçalho, navegadores podem tentar adivinhar (sniff) o MIME-type, executando arquivos de texto como scripts."
        ), 0

    if value.strip().lower() == "nosniff":
        return HeaderFinding(
            header="X-Content-Type-Options",
            value=value,
            status="OK",
            severity="Baixa",
            recommendation="Configurado perfeitamente com 'nosniff'.",
            description="Instrui o navegador a respeitar estritamente o Content-Type informado pelo servidor."
        ), 15

    return HeaderFinding(
        header="X-Content-Type-Options",
        value=value,
        status="Aviso",
        severity="Média",
        recommendation="O único valor válido aceito pelos navegadores é 'nosniff'.",
        description=f"Valor inesperado: '{value}'."
    ), 5


def _evaluate_referrer_policy(value: Optional[str]) -> Tuple[HeaderFinding, int]:
    """Avalia o cabeçalho Referrer-Policy."""
    if not value:
        return HeaderFinding(
            header="Referrer-Policy",
            value="Ausente",
            status="Aviso",
            severity="Baixa",
            recommendation="Configure 'Referrer-Policy: strict-origin-when-cross-origin' ou 'no-referrer'.",
            description="Controla a quantidade de informações de URL enviadas no cabeçalho Referer em requisições externas."
        ), 5

    val_lower = value.strip().lower()
    good_policies = {
        "strict-origin-when-cross-origin",
        "strict-origin",
        "same-origin",
        "no-referrer",
        "no-referrer-when-downgrade",
    }

    if val_lower in good_policies:
        return HeaderFinding(
            header="Referrer-Policy",
            value=value,
            status="OK",
            severity="Baixa",
            recommendation="Política segura e adequada de privacidade do cabeçalho Referer.",
            description="Protege os parâmetros e caminhos da URL contra vazamentos em sites de terceiros."
        ), 10

    if "unsafe-url" in val_lower:
        return HeaderFinding(
            header="Referrer-Policy",
            value=value,
            status="Aviso",
            severity="Alta",
            recommendation="Evite 'unsafe-url', pois expõe URLs completas (incluindo possíveis tokens de query string) na rede.",
            description="Envia a URL completa e parâmetros sensíveis para qualquer origem externa."
        ), 0

    return HeaderFinding(
        header="Referrer-Policy",
        value=value,
        status="Aviso",
        severity="Baixa",
        recommendation="Revise o valor configurado para seguir uma política restritiva recomendada.",
        description=f"Valor configurado: '{value}'."
    ), 5


def _evaluate_permissions_policy(value: Optional[str]) -> Tuple[HeaderFinding, int]:
    """Avalia o cabeçalho Permissions-Policy."""
    if not value:
        return HeaderFinding(
            header="Permissions-Policy",
            value="Ausente",
            status="Informativo",
            severity="Informativa",
            recommendation="Considere configurar Permissions-Policy (ex: geolocation=(), camera=(), microphone=()).",
            description="Permite restringir o acesso a recursos do navegador e hardware por parte de iframes e scripts."
        ), 0

    return HeaderFinding(
        header="Permissions-Policy",
        value=value,
        status="OK",
        severity="Baixa",
        recommendation="Controle de recursos de hardware e APIs do navegador ativo.",
        description="Restringe o uso de recursos como geolocalização, câmera e microfone."
    ), 5


def _evaluate_coop(value: Optional[str]) -> Tuple[HeaderFinding, int]:
    """Avalia Cross-Origin-Opener-Policy."""
    if not value:
        return HeaderFinding(
            header="Cross-Origin-Opener-Policy",
            value="Ausente",
            status="Informativo",
            severity="Informativa",
            recommendation="Configure 'Cross-Origin-Opener-Policy: same-origin' se seu site necessitar de isolamento de processos.",
            description="Garante que janelas abertas de outras origens não possam interagir com seu contexto de navegação."
        ), 0

    return HeaderFinding(
        header="Cross-Origin-Opener-Policy",
        value=value,
        status="OK",
        severity="Baixa",
        recommendation="Isolamento de contexto entre janelas ativado.",
        description="Protege contra ataques de timing e Spectre entre contextos cruzados."
    ), 2


def _evaluate_coep(value: Optional[str]) -> Tuple[HeaderFinding, int]:
    """Avalia Cross-Origin-Embedder-Policy."""
    if not value:
        return HeaderFinding(
            header="Cross-Origin-Embedder-Policy",
            value="Ausente",
            status="Informativo",
            severity="Informativa",
            recommendation="Configure 'Cross-Origin-Embedder-Policy: require-corp' caso use buffers de memória compartilhada.",
            description="Impede o carregamento de recursos que não declararam explicitamente política de compartilhamento."
        ), 0

    return HeaderFinding(
        header="Cross-Origin-Embedder-Policy",
        value=value,
        status="OK",
        severity="Baixa",
        recommendation="Política de incorporação de recursos externos controlada.",
        description="Força controle explícito sobre mídias e scripts externos incorporados."
    ), 2


def _evaluate_corp(value: Optional[str]) -> Tuple[HeaderFinding, int]:
    """Avalia Cross-Origin-Resource-Policy."""
    if not value:
        return HeaderFinding(
            header="Cross-Origin-Resource-Policy",
            value="Ausente",
            status="Informativo",
            severity="Informativa",
            recommendation="Configure 'Cross-Origin-Resource-Policy: same-origin' para proteger recursos estáticos sensíveis.",
            description="Bloqueia a leitura do recurso por sites externos (proteção contra Spectre e vazamento de dados)."
        ), 0

    return HeaderFinding(
        header="Cross-Origin-Resource-Policy",
        value=value,
        status="OK",
        severity="Baixa",
        recommendation="Proteção de recursos entre origens ativada.",
        description="Instrui o navegador a bloquear a leitura do conteúdo por outros domínios."
    ), 1


def _evaluate_info_leaks(raw_headers_lower: Dict[str, str]) -> Tuple[List[HeaderFinding], int]:
    """Detecta vazamento de versões e tecnologias de servidor."""
    findings = []
    penalty = 0

    for leak_hdr in INFO_LEAK_HEADERS:
        val = raw_headers_lower.get(leak_hdr.lower())
        if val:
            has_version = bool(re.search(r"\d+\.\d+", val))
            if has_version:
                findings.append(HeaderFinding(
                    header=leak_hdr,
                    value=val,
                    status="Aviso",
                    severity="Média",
                    recommendation=f"Oculte a versão detalhada da tecnologia no cabeçalho '{leak_hdr}'.",
                    description="Expor versões específicas auxilia invasores a pesquisar vulnerabilidades conhecidas (CVEs)."
                ))
                penalty += 3
            else:
                findings.append(HeaderFinding(
                    header=leak_hdr,
                    value=val,
                    status="Informativo",
                    severity="Informativa",
                    recommendation=f"Opcionalmente remova ou mascare o cabeçalho '{leak_hdr}' para dificultar fingerprinting.",
                    description="Indica a tecnologia do servidor web para qualquer cliente público."
                ))

    return findings, penalty


def _calculate_grade(score: int, is_https: bool, findings: List[HeaderFinding]) -> str:
    """Calcula a nota de A+ a F baseada nos critérios e regras determinísticas."""
    if not is_https:
        return "F"

    # Verifica se algum cabeçalho crítico está presente
    hsts = next((f for f in findings if f.header == "Strict-Transport-Security"), None)
    csp = next((f for f in findings if f.header == "Content-Security-Policy"), None)
    xcto = next((f for f in findings if f.header == "X-Content-Type-Options"), None)

    hsts_ok = hsts is not None and hsts.status == "OK"
    csp_ok = csp is not None and csp.status == "OK"
    xcto_ok = xcto is not None and xcto.status == "OK"

    if score >= 95 and hsts_ok and csp_ok and xcto_ok:
        return "A+"
    if score >= 85 and hsts_ok and xcto_ok:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    if score >= 30:
        return "D"
    return "F"


def analyze_headers(
    headers_dict: Dict[str, str],
    target_url: str,
    effective_url: str,
    status_code: int = 200,
    is_https: bool = True
) -> HeaderAuditResult:
    """
    Analisa um dicionário de cabeçalhos HTTP recebidos e gera o relatório completo.

    Args:
        headers_dict: Dicionário contendo os cabeçalhos da resposta.
        target_url: URL inicial solicitada.
        effective_url: URL final após redirecionamentos.
        status_code: Código HTTP retornado.
        is_https: Se a conexão final utilizou HTTPS.

    Returns:
        HeaderAuditResult com nota, pontuação e lista de HeaderFinding.
    """
    raw_lower = {k.lower(): v for k, v in headers_dict.items()}

    findings: List[HeaderFinding] = []
    total_score = 0

    # 1. HSTS
    f_hsts, pts_hsts = _evaluate_hsts(raw_lower.get("strict-transport-security"), is_https)
    findings.append(f_hsts)
    total_score += pts_hsts

    # 2. CSP
    f_csp, pts_csp = _evaluate_csp(raw_lower.get("content-security-policy"))
    findings.append(f_csp)
    total_score += pts_csp

    # 3. X-Frame-Options
    f_xfo, pts_xfo = _evaluate_xfo(raw_lower.get("x-frame-options"), raw_lower.get("content-security-policy"))
    findings.append(f_xfo)
    total_score += pts_xfo

    # 4. X-Content-Type-Options
    f_xcto, pts_xcto = _evaluate_xcto(raw_lower.get("x-content-type-options"))
    findings.append(f_xcto)
    total_score += pts_xcto

    # 5. Referrer-Policy
    f_ref, pts_ref = _evaluate_referrer_policy(raw_lower.get("referrer-policy"))
    findings.append(f_ref)
    total_score += pts_ref

    # 6. Permissions-Policy
    f_perm, pts_perm = _evaluate_permissions_policy(raw_lower.get("permissions-policy"))
    findings.append(f_perm)
    total_score += pts_perm

    # 7. COOP
    f_coop, pts_coop = _evaluate_coop(raw_lower.get("cross-origin-opener-policy"))
    findings.append(f_coop)
    total_score += pts_coop

    # 8. COEP
    f_coep, pts_coep = _evaluate_coep(raw_lower.get("cross-origin-embedder-policy"))
    findings.append(f_coep)
    total_score += pts_coep

    # 9. CORP
    f_corp, pts_corp = _evaluate_corp(raw_lower.get("cross-origin-resource-policy"))
    findings.append(f_corp)
    total_score += pts_corp

    # 10. Detecção de vazamentos
    leak_findings, penalty = _evaluate_info_leaks(raw_lower)
    findings.extend(leak_findings)
    total_score = max(0, total_score - penalty)

    grade = _calculate_grade(total_score, is_https, findings)

    # Sumário explicativo
    ok_count = sum(1 for f in findings if f.status == "OK")
    warn_count = sum(1 for f in findings if f.status == "Aviso")
    missing_count = sum(1 for f in findings if f.status == "Ausente")

    summary = (
        f"Auditoria concluída com Nota {grade} ({total_score}/100 pontos). "
        f"{ok_count} cabeçalho(s) em conformidade, {warn_count} recomendação(ões) de ajuste "
        f"e {missing_count} cabeçalho(s) essencial(is) ausente(s)."
    )

    return HeaderAuditResult(
        target_url=target_url,
        effective_url=effective_url,
        status_code=status_code,
        is_https=is_https,
        score=total_score,
        grade=grade,
        summary=summary,
        findings=findings,
        raw_headers=headers_dict,
    )


def audit_http_headers(
    url: str,
    timeout: float = 12.0,
    user_agent: Optional[str] = None
) -> HeaderAuditResult:
    """
    Executa uma requisição HTTP GET pública e analisa todos os cabeçalhos de resposta.

    Args:
        url: Endereço do site a auditar.
        timeout: Tempo limite de resposta em segundos.
        user_agent: Identificador de cliente HTTP customizado.

    Returns:
        HeaderAuditResult detalhado.

    Raises:
        ValueError: Se a URL for inválida.
        urllib.error.HTTPError: Se o servidor responder erro HTTP de status >= 400.
        urllib.error.URLError: Se houver falha de rede, resolução de DNS ou conexão.
    """
    target = normalize_url(url)
    ua = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WinToolbox-SecurityAuditor/1.0"

    req = urllib.request.Request(
        target,
        headers={"User-Agent": ua, "Accept": "*/*"},
        method="GET"
    )

    _log.info(f"Auditoria iniciada para {target}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            effective_url = resp.geturl()
            status_code = resp.getcode()
            is_https = effective_url.lower().startswith("https://")

            # Converte cabeçalhos HTTP da resposta
            headers_dict = dict(resp.headers.items())

            return analyze_headers(
                headers_dict=headers_dict,
                target_url=target,
                effective_url=effective_url,
                status_code=status_code,
                is_https=is_https,
            )

    except urllib.error.HTTPError as err:
        # Servidores que retornam 403, 401 ou 500 ainda assim retornam cabeçalhos HTTP!
        effective_url = err.geturl() if hasattr(err, "geturl") else target
        headers_dict = dict(err.headers.items()) if err.headers else {}
        is_https = str(effective_url).lower().startswith("https://")

        _log.warning(f"Resposta com status de erro {err.code} de {target}")

        res = analyze_headers(
            headers_dict=headers_dict,
            target_url=target,
            effective_url=effective_url,
            status_code=err.code,
            is_https=is_https,
        )
        res.summary += f" (Nota: O servidor respondeu com código de status HTTP {err.code})."
        return res

    except urllib.error.URLError as err:
        _log.error(f"Falha de conexão com {target}: {err.reason}")
        raise

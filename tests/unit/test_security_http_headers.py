"""
Testes unitários rigorosos para a lógica de auditoria defensiva de cabeçalhos HTTP.

Segue estritamente as diretrizes de qualidade do projeto:
- Validação de efeito real determinístico (==)
- Happy path com todas as notas esperadas
- Casos de borda (HTTP puro, HSTS curto, CSP com unsafe-inline, normalização de URL)
- Cenários de falha e isolamento de rede com mocks (502 Bad Gateway, URLError timeout)
"""
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from wintoolbox.tools.security.http_headers.logic import (
    HeaderAuditResult,
    analyze_headers,
    audit_http_headers,
    normalize_url,
)


def test_normalize_url_variations():
    """Valida a normalização de diferentes formatos de URL digitadas."""
    # Sem protocolo -> adiciona https://
    assert normalize_url("exemplo.com.br") == "https://exemplo.com.br"
    assert normalize_url("sub.meudominio.org/api") == "https://sub.meudominio.org/api"

    # Com HTTP explícito -> mantém http://
    assert normalize_url("http://meusite.local") == "http://meusite.local"

    # Com espaços -> remove espaços
    assert normalize_url("   https://site.com   ") == "https://site.com"

    # Casos de erro
    with pytest.raises(ValueError, match="não pode estar vazia"):
        normalize_url("   ")

    with pytest.raises(ValueError, match="sem nome de domínio"):
        normalize_url("https://")


def test_analyze_headers_perfect_a_plus_grade():
    """Happy Path: Cabeçalhos com pontuação máxima devem receber nota A+."""
    headers = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; object-src 'none'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
        "Cross-Origin-Resource-Policy": "same-origin",
    }

    result = analyze_headers(
        headers_dict=headers,
        target_url="https://site-seguro.com.br",
        effective_url="https://site-seguro.com.br",
        status_code=200,
        is_https=True,
    )

    assert result.grade == "A+"
    assert result.score == 105  # 25 + 30 + 15 + 15 + 10 + 5 + 2 + 2 + 1 = 105
    assert result.is_https is True
    assert result.status_code == 200

    # Validação detalhada dos findings
    hsts = next(f for f in result.findings if f.header == "Strict-Transport-Security")
    assert hsts.status == "OK"
    assert hsts.severity == "Baixa"

    csp = next(f for f in result.findings if f.header == "Content-Security-Policy")
    assert csp.status == "OK"
    assert csp.severity == "Baixa"

    xcto = next(f for f in result.findings if f.header == "X-Content-Type-Options")
    assert xcto.status == "OK"
    assert xcto.value == "nosniff"


def test_analyze_headers_http_insecure_gets_f_grade():
    """Casos de borda: Qualquer site que responda em HTTP puro (não criptografado) deve receber Nota F."""
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }

    result = analyze_headers(
        headers_dict=headers,
        target_url="http://inseguro.com",
        effective_url="http://inseguro.com",
        status_code=200,
        is_https=False,
    )

    assert result.grade == "F"
    assert result.is_https is False

    hsts = next(f for f in result.findings if f.header == "Strict-Transport-Security")
    assert hsts.status == "Aviso"
    assert "Migre o site para HTTPS" in hsts.recommendation


def test_analyze_headers_csp_with_unsafe_inline_and_short_hsts():
    """Casos de borda: CSP permissivo com unsafe-inline e HSTS com max-age baixo."""
    headers = {
        "Strict-Transport-Security": "max-age=86400",  # Apenas 1 dia
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'",
        "X-Frame-Options": "SAMEORIGIN",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "unsafe-url",
        "Server": "nginx/1.18.0 (Ubuntu)",
        "X-Powered-By": "PHP/8.1.2",
    }

    result = analyze_headers(
        headers_dict=headers,
        target_url="https://legado.com",
        effective_url="https://legado.com",
        status_code=200,
        is_https=True,
    )

    # Não deve alcançar A+ nem A devido a unsafe-inline e HSTS curto
    assert result.grade in ("B", "C")

    # Verifica achado do CSP
    csp = next(f for f in result.findings if f.header == "Content-Security-Policy")
    assert csp.status == "Aviso"
    assert "unsafe-inline" in csp.recommendation

    # Verifica achado do HSTS
    hsts = next(f for f in result.findings if f.header == "Strict-Transport-Security")
    assert hsts.status == "Aviso"
    assert "Aumente o max-age" in hsts.recommendation

    # Verifica detecção de vazamento de versão
    server_f = next(f for f in result.findings if f.header == "Server")
    assert server_f.status == "Aviso"
    assert "Oculte a versão detalhada" in server_f.recommendation


def test_analyze_headers_completely_empty():
    """Casos de borda: Servidor sem nenhum cabeçalho de segurança configurado."""
    result = analyze_headers(
        headers_dict={"Content-Type": "text/html; charset=utf-8"},
        target_url="https://vulneravel.com",
        effective_url="https://vulneravel.com",
        status_code=200,
        is_https=True,
    )

    assert result.grade == "F"
    assert result.score == 5  # apenas 5 pontos de Referrer-Policy ausente default

    hsts = next(f for f in result.findings if f.header == "Strict-Transport-Security")
    assert hsts.status == "Ausente"
    assert hsts.severity == "Alta"

    xfo = next(f for f in result.findings if f.header == "X-Frame-Options")
    assert xfo.status == "Ausente"


def test_audit_http_headers_mocked_network_success():
    """Validação de rede isolada: Simula resposta HTTP 200 real."""
    fake_headers = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
    }

    mock_resp = MagicMock()
    mock_resp.geturl.return_value = "https://meusite.com.br"
    mock_resp.getcode.return_value = 200
    mock_resp.headers.items.return_value = list(fake_headers.items())
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        res = audit_http_headers("meusite.com.br")

        assert mock_urlopen.called
        assert res.status_code == 200
        assert res.effective_url == "https://meusite.com.br"
        assert res.grade in ("A+", "A")


def test_audit_http_headers_mocked_http_error_502_bad_gateway():
    """Cenários de falha real: Servidor responde 502 Bad Gateway com cabeçalhos de proxy."""
    mock_headers = MagicMock()
    mock_headers.items.return_value = [
        ("Server", "cloudflare"),
        ("X-Content-Type-Options", "nosniff"),
    ]

    http_err = urllib.error.HTTPError(
        url="https://proxy-error.com",
        code=502,
        msg="Bad Gateway",
        hdrs=mock_headers,
        fp=None
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        res = audit_http_headers("https://proxy-error.com")

        # Mesmo com 502, os cabeçalhos são analisados e o código de erro é reportado no sumário
        assert res.status_code == 502
        assert "502" in res.summary
        assert res.effective_url == "https://proxy-error.com"


def test_audit_http_headers_mocked_network_timeout():
    """Cenários de falha real: Timeout ou falha de DNS (URLError) deve levantar exceção capturável."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection timed out")):
        with pytest.raises(urllib.error.URLError) as exc_info:
            audit_http_headers("https://site-offline.net")

        assert "Connection timed out" in str(exc_info.value)

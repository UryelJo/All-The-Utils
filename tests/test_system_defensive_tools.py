"""Testes black-box reais para as ferramentas defensivas de sistema.

Validações:
1. system.defender_audit: coleta status, avalia exclusões suspeitas, gera laudo;
2. system.firewall_audit: mapeia perfis e portas em escuta, detecta portas críticas;
3. system.credential_audit: calcula métricas de força sem expor senha e detecta reutilização;
4. system.dns_leak_test: analisa vazamento de DNS com isolamento de rede e resiliência a falhas.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from wintoolbox.tools.system.defender_audit.logic import (
    coletar_status_defender,
    gerar_relatorio_defender,
)
from wintoolbox.tools.system.firewall_audit.logic import (
    PORTAS_SENSIVEIS,
    coletar_status_firewall,
    gerar_relatorio_firewall,
)
from wintoolbox.tools.system.credential_audit.logic import (
    _analisar_forca_senha,
    coletar_credenciais_locais,
    gerar_relatorio_credenciais,
)
from wintoolbox.tools.system.dns_leak_test.logic import (
    coletar_dados_dns_leak,
    gerar_relatorio_dns_leak,
)


def test_defender_audit_logic() -> None:
    """Valida a auditoria e geração de laudo do Windows Defender."""
    status = coletar_status_defender()
    assert "score_conformidade" in status
    assert 0 <= status["score_conformidade"] <= 100
    assert "alertas" in status
    assert "recomendacoes" in status

    laudo = gerar_relatorio_defender(status)
    assert "RELATÓRIO DE AUDITORIA — MICROSOFT DEFENDER" in laudo
    assert "STATUS DE PROTEÇÃO" in laudo
    assert "EXCLUSÕES CONFIGURADAS" in laudo


def test_firewall_audit_logic() -> None:
    """Valida mapeamento de portas e avaliação de segurança do Firewall."""
    status = coletar_status_firewall()
    assert "perfis" in status
    assert "portas_escuta" in status
    assert "score_seguranca" in status
    assert 0 <= status["score_seguranca"] <= 100

    # Validar portas sensíveis conhecidas
    assert 445 in PORTAS_SENSIVEIS
    assert 3389 in PORTAS_SENSIVEIS

    laudo = gerar_relatorio_firewall(status)
    assert "RELATÓRIO DE AUDITORIA — FIREWALL DO WINDOWS" in laudo
    assert "STATUS DOS PERFIS DE REDE" in laudo


def test_credential_audit_password_strength_and_reuse() -> None:
    """Valida cálculo de força de senhas e detecção de reutilização."""
    # 1. Senha Vazia
    res_vazia = _analisar_forca_senha(b"")
    assert res_vazia["forca"] == "Vazia"
    assert res_vazia["tamanho"] == 0

    # 2. Senha Fraca
    res_fraca = _analisar_forca_senha("123456".encode("utf-8"))
    assert res_fraca["forca"] == "Fraca"
    assert res_fraca["tem_numero"] is True
    assert res_fraca["tem_maiuscula"] is False

    # 3. Senha Forte
    res_forte = _analisar_forca_senha("S3nh@_Extremamente_F0rte_2026!".encode("utf-8"))
    assert res_forte["forca"] == "Forte"
    assert res_forte["tem_maiuscula"] is True
    assert res_forte["tem_numero"] is True
    assert res_forte["tem_simbolo"] is True

    # 4. Hash anônimo idêntico para mesma senha (detecção de reutilização)
    h1 = _analisar_forca_senha(b"mesmasenha")["hash_anonimo"]
    h2 = _analisar_forca_senha(b"mesmasenha")["hash_anonimo"]
    assert h1 == h2 and len(h1) == 12

    # 5. Coleta real no perfil atual
    dados = coletar_credenciais_locais()
    assert "total_credenciais" in dados
    assert "score_higiene" in dados
    laudo = gerar_relatorio_credenciais(dados)
    assert "GERENCIADOR DE CREDENCIAIS DO WINDOWS" in laudo


def test_dns_leak_network_isolation_and_leak_detection() -> None:
    """Testa detecção de vazamento de DNS com mocks sem chamadas reais à internet."""
    # Mock de resposta do endpoint Cloudflare trace
    trace_mock = (
        "ip=203.0.113.42\n"
        "loc=BR\n"
        "colo=GRU\n"
        "warp=on\n"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = trace_mock

    # Simular adaptador com DNS local de roteador enquanto WARP/VPN está ativo (vazamento)
    dns_windows_mock = [
        {"interface": "Wi-Fi", "ip": "192.168.1.1", "provedor": "Roteador Local"}
    ]

    with patch("requests.get", return_value=mock_resp), \
         patch("wintoolbox.tools.system.dns_leak_test.logic._obter_dns_windows", return_value=dns_windows_mock):
        resultado = coletar_dados_dns_leak()

        assert resultado["conectado"] is True
        assert resultado["ip_publico"] == "203.0.113.42"
        assert resultado["pais"] == "BR"
        assert resultado["vpn_warp"] is True
        # Deve detectar risco de vazamento porque DNS é 192.168.1.1 enquanto VPN está ativa
        assert resultado["possivel_vazamento"] is True
        assert any("Vazamento de DNS" in al["titulo"] for al in resultado["alertas"])

        laudo = gerar_relatorio_dns_leak(resultado)
        assert "TESTE DE VAZAMENTO DE DNS" in laudo
        assert "203.0.113.42" in laudo


def test_dns_leak_failure_resilience() -> None:
    """Garante resiliência caso o endpoint externo falhe (502 Gateway, Timeout)."""
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Timeout")):
        resultado = coletar_dados_dns_leak()
        assert resultado["conectado"] is False
        assert resultado["ip_publico"] == "N/D"
        assert len(resultado["alertas"]) >= 1


def test_keylogger_detect_logic() -> None:
    """Valida varreduras heurísticas antikeylogger e geração de laudo."""
    from wintoolbox.tools.system.keylogger_detect.logic import (
        _verificar_filtros_teclado,
        coletar_dados_keylogger,
        gerar_relatorio_keylogger,
    )

    filtros = _verificar_filtros_teclado()
    assert "filtros_instalados" in filtros
    assert isinstance(filtros["filtros_instalados"], list)

    dados = coletar_dados_keylogger()
    assert "score_seguranca" in dados
    assert 0 <= dados["score_seguranca"] <= 100
    assert "filtros_teclado" in dados
    assert "processos_suspeitos" in dados

    laudo = gerar_relatorio_keylogger(dados)
    assert "DETECTOR HEURÍSTICO DE KEYLOGGERS" in laudo
    assert "DRIVERS DE FILTRO DE TECLADO" in laudo


def test_rootkit_detect_logic() -> None:
    """Valida cross-check de processos nativos, System32 e portas órfãs."""
    from wintoolbox.tools.system.rootkit_detect.logic import (
        _coletar_pids_nativos,
        _verificar_processos_criticos,
        coletar_dados_rootkit,
        gerar_relatorio_rootkit,
    )

    pids_nativos = _coletar_pids_nativos()
    assert isinstance(pids_nativos, dict)
    assert len(pids_nativos) > 0

    dados = coletar_dados_rootkit()
    assert "score_integridade" in dados
    assert 0 <= dados["score_integridade"] <= 100
    assert "total_processos_nativos" in dados

    laudo = gerar_relatorio_rootkit(dados)
    assert "DETECTOR HEURÍSTICO DE ROOTKITS" in laudo
    assert "PROCESSOS OCULTOS IDENTIFICADOS" in laudo


def test_webrtc_leak_logic() -> None:
    """Valida análise de candidatos ICE WebRTC contra vazamento de IP."""
    from wintoolbox.tools.system.webrtc_leak.logic import (
        analisar_candidatos_webrtc,
        gerar_relatorio_webrtc,
    )

    # 1. Sem IPs expostos (WebRTC bloqueado/protegido)
    res_seguro = analisar_candidatos_webrtc([])
    assert res_seguro["score_privacidade"] == 100
    assert res_seguro["vazamento_detectado"] is False

    # 2. Apenas IP local exposto
    res_local = analisar_candidatos_webrtc(["192.168.1.100"])
    assert "192.168.1.100" in res_local["ips_privados"]
    assert res_local["vazamento_detectado"] is False

    # 3. Vazamento crítico: IP público real exposto diferente do túnel VPN
    res_vazamento = analisar_candidatos_webrtc(
        ["192.168.1.100", "187.33.206.6"],
        ip_publico_esperado="142.250.190.46",
    )
    assert res_vazamento["vazamento_detectado"] is True
    assert res_vazamento["score_privacidade"] < 60
    assert any("Vazamento Crítico" in a["titulo"] for a in res_vazamento["alertas"])

    laudo = gerar_relatorio_webrtc(res_vazamento)
    assert "DETECTOR DE VAZAMENTO WEBRTC" in laudo
    assert "187.33.206.6" in laudo


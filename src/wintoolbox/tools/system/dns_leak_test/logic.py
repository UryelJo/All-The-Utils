"""Lógica pura de teste e diagnóstico de vazamento de DNS (DNS Leak Test).

Avalia a postura de privacidade de resolução de nomes do sistema:
1. Detecta o endereço IP público, geolocalização e conexão através de endpoints seguros;
2. Enumera os servidores DNS configurados nos adaptadores de rede do Windows;
3. Identifica resolvedores públicos seguros (Cloudflare, Quad9, Google) vs. resolvedores
   de operadora (ISP) e alerta sobre vazamento de tráfego fora do túnel VPN.
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

RESOLVEDORES_CONHECIDOS: Dict[str, str] = {
    "1.1.1.1": "Cloudflare DNS (Alta Privacidade)",
    "1.0.0.1": "Cloudflare DNS Secundário",
    "8.8.8.8": "Google Public DNS",
    "8.8.4.4": "Google Public DNS Secundário",
    "9.9.9.9": "Quad9 (Bloqueio de Malware)",
    "149.112.112.112": "Quad9 Secundário",
    "208.67.222.222": "Cisco OpenDNS",
    "208.67.220.220": "Cisco OpenDNS Secundário",
    "94.140.14.14": "AdGuard DNS (Bloqueio de Anúncios)",
    "94.140.15.15": "AdGuard DNS Secundário",
}


def _obter_dns_windows() -> List[Dict[str, Any]]:
    """Enumera servidores DNS configurados nos adaptadores ativos via PowerShell."""
    cmd = (
        "Get-DnsClientServerAddress -AddressFamily IPv4 | "
        "Where-Object { $_.ServerAddresses.Count -gt 0 } | "
        "Select-Object InterfaceAlias, ServerAddresses | ConvertTo-Json -Compress"
    )
    itens: List[Dict[str, Any]] = []
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            dados = json.loads(proc.stdout.strip())
            if isinstance(dados, dict):
                dados = [dados]
            for adp in dados:
                alias = str(adp.get("InterfaceAlias") or "Adaptador")
                addrs = adp.get("ServerAddresses") or []
                if isinstance(addrs, str):
                    addrs = [addrs]
                for ip in addrs:
                    itens.append({
                        "interface": alias,
                        "ip": str(ip),
                        "provedor": RESOLVEDORES_CONHECIDOS.get(str(ip), "ISP / Roteador Local"),
                    })
    except Exception:
        pass
    return itens


def coletar_dados_dns_leak(timeout: int = 5) -> Dict[str, Any]:
    """Executa a coleta de IP público e resolvedores DNS para teste de vazamento."""
    resultado: Dict[str, Any] = {
        "conectado": False,
        "ip_publico": "N/D",
        "pais": "N/D",
        "colo": "N/D",
        "vpn_warp": False,
        "servidores_dns": [],
        "possivel_vazamento": False,
        "score_privacidade": 100,
        "alertas": [],
        "recomendacoes": [],
    }

    # 1. IP Público via Cloudflare trace
    try:
        resp = requests.get("https://1.1.1.1/cdn-cgi/trace", timeout=timeout)
        if resp.status_code == 200:
            resultado["conectado"] = True
            for linha in resp.text.splitlines():
                if "=" in linha:
                    k, v = linha.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k == "ip":
                        resultado["ip_publico"] = v
                    elif k == "loc":
                        resultado["pais"] = v
                    elif k == "colo":
                        resultado["colo"] = v
                    elif k == "warp":
                        resultado["vpn_warp"] = (v == "on")
    except Exception:
        # Fallback offline ou erro de rede
        pass

    # 2. Servidores DNS do Sistema
    dns_lista = _obter_dns_windows()
    resultado["servidores_dns"] = dns_lista

    # 3. Análise de Vazamento e Privacidade
    score = 100
    alertas: List[Dict[str, str]] = []
    recoms: List[str] = []

    if not resultado["conectado"]:
        score -= 50
        alertas.append({
            "severidade": "Médio",
            "titulo": "Sem Acesso ao Diagnóstico Externo",
            "detalhe": "Não foi possível verificar a conectividade externa com o endpoint de trace.",
        })
        recoms.append("Verifique a conexão com a internet.")
    else:
        # Verificar se servidores DNS são todos de roteador local / operadora
        tem_dns_privado = any(
            d["ip"].startswith(("192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31."))
            for d in dns_lista
        )
        tem_dns_criptografado = any(d["ip"] in ("1.1.1.1", "1.0.0.1", "9.9.9.9", "149.112.112.112") for d in dns_lista)

        if tem_dns_privado and not tem_dns_criptografado:
            score -= 25
            resultado["possivel_vazamento"] = True
            alertas.append({
                "severidade": "Alto",
                "titulo": "DNS Padrão do Provedor de Internet (ISP)",
                "detalhe": "As requisições de nomes de domínio estão sendo resolvidas pelo roteador/operadora local em texto claro.",
            })
            recoms.append("Configure servidores DNS com proteção de privacidade (ex: 1.1.1.1 ou 9.9.9.9) ou utilize DNS-over-HTTPS (DoH).")

        # Alerta de VPN com DNS do ISP
        if resultado["vpn_warp"] and tem_dns_privado:
            score -= 30
            resultado["possivel_vazamento"] = True
            alertas.append({
                "severidade": "Crítico",
                "titulo": "Vazamento de DNS com VPN/Proxy Ativo",
                "detalhe": "Seu túnel VPN está ativo, mas as requisições DNS continuam sendo enviadas ao provedor local.",
            })
            recoms.append("Ative a proteção contra vazamento de DNS (DNS Leak Protection) no seu cliente de VPN.")

    resultado["score_privacidade"] = max(0, min(100, score))
    resultado["alertas"] = alertas
    resultado["recomendacoes"] = recoms
    return resultado


def gerar_relatorio_dns_leak(dados: Dict[str, Any]) -> str:
    """Gera laudo técnico da auditoria de privacidade e vazamento de DNS."""
    linhas: List[str] = [
        "=" * 72,
        "RELATÓRIO DE AUDITORIA — TESTE DE VAZAMENTO DE DNS (DNS LEAK)",
        "=" * 72,
        f"Data da Auditoria        : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Score de Privacidade    : {dados['score_privacidade']}/100",
        f"IP Público Detectado     : {dados['ip_publico']}",
        f"País / Localidade        : {dados['pais']} (Data Center: {dados['colo']})",
        f"Túnel VPN / WARP         : {'ATIVO' if dados['vpn_warp'] else 'INATIVO'}",
        f"Possível Vazamento       : {'SIM (RISCO)' if dados['possivel_vazamento'] else 'NÃO DETECTADO'}",
        "",
        f"1. SERVIDORES DNS CONFIGURADOS ({len(dados['servidores_dns'])})",
        "   INTERFACE                     | IP RESOLVEDOR   | CLASSIFICAÇÃO / PROVEDOR",
        "   " + "-" * 74,
    ]
    for d in dados["servidores_dns"]:
        linhas.append(f"   {d['interface'][:29]:<29} | {d['ip']:<15} | {d['provedor']}")

    linhas.append("")
    linhas.append(f"2. ALERTAS DE PRIVACIDADE ({len(dados['alertas'])})")
    if not dados["alertas"]:
        linhas.append("   Nenhum vazamento ou fraqueza de resolução de DNS identificados.")
    else:
        for al in dados["alertas"]:
            linhas.append(f"   [{al['severidade'].upper()}] {al['titulo']}")
            linhas.append(f"     Detalhe: {al['detalhe']}")

    linhas.append("")
    linhas.append(f"3. RECOMENDAÇÕES ({len(dados['recomendacoes'])})")
    if not dados["recomendacoes"]:
        linhas.append("   A configuração de DNS atual oferece boa postura de privacidade.")
    else:
        for rec in dados["recomendacoes"]:
            linhas.append(f"   - {rec}")

    linhas.append("=" * 72)
    return "\n".join(linhas)


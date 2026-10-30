"""Lógica pura de auditoria do Firewall do Windows.

Analisa o estado dos perfis de rede (Domain, Private, Public), regras de entrada
permissivas em portas sensíveis (SMB, RDP, WinRM) e portas atualmente em escuta
(LISTEN) associadas aos respectivos processos do sistema.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psutil

PORTAS_SENSIVEIS: Dict[int, str] = {
    21: "FTP (Transferência de Arquivos não criptografada)",
    22: "SSH (Acesso Remoto)",
    23: "Telnet (Terminal em texto claro)",
    135: "RPC Endpoint Mapper",
    139: "NetBIOS Session Service",
    445: "SMB / Compartilhamento de Arquivos",
    1433: "Microsoft SQL Server",
    3389: "RDP (Área de Trabalho Remota)",
    5900: "VNC (Acesso Remoto)",
    5985: "WinRM HTTP (Gerenciamento Remoto)",
    5986: "WinRM HTTPS (Gerenciamento Remoto)",
}


def _executar_ps(comando: str, timeout: int = 15) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return None


def coletar_status_firewall() -> Dict[str, Any]:
    """Audita perfis, regras permissivas e portas abertas em escuta."""
    resultado: Dict[str, Any] = {
        "perfis": {},
        "portas_escuta": [],
        "alertas": [],
        "recomendacoes": [],
        "score_seguranca": 100,
    }

    # 1. Perfis de Firewall
    cmd_perfis = (
        "Get-NetFirewallProfile | Select-Object -Property "
        "Name, Enabled, DefaultInboundAction, DefaultOutboundAction | ConvertTo-Json -Compress"
    )
    raw_perfis = _executar_ps(cmd_perfis)
    perfis_dict: Dict[str, Dict[str, Any]] = {}
    if raw_perfis:
        try:
            dados = json.loads(raw_perfis)
            if isinstance(dados, dict):
                dados = [dados]
            for p in dados:
                nome = str(p.get("Name", "Desconhecido"))
                # Enabled: 1 = Ativo, 0 = Inativo (ou booleano)
                ativo = bool(p.get("Enabled") in (1, True, "True"))
                # DefaultInboundAction: 0 = Block, 1 = Allow (ou string)
                inbound_block = str(p.get("DefaultInboundAction", "")).lower() in ("0", "block", "notconfigured")
                perfis_dict[nome] = {
                    "ativo": ativo,
                    "inbound_bloqueado": inbound_block,
                    "outbound_acao": str(p.get("DefaultOutboundAction", "Allow")),
                }
        except Exception:
            pass
    resultado["perfis"] = perfis_dict

    # 2. Portas em Escuta via psutil
    conexoes_escuta: List[Dict[str, Any]] = []
    try:
        for c in psutil.net_connections(kind="tcp"):
            if c.status == "LISTEN" and c.laddr:
                porta = c.laddr.port
                ip = c.laddr.ip
                pid = c.pid or 0
                pname = "Sistema"
                if pid:
                    try:
                        pname = psutil.Process(pid).name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pname = "Desconhecido"

                eh_sensivel = porta in PORTAS_SENSIVEIS
                conexoes_escuta.append({
                    "ip": ip,
                    "porta": porta,
                    "pid": pid,
                    "processo": pname,
                    "sensivel": eh_sensivel,
                    "descricao": PORTAS_SENSIVEIS.get(porta, ""),
                })
    except Exception:
        pass

    # Ordenar portas
    conexoes_escuta.sort(key=lambda x: (not x["sensivel"], x["porta"]))
    resultado["portas_escuta"] = conexoes_escuta

    # 3. Avaliação de Risco e Score
    score = 100
    alertas: List[Dict[str, str]] = []
    recoms: List[str] = []

    # Verificar perfis desabilitados
    for perfil, dados_p in perfis_dict.items():
        if not dados_p.get("ativo", False):
            score -= 30
            alertas.append({
                "severidade": "Crítico",
                "titulo": f"Perfil '{perfil}' Desativado",
                "detalhe": f"O Firewall do Windows está desligado para conexões do tipo '{perfil}'.",
            })
            recoms.append(f"Habilite o perfil '{perfil}' nas configurações do Firewall do Windows Defender.")
        elif not dados_p.get("inbound_bloqueado", True):
            score -= 25
            alertas.append({
                "severidade": "Alto",
                "titulo": f"Entrada Permissiva no Perfil '{perfil}'",
                "detalhe": "Conexões de entrada não solicitadas estão configuradas como 'Permitir' por padrão.",
            })
            recoms.append(f"Configure a ação padrão de entrada do perfil '{perfil}' para 'Bloquear'.")

    # Verificar portas críticas em escuta em todas as interfaces (0.0.0.0 ou ::)
    portas_abertas_gerais = {c["porta"]: c for c in conexoes_escuta if c["ip"] in ("0.0.0.0", "::")}
    for p_sens, desc in PORTAS_SENSIVEIS.items():
        if p_sens in portas_abertas_gerais:
            proc_info = portas_abertas_gerais[p_sens]
            score -= 10
            alertas.append({
                "severidade": "Médio",
                "titulo": f"Porta Sensível em Escuta Aberta: {p_sens} ({desc})",
                "detalhe": f"Processo '{proc_info['processo']}' (PID {proc_info['pid']}) está aguardando conexões.",
            })
            recoms.append(f"Verifique se o serviço na porta {p_sens} ({desc}) precisa permanecer exposto à rede local.")

    resultado["score_seguranca"] = max(0, min(100, score))
    resultado["alertas"] = alertas
    resultado["recomendacoes"] = recoms
    return resultado


def gerar_relatorio_firewall(status: Dict[str, Any]) -> str:
    """Formata os dados em relatório estruturado de auditoria do Firewall."""
    linhas: List[str] = [
        "=" * 72,
        "RELATÓRIO DE AUDITORIA — FIREWALL DO WINDOWS",
        "=" * 72,
        f"Data da Auditoria     : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Score de Segurança    : {status['score_seguranca']}/100",
        "",
        "1. STATUS DOS PERFIS DE REDE",
    ]
    for perfil, dados in status["perfis"].items():
        status_txt = "ATIVO" if dados["ativo"] else "DESATIVADO"
        inbound_txt = "BLOQUEAR (SEGURO)" if dados["inbound_bloqueado"] else "PERMITIR (PERMISSIVO)"
        linhas.append(f"   Perfil {perfil:<12}: Status [{status_txt}] | Entrada: [{inbound_txt}]")

    linhas.append("")
    linhas.append(f"2. PORTAS EM ESCUTA (LISTEN) NO SISTEMA ({len(status['portas_escuta'])})")
    linhas.append("   PORTA | IP BIND       | PID    | PROCESSO             | OBSERVAÇÃO")
    linhas.append("   " + "-" * 66)
    for c in status["portas_escuta"]:
        obs = c["descricao"] if c["sensivel"] else "Padrão"
        linhas.append(f"   {c['porta']:<5} | {c['ip']:<13} | {c['pid']:<6} | {c['processo']:<20} | {obs}")

    linhas.append("")
    linhas.append(f"3. ALERTAS DE SEGURANÇA ({len(status['alertas'])})")
    if not status["alertas"]:
        linhas.append("   Nenhum alerta crítico encontrado nos perfis e portas auditados.")
    else:
        for al in status["alertas"]:
            linhas.append(f"   [{al['severidade'].upper()}] {al['titulo']}")
            linhas.append(f"     Detalhe: {al['detalhe']}")

    linhas.append("")
    linhas.append(f"4. RECOMENDAÇÕES DEFENSIVAS ({len(status['recomendacoes'])})")
    if not status["recomendacoes"]:
        linhas.append("   As regras de firewall atendem às diretrizes de conformidade recomendadas.")
    else:
        for rec in status["recomendacoes"]:
            linhas.append(f"   - {rec}")

    linhas.append("=" * 72)
    return "\n".join(linhas)


"""Lógica pura de auditoria defensiva do Windows Defender.

Coleta configurações de proteção, status do motor antimalware, data das assinaturas,
regras de redução de superfície de ataque (ASR) e exclusões ativas via PowerShell.
Avalia a postura de segurança com pontuação de conformidade e alertas contextuais.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PASTAS_SUSPEITAS_EXCLUSAO = [
    r"c:\users\public",
    r"c:\windows\temp",
    r"c:\temp",
    r"\appdata\local\temp",
    r"\temp",
    "c:\\",
]


def _executar_ps(comando: str, timeout: int = 15) -> Optional[str]:
    """Executa comando PowerShell em formato JSON com tratamento de erro e timeout."""
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


def coletar_status_defender() -> Dict[str, Any]:
    """Audita o Windows Defender e avalia os parâmetros de proteção."""
    resultado: Dict[str, Any] = {
        "disponivel": False,
        "em_execucao": False,
        "protecao_tempo_real": False,
        "antivirus_habilitado": False,
        "monitor_comportamento": False,
        "protecao_nuvem": False,
        "tamper_protection": False,
        "versao_engine": "Desconhecida",
        "versao_assinaturas": "Desconhecida",
        "ultima_atualizacao": "Desconhecida",
        "dias_desatualizado": 0,
        "exclusoes_caminhos": [],
        "exclusoes_extensoes": [],
        "exclusoes_processos": [],
        "regras_asr": [],
        "alertas": [],
        "recomendacoes": [],
        "score_conformidade": 100,
    }

    # 1. Status Geral
    cmd_status = (
        "Get-MpComputerStatus | Select-Object -Property "
        "RealTimeProtectionEnabled, AntivirusEnabled, AMServiceEnabled, "
        "AntispywareEnabled, BehaviorMonitorEnabled, IoavProtectionEnabled, "
        "AntivirusSignatureVersion, AntivirusSignatureLastUpdated, "
        "AMEngineVersion, IsTamperProtected | ConvertTo-Json -Compress"
    )
    raw_status = _executar_ps(cmd_status)
    if raw_status:
        try:
            dados = json.loads(raw_status)
            resultado["disponivel"] = True
            resultado["em_execucao"] = bool(dados.get("AMServiceEnabled", False))
            resultado["protecao_tempo_real"] = bool(dados.get("RealTimeProtectionEnabled", False))
            resultado["antivirus_habilitado"] = bool(dados.get("AntivirusEnabled", False))
            resultado["monitor_comportamento"] = bool(dados.get("BehaviorMonitorEnabled", False))
            resultado["protecao_nuvem"] = bool(dados.get("IoavProtectionEnabled", False))
            resultado["tamper_protection"] = bool(dados.get("IsTamperProtected", False))
            resultado["versao_engine"] = str(dados.get("AMEngineVersion") or "N/D")
            resultado["versao_assinaturas"] = str(dados.get("AntivirusSignatureVersion") or "N/D")

            data_str = dados.get("AntivirusSignatureLastUpdated")
            if data_str:
                resultado["ultima_atualizacao"] = str(data_str)
        except Exception:
            pass

    # 2. Exclusões e Preferências
    cmd_pref = (
        "Get-MpPreference | Select-Object -Property "
        "ExclusionPath, ExclusionExtension, ExclusionProcess, "
        "AttackSurfaceReductionRules_Ids, AttackSurfaceReductionRules_Actions | ConvertTo-Json -Compress"
    )
    raw_pref = _executar_ps(cmd_pref)
    if raw_pref:
        try:
            pref = json.loads(raw_pref)
            for campo, chave_res in [
                ("ExclusionPath", "exclusoes_caminhos"),
                ("ExclusionExtension", "exclusoes_extensoes"),
                ("ExclusionProcess", "exclusoes_processos"),
            ]:
                val = pref.get(campo)
                if isinstance(val, list):
                    resultado[chave_res] = [str(x) for x in val if x]
                elif isinstance(val, str) and val.strip():
                    resultado[chave_res] = [val.strip()]
        except Exception:
            pass

    # 3. Avaliação e Pontuação de Conformidade
    score = 100
    alertas: List[Dict[str, str]] = []
    recoms: List[str] = []

    if not resultado["em_execucao"]:
        score -= 40
        alertas.append({
            "severidade": "Crítico",
            "titulo": "Serviço do Defender Inativo",
            "detalhe": "O serviço Antimalware (WinDefend) não está em execução ou foi desabilitado por terceiros.",
        })
        recoms.append("Habilite o serviço Microsoft Defender Antivirus ou verifique se há outro antivírus gerenciando o sistema.")

    if not resultado["protecao_tempo_real"]:
        score -= 30
        alertas.append({
            "severidade": "Crítico",
            "titulo": "Proteção em Tempo Real Desativada",
            "detalhe": "Arquivos abertos ou baixados não estão sendo verificados imediatamente.",
        })
        recoms.append("Ative a proteção em tempo real nas Configurações de Segurança do Windows.")

    if not resultado["monitor_comportamento"]:
        score -= 15
        alertas.append({
            "severidade": "Alto",
            "titulo": "Monitor de Comportamento Desativado",
            "detalhe": "A detecção comportamental heurística de processos maliciosos está desligada.",
        })
        recoms.append("Ative o monitor de comportamento heurístico do Defender.")

    if not resultado["tamper_protection"]:
        score -= 10
        alertas.append({
            "severidade": "Médio",
            "titulo": "Proteção contra Violações (Tamper Protection) Inativa",
            "detalhe": "A proteção que impede malwares de alterarem configurações do Defender está desabilitada.",
        })
        recoms.append("Ative a Proteção contra Violações no aplicativo Segurança do Windows.")

    # Analisar exclusões suspeitas
    for caminho in resultado["exclusoes_caminhos"]:
        caminho_baixo = caminho.lower()
        for susp in PASTAS_SUSPEITAS_EXCLUSAO:
            if susp in caminho_baixo:
                score -= 10
                alertas.append({
                    "severidade": "Alto",
                    "titulo": f"Exclusão Suspeita: {caminho}",
                    "detalhe": "Esta pasta é comumente utilizada por invasores ou malwares para descartar payloads sem verificação.",
                })
                recoms.append(f"Remova a exclusão da pasta '{caminho}' para manter a integridade do sistema.")
                break

    resultado["score_conformidade"] = max(0, min(100, score))
    resultado["alertas"] = alertas
    resultado["recomendacoes"] = recoms
    return resultado


def gerar_relatorio_defender(status: Dict[str, Any]) -> str:
    """Formata os dados coletados em um relatório estruturado de conformidade."""
    linhas: List[str] = [
        "=" * 72,
        "RELATÓRIO DE AUDITORIA — MICROSOFT DEFENDER ANTIVIRUS",
        "=" * 72,
        f"Data da Auditoria     : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Score de Conformidade : {status['score_conformidade']}/100",
        "",
        "1. STATUS DE PROTEÇÃO EM TEMPO REAL",
        f"   Serviço Antimalware Ativo     : {'SIM' if status['em_execucao'] else 'NÃO'}",
        f"   Proteção em Tempo Real        : {'HABILITADA' if status['protecao_tempo_real'] else 'DESABILITADA'}",
        f"   Monitor de Comportamento      : {'HABILITADO' if status['monitor_comportamento'] else 'DESABILITADO'}",
        f"   Proteção na Nuvem (IOAV)      : {'HABILITADA' if status['protecao_nuvem'] else 'DESABILITADA'}",
        f"   Proteção contra Violações     : {'HABILITADA' if status['tamper_protection'] else 'DESABILITADA'}",
        "",
        "2. INFORMAÇÕES DO MOTOR E ASSINATURAS",
        f"   Versão do Motor (Engine)      : {status['versao_engine']}",
        f"   Versão das Assinaturas        : {status['versao_assinaturas']}",
        f"   Última Atualização            : {status['ultima_atualizacao']}",
        "",
        "3. EXCLUSÕES CONFIGURADAS",
        f"   Pastas/Caminhos Excluídos     : {len(status['exclusoes_caminhos'])}",
    ]
    for c in status["exclusoes_caminhos"]:
        linhas.append(f"     - {c}")

    linhas.append(f"   Extensões Excluídas           : {len(status['exclusoes_extensoes'])}")
    for e in status["exclusoes_extensoes"]:
        linhas.append(f"     - {e}")

    linhas.append(f"   Processos Excluídos           : {len(status['exclusoes_processos'])}")
    for p in status["exclusoes_processos"]:
        linhas.append(f"     - {p}")

    linhas.append("")
    linhas.append(f"4. ALERTAS DE SEGURANÇA ({len(status['alertas'])})")
    if not status["alertas"]:
        linhas.append("   Nenhum alerta crítico ou médio detectado nas configurações vigentes.")
    else:
        for al in status["alertas"]:
            linhas.append(f"   [{al['severidade'].upper()}] {al['titulo']}")
            linhas.append(f"     Detalhe: {al['detalhe']}")

    linhas.append("")
    linhas.append(f"5. RECOMENDAÇÕES DEFENSIVAS ({len(status['recomendacoes'])})")
    if not status["recomendacoes"]:
        linhas.append("   O ambiente está aderente às melhores práticas recomendadas.")
    else:
        for rec in status["recomendacoes"]:
            linhas.append(f"   - {rec}")

    linhas.append("=" * 72)
    return "\n".join(linhas)

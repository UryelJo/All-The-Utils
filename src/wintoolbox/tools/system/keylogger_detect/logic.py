"""Lógica pura de detecção heurística de keyloggers (sem Qt).

Executa varreduras de diagnóstico defensivo no sistema:
1. Inspeção de drivers de filtro de teclado (UpperFilters) no Registro do Windows;
2. Varredura de módulos e processos em execução com assinaturas e nomes suspeitos;
3. Varredura de diretórios temporários (%TEMP% e %APPDATA%) em busca de logs de teclas.
"""
from __future__ import annotations

import os
import winreg
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

PALAVRAS_SUSPEITAS_PROCESSO = [
    "keylog",
    "keystroke",
    "klog",
    "keyspy",
    "hookkbd",
    "keycapture",
    "inputspy",
]

PADROES_ARQUIVOS_SUSPEITOS = [
    "*keylog*",
    "*keystroke*",
    "*teclas*",
    "*typed_keys*",
    "*klog*",
]


def _verificar_filtros_teclado() -> Dict[str, Any]:
    """Lê a chave de classe do teclado e extrai UpperFilters."""
    caminho_chave = r"SYSTEM\CurrentControlSet\Control\Class\{4D36E96B-E325-11CE-BFC1-08002BE10318}"
    filtros: List[str] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, caminho_chave) as k:
            val, _ = winreg.QueryValueEx(k, "UpperFilters")
            if isinstance(val, list):
                filtros = [str(x) for x in val]
            elif isinstance(val, str):
                filtros = [val]
    except Exception:
        pass

    # Padrão legítimo do Windows é apenas 'kbdclass'
    filtros_adicionais = [f for f in filtros if f.lower() != "kbdclass"]
    return {
        "filtros_instalados": filtros,
        "filtros_terceiros": filtros_adicionais,
        "suspeito": len(filtros_adicionais) > 0,
    }


def _varrer_processos_suspeitos(limite_processos: int = 400) -> List[Dict[str, Any]]:
    """Examina processos em execução procurando nomes associados a gravação de teclas."""
    encontrados: List[Dict[str, Any]] = []
    cont = 0
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        if cont >= limite_processos:
            break
        cont += 1
        try:
            info = proc.info
            nome = str(info.get("name") or "").lower()
            exe = str(info.get("exe") or "").lower()

            for termo in PALAVRAS_SUSPEITAS_PROCESSO:
                if termo in nome or termo in exe:
                    encontrados.append({
                        "pid": info["pid"],
                        "nome": info["name"],
                        "executavel": info.get("exe") or "N/D",
                        "motivo": f"Nome ou caminho contém termo suspeito '{termo}'",
                    })
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return encontrados


def _varrer_arquivos_log_suspeitos() -> List[Dict[str, Any]]:
    """Varre %TEMP% e %APPDATA% em busca de arquivos com nomes típicos de logs de keylogger."""
    arquivos: List[Dict[str, Any]] = []
    pastas_alvo = [
        os.environ.get("TEMP"),
        os.environ.get("APPDATA"),
    ]

    for p_str in pastas_alvo:
        if not p_str:
            continue
        pasta = Path(p_str)
        if not pasta.exists():
            continue

        try:
            for padrao in PADROES_ARQUIVOS_SUSPEITOS:
                for arq in pasta.glob(padrao):
                    if arq.is_file():
                        try:
                            stat = arq.stat()
                            arquivos.append({
                                "caminho": str(arq),
                                "tamanho": stat.st_size,
                                "modificado": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                            })
                        except Exception:
                            continue
        except Exception:
            continue

    return arquivos


def coletar_dados_keylogger() -> Dict[str, Any]:
    """Executa a auditoria heurística completa contra keyloggers."""
    dados_filtros = _verificar_filtros_teclado()
    processos_suspeitos = _varrer_processos_suspeitos()
    arquivos_suspeitos = _varrer_arquivos_log_suspeitos()

    score = 100
    alertas: List[Dict[str, str]] = []
    recoms: List[str] = []

    if dados_filtros["suspeito"]:
        score -= 20
        filtros_str = ", ".join(dados_filtros["filtros_terceiros"])
        alertas.append({
            "severidade": "Médio",
            "titulo": f"Driver de Filtro de Teclado de Terceiros: {filtros_str}",
            "detalhe": "Há drivers interceptando mensagens de hardware de teclado antes do kbdclass.",
        })
        recoms.append(f"Identifique se os drivers ({filtros_str}) pertencem ao antivírus legítimo instalado ou a software corporativo.")

    if processos_suspeitos:
        score -= len(processos_suspeitos) * 35
        for p in processos_suspeitos:
            alertas.append({
                "severidade": "Crítico",
                "titulo": f"Processo com Nome Suspeito: {p['nome']} (PID {p['pid']})",
                "detalhe": p["motivo"],
            })
            recoms.append(f"Inspecione o processo {p['nome']} (PID {p['pid']}) no Gerenciador de Tarefas e envie para análise no VirusTotal.")

    if arquivos_suspeitos:
        score -= min(30, len(arquivos_suspeitos) * 15)
        for a in arquivos_suspeitos[:5]:
            alertas.append({
                "severidade": "Alto",
                "titulo": f"Arquivo de Log Suspeito: {Path(a['caminho']).name}",
                "detalhe": f"Caminho: {a['caminho']} ({a['tamanho']} bytes)",
            })
            recoms.append(f"Abra o arquivo {a['caminho']} para verificar se contém registros de teclas ou senhas digitadas.")

    return {
        "filtros_teclado": dados_filtros,
        "processos_suspeitos": processos_suspeitos,
        "arquivos_suspeitos": arquivos_suspeitos,
        "score_seguranca": max(0, min(100, score)),
        "alertas": alertas,
        "recomendacoes": recoms,
    }


def gerar_relatorio_keylogger(dados: Dict[str, Any]) -> str:
    """Formata os dados em laudo técnico de detecção de keyloggers."""
    linhas: List[str] = [
        "=" * 72,
        "RELATÓRIO DE AUDITORIA — DETECTOR HEURÍSTICO DE KEYLOGGERS",
        "=" * 72,
        f"Data da Auditoria     : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Score de Segurança    : {dados['score_seguranca']}/100",
        "",
        "1. DRIVERS DE FILTRO DE TECLADO (UPPERFILTERS)",
        f"   Filtros Registrados   : {', '.join(dados['filtros_teclado']['filtros_instalados']) or 'Nenhum'}",
        f"   Filtros de Terceiros  : {', '.join(dados['filtros_teclado']['filtros_terceiros']) or 'Nenhum (Padrão Windows)'}",
        "",
        f"2. PROCESSOS COM NOMES SUSPEITOS ({len(dados['processos_suspeitos'])})",
    ]
    if not dados["processos_suspeitos"]:
        linhas.append("   Nenhum processo com assinatura de keylogger em execução.")
    else:
        for p in dados["processos_suspeitos"]:
            linhas.append(f"   - PID {p['pid']}: {p['nome']} -> {p['motivo']}")

    linhas.append("")
    linhas.append(f"3. ARQUIVOS DE LOG DE TECLADO DETECTADOS ({len(dados['arquivos_suspeitos'])})")
    if not dados["arquivos_suspeitos"]:
        linhas.append("   Nenhum arquivo com padrão de captura de teclas encontrado nas pastas temporárias.")
    else:
        for a in dados["arquivos_suspeitos"]:
            linhas.append(f"   - {a['caminho']} ({a['tamanho']} bytes)")

    linhas.append("")
    linhas.append(f"4. ALERTAS DEFENSIVOS ({len(dados['alertas'])})")
    if not dados["alertas"]:
        linhas.append("   Ambiente limpo: sem evidências de captura ou interceptação de teclado.")
    else:
        for al in dados["alertas"]:
            linhas.append(f"   [{al['severidade'].upper()}] {al['titulo']}")
            linhas.append(f"     Detalhe: {al['detalhe']}")

    linhas.append("=" * 72)
    return "\n".join(linhas)


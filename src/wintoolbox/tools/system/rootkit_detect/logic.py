"""Lógica pura de detecção heurística de rootkits (sem Qt).

Aplica técnicas de análise comparativa defensiva:
1. Cross-check de processos: compara a enumeração nativa do kernel do Windows
   (CreateToolhelp32Snapshot) com as APIs de usuário do psutil para identificar processos ocultos;
2. Verificação de integridade e caminhos de processos críticos (lsass.exe, csrss.exe,
   services.exe, winlogon.exe) para detectar trojans e masquerading;
3. Detecção de portas TCP em escuta (LISTEN) órfãs ou sem identificação de processo.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import psutil

PROCESSOS_CRITICOS = {
    "lsass.exe": r"\windows\system32\lsass.exe",
    "csrss.exe": r"\windows\system32\csrss.exe",
    "services.exe": r"\windows\system32\services.exe",
    "winlogon.exe": r"\windows\system32\winlogon.exe",
    "smss.exe": r"\windows\system32\smss.exe",
}


class _PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def _coletar_pids_nativos() -> Dict[int, str]:
    """Enumera processos via API Win32 CreateToolhelp32Snapshot."""
    TH32CS_SNAPPROCESS = 0x00000002
    kernel32 = ctypes.windll.kernel32

    hSnapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if hSnapshot == -1:
        return {}

    pe = _PROCESSENTRY32()
    pe.dwSize = ctypes.sizeof(_PROCESSENTRY32)

    pids: Dict[int, str] = {}
    try:
        if kernel32.Process32First(hSnapshot, ctypes.byref(pe)):
            while True:
                pid = pe.th32ProcessID
                try:
                    nome = pe.szExeFile.decode("utf-8", errors="replace")
                except Exception:
                    nome = "desconhecido"
                pids[pid] = nome
                if not kernel32.Process32Next(hSnapshot, ctypes.byref(pe)):
                    break
    finally:
        kernel32.CloseHandle(hSnapshot)

    return pids


def _verificar_processos_criticos() -> List[Dict[str, Any]]:
    """Valida se processos críticos estão executando a partir do diretório legítimo System32."""
    anomalias: List[Dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            info = proc.info
            nome = str(info.get("name") or "").lower()
            if nome in PROCESSOS_CRITICOS:
                caminho_esperado = PROCESSOS_CRITICOS[nome].lower()
                caminho_real = str(info.get("exe") or "").lower()

                if caminho_real and not caminho_real.endswith(caminho_esperado):
                    anomalias.append({
                        "pid": info["pid"],
                        "nome": info["name"],
                        "caminho_real": caminho_real,
                        "caminho_esperado": caminho_esperado,
                        "motivo": f"Processo crítico '{info['name']}' executando fora do System32!",
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return anomalias


def _verificar_portas_orfas() -> List[Dict[str, Any]]:
    """Detecta sockets em escuta associados a PIDs inexistentes ou ocultos."""
    pids_vivos = set(psutil.pids())
    orfas: List[Dict[str, Any]] = []

    try:
        for c in psutil.net_connections(kind="tcp"):
            if c.status == "LISTEN" and c.laddr:
                pid = c.pid or 0
                if pid != 0 and pid not in pids_vivos:
                    orfas.append({
                        "porta": c.laddr.port,
                        "ip": c.laddr.ip,
                        "pid": pid,
                        "motivo": f"Porta {c.laddr.port} associada a PID {pid} inexistente na tabela de processos",
                    })
    except Exception:
        pass

    return orfas


def coletar_dados_rootkit() -> Dict[str, Any]:
    """Auditoria heurística completa de processos ocultos e integridade do kernel."""
    pids_nativos = _coletar_pids_nativos()
    pids_psutil = set(psutil.pids())

    # Processos presentes na API nativa mas ausentes na lista de usuário (PID 0 é System Idle)
    pids_ocultos: List[Dict[str, Any]] = []
    for pid, nome in pids_nativos.items():
        if pid != 0 and pid not in pids_psutil:
            # Revalidar se o processo acabou de encerrar
            if not psutil.pid_exists(pid):
                continue
            pids_ocultos.append({
                "pid": pid,
                "nome": nome,
                "motivo": "Presente em CreateToolhelp32Snapshot mas invisível para psutil",
            })

    processos_mascarados = _verificar_processos_criticos()
    portas_orfas = _verificar_portas_orfas()

    score = 100
    alertas: List[Dict[str, str]] = []
    recoms: List[str] = []

    if pids_ocultos:
        score -= len(pids_ocultos) * 40
        for p in pids_ocultos:
            alertas.append({
                "severidade": "Crítico",
                "titulo": f"Processo Oculto Detectado: {p['nome']} (PID {p['pid']})",
                "detalhe": p["motivo"],
            })
        recoms.append("Execute ferramentas de remoção especializada em nível de kernel (como TDSSKiller ou GMER).")

    if processos_mascarados:
        score -= len(processos_mascarados) * 45
        for m in processos_mascarados:
            alertas.append({
                "severidade": "Crítico",
                "titulo": f"Masquerading de Processo do Sistema: {m['nome']} (PID {m['pid']})",
                "detalhe": f"Caminho anômalo: {m['caminho_real']}",
            })
        recoms.append("Isole o executável suspeito imediatamente e analise com antivírus.")

    if portas_orfas:
        score -= len(portas_orfas) * 20
        for o in portas_orfas:
            alertas.append({
                "severidade": "Alto",
                "titulo": f"Porta Órfã em Escuta: {o['porta']}",
                "detalhe": o["motivo"],
            })
        recoms.append("Verifique se há drivers de rede com portas ocultas ativas.")

    return {
        "total_processos_nativos": len(pids_nativos),
        "total_processos_psutil": len(pids_psutil),
        "processos_ocultos": pids_ocultos,
        "processos_mascarados": processos_mascarados,
        "portas_orfas": portas_orfas,
        "score_integridade": max(0, min(100, score)),
        "alertas": alertas,
        "recomendacoes": recoms,
    }


def gerar_relatorio_rootkit(dados: Dict[str, Any]) -> str:
    """Gera laudo pericial da análise heurística de rootkits."""
    linhas: List[str] = [
        "=" * 72,
        "RELATÓRIO DE AUDITORIA — DETECTOR HEURÍSTICO DE ROOTKITS",
        "=" * 72,
        f"Data da Auditoria        : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Score de Integridade     : {dados['score_integridade']}/100",
        f"Processos Nativo (Win32) : {dados['total_processos_nativos']}",
        f"Processos (psutil)       : {dados['total_processos_psutil']}",
        "",
        f"1. PROCESSOS OCULTOS IDENTIFICADOS ({len(dados['processos_ocultos'])})",
    ]
    if not dados["processos_ocultos"]:
        linhas.append("   Nenhum processo oculto identificado no cross-check de APIs.")
    else:
        for p in dados["processos_ocultos"]:
            linhas.append(f"   [ALERTA] PID {p['pid']}: {p['nome']} -> {p['motivo']}")

    linhas.append("")
    linhas.append(f"2. PROCESSOS CRÍTICOS COM MASQUERADING ({len(dados['processos_mascarados'])})")
    if not dados["processos_mascarados"]:
        linhas.append("   Todos os processos essenciais de segurança estão em C:\\Windows\\System32.")
    else:
        for m in dados["processos_mascarados"]:
            linhas.append(f"   [CRÍTICO] PID {m['pid']}: {m['nome']}")
            linhas.append(f"     Caminho Anômalo: {m['caminho_real']}")

    linhas.append("")
    linhas.append(f"3. PORTAS EM ESCUTA ÓRFÃS ({len(dados['portas_orfas'])})")
    if not dados["portas_orfas"]:
        linhas.append("   Nenhuma porta em escuta desvinculada de processos legítimos.")
    else:
        for o in dados["portas_orfas"]:
            linhas.append(f"   - Porta {o['porta']} (IP {o['ip']}) -> {o['motivo']}")

    linhas.append("")
    linhas.append(f"4. ALERTAS DEFENSIVOS ({len(dados['alertas'])})")
    if not dados["alertas"]:
        linhas.append("   Nenhum indício heurístico de rootkit em nível de usuário ou processos.")
    else:
        for al in dados["alertas"]:
            linhas.append(f"   [{al['severidade'].upper()}] {al['titulo']}")
            linhas.append(f"     Detalhe: {al['detalhe']}")

    linhas.append("=" * 72)
    return "\n".join(linhas)


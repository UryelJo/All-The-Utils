"""
Lógica pura de análise de travamentos do Windows, telas azuis (BSODs), erros WHEA e desligamentos inesperados.
Totalmente desacoplada de bibliotecas de interface visual.
"""
from datetime import datetime
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.crash_analyzer")

# Tabela semântica dos principais códigos de parada (BugCheck Codes) da Microsoft
BUGCHECK_DESCRIPTIONS: Dict[int, str] = {
    0x0000000A: "IRQL_NOT_LESS_OR_EQUAL — Driver tentou acessar memória inválida em IRQL alto.",
    0x0000001A: "MEMORY_MANAGEMENT — Erro crítico na gestão de memória RAM do sistema.",
    0x0000001E: "KMODE_EXCEPTION_NOT_HANDLED — Exceção no modo kernel não capturada pelo driver.",
    0x00000024: "NTFS_FILE_SYSTEM — Falha no driver do sistema de arquivos NTFS ou corrupção de disco.",
    0x0000003B: "SYSTEM_SERVICE_EXCEPTION — Falha em serviço do sistema operacional ou driver gráfico.",
    0x00000050: "PAGE_FAULT_IN_NONPAGED_AREA — Memória de sistema referenciada é inválida (RAM defeituosa ou driver).",
    0x0000007E: "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED — Thread do sistema gerou exceção que não foi tratada.",
    0x0000007F: "UNEXPECTED_KERNEL_MODE_TRAP — Falha de hardware ou estouro de pilha no kernel (stack overflow).",
    0x0000009F: "DRIVER_POWER_STATE_FAILURE — Driver travou ao suspender, hibernar ou gerenciar energia.",
    0x000000BE: "ATTEMPTED_WRITE_TO_READONLY_MEMORY — Tentativa de escrita em memória somente-leitura.",
    0x000000C2: "BAD_POOL_CALLER — Driver realizou requisição incorreta de alocação de pool de memória.",
    0x000000C4: "DRIVER_VERIFIER_DETECTED_VIOLATION — O Driver Verifier detectou violação de segurança do driver.",
    0x000000D1: "DRIVER_IRQL_NOT_LESS_OR_EQUAL — Driver causou falha de página em nível IRQL elevado.",
    0x00000109: "CRITICAL_STRUCTURE_CORRUPTION — Modificação não autorizada em estrutura vital do kernel (PatchGuard).",
    0x00000116: "VIDEO_TDR_FAILURE — O driver da placa de vídeo (GPU) parou de responder e não recuperou.",
    0x00000124: "WHEA_UNCORRECTABLE_ERROR — Erro fatal e irrecuperável de hardware (CPU, barramento PCIe ou cache).",
    0x00000133: "DPC_WATCHDOG_VIOLATION — Rotina DPC travou ou demorou além do limite permitido.",
    0x00000139: "KERNEL_SECURITY_CHECK_FAILURE — Falha na verificação de integridade de segurança do kernel.",
    0x00000154: "UNEXPECTED_STORE_EXCEPTION — Falha no componente de armazenamento de paginação compactada (SSD/HDD)."
}


def explain_bugcheck_code(code_num: int) -> str:
    """Retorna uma explicação humana detalhada a partir do código numérico de BugCheck."""
    if code_num in BUGCHECK_DESCRIPTIONS:
        return BUGCHECK_DESCRIPTIONS[code_num]
    return f"Código de parada 0x{code_num:08X} (consulte a base de conhecimento da Microsoft para este código específico)."


def list_minidump_files() -> List[Dict[str, Any]]:
    """Localiza e lista arquivos de despejo de memória (Minidumps) em C:\\Windows\\Minidump."""
    minidumps: List[Dict[str, Any]] = []
    dump_dir = Path("C:/Windows/Minidump")

    if dump_dir.exists() and dump_dir.is_dir():
        try:
            for p in sorted(dump_dir.glob("*.dmp"), key=lambda f: f.stat().st_mtime, reverse=True):
                stat = p.stat()
                minidumps.append({
                    "name": p.name,
                    "path": str(p),
                    "size_bytes": stat.st_size,
                    "size_str": f"{stat.st_size / 1024:.1f} KB",
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
                })
        except Exception as exc:
            _log.warning("Falha ao ler diretório de minidumps: %s", exc)

    # Verifica também o MEMORY.DMP completo se existir
    full_dump = Path("C:/Windows/MEMORY.DMP")
    if full_dump.exists():
        try:
            stat = full_dump.stat()
            minidumps.insert(0, {
                "name": "MEMORY.DMP (Completo)",
                "path": str(full_dump),
                "size_bytes": stat.st_size,
                "size_str": f"{stat.st_size / (1024*1024):.1f} MB",
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
            })
        except Exception:
            pass

    return minidumps


def query_system_crash_events(max_events: int = 50) -> List[Dict[str, Any]]:
    """
    Consulta o Log de Eventos do Windows (System) por eventos críticos de falha:
    - ID 41 (Kernel-Power: reinício sem desligamento prévio limpo)
    - ID 1001 (BugCheck: registro da BSOD com código de erro)
    - ID 6008 (Desligamento inesperado)
    - Provedor WHEA-Logger (Erros de hardware de CPU/PCIe)
    """
    events: List[Dict[str, Any]] = []

    ps_script = f"""
    $events = Get-WinEvent -FilterHashtable @{{
        LogName = 'System';
        Id = 41, 1001, 6008;
    }} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
    Select-Object Id, TimeCreated, ProviderName, Message

    $events | ConvertTo-Json -Compress
    """

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=25
        )
        stdout = proc.stdout.strip()
        if not stdout:
            return []

        import json
        raw = json.loads(stdout)
        event_list = [raw] if isinstance(raw, dict) else raw

        for ev in event_list:
            eid = int(ev.get("Id", 0))
            msg = str(ev.get("Message", "")).strip()

            # Converte data / timestamp
            time_raw = ev.get("TimeCreated", "")
            time_str = str(time_raw)

            # Interpretação amigável do evento
            if eid == 41:
                category = "Reinicio Inesperado (Kernel-Power)"
                explanation = "O sistema reiniciou sem desligar corretamente primeiro. Causado por queda de energia, travamento ou BSOD."
            elif eid == 1001:
                category = "Tela Azul (BugCheck / BSOD)"
                # Tenta extrair código Bugcheck
                explanation = "O computador foi reinicializado após uma verificação de erro (Blue Screen of Death)."
                for line in msg.splitlines():
                    if "0x" in line:
                        explanation += f" Detalhe: {line.strip()}"
                        break
            elif eid == 6008:
                category = "Desligamento Inesperado"
                explanation = "O desligamento anterior do sistema às foi inesperado."
            else:
                category = f"Evento {eid}"
                explanation = msg[:200]

            events.append({
                "id": eid,
                "time": time_str,
                "category": category,
                "provider": ev.get("ProviderName", "System"),
                "explanation": explanation,
                "raw_message": msg
            })
    except Exception as exc:
        _log.warning("Falha ao consultar logs de travamentos: %s", exc)

    return events

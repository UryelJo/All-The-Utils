"""
Lógica pura de análise de travamentos do Windows, telas azuis (BSODs), erros de aplicativos,
erros WHEA e desligamentos inesperados.
Totalmente desacoplada de bibliotecas de interface visual.
"""
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.crash_analyzer")

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


def format_crash_timestamp(raw_val: Any) -> str:
    """
    Converte datas serializadas pelo PowerShell/JSON (como '/Date(1794022269145)/' ou ISO)
    para o formato legível brasileiro 'dd/MM/yyyy HH:mm:ss'.
    """
    s = str(raw_val or "").strip()
    if not s:
        return "-"

    # Trata formato Microsoft JSON: /Date(1794022269145)/ ou /Date(1794022269145-0300)/
    m = re.search(r"/Date\((-?\d+)(?:[+-]\d+)?\)/", s)
    if m:
        try:
            ms = int(m.group(1))
            dt = datetime.fromtimestamp(ms / 1000.0)
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            pass

    # Trata ISO 8601: 2026-10-30T14:22:10...
    if "T" in s and re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", s):
        try:
            clean_iso = s.split(".")[0].replace("Z", "")
            dt = datetime.strptime(clean_iso[:19], "%Y-%m-%dT%H:%M:%S")
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            pass

    return s


def extract_faulting_app_or_module(message: str, provider: str = "", event_id: int = 0) -> str:
    """
    Extrai da mensagem do evento o aplicativo (.exe), biblioteca (.dll) ou driver (.sys)
    que causou o travamento ou tela azul.
    """
    msg = (message or "").strip()
    app_name = ""
    mod_name = ""

    # 1. Padrão Application Error (ID 1000) em PT-BR e EN-US
    m_app = re.search(
        r"(?:Nome do aplicativo com falha|Faulting application name|Aplicativo com falha)\s*:\s*([^\r\n,;]+)",
        msg,
        re.IGNORECASE,
    )
    if m_app:
        val = m_app.group(1).strip()
        if val and val.lower() not in ("unknown", "desconhecido"):
            app_name = Path(val).name

    m_mod = re.search(
        r"(?:Nome do m[óo]dulo com falha|Faulting module name|M[óo]dulo com falha)\s*:\s*([^\r\n,;]+)",
        msg,
        re.IGNORECASE,
    )
    if m_mod:
        val = m_mod.group(1).strip()
        if val and val.lower() not in ("unknown", "desconhecido"):
            mod_name = Path(val).name

    if app_name and mod_name and app_name.lower() != mod_name.lower():
        return f"{app_name} ({mod_name})"
    if app_name:
        return app_name
    if mod_name:
        return mod_name

    # 2. Padrão Application Hang (ID 1002): "O programa X.exe versão Y parou de interagir com o Windows"
    m_hang = re.search(
        r"(?:O programa|The program)\s+([^\s,]+\.exe)\b",
        msg,
        re.IGNORECASE,
    )
    if m_hang:
        return m_hang.group(1).strip()

    # 3. Qualquer menção direta a driver (.sys) ou executável (.exe) na mensagem
    m_bin = re.search(r"\b([a-zA-Z0-9_\-\.]+\.(?:sys|exe|dll))\b", msg, re.IGNORECASE)
    if m_bin:
        found = m_bin.group(1)
        if found.lower() not in ("explorer.exe", "svchost.exe") or event_id in (1000, 1002):
            return found

    # 4. Fallbacks semânticos por tipo de evento
    if event_id == 41 or "kernel-power" in (provider or "").lower():
        return "Sistema / Energia (Kernel-Power)"
    if event_id == 1001 or "bugcheck" in (provider or "").lower() or "wer" in (provider or "").lower():
        return "Kernel / Driver (BSOD)"
    if "whea" in (provider or "").lower():
        return "Hardware Físico (WHEA)"
    if event_id == 6008:
        return "Sistema Operacional (EventLog)"

    return provider or "Sistema"


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
    Consulta o Log de Eventos do Windows (System e Application) por eventos críticos de falha:
    - System: ID 41 (Kernel-Power), ID 1001 (BugCheck/BSOD), ID 6008 (Desligamento inesperado)
    - Application: ID 1000 (Application Error / Crash de App), ID 1002 (Application Hang / App Travado)
    """
    events: List[Dict[str, Any]] = []

    ps_script = f"""
    $sysEvents = @(Get-WinEvent -FilterHashtable @{{
        LogName = 'System';
        Id = 41, 1001, 6008;
    }} -MaxEvents {max_events} -ErrorAction SilentlyContinue)

    $appEvents = @(Get-WinEvent -FilterHashtable @{{
        LogName = 'Application';
        Id = 1000, 1002;
    }} -MaxEvents {max_events} -ErrorAction SilentlyContinue)

    $all = ($sysEvents + $appEvents) | Sort-Object TimeCreated -Descending | Select-Object -First {max_events}
    $all | Select-Object Id,
        @{{Name='TimeFormatted'; Expression={{$_.TimeCreated.ToString('dd/MM/yyyy HH:mm:ss')}}}},
        TimeCreated,
        ProviderName,
        Message | ConvertTo-Json -Compress
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

        raw = json.loads(stdout)
        event_list = [raw] if isinstance(raw, dict) else raw

        for ev in event_list:
            eid = int(ev.get("Id", 0))
            msg = str(ev.get("Message", "")).strip()
            provider = str(ev.get("ProviderName", "System")).strip()

            raw_time = ev.get("TimeFormatted") or ev.get("TimeCreated") or ""
            time_str = format_crash_timestamp(raw_time)
            faulting_app = extract_faulting_app_or_module(msg, provider=provider, event_id=eid)

            if eid == 41:
                category = "Reinício Inesperado (Kernel-Power)"
                explanation = "O sistema reiniciou sem desligar limpa e previamente (queda de energia, reset forçado ou BSOD)."
            elif eid == 1001:
                category = "Tela Azul (BugCheck / BSOD)"
                explanation = "O computador foi reinicializado após uma verificação de erro (Blue Screen of Death)."
                for line in msg.splitlines():
                    if "0x" in line:
                        explanation += f" Detalhe: {line.strip()}"
                        break
            elif eid == 6008:
                category = "Desligamento Inesperado"
                explanation = "O desligamento anterior do sistema foi inesperado."
            elif eid == 1000:
                category = "Falha de Aplicativo (Crash)"
                explanation = f"O aplicativo '{faulting_app}' encerrou inesperadamente devido a uma exceção não tratada."
            elif eid == 1002:
                category = "Travamento de Aplicativo (Hang)"
                explanation = f"O aplicativo '{faulting_app}' parou de responder (Congelamento / Não Está Respondendo)."
            else:
                category = f"Evento {eid}"
                explanation = msg[:200]

            events.append({
                "id": eid,
                "time": time_str,
                "category": category,
                "faulting_app": faulting_app,
                "provider": provider,
                "explanation": explanation,
                "raw_message": msg
            })
    except Exception as exc:
        _log.warning("Falha ao consultar logs de travamentos: %s", exc)

    return events

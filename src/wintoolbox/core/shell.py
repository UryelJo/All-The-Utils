"""
Execução segura e invisível de comandos de sistema e PowerShell no Windows.
Tratamento robusto de encodings (UTF-8, CP1252, CP850).
"""
import sys
import json
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

def run_command(
    cmd: Union[str, List[str]],
    shell: bool = False,
    timeout: Optional[int] = None
) -> Tuple[int, str, str]:
    """
    Executa um comando de forma síncrona, capturando stdout e stderr sem abrir janelas.
    """
    try:
        proc = subprocess.Popen(
            cmd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=CREATION_FLAGS
        )
        out_bytes, err_bytes = proc.communicate(timeout=timeout)

        # Decodificação inteligente com múltiplos encodings do Windows
        out = _decode_smart(out_bytes)
        err = _decode_smart(err_bytes)
        return proc.returncode, out, err
    except Exception as e:
        return -1, "", str(e)

def run_command_streaming(
    cmd: Union[str, List[str]],
    on_output: Callable[[str], None],
    shell: bool = False,
    is_cancelled: Optional[Callable[[], bool]] = None
) -> int:
    """
    Executa um comando e transmite as linhas de saída em tempo real via callback.
    """
    try:
        proc = subprocess.Popen(
            cmd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=CREATION_FLAGS
        )

        while True:
            if is_cancelled and is_cancelled():
                proc.terminate()
                return -1

            line_bytes = proc.stdout.readline()
            if not line_bytes and proc.poll() is not None:
                break
            if line_bytes:
                line_str = _decode_smart(line_bytes).rstrip()
                on_output(line_str)

        proc.wait()
        return proc.returncode
    except Exception as e:
        on_output(f"[ERRO]: {str(e)}")
        return -1

def run_powershell_json(script: str) -> Optional[Union[Dict, List, Any]]:
    """
    Executa um comando/script no PowerShell e faz parse da saída JSON.
    Garante codificação UTF-8 na saída do console do PowerShell.
    """
    # Força UTF-8 no console do PowerShell antes de emitir JSON
    wrapped_script = (
        f"$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        f"{script} | ConvertTo-Json -Depth 5"
    )
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", wrapped_script]
    code, out, _ = run_command(cmd)
    if code != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except Exception:
        return None

def _decode_smart(b: bytes) -> str:
    """Tenta decodificar sequencialmente em UTF-8, CP1252 e CP850."""
    if not b:
        return ""
    for enc in ("utf-8", "cp1252", "cp850", "latin1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")

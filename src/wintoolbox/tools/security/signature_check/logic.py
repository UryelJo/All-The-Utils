"""
Lógica pura de validação de assinaturas digitais Authenticode de executáveis e DLLs no Windows.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import json
from pathlib import Path
import subprocess
from typing import Any, Dict

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("security.signature_check")


def check_authenticode_signature(file_path: Path) -> Dict[str, Any]:
    """
    Verifica a autenticidade e validade da assinatura digital Authenticode de um arquivo executável.
    """
    p_str = str(file_path).strip()
    if not p_str or not file_path.is_file():
        raise ValueError(f"Arquivo não encontrado: {p_str}")

    import base64
    import shutil

    ps_script = f"""
    $sig = Get-AuthenticodeSignature -LiteralPath "{p_str}"
    $cert = $sig.SignerCertificate
    $subject = ""
    $issuer = ""
    $thumb = ""
    $notAfter = ""
    if ($cert -ne $null) {{
        $subject = [string]$cert.Subject
        $issuer = [string]$cert.Issuer
        $thumb = [string]$cert.Thumbprint
        $notAfter = $cert.NotAfter.ToString("yyyy-MM-dd")
    }}
    [PSCustomObject]@{{
        Status = $sig.Status.ToString()
        StatusMessage = [string]$sig.StatusMessage
        Subject = $subject
        Issuer = $issuer
        Thumbprint = $thumb
        NotAfter = $notAfter
    }} | ConvertTo-Json -Compress
    """
    encoded_cmd = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
    ps_exe = shutil.which("pwsh.exe") or shutil.which("pwsh") or "powershell.exe"

    try:
        proc = subprocess.run(
            [ps_exe, "-NoProfile", "-EncodedCommand", encoded_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=20
        )
        stdout = proc.stdout.strip()
        if not stdout:
            return {
                "file_name": file_path.name,
                "status": "NotSigned",
                "status_label": "Não Assinado",
                "is_valid": False,
                "signer": "Nenhum certificado anexado",
                "issuer": "-",
                "thumbprint": "-",
                "valid_until": "-"
            }

        data = json.loads(stdout)
        raw_status = str(data.get("Status", "NotSigned"))

        # Tradução semântica do status
        status_map = {
            "Valid": ("Válida e Autêntica", True),
            "0": ("Válida e Autêntica", True),
            "NotSigned": ("Não Assinado", False),
            "HashMismatch": ("Assinatura Adulterada / Hash Incorreto", False),
            "NotTrusted": ("Certificado Não Confiável", False),
            "NotSupportedFileFormat": ("Formato Não Suportado", False)
        }

        label, is_valid = status_map.get(raw_status, (f"Status: {raw_status}", False))

        # Limpa Subject (geralmente no formato 'CN=Empresa, O=Empresa...')
        subj = str(data.get("Subject") or "Não especificado")
        issuer = str(data.get("Issuer") or "-")

        return {
            "file_name": file_path.name,
            "file_path": p_str,
            "raw_status": raw_status,
            "status_label": label,
            "is_valid": is_valid,
            "signer": subj,
            "issuer": issuer,
            "thumbprint": str(data.get("Thumbprint") or "-"),
            "valid_until": str(data.get("NotAfter") or "-")
        }

    except Exception as exc:
        _log.warning("Falha ao checar assinatura de %s: %s", file_path.name, exc)
        return {
            "file_name": file_path.name,
            "file_path": p_str,
            "raw_status": "Error",
            "status_label": f"Erro na verificação: {exc}",
            "is_valid": False,
            "signer": "-",
            "issuer": "-",
            "thumbprint": "-",
            "valid_until": "-"
        }

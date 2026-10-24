"""
Lógica pura de consulta de reputação e verificação de hashes de arquivos no VirusTotal via API v3.
Consome credenciais exclusivamente através de get_api_token('virustotal') de settings.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import urllib.error
import urllib.request

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.settings import get_api_token

_log = get_logger("security.virustotal")


def calculate_file_sha256(file_path: Path) -> str:
    """Calcula o hash SHA-256 do arquivo local."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def query_virustotal_hash(file_hash: str) -> Dict[str, Any]:
    """
    Consulta o relatório de reputação de um hash de arquivo na API v3 do VirusTotal.
    """
    clean_hash = file_hash.strip().lower()
    if not clean_hash or len(clean_hash) not in (32, 40, 64):
        return {"error": "Hash inválido. Informe um hash MD5 (32 chars), SHA-1 (40 chars) ou SHA-256 (64 chars)."}

    api_key = get_api_token("virustotal")
    if not api_key:
        return {
            "error": "Chave de API do VirusTotal não configurada.\n"
                     "Cadastre sua chave gratuita em 'Configurações > Chaves de API e Tokens de Serviços'."
        }

    url = f"https://www.virustotal.com/api/v3/files/{clean_hash}"
    headers = {
        "x-apikey": api_key.strip(),
        "User-Agent": "WinToolbox-Security-Audit/1.0"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})
        results_by_engine = attrs.get("last_analysis_results", {})

        detections = []
        for engine, res in results_by_engine.items():
            cat = res.get("category", "")
            if cat in ("malicious", "suspicious"):
                detections.append({
                    "engine": engine,
                    "category": cat,
                    "result": res.get("result", "Ameaça Detectada")
                })

        return {
            "hash": clean_hash,
            "meaningful_name": attrs.get("meaningful_name", "Desconhecido"),
            "file_size": attrs.get("size", 0),
            "malicious": stats.get("malicious", 0),
            "suspicious": stats.get("suspicious", 0),
            "undetected": stats.get("undetected", 0),
            "harmless": stats.get("harmless", 0),
            "total_engines": len(results_by_engine),
            "detections": detections,
            "reputation": attrs.get("reputation", 0)
        }

    except urllib.error.HTTPError as http_err:
        if http_err.code == 404:
            return {"not_found": True, "hash": clean_hash, "message": "O hash não foi encontrado na base do VirusTotal (arquivo nunca analisado ou limpo)."}
        elif http_err.code == 401 or http_err.code == 403:
            return {"error": "Chave de API do VirusTotal rejeitada pelo servidor (chave inválida ou limite diário excedido)."}
        return {"error": f"Erro HTTP {http_err.code} do VirusTotal: {http_err.reason}"}
    except Exception as exc:
        _log.warning("Falha ao consultar VirusTotal: %s", exc)
        return {"error": f"Falha na conexão com VirusTotal: {exc}"}

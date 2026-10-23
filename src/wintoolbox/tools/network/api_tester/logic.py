"""
Lógica pura da ferramenta Testador de API HTTP (Mini Postman).
Disparo de requisições REST, parse de cabeçalhos e formatação de resposta sem Qt.
"""
from dataclasses import dataclass
import json
import time
from typing import Dict, Optional
import urllib.error
import urllib.request


@dataclass
class ApiResponse:
    code: int
    time_ms: float
    size: int
    headers: Dict[str, str]
    body: str
    error: Optional[str] = None


def parse_headers_str(headers_str: str) -> Dict[str, str]:
    """Converte texto de cabeçalhos chave: valor em dicionário."""
    headers_dict = {}
    for line in headers_str.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            headers_dict[k.strip()] = v.strip()
    return headers_dict


def format_json_if_possible(text: str) -> str:
    """Tenta formatar uma string JSON com indentação legível."""
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except Exception:
        return text


def execute_http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    timeout: float = 12.0,
) -> ApiResponse:
    """Executa a requisição HTTP com temporização e captura de status, cabeçalhos e corpo."""
    headers_dict = headers or {}
    t0 = time.time()
    data_bytes = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data_bytes, headers=headers_dict, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = (time.time() - t0) * 1000
            raw_content = resp.read()
            text = raw_content.decode("utf-8", errors="replace")
            resp_headers = dict(resp.getheaders())
            return ApiResponse(
                code=resp.getcode(),
                time_ms=elapsed,
                size=len(raw_content),
                headers=resp_headers,
                body=text,
                error=None,
            )
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - t0) * 1000
        raw = e.read()
        return ApiResponse(
            code=e.code,
            time_ms=elapsed,
            size=len(raw),
            headers=dict(e.headers.items()) if e.headers else {},
            body=raw.decode("utf-8", errors="replace"),
            error=str(e.reason),
        )
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        return ApiResponse(
            code=0,
            time_ms=elapsed,
            size=0,
            headers={},
            body=f"Erro de conexão: {str(e)}",
            error=str(e),
        )

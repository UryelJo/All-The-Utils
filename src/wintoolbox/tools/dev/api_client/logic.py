"""
Lógica pura para o Cliente HTTP / REST de Desenvolvedor (dev.api_client).
Executa requisições HTTP e HTTPS nativas (GET, POST, PUT, DELETE, PATCH, HEAD),
com medição precisa de latência, suporte a headers, body e detecção automática de JSON.

Zero dependências de interface gráfica.
"""
import io
import json
import time
from typing import Any, Dict, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request


def execute_http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    timeout_seconds: float = 10.0,
) -> Dict[str, Any]:
    """
    Executa uma requisição HTTP/HTTPS e retorna a resposta detalhada e estatísticas de rede.
    """
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("A URL da requisição não pode estar vazia.")

    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"http://{clean_url}"

    method = method.upper().strip()
    req_headers = dict(headers or {})
    # Adiciona User-Agent padrão se não especificado
    if "User-Agent" not in req_headers:
        req_headers["User-Agent"] = "WinToolbox-Dev-Client/1.0"

    data_bytes: Optional[bytes] = None
    if body is not None and method in ("POST", "PUT", "PATCH"):
        data_bytes = body.encode("utf-8")
        if "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/json" if (body.startswith("{") or body.startswith("[")) else "text/plain"

    req = urllib.request.Request(
        url=clean_url,
        data=data_bytes,
        headers=req_headers,
        method=method,
    )

    t0 = time.perf_counter()
    status_code = 0
    status_text = ""
    res_headers: Dict[str, str] = {}
    response_body = ""
    error_message: Optional[str] = None

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            status_code = resp.status
            status_text = resp.reason or "OK"
            res_headers = {k: v for k, v in resp.getheaders()}
            raw_bytes = resp.read()
            response_body = raw_bytes.decode("utf-8", errors="replace")

    except urllib.error.HTTPError as http_err:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        status_code = http_err.code
        status_text = http_err.reason or "Erro HTTP"
        res_headers = {k: v for k, v in http_err.headers.items()}
        try:
            response_body = http_err.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = ""
        error_message = f"HTTP {status_code} {status_text}"

    except urllib.error.URLError as url_err:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        status_code = 0
        status_text = "Falha de Conexão"
        error_message = f"Falha na conexão: {url_err.reason}"

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        status_code = 0
        status_text = "Erro"
        error_message = str(exc)

    # Detecção e formatação de JSON
    is_json = False
    parsed_json: Optional[Any] = None
    if response_body and (response_body.startswith("{") or response_body.startswith("[")):
        try:
            parsed_json = json.loads(response_body)
            is_json = True
            response_body = json.dumps(parsed_json, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {
        "status_code": status_code,
        "status_text": status_text,
        "elapsed_ms": elapsed_ms,
        "headers": res_headers,
        "body": response_body,
        "body_bytes": len(response_body.encode("utf-8")),
        "is_json": is_json,
        "error": error_message,
        "success": 200 <= status_code < 400,
    }

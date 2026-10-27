"""
Testes unitários rigorosos (Isolamento de Rede Local) para o Cliente HTTP / REST (dev.api_client).
Utiliza servidor HTTP nativo local efêmero, testando GET, POST, erros HTTP e timeout.
"""
import http.server
import json
import threading
from typing import Generator
import pytest

from wintoolbox.tools.dev.api_client.logic import execute_http_request
from wintoolbox.tools.dev.api_client.tool import ApiClientTool


class MockApiHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "app": "wintoolbox"}')
        elif self.path == "/error502":
            self.send_response(502)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>502 Bad Gateway Proxy Error</body></html>")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        # Ecoa os dados recebidos
        resp = {"received": body.decode("utf-8", errors="replace"), "method": "POST"}
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def log_message(self, format, *args):
        # Silencia logs no terminal durante testes
        pass


@pytest.fixture(scope="module")
def local_mock_server() -> Generator[str, None, None]:
    """Cria servidor HTTP local em porta efêmera para os testes unitários sem tocar a internet."""
    server = http.server.HTTPServer(("127.0.0.1", 0), MockApiHandler)
    host, port = server.server_address
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_api_client_get_success(local_mock_server: str):
    url = f"{local_mock_server}/health"
    res = execute_http_request(url, method="GET")

    assert res["status_code"] == 200
    assert res["success"] is True
    assert res["is_json"] is True
    assert '"status": "ok"' in res["body"]
    assert res["headers"].get("Content-Type") == "application/json"
    assert res["elapsed_ms"] >= 0.0


def test_api_client_post_payload(local_mock_server: str):
    url = f"{local_mock_server}/items"
    payload = '{"nome": "Caderno", "quantidade": 5}'

    res = execute_http_request(url, method="POST", body=payload)
    assert res["status_code"] == 201
    assert res["success"] is True
    assert "Caderno" in res["body"]


def test_api_client_http_502_error(local_mock_server: str):
    url = f"{local_mock_server}/error502"
    res = execute_http_request(url, method="GET")

    assert res["status_code"] == 502
    assert res["success"] is False
    assert "502 Bad Gateway" in res["body"]


def test_api_client_invalid_url_and_empty():
    with pytest.raises(ValueError, match="não pode estar vazia"):
        execute_http_request("   ")

    # Porta que não existe no localhost (conexão recusada)
    res = execute_http_request("http://127.0.0.1:59999/test", timeout_seconds=0.5)
    assert res["status_code"] == 0
    assert res["success"] is False
    assert "Falha" in res["status_text"]


def test_api_client_tool_ui(qtbot, local_mock_server: str):
    tool = ApiClientTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    view._txt_url.setText(f"{local_mock_server}/health")
    res = execute_http_request(f"{local_mock_server}/health", method="GET")
    view._on_request_success(res)

    assert "Status: 200" in view._lbl_status_badge.text()
    assert '"status": "ok"' in view._txt_resp_body.toPlainText()
    assert view._headers_table.visible_count() >= 1

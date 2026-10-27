"""
Lógica pura para servidor HTTP local de testes e mock de APIs.
Implementado com a biblioteca padrão http.server e threading, com suporte a rotas, latência e log de chamadas.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Dict, List, Optional


@dataclass
class MockRoute:
    """Representa uma rota configurada no servidor mock."""
    path: str
    method: str = "GET"  # "GET", "POST", "PUT", "DELETE", "PATCH", "ALL"
    status_code: int = 200
    content_type: str = "application/json"
    body: str = "{}"
    delay_ms: int = 0


@dataclass
class RequestLogEntry:
    """Registro de uma requisição recebida pelo servidor mock."""
    timestamp: str
    client_ip: str
    method: str
    path: str
    status_code: int


class MockRequestHandler(BaseHTTPRequestHandler):
    """Handler HTTP customizado para roteamento dinâmico em memória."""

    def _match_route(self, method: str, path: str) -> Optional[MockRoute]:
        routes: List[MockRoute] = getattr(self.server, "mock_routes", [])
        clean_path = path.split("?")[0].rstrip("/")
        if not clean_path:
            clean_path = "/"

        for r in routes:
            r_path = r.path.rstrip("/")
            if not r_path:
                r_path = "/"
            if r_path == clean_path:
                if r.method == "ALL" or r.method.upper() == method.upper():
                    return r
        return None

    def _handle_any(self, method: str):
        route = self._match_route(method, self.path)
        log_callback = getattr(self.server, "log_callback", None)
        now_str = datetime.now().strftime("%H:%M:%S")

        if route:
            # Latência simulada
            if route.delay_ms > 0:
                time.sleep(route.delay_ms / 1000.0)

            self.send_response(route.status_code)
            self.send_header("Content-Type", f"{route.content_type}; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

            body_bytes = route.body.encode("utf-8")
            self.wfile.write(body_bytes)

            if log_callback:
                log_callback(
                    RequestLogEntry(
                        timestamp=now_str,
                        client_ip=self.client_address[0],
                        method=method,
                        path=self.path,
                        status_code=route.status_code
                    )
                )
        else:
            # 404 Padrão
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            err_body = json.dumps({"error": "Rota não encontrada no mock server", "path": self.path}).encode("utf-8")
            self.wfile.write(err_body)

            if log_callback:
                log_callback(
                    RequestLogEntry(
                        timestamp=now_str,
                        client_ip=self.client_address[0],
                        method=method,
                        path=self.path,
                        status_code=404
                    )
                )

    def do_GET(self):
        self._handle_any("GET")

    def do_POST(self):
        self._handle_any("POST")

    def do_PUT(self):
        self._handle_any("PUT")

    def do_DELETE(self):
        self._handle_any("DELETE")

    def do_PATCH(self):
        self._handle_any("PATCH")

    def do_OPTIONS(self):
        # Suporte a preflight CORS
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def log_message(self, format, *args):
        # Suprime logs padrão no stderr do console
        pass


class MockHttpServer:
    """Controlador do servidor HTTP em segundo plano."""

    def __init__(self):
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._routes: List[MockRoute] = []
        self._log_history: List[RequestLogEntry] = []
        self._lock = threading.Lock()
        self.log_listener: Optional[Callable[[RequestLogEntry], None]] = None

    @property
    def is_running(self) -> bool:
        return self._server is not None

    def set_routes(self, routes: List[MockRoute]):
        self._routes = routes
        if self._server:
            self._server.mock_routes = routes

    def _on_request_logged(self, entry: RequestLogEntry):
        with self._lock:
            self._log_history.append(entry)
        if self.log_listener:
            self.log_listener(entry)

    def start(self, port: int = 8080, routes: Optional[List[MockRoute]] = None) -> int:
        """Inicia o servidor na porta especificada."""
        if self.is_running:
            raise RuntimeError("O servidor mock já está em execução.")

        if routes is not None:
            self._routes = routes

        try:
            self._server = HTTPServer(("127.0.0.1", port), MockRequestHandler)
        except OSError:
            # Tenta porta alternativa se estiver ocupada
            port += 1
            self._server = HTTPServer(("127.0.0.1", port), MockRequestHandler)

        self._server.mock_routes = self._routes
        self._server.log_callback = self._on_request_logged

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return port

    def stop(self):
        """Finaliza a execução do servidor."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None

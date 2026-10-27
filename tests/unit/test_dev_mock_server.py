"""
Testes unitários para dev.mock_server.
Valida ciclo de vida, roteamento e respostas HTTP do servidor mock local.
"""
import json
import urllib.request
import pytest

from wintoolbox.tools.dev.mock_server.logic import (
    MockHttpServer,
    MockRoute,
    RequestLogEntry,
)


@pytest.fixture
def running_mock_server():
    """Inicia um servidor mock em porta aleatória/alta e garante seu desligamento."""
    server = MockHttpServer()
    routes = [
        MockRoute(path="/api/teste", method="GET", status_code=200, body='{"mensagem": "ok"}'),
        MockRoute(path="/api/auth", method="POST", status_code=201, body='{"status": "created"}'),
    ]
    port = server.start(port=18923, routes=routes)
    yield server, port
    server.stop()


def test_mock_server_get_route(running_mock_server):
    """Testa requisição HTTP real ao servidor mock."""
    server, port = running_mock_server
    url = f"http://127.0.0.1:{port}/api/teste"

    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data == {"mensagem": "ok"}


def test_mock_server_post_route(running_mock_server):
    """Testa requisição POST ao servidor mock."""
    server, port = running_mock_server
    url = f"http://127.0.0.1:{port}/api/auth"

    req = urllib.request.Request(url, data=b"{}", method="POST")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "created"


def test_mock_server_404_not_found(running_mock_server):
    """Testa resposta 404 para rota não cadastrada."""
    server, port = running_mock_server
    url = f"http://127.0.0.1:{port}/rota/inexistente"

    req = urllib.request.Request(url, method="GET")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 404


def test_mock_server_lifecycle():
    """Valida controle de estado e proteção contra início duplo."""
    server = MockHttpServer()
    assert not server.is_running
    p = server.start(port=18924, routes=[])
    assert server.is_running

    with pytest.raises(RuntimeError):
        server.start(port=p)

    server.stop()
    assert not server.is_running

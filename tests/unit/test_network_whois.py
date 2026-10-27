"""
Testes de validação de efeito real para network.whois.logic.
"""
import socket
import threading
import pytest

from wintoolbox.tools.network.whois.logic import (
    WhoisResult,
    normalize_domain,
    get_whois_server_for_domain,
    parse_whois_text,
    query_whois_socket,
)


def test_normalize_domain_deterministic():
    assert normalize_domain("https://github.com/torvalds/linux") == "github.com"
    assert normalize_domain("http://PYTHON.ORG:8080/") == "python.org"
    assert normalize_domain("  uol.com.br  ") == "uol.com.br"


def test_get_whois_server_for_domain_mapping():
    assert get_whois_server_for_domain("exemplo.com.br") == "whois.registro.br"
    assert get_whois_server_for_domain("google.com") == "whois.verisign-grs.com"
    assert get_whois_server_for_domain("wikipedia.org") == "whois.pir.org"
    assert get_whois_server_for_domain("desconhecido.xyz") == "whois.iana.org"


def test_parse_whois_text_deterministic():
    sample_text = """
    Domain Name: GITHUB.COM
    Registry Domain ID: 123456789_DOMAIN_COM-VRSN
    Registrar: MarkMonitor Inc.
    Registrant Organization: GitHub, Inc.
    Creation Date: 2007-10-09T18:20:50Z
    Registry Expiry Date: 2028-10-09T18:20:50Z
    Domain Status: clientDeleteProhibited
    Name Server: DNS1.P08.NSONE.NET
    Name Server: DNS2.P08.NSONE.NET
    Name Server: NS-123.AWSDNS-15.COM
    """
    res = parse_whois_text("github.com", sample_text)
    assert res.domain == "github.com"
    assert res.registrar == "MarkMonitor Inc."
    assert res.registrant == "GitHub, Inc."
    assert res.creation_date == "2007-10-09"
    assert res.expiration_date == "2028-10-09"
    assert len(res.name_servers) == 3
    assert "dns1.p08.nsone.net" in res.name_servers
    assert "clientDeleteProhibited" in res.status


def test_parse_whois_text_registro_br():
    sample_br = """
    domain:      globo.com.br
    owner:       Globo Comunicação e Participações S/A
    responsible: Registro BR
    country:     BR
    owner-c:     GCP7
    admin-c:     GCP7
    tech-c:      GCP7
    billing-c:   GCP7
    nserver:     ns1.globo.com
    nserver:     ns2.globo.com
    status:      published
    created:     19960520 #1234
    expires:     20280520
    """
    res = parse_whois_text("globo.com.br", sample_br)
    assert res.domain == "globo.com.br"
    assert res.registrant == "Globo Comunicação e Participações S/A"
    assert len(res.name_servers) == 2
    assert "ns1.globo.com" in res.name_servers


def test_query_whois_socket_mock_server():
    # Inicia um servidor TCP mock em 127.0.0.1 porta livre
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    def _responder():
        try:
            conn, _ = server_sock.accept()
            req = conn.recv(1024)
            reply = (
                "Domain Name: MOCK.COM\n"
                "Registrar: Mock Registrar\n"
                "Creation Date: 2026-01-01\n"
                "Name Server: ns1.mock.com\n"
            )
            conn.sendall(reply.encode("utf-8"))
            conn.close()
        except Exception:
            pass

    t = threading.Thread(target=_responder, daemon=True)
    t.start()

    try:
        # Consulta com timeout curto diretamente no socket mockado
        res = query_whois_socket("mock.com", server="127.0.0.1", port=port, timeout_sec=2.0)
        assert res.domain == "mock.com"
        assert res.registrar == "Mock Registrar"
        assert res.creation_date == "2026-01-01"
        assert "ns1.mock.com" in res.name_servers
    finally:
        server_sock.close()

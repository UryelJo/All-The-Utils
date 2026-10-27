"""
Testes de validação de efeito real para network.dns_benchmark.logic.
"""
import socket
import struct
import threading
import pytest

from wintoolbox.tools.network.dns_benchmark.logic import (
    build_dns_query_packet,
    measure_single_dns_query,
    benchmark_dns_server,
)


def test_build_dns_query_packet_rfc1035_deterministic():
    # ID fixo 0xABCD
    packet = build_dns_query_packet("google.com", query_id=0xABCD)

    # 1. Header (12 bytes)
    qid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", packet[:12])
    assert qid == 0xABCD
    assert flags == 0x0100  # Recursion Desired
    assert qd == 1
    assert an == 0

    # 2. QNAME: \x06google\x03com\x00
    expected_qname = b"\x06google\x03com\x00"
    assert packet[12:12+len(expected_qname)] == expected_qname

    # 3. Footer: QTYPE=1 (A), QCLASS=1 (IN)
    footer = packet[12+len(expected_qname):]
    qtype, qclass = struct.unpack("!HH", footer)
    assert qtype == 1
    assert qclass == 1


def test_measure_single_dns_query_mock_udp_server():
    # Inicia um servidor DNS UDP simulado em 127.0.0.1
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]

    def _responder():
        try:
            data, client_addr = server_sock.recvfrom(512)
            # Monta resposta mínima de 12 bytes reutilizando o ID da consulta
            qid = struct.unpack("!H", data[:2])[0]
            resp_header = struct.pack("!HHHHHH", qid, 0x8180, 1, 1, 0, 0)
            server_sock.sendto(resp_header + data[12:], client_addr)
        except Exception:
            pass

    t = threading.Thread(target=_responder, daemon=True)
    t.start()

    # Validação do Efeito Real: cliente envia requisição UDP real e recebe resposta
    try:
        latency = measure_single_dns_query("127.0.0.1", "google.com", timeout_sec=2.0, port=port)
        assert latency is not None
        assert latency >= 0.0
    finally:
        server_sock.close()


def test_measure_single_dns_query_timeout_non_responsive():
    # Testa timeout em porta local onde ninguém está escutando
    latency = measure_single_dns_query("127.0.0.1", "invalido.local", timeout_sec=0.2)
    # Em caso de timeout deve retornar None sem levantar exceção
    assert latency is None

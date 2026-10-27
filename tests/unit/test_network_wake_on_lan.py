"""
Testes de validação de efeito real para network.wake_on_lan.logic.
"""
from pathlib import Path
import socket
import pytest

from wintoolbox.tools.network.wake_on_lan.logic import (
    create_magic_packet,
    normalize_mac_address,
    send_magic_packet,
)


def test_normalize_mac_address_deterministic():
    assert normalize_mac_address("00:11:22:33:44:55") == "00:11:22:33:44:55"
    assert normalize_mac_address("00-11-22-33-44-55") == "00:11:22:33:44:55"
    assert normalize_mac_address("0011.2233.4455") == "00:11:22:33:44:55"
    assert normalize_mac_address("aabbccddeeff") == "AA:BB:CC:DD:EE:FF"

    with pytest.raises(ValueError):
        normalize_mac_address("00:11:22")  # Muito curto

    with pytest.raises(ValueError):
        normalize_mac_address("00:11:22:33:44:55:66")  # Muito longo


def test_create_magic_packet_structure():
    mac = "AA:BB:CC:DD:EE:FF"
    packet = create_magic_packet(mac)

    # Magic packet DEVE ter exatamente 102 bytes
    assert len(packet) == 102

    # Primeiros 6 bytes devem ser 0xFF
    assert packet[:6] == b"\xff\xff\xff\xff\xff\xff"

    # Próximos 96 bytes são 16 repetições de 6 bytes
    mac_bytes = bytes.fromhex("AABBCCDDEEFF")
    assert packet[6:12] == mac_bytes
    assert packet[96:102] == mac_bytes
    assert packet[6:] == mac_bytes * 16


def test_send_magic_packet_real_udp_loopback():
    # Cria socket UDP receptor em porta temporária local
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2.0)
        port = receiver.getsockname()[1]

        target_mac = "12:34:56:78:9A:BC"
        ok, msg = send_magic_packet(target_mac, broadcast_ip="127.0.0.1", port=port)
        assert ok is True

        # Validação do Efeito Real: o socket receptor deve receber os 102 bytes reais
        data, addr = receiver.recvfrom(256)
        assert len(data) == 102
        assert data == create_magic_packet(target_mac)

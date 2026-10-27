"""
Lógica pura para Wake-on-LAN (WOL).

Constrói e transmite Magic Packets via UDP broadcast para ligar remotamente
computadores e servidores na rede local.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import json
from pathlib import Path
import re
import socket
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("network.wake_on_lan.logic")


def normalize_mac_address(mac_str: str) -> str:
    """
    Normaliza um endereço MAC para o formato padrão maiúsculo XX:XX:XX:XX:XX:XX.

    Raises:
        ValueError: se o MAC não contiver exatamente 12 dígitos hexadecimais.
    """
    clean_hex = re.sub(r"[^0-9A-Fa-f]", "", mac_str.strip())
    if len(clean_hex) != 12:
        raise ValueError(
            f"Endereço MAC inválido: '{mac_str}'. Deve conter exatamente 12 caracteres hexadecimais."
        )

    return ":".join(clean_hex[i:i+2].upper() for i in range(0, 12, 2))


def create_magic_packet(mac_address: str) -> bytes:
    """
    Monta o payload binário do Magic Packet oficial da AMD:
    6 bytes de 0xFF seguidos de 16 repetições dos 6 bytes do MAC (total: 102 bytes).
    """
    normalized = normalize_mac_address(mac_address)
    mac_bytes = bytes.fromhex(normalized.replace(":", ""))

    # 6 bytes 0xFF + 16x MAC
    return (b"\xff" * 6) + (mac_bytes * 16)


def send_magic_packet(
    mac_address: str,
    broadcast_ip: str = "255.255.255.255",
    port: int = 9
) -> Tuple[bool, str]:
    """
    Transmite o Magic Packet via socket UDP broadcast.
    """
    try:
        packet = create_magic_packet(mac_address)
    except ValueError as e:
        return (False, str(e))

    target_port = 9 if port <= 0 or port > 65535 else port
    target_ip = broadcast_ip.strip() or "255.255.255.255"

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2.0)
            sock.sendto(packet, (target_ip, target_port))

        norm_mac = normalize_mac_address(mac_address)
        return (True, f"Magic Packet enviado para {norm_mac} ({target_ip}:{target_port})")
    except Exception as e:
        _log.error(f"Erro ao transmitir pacote WOL: {e}")
        return (False, f"Falha ao enviar pacote UDP: {e}")


def get_wol_devices_file() -> Path:
    """Retorna o caminho do arquivo de persistência de dispositivos salvos."""
    app_data = Path.home() / ".wintoolbox"
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data / "wol_devices.json"


def load_saved_wol_devices() -> List[Dict[str, Any]]:
    """Carrega lista de dispositivos Wake-on-LAN salvos pelo usuário."""
    p = get_wol_devices_file()
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        _log.warning(f"Erro ao ler dispositivos WOL salvos: {e}")
        return []


def save_wol_devices(devices: List[Dict[str, Any]]) -> None:
    """Salva a lista de dispositivos Wake-on-LAN."""
    p = get_wol_devices_file()
    p.write_text(json.dumps(devices, indent=2, ensure_ascii=False), encoding="utf-8")

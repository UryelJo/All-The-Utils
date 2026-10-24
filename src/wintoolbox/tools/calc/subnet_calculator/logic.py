"""
Lógica pura de cálculo e análise de sub-redes IPv4 / CIDR.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import ipaddress
from typing import Any, Dict, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("calc.subnet_calculator")


def ip_to_binary(ip_str: str) -> str:
    """Converte um endereço IPv4 decimal com pontos para formato binário (8.8.8.8)."""
    octets = [int(x) for x in ip_str.split(".")]
    return ".".join(f"{o:08b}" for o in octets)


def calculate_subnet(ip_or_cidr: str, netmask: Optional[str] = None) -> Dict[str, Any]:
    """
    Calcula detalhadamente todos os parâmetros de uma sub-rede IPv4.
    Aceita '192.168.1.50/24' ou IP '192.168.1.50' com máscara '255.255.255.0'.
    """
    raw = ip_or_cidr.strip()
    if not raw:
        raise ValueError("O endereço IP não pode estar vazio.")

    if netmask and netmask.strip():
        full_spec = f"{raw}/{netmask.strip()}"
    else:
        full_spec = raw

    try:
        interface = ipaddress.IPv4Interface(full_spec)
        network = interface.network
    except Exception as exc:
        raise ValueError(f"Endereço IP ou máscara inválidos ({full_spec}): {exc}")

    # Wildcard Mask
    netmask_int = int(network.netmask)
    wildcard_int = 0xFFFFFFFF ^ netmask_int
    wildcard_str = str(ipaddress.IPv4Address(wildcard_int))

    # Hosts
    total_ips = network.num_addresses
    if total_ips > 2:
        first_host = str(network.network_address + 1)
        last_host = str(network.broadcast_address - 1)
        usable_hosts = total_ips - 2
    elif total_ips == 2:  # Ponto a ponto /31
        first_host = str(network.network_address)
        last_host = str(network.broadcast_address)
        usable_hosts = 2
    else:  # Host único /32
        first_host = str(network.network_address)
        last_host = str(network.network_address)
        usable_hosts = 1

    # Classe IPv4
    first_octet = int(str(interface.ip).split(".")[0])
    if 1 <= first_octet <= 126:
        ip_class = "Classe A"
    elif 128 <= first_octet <= 191:
        ip_class = "Classe B"
    elif 192 <= first_octet <= 223:
        ip_class = "Classe C"
    elif 224 <= first_octet <= 239:
        ip_class = "Classe D (Multicast)"
    else:
        ip_class = "Classe E (Experimental)"

    # Tipo
    if interface.ip.is_private:
        ip_type = "Privado (RFC 1918 - Rede Local)"
    elif interface.ip.is_loopback:
        ip_type = "Loopback (Localhost)"
    elif interface.ip.is_link_local:
        ip_type = "Link-Local (APIPA 169.254.x.x)"
    else:
        ip_type = "Público (Roteável na Internet)"

    return {
        "ip": str(interface.ip),
        "cidr_prefix": f"/{network.prefixlen}",
        "network_address": str(network.network_address),
        "netmask": str(network.netmask),
        "wildcard_mask": wildcard_str,
        "broadcast_address": str(network.broadcast_address) if network.broadcast_address else "N/A",
        "first_host": first_host,
        "last_host": last_host,
        "total_ips": total_ips,
        "usable_hosts": usable_hosts,
        "ip_class": ip_class,
        "ip_type": ip_type,
        "ip_binary": ip_to_binary(str(interface.ip)),
        "netmask_binary": ip_to_binary(str(network.netmask))
    }

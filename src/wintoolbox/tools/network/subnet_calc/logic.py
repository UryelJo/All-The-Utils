"""
Lógica pura para cálculo e planejamento visual de sub-redes IPv4 e notação CIDR.

Calcula endereços de rede, broadcast, primeiro/último host utilizável,
máscara wildcard, notação binária, classe e tipo de escopo (RFC 1918 / Público).
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from dataclasses import asdict, dataclass
import ipaddress
from typing import Any, Dict, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("network.subnet_calc.logic")


@dataclass
class SubnetDetails:
    ip: str
    prefix: int
    netmask: str
    wildcard: str
    network_ip: str
    broadcast_ip: str
    first_host: str
    last_host: str
    total_addresses: int
    usable_hosts: int
    ip_class: str
    scope_type: str
    ip_binary: str
    netmask_binary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ip_to_binary_string(ip_int: int) -> str:
    """Converte inteiro de 32 bits para string binária pontuada em 4 octetos."""
    b = f"{ip_int:032b}"
    return f"{b[0:8]}.{b[8:16]}.{b[16:24]}.{b[24:32]}"


def determine_ip_class(first_octet: int) -> str:
    """Classifica o IP de acordo com as classes tradicionais IPv4."""
    if 1 <= first_octet <= 126:
        return "Classe A"
    elif first_octet == 127:
        return "Classe A (Loopback)"
    elif 128 <= first_octet <= 191:
        return "Classe B"
    elif 192 <= first_octet <= 223:
        return "Classe C"
    elif 224 <= first_octet <= 239:
        return "Classe D (Multicast)"
    elif 240 <= first_octet <= 255:
        return "Classe E (Experimental)"
    return "Especial / Reservado"


def determine_scope_type(net: ipaddress.IPv4Network) -> str:
    """Determina o escopo do bloco de IP (Privado, Público, Loopback, Link-Local)."""
    if net.is_private:
        return "Privado (RFC 1918)"
    elif net.is_loopback:
        return "Loopback Local"
    elif net.is_link_local:
        return "Link-Local (APIPA)"
    elif net.is_multicast:
        return "Multicast"
    elif net.is_reserved:
        return "Reservado pelo IETF"
    return "Público / Internet Global"


def calculate_subnet_details(ip_str: str, prefix_or_mask: str) -> SubnetDetails:
    """
    Calcula detalhadamente todos os parâmetros de rede e sub-rede IPv4.

    Args:
        ip_str: Endereço IP em notação decimal (ex: "192.168.1.50").
        prefix_or_mask: Prefixo numérico (ex: "24", "/24") ou máscara (ex: "255.255.255.0").

    Raises:
        ValueError: caso o IP ou a máscara sejam inválidos.
    """
    clean_ip = ip_str.strip()
    clean_mask = prefix_or_mask.strip().lstrip("/")

    # Monta a string no formato CIDR "192.168.1.50/24" ou "192.168.1.50/255.255.255.0"
    cidr_input = f"{clean_ip}/{clean_mask}"

    try:
        if_net = ipaddress.IPv4Interface(cidr_input)
    except Exception as e:
        raise ValueError(f"Endereço IP ou máscara de sub-rede inválidos ('{cidr_input}'): {e}")

    ip_obj = if_net.ip
    network_obj = if_net.network
    prefix = network_obj.prefixlen
    netmask_str = str(network_obj.netmask)

    # Wildcard = complemento de 1s da máscara
    wildcard_int = int(network_obj.hostmask)
    wildcard_str = str(network_obj.hostmask)

    net_ip_str = str(network_obj.network_address)
    bcast_ip_str = str(network_obj.broadcast_address)

    total_addrs = network_obj.num_addresses

    # Hosts utilizáveis
    if prefix >= 31:
        # /31 (RFC 3021 ponto a ponto) ou /32 (host único)
        usable_count = total_addrs
        first_host = net_ip_str
        last_host = bcast_ip_str
    else:
        usable_count = total_addrs - 2
        first_host = str(network_obj.network_address + 1)
        last_host = str(network_obj.broadcast_address - 1)

    first_octet = int(ip_obj.exploded.split(".")[0])
    ip_class = determine_ip_class(first_octet)
    scope = determine_scope_type(network_obj)

    ip_bin = ip_to_binary_string(int(ip_obj))
    mask_bin = ip_to_binary_string(int(network_obj.netmask))

    return SubnetDetails(
        ip=str(ip_obj),
        prefix=prefix,
        netmask=netmask_str,
        wildcard=wildcard_str,
        network_ip=net_ip_str,
        broadcast_ip=bcast_ip_str,
        first_host=first_host,
        last_host=last_host,
        total_addresses=total_addrs,
        usable_hosts=usable_count,
        ip_class=ip_class,
        scope_type=scope,
        ip_binary=ip_bin,
        netmask_binary=mask_bin
    )

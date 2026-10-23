"""
Lógica pura da ferramenta Gerenciador de DNS e Reset de Rede.
Predefinições e comandos de configuração de pilha de rede sem acoplamento ao Qt.
"""
from typing import Dict, List, Tuple
import psutil

DNS_PRESETS: Dict[str, Tuple[str, str]] = {
    "Cloudflare (1.1.1.1 / 1.0.0.1) - Mais Rápido": ("1.1.1.1", "1.0.0.1"),
    "Google Public DNS (8.8.8.8 / 8.8.4.4)": ("8.8.8.8", "8.8.4.4"),
    "Quad9 (9.9.9.9 / 149.112.112.112) - Com Filtro de Segurança": ("9.9.9.9", "149.112.112.112"),
    "OpenDNS (208.67.222.222 / 208.67.220.220)": ("208.67.222.222", "208.67.220.220"),
    "Automático (Obter endereço DNS via DHCP)": ("dhcp", ""),
}


def get_active_interface_names() -> List[str]:
    """Retorna nomes de adaptadores de rede conectados."""
    stats = psutil.net_if_stats()
    names = []
    for name, stat in stats.items():
        if stat.isup and not name.lower().startswith("loopback"):
            names.append(name)
    return names or list(stats.keys())


def build_set_dns_command(iface: str, p1: str, p2: str = "") -> List[List[str]]:
    """Gera os comandos netsh (lista de argumentos, sem shell) para definir DNS estático ou DHCP."""
    if p1 == "dhcp":
        return [["netsh", "interface", "ip", "set", "dns", f"name={iface}", "source=dhcp"]]
    cmds = [["netsh", "interface", "ip", "set", "dns", f"name={iface}", "static", p1, "primary"]]
    if p2:
        cmds.append(["netsh", "interface", "ip", "add", "dns", f"name={iface}", p2, "index=2"])
    return cmds

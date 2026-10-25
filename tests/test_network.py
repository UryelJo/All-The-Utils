"""
Testes unitários para as ferramentas do módulo de Rede e Internet.
Validações estritas de Wi-Fi QR Code (zxing-cpp), FTP e interfaces de rede.
"""
import pytest
import zxingcpp

from wintoolbox.core.registry import get_all_tools, get_categories, get_tool
from wintoolbox.tools.network.ip_info.tool import get_local_interfaces
from wintoolbox.tools.network.wifi.logic import generate_wifi_qr_image
from wintoolbox.tools.network.wifi.tool import generate_wifi_qr_pixmap
from wintoolbox.tools.network.utilities.tool import send_wake_on_lan
from wintoolbox.tools.network.public_apis.tool import fetch_cep_info


def test_network_tools_registered():
    tools = get_all_tools()
    tool_ids = [t.id for t in tools]

    expected = [
        "network.ip_info",
        "network.diagnostics",
        "network.scanner",
        "network.wifi",
        "network.dns_manager",
        "network.http_server",
        "network.api_tester",
        "network.public_apis",
        "network.utilities",
        "network.speedtest",
        "network.ftp_client",
        "network.connections",
        "network.latency_monitor",
        "network.firewall"
    ]
    for exp_id in expected:
        assert exp_id in tool_ids, f"Ferramenta {exp_id} não foi encontrada no registro!"

    cats = get_categories()
    assert "Rede e Internet" in cats
    net_tools = cats["Rede e Internet"]
    assert len(net_tools) == len(expected)


def test_ftp_client_instantiation_and_validation():
    from wintoolbox.tools.network.ftp_client.logic import FtpOrSftpClient
    client = FtpOrSftpClient(host="ftp.exemplo.com", port=21, user="teste", password="123", protocol="FTP")
    assert client.host == "ftp.exemplo.com"
    assert client.port == 21
    assert client.protocol == "FTP"
    assert client.current_remote_dir == "/"


def test_get_local_interfaces():
    ifaces = get_local_interfaces()
    assert isinstance(ifaces, list)
    for iface in ifaces:
        assert "name" in iface
        assert "status" in iface
        assert isinstance(iface["name"], str)
        assert isinstance(iface["status"], str)


def test_generate_wifi_qr_and_payload_inspection(qapp):
    """Valida que o QR Code gerado possui o payload estrito da RFC Wi-Fi."""
    # 1. Rede WPA2 com senha
    pil_wpa = generate_wifi_qr_image(ssid="MinhaRede", password="Senha123!@#", auth_type="WPA2")
    res_wpa = zxingcpp.read_barcode(pil_wpa)
    assert res_wpa is not None
    assert res_wpa.text == "WIFI:T:WPA;S:MinhaRede;P:Senha123!@#;;"

    # 2. Rede Aberta sem senha
    pil_open = generate_wifi_qr_image(ssid="RedeLivre", password="", auth_type="Aberta")
    res_open = zxingcpp.read_barcode(pil_open)
    assert res_open is not None
    assert res_open.text == "WIFI:S:RedeLivre;T:nopass;;"

    # 3. SSID com caracteres reservados escapados
    pil_escaped = generate_wifi_qr_image(ssid="Loja;Cafe:Centro", password="123", auth_type="WPA")
    res_escaped = zxingcpp.read_barcode(pil_escaped)
    assert res_escaped is not None
    assert "Loja\\;Cafe\\:Centro" in res_escaped.text

    # 4. Geração do QPixmap para UI Qt
    pix = generate_wifi_qr_pixmap(ssid="MinhaRede", password="123", auth_type="WPA2")
    assert not pix.isNull()
    assert pix.width() == pil_wpa.width
    assert pix.height() == pil_wpa.height


def test_wake_on_lan_packet_validation():
    # Valida MACs inválidos lançando ValueError
    with pytest.raises(ValueError):
        send_wake_on_lan("00:11")  # incompleto

    with pytest.raises(ValueError):
        send_wake_on_lan("ZZ:ZZ:ZZ:ZZ:ZZ:ZZ")  # caracteres hex inválidos


def test_cep_validation():
    with pytest.raises(ValueError, match="8 dígitos"):
        fetch_cep_info("123")  # CEP incompleto

    with pytest.raises(ValueError, match="8 dígitos"):
        fetch_cep_info("1234567890")  # CEP com tamanho excessivo

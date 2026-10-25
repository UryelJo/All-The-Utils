"""
Testes unitários para as ferramentas do módulo de Rede e Internet.
"""
from wintoolbox.core.registry import get_all_tools, get_categories, get_tool
from wintoolbox.tools.network.ip_info.tool import get_local_interfaces
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
        "network.ftp_client"
    ]
    for exp_id in expected:
        assert exp_id in tool_ids, f"Ferramenta {exp_id} não foi encontrada no registro!"

def test_network_category_populated():
    cats = get_categories()
    assert "Rede e Internet" in cats
    net_tools = cats["Rede e Internet"]
    assert len(net_tools) >= 11

def test_ftp_client_instantiation():
    from wintoolbox.tools.network.ftp_client.logic import FtpOrSftpClient
    client = FtpOrSftpClient(host="ftp.exemplo.com", port=21, user="teste", password="123", protocol="FTP")
    assert client.host == "ftp.exemplo.com"
    assert client.protocol == "FTP"
    assert client.current_remote_dir == "/"

def test_get_local_interfaces():
    ifaces = get_local_interfaces()
    assert isinstance(ifaces, list)
    assert len(ifaces) > 0
    # Ao menos uma interface deve ter IP ou MAC
    first = ifaces[0]
    assert "name" in first
    assert "status" in first

def test_generate_wifi_qr_pixmap(qapp):
    pix = generate_wifi_qr_pixmap(ssid="MinhaRede", password="123", auth_type="WPA2")
    assert not pix.isNull()
    assert pix.width() > 50
    assert pix.height() > 50

def test_wake_on_lan_packet_validation():
    # Valida que MAC com tamanho incorreto levanta exceção
    import pytest
    with pytest.raises(ValueError):
        send_wake_on_lan("00:11")  # inválido

def test_cep_validation():
    import pytest
    with pytest.raises(ValueError):
        fetch_cep_info("123")  # CEP incompleto

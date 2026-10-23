"""
Testes de arquitetura e cobertura da camada de lógica desacoplada (logic.py).
Garante que todas as 55 ferramentas do All the Utils respeitam a separação estrita
entre UI (tool.py) e regras de negócio puras (logic.py).
"""
from pathlib import Path
import pytest
from wintoolbox.core.registry import get_all_tools
from wintoolbox.tools.text.transform.logic import to_camel_case, to_snake_case, to_kebab_case
from wintoolbox.tools.text.validators_br.logic import generate_valid_cpf, validate_cpf, validate_cnpj, generate_valid_cnpj
from wintoolbox.tools.encode.generators.logic import generate_ulid, generate_secure_password
from wintoolbox.tools.encode.crypto_hash.logic import compute_text_hashes
from wintoolbox.tools.encode.converter.logic import convert_epoch_to_dates
from wintoolbox.tools.files.rename.logic import compute_new_name
from wintoolbox.tools.files.duplicates.logic import format_size
from wintoolbox.tools.network.utilities.logic import send_wake_on_lan
from wintoolbox.tools.network.dns_manager.logic import DNS_PRESETS
from wintoolbox.tools.system.monitor.logic import collect_hardware_metrics


def test_all_tools_have_logic_file():
    """Valida que toda ferramenta registrada possui um logic.py desacoplado."""
    tools_dir = Path("src/wintoolbox/tools")
    tool_files = list(tools_dir.rglob("tool.py"))
    assert len(tool_files) >= 50

    missing_logic = []
    pyside_in_logic = []

    for tool_path in tool_files:
        folder = tool_path.parent
        logic_path = folder / "logic.py"
        if not logic_path.exists():
            missing_logic.append(str(folder))
        else:
            code = logic_path.read_text(encoding="utf-8")
            if "PySide6" in code or "PyQt" in code:
                pyside_in_logic.append(str(logic_path))

    assert missing_logic == [], f"Ferramentas sem logic.py: {missing_logic}"
    assert pyside_in_logic == [], f"Módulos logic.py que violam desacoplamento do Qt: {pyside_in_logic}"


def test_text_logic_pure():
    assert to_snake_case("HelloWorldTest") == "hello_world_test"
    assert to_camel_case("hello_world_test") == "helloWorldTest"
    assert to_kebab_case("helloWorld") == "hello-world"


def test_validators_br_logic_pure():
    cpf = generate_valid_cpf(formatted=False)
    assert len(cpf) == 11
    valid, msg = validate_cpf(cpf)
    assert valid is True

    valid_inv, _ = validate_cpf("12345678900")
    assert valid_inv is False

    cnpj = generate_valid_cnpj(formatted=True)
    valid_cnpj, _ = validate_cnpj(cnpj)
    assert valid_cnpj is True


def test_encode_logic_pure():
    ulid = generate_ulid()
    assert len(ulid) == 26

    pwd = generate_secure_password(length=16, use_special=True)
    assert len(pwd) == 16

    hashes = compute_text_hashes("teste de hash")
    assert "MD5" in hashes
    assert "SHA-256" in hashes
    assert len(hashes["SHA-256"]) == 64

    ts_res = convert_epoch_to_dates("1700000000")
    assert "2023" in ts_res.utc_str


def test_files_logic_pure():
    name = compute_new_name(
        original_name="arquivo_velho.txt",
        find_str="velho",
        replace_str="novo",
        prefix="PRE_",
        suffix="_POS",
        case_opt="MAIÚSCULAS",
    )
    assert name == "PRE_ARQUIVO_NOVO_POS.txt"
    assert format_size(1024 * 1024 * 5) == "5.0 MB"


def test_network_and_system_logic_pure():
    # Wake on LAN validação de MAC
    with pytest.raises(ValueError):
        send_wake_on_lan("00:INVALID_MAC")

    # DNS presets contém servidores conhecidos
    assert any("Google" in k for k in DNS_PRESETS.keys())
    assert any("Cloudflare" in k for k in DNS_PRESETS.keys())

    # Métricas de hardware
    metrics = collect_hardware_metrics()
    assert metrics.cpu_percent >= 0.0
    assert metrics.mem_total_gb > 0.0

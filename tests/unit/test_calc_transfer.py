"""
Testes unitários para o estimador de tempo de transferência e download.
Diretrizes Anti-Gambiarra: Validação determinística de conversão de grandezas binárias/decimais.
"""
from wintoolbox.tools.calc.transfer.logic import (
    calculate_transfer_time,
    size_to_bytes,
    speed_to_bps,
)


def test_size_to_bytes():
    assert size_to_bytes(1.0, "B") == 1.0
    assert size_to_bytes(1.0, "KB") == 1024.0
    assert size_to_bytes(1.0, "MB") == 1048576.0
    assert size_to_bytes(1.0, "GB") == 1073741824.0


def test_speed_to_bps():
    # Telecom: 1 Mbps = 1.000.000 bps
    assert speed_to_bps(1.0, "Mbps") == 1_000_000.0
    assert speed_to_bps(1.0, "Gbps") == 1_000_000_000.0
    # Bytes: 1 MB/s = 8 * 1024^2 = 8.388.608 bps
    assert speed_to_bps(1.0, "MB/s") == 8.0 * (1024.0 ** 2)


def test_calculate_transfer_time():
    # 100 MB com velocidade de 100 MB/s e 0% de overhead -> exatamente 1 segundo
    res = calculate_transfer_time(
        file_size_val=100.0,
        size_unit="MB",
        speed_val=100.0,
        speed_unit="MB/s",
        overhead_pct=0.0
    )
    assert res["segundos"] == 1.0
    assert "1 seg" in res["tempo_formatado"]
    assert res["tamanho_mb"] == 100.0

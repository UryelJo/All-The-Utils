"""
Testes de validação de efeito real para network.bandwidth_monitor.logic.
"""
import pytest
from wintoolbox.tools.network.bandwidth_monitor.logic import (
    NetworkSnapshot,
    BandwidthRate,
    format_bandwidth_speed,
    format_total_bytes,
    calculate_bandwidth_rate,
    take_network_snapshot,
    get_available_interfaces,
)


def test_format_bandwidth_speed_deterministic():
    assert format_bandwidth_speed(500.0) == "500.0 B/s"
    assert format_bandwidth_speed(1024.0 * 2.5) == "2.5 KB/s"
    assert format_bandwidth_speed(1024.0 * 1024.0 * 10.0) == "10.00 MB/s"
    assert format_bandwidth_speed(1024.0 * 1024.0 * 1024.0 * 1.5) == "1.50 GB/s"
    assert format_bandwidth_speed(-5.0) == "0.0 B/s"


def test_format_total_bytes_deterministic():
    assert format_total_bytes(500) == "500 B"
    assert format_total_bytes(1024 * 50) == "50.0 KB"
    assert format_total_bytes(1024 * 1024 * 150) == "150.00 MB"


def test_calculate_bandwidth_rate_deterministic():
    t0 = 1000.0
    snap0 = NetworkSnapshot(bytes_recv=10000, bytes_sent=5000, timestamp=t0)

    t1 = 1002.0  # delta = 2.0s
    snap1 = NetworkSnapshot(bytes_recv=14000, bytes_sent=9000, timestamp=t1)

    # (14000 - 10000) / 2.0 = 2000.0 bytes/s download
    # (9000 - 5000) / 2.0 = 2000.0 bytes/s upload
    rate = calculate_bandwidth_rate(snap0, snap1)
    assert rate.delta_seconds == 2.0
    assert rate.download_bytes_per_sec == 2000.0
    assert rate.upload_bytes_per_sec == 2000.0
    assert "KB/s" in rate.download_display

    # Delta zero ou negativo não divide por zero
    rate_zero = calculate_bandwidth_rate(snap1, snap1)
    assert rate_zero.download_bytes_per_sec == 0.0
    assert rate_zero.upload_bytes_per_sec == 0.0


def test_take_network_snapshot_real_system():
    snap = take_network_snapshot()
    assert isinstance(snap, NetworkSnapshot)
    assert snap.bytes_recv >= 0
    assert snap.bytes_sent >= 0
    assert snap.timestamp > 0

    ifaces = get_available_interfaces()
    assert isinstance(ifaces, list)

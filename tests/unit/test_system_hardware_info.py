"""
Testes de validação de efeito real para system.hardware_info.logic.
"""
import pytest
from unittest.mock import patch, MagicMock

from wintoolbox.tools.system.hardware_info.logic import (
    parse_cpu_data,
    parse_ram_slots_data,
    parse_gpu_data,
    parse_motherboard_data,
    parse_bios_data,
    parse_battery_data,
    HardwareInventory,
    query_hardware_inventory,
)


def test_parse_cpu_data_deterministic():
    raw = {
        "Name": "AMD Ryzen 7 5800X 8-Core Processor",
        "NumberOfCores": 8,
        "NumberOfLogicalProcessors": 16,
        "MaxClockSpeed": 3800,
        "Manufacturer": "AuthenticAMD",
        "Architecture": 9
    }
    cpu = parse_cpu_data(raw)
    assert cpu.name == "AMD Ryzen 7 5800X 8-Core Processor"
    assert cpu.cores == 8
    assert cpu.logical_processors == 16
    assert cpu.max_clock_mhz == 3800
    assert cpu.manufacturer == "AuthenticAMD"
    assert cpu.architecture == "x64 (64-bit)"


def test_parse_ram_slots_data_capacity_and_speed():
    raw_slots = [
        {
            "BankLabel": "BANK 0",
            "Capacity": 17179869184,  # 16 GB exatos (16 * 1024^3)
            "Speed": 3600,
            "Manufacturer": "Corsair",
            "PartNumber": "CMK32GX4M2D3600C18",
            "DeviceLocator": "DIMM 0"
        },
        {
            "BankLabel": "BANK 1",
            "Capacity": 8589934592,   # 8 GB exatos (8 * 1024^3)
            "Speed": 3200,
            "Manufacturer": "Kingston",
            "PartNumber": "KF432C16BB/8",
            "DeviceLocator": "DIMM 1"
        }
    ]
    slots = parse_ram_slots_data(raw_slots)
    assert len(slots) == 2
    assert slots[0].capacity_gb == 16.0
    assert slots[0].speed_mhz == 3600
    assert slots[0].manufacturer == "Corsair"

    assert slots[1].capacity_gb == 8.0
    assert slots[1].speed_mhz == 3200


def test_parse_battery_health_and_status():
    raw_bat = {
        "EstimatedChargeRemaining": 85,
        "BatteryStatus": 2,  # Carregando
        "DesignCapacity": 60000,
        "FullChargeCapacity": 54000,
        "CycleCount": 142
    }
    bat = parse_battery_data(raw_bat)
    assert bat.present is True
    assert bat.estimated_charge_percent == 85
    assert bat.status == "Conectada (Carregando)"
    # Saúde esperada: (54000 / 60000) * 100 = 90.0%
    assert bat.health_percent == 90.0
    assert bat.cycle_count == 142

    # Caso sem bateria (Desktop)
    no_bat = parse_battery_data(None)
    assert no_bat.present is False
    assert no_bat.status == "Não detectada"


def test_hardware_inventory_total_ram_and_dict():
    raw_cpu = {"Name": "Intel Core i5", "NumberOfCores": 4, "NumberOfLogicalProcessors": 4}
    cpu = parse_cpu_data(raw_cpu)
    slots = parse_ram_slots_data([{"Capacity": 8589934592}, {"Capacity": 8589934592}])
    inv = HardwareInventory(cpu=cpu, ram_slots=slots)

    assert inv.total_ram_gb == 16.0
    d = inv.to_dict()
    assert d["cpu"]["name"] == "Intel Core i5"
    assert len(d["ram_slots"]) == 2


def test_query_hardware_inventory_real_or_fallback():
    # Executa a chamada real no sistema operacional do usuário
    inv = query_hardware_inventory()
    assert inv is not None
    assert inv.cpu.cores >= 1
    assert isinstance(inv.ram_slots, list)

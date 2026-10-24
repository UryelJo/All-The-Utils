"""
Testes unitários para as ferramentas de cálculo (Fase 11).
"""
import datetime
import pytest

from wintoolbox.tools.calc.unit_converter.logic import (
    convert_units, get_categories, get_units_for_category
)
from wintoolbox.tools.calc.date_calculator.logic import (
    add_business_days, diff_dates, get_brazilian_holidays
)
from wintoolbox.tools.calc.finance.logic import (
    calculate_compound_interest, calculate_financing, calculate_margin_and_markup
)
from wintoolbox.tools.calc.subnet_calculator.logic import calculate_subnet
from wintoolbox.tools.calc.world_clock.logic import (
    convert_time_between_zones, get_all_world_clocks, get_available_timezones
)


class TestUnitConverter:
    def test_length_conversion(self):
        result = convert_units(1000.0, "Comprimento", "Metro (m)", "Quilômetro (km)")
        assert result == pytest.approx(1.0)

    def test_temperature_celsius_to_fahrenheit(self):
        result = convert_units(100.0, "Temperatura", "Graus Celsius (°C)", "Graus Fahrenheit (°F)")
        assert result == pytest.approx(212.0)

    def test_temperature_kelvin_to_celsius(self):
        result = convert_units(273.15, "Temperatura", "Kelvin (K)", "Graus Celsius (°C)")
        assert result == pytest.approx(0.0)

    def test_data_storage_gigabytes_to_megabytes(self):
        result = convert_units(2.0, "Dados Digitais", "Gibibyte (GiB - 1024 MiB)", "Mebibyte (MiB - 1024 KiB)")
        assert result == pytest.approx(2048.0)

    def test_mass_kilograms_to_pounds(self):
        result = convert_units(1.0, "Massa e Peso", "Quilograma (kg)", "Libra (lb)")
        assert result == pytest.approx(2.20462, rel=1e-3)

    def test_categories_list(self):
        cats = get_categories()
        assert "Comprimento" in cats
        assert "Temperatura" in cats
        assert "Dados Digitais" in cats
        assert "Massa e Peso" in cats


class TestDateCalculator:
    def test_date_difference(self):
        d1 = datetime.date(2026, 1, 1)
        d2 = datetime.date(2026, 1, 11)
        diff = diff_dates(d1, d2)
        assert diff["total_days"] == 10
        assert diff["weeks"] == 1
        assert diff["remaining_days"] == 3

    def test_brazilian_holidays(self):
        holidays_2026 = get_brazilian_holidays(2026)
        holiday_names = list(holidays_2026.values())
        assert "Confraternização Universal" in holiday_names
        assert "Independência do Brasil" in holiday_names
        assert "Natal" in holiday_names
        # Feriado nacional recente da Consciência Negra
        assert "Dia Nacional de Zumbi e da Consciência Negra" in holiday_names

    def test_add_business_days(self):
        # Sexta-feira: 2026-05-08 -> +1 dia útil cai na Segunda-feira 2026-05-11
        start = datetime.date(2026, 5, 8)
        end = add_business_days(start, 1)
        assert end == datetime.date(2026, 5, 11)


class TestFinanceCalculator:
    def test_compound_interest(self):
        res = calculate_compound_interest(
            initial_amount=1000.0,
            monthly_deposit=100.0,
            annual_rate_percent=12.0,
            total_months=12
        )
        assert res["total_invested"] == 2200.0
        assert res["final_balance"] > 2200.0
        assert res["total_interest"] > 0
        assert len(res["history"]) >= 1

    def test_loan_price(self):
        res = calculate_financing(loan_amount=10000.0, annual_interest_rate=12.0, total_months=12, system="PRICE")
        assert res["first_payment"] > 0
        assert res["total_paid"] > 10000.0
        assert len(res["schedule"]) >= 1
        # Na última parcela o saldo devedor deve estar próximo de zero
        assert res["schedule"][-1]["balance"] == pytest.approx(0.0, abs=1.0)

    def test_loan_sac(self):
        res = calculate_financing(loan_amount=12000.0, annual_interest_rate=12.0, total_months=12, system="SAC")
        assert len(res["schedule"]) >= 1
        # No SAC a amortização é constante: 12000 / 12 = 1000
        assert res["schedule"][0]["amortization"] == pytest.approx(1000.0)
        # Primeira parcela é maior que a última
        assert res["first_payment"] > res["last_payment"]

    def test_margin_and_markup(self):
        res = calculate_margin_and_markup(cost_price=100.0, sell_price=125.0)
        assert res["profit"] == pytest.approx(25.0)
        assert res["markup_percent"] == pytest.approx(25.0)
        assert res["margin_percent"] == pytest.approx(20.0)


class TestSubnetCalculator:
    def test_ipv4_cidr_calculation(self):
        net = calculate_subnet("192.168.1.100/24")
        assert net["network_address"] == "192.168.1.0"
        assert net["broadcast_address"] == "192.168.1.255"
        assert net["netmask"] == "255.255.255.0"
        assert net["usable_hosts"] == 254
        assert net["first_host"] == "192.168.1.1"
        assert net["last_host"] == "192.168.1.254"
        assert "Privado" in net["ip_type"]

    def test_ipv4_with_mask_string(self):
        net = calculate_subnet("10.0.0.5", "255.255.255.240")
        assert net["cidr_prefix"] == "/28"
        assert net["usable_hosts"] == 14
        assert net["network_address"] == "10.0.0.0"

    def test_invalid_ip_raises_value_error(self):
        with pytest.raises(ValueError):
            calculate_subnet("999.999.999.999/24")


class TestWorldClock:
    def test_get_world_times(self):
        times = get_all_world_clocks()
        assert len(times) >= 5
        cities = [t["city"] for t in times]
        assert any("São Paulo" in c for c in cities)
        assert any("Nova York" in c for c in cities)
        assert any("Tóquio" in c for c in cities)

    def test_convert_time_between_zones(self):
        dt = datetime.datetime(2026, 6, 15, 12, 0, 0)
        res = convert_time_between_zones(dt, "Europe/London", "Asia/Tokyo")
        assert "target_str" in res
        assert "Asia/Tokyo" in res["target_dt"] or "target_abbr" in res
        assert res["target_offset"] == "UTC+09:00"

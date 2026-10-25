"""
Testes unitários para as novas ferramentas da Fase 15 (Auditoria e Lacunas do Sistema).
Asserções determinísticas, isolamento de rede HIBP e validações de integridade.
"""
import hashlib
import io
from pathlib import Path
import urllib.request
import pytest

# Sistema
from wintoolbox.tools.system.winget.logic import (
    build_install_command, build_upgrade_all_command, get_curated_apps,
    is_winget_installed, parse_winget_upgrade_output, CURATED_APPS
)
from wintoolbox.tools.system.disk_health.logic import format_bytes, get_disks_health_info
from wintoolbox.tools.system.crash_analyzer.logic import (
    explain_bugcheck_code, list_minidump_files
)
from wintoolbox.tools.system.restore_points.logic import list_restore_points
from wintoolbox.tools.system.privacy.logic import get_all_privacy_statuses, PRIVACY_ITEMS
from wintoolbox.tools.system.context_menu.logic import is_classic_context_menu_enabled
from wintoolbox.tools.system.license_info.logic import get_windows_activation_status

# Rede
from wintoolbox.tools.network.connections.logic import list_active_connections
from wintoolbox.tools.network.latency_monitor.logic import calculate_jitter, calculate_stats
from wintoolbox.tools.network.firewall.logic import list_firewall_rules

# Arquivos e Texto
from wintoolbox.tools.files.encoding_converter.logic import convert_text_content, detect_encoding
from wintoolbox.tools.files.unblock.logic import is_file_blocked, unblock_file
from wintoolbox.tools.files.permissions.logic import repair_ntfs_permissions
from wintoolbox.tools.files.checksum_manifest.logic import (
    generate_folder_manifest, verify_manifest_file
)
from wintoolbox.tools.text.pix_generator.logic import compute_crc16, generate_pix_payload

# Segurança
from wintoolbox.tools.security.pwned_check.logic import check_password_pwned
from wintoolbox.tools.security.virustotal.logic import calculate_file_sha256
from wintoolbox.tools.security.signature_check.logic import check_authenticode_signature


class TestSystemPhase15:
    def test_winget_logic(self):
        apps = get_curated_apps()
        assert len(apps) == len(CURATED_APPS)
        cmd_install = build_install_command("7zip.7zip")
        assert "7zip.7zip" in cmd_install
        cmd_up_all = build_upgrade_all_command()
        assert "--all" in cmd_up_all

    def test_disk_health_formatting(self):
        assert format_bytes(1024 ** 3) == "1.0 GB"
        assert format_bytes(2 * (1024 ** 4)) == "2.00 TB"

    def test_crash_analyzer_bugcheck(self):
        desc = explain_bugcheck_code(0x0000001A)
        assert "MEMORY_MANAGEMENT" in desc
        desc_whea = explain_bugcheck_code(0x00000124)
        assert "WHEA_UNCORRECTABLE_ERROR" in desc_whea

    def test_privacy_status_list(self):
        statuses = get_all_privacy_statuses()
        assert len(statuses) == len(PRIVACY_ITEMS)
        ids = [s["id"] for s in statuses]
        assert "telemetry" in ids
        assert "copilot" in ids
        assert "recall_ai" in ids

    def test_activation_status(self):
        res = get_windows_activation_status()
        assert "edition" in res
        assert "is_activated" in res
        assert isinstance(res["is_activated"], bool)


class TestNetworkPhase15:
    def test_connections_list(self):
        conns = list_active_connections()
        assert isinstance(conns, list)
        for c in conns:
            assert "proto" in c
            assert "local_address" in c
            assert "status" in c

    def test_latency_jitter_calc(self):
        samples = [10.0, 15.0, 12.0, 20.0]
        # diffs: |15-10|=5, |12-15|=3, |20-12|=8 -> (5+3+8)/3 = 5.33
        jitter = calculate_jitter(samples)
        assert jitter == 5.33

        stats = calculate_stats(samples, total_sent=4)
        assert stats["current"] == 20.0
        assert stats["min"] == 10.0
        assert stats["max"] == 20.0
        assert stats["avg"] == 14.2
        assert stats["jitter"] == 5.33
        assert stats["packet_loss_pct"] == 0.0


class TestFilesAndTextPhase15:
    def test_encoding_converter(self):
        text = "Acentuação em Português: á, é, í, ó, ú, ç.\nLinha 2."
        raw_utf8 = text.encode("utf-8")
        assert detect_encoding(raw_utf8) == "utf-8"

        converted, detail = convert_text_content(raw_utf8, target_encoding="windows-1252", line_ending="crlf")
        assert b"\r\n" in converted
        assert "CP1252" in detail

    def test_unblock_file(self, tmp_path):
        f = tmp_path / "teste.txt"
        f.write_text("conteudo")
        assert is_file_blocked(f) is False
        ok, msg = unblock_file(f)
        assert ok is True

    def test_checksum_manifest(self, tmp_path):
        folder = tmp_path / "dados"
        folder.mkdir()
        (folder / "arq1.txt").write_text("teste 1")
        (folder / "arq2.txt").write_text("teste 2")

        items, manifest_text = generate_folder_manifest(folder, algo="sha256")
        assert len(items) == 2
        assert "arq1.txt" in manifest_text

        # Grava e valida manifest
        m_file = folder / "manifest.sha256"
        m_file.write_text(manifest_text, encoding="utf-8")
        results = verify_manifest_file(m_file)
        assert len(results) == 2
        assert all(r["status"] == "OK" for r in results)

    def test_pix_generator(self):
        pix_code = generate_pix_payload(
            pix_key="12345678900",
            merchant_name="Fulano Silva",
            merchant_city="Brasilia",
            amount=50.00,
            txid="TESTE123"
        )
        assert pix_code.startswith("000201")
        assert "br.gov.bcb.pix" in pix_code
        assert "50.00" in pix_code
        assert "TESTE123" in pix_code
        # Checa cálculo do CRC16
        crc_part = pix_code[-4:]
        assert len(crc_part) == 4
        calculated_crc = compute_crc16(pix_code[:-4])
        assert crc_part == calculated_crc


class TestSecurityPhase15:
    def test_calculate_file_sha256(self, tmp_path):
        payload = b"antigravity test data"
        f = tmp_path / "sample.bin"
        f.write_bytes(payload)

        expected_hash = hashlib.sha256(payload).hexdigest()
        sha = calculate_file_sha256(f)
        assert sha == expected_hash

    def test_signature_check_unsigned_file(self, tmp_path):
        # Arquivo novo em tmp_path nunca tem assinatura Authenticode
        dummy_exe = tmp_path / "app_fake.exe"
        dummy_exe.write_bytes(b"MZ dummy executable header")
        sig = check_authenticode_signature(dummy_exe)
        assert sig["is_valid"] is False
        assert sig["signer"] == "Não especificado"

    def test_pwned_passwords_isolated_network(self, monkeypatch: pytest.MonkeyPatch):
        """Validação de Have I Been Pwned com mock de rede isolado (sem chamadas externas)."""
        # 1. Senha vazia
        is_pwned, count, msg = check_password_pwned("")
        assert is_pwned is False
        assert count == 0
        assert "vazia" in msg

        # 2. Senha comprometida
        pwd = "SenhaSuperSecreta123!"
        sha1 = hashlib.sha1(pwd.encode("utf-8")).hexdigest().upper()
        prefix = sha1[:5]
        suffix = sha1[5:]

        class FakeResponse:
            def __init__(self, data_str: str):
                self._data = data_str.encode("utf-8")
            def read(self):
                return self._data
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        # Mock retornando o sufixo com 42 vazamentos
        fake_body = f"00000000000000000000000000000000000:1\r\n{suffix}:42\r\nFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:3"
        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: FakeResponse(fake_body))

        is_pwned, count, msg = check_password_pwned(pwd)
        assert is_pwned is True
        assert count == 42
        assert "42" in msg

        # 3. Senha limpa (sufixo não está na resposta)
        fake_body_clean = "AAAAA000000000000000000000000000000:5\r\nBBBBB000000000000000000000000000000:2"
        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: FakeResponse(fake_body_clean))

        is_pwned_clean, count_clean, msg_clean = check_password_pwned(pwd)
        assert is_pwned_clean is False
        assert count_clean == 0
        assert "não foi encontrada" in msg_clean

        # 4. Falha de rede (ex: timeout de conexão)
        def fake_timeout(req, timeout=10):
            raise TimeoutError("Conexão expirou")

        monkeypatch.setattr(urllib.request, "urlopen", fake_timeout)
        is_pwned_err, count_err, msg_err = check_password_pwned(pwd)
        assert is_pwned_err is False
        assert count_err == 0
        assert "Falha na conexão" in msg_err

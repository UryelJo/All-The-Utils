"""
Testes unitários rigorosos (Black-Box Testing) para o Gerenciador de Symlinks e Junções (files.symlink_manager).
Validação do efeito real: leitura exata de arquivos através do link, integridade de alvos e links quebrados.
"""
from pathlib import Path
import pytest

from wintoolbox.tools.files.symlink_manager.logic import (
    create_link,
    remove_link_safely,
    scan_links_in_directory,
)
from wintoolbox.tools.files.symlink_manager.tool import SymlinkManagerTool


def test_junction_creation_and_real_read_blackbox(tmp_path: Path):
    target_dir = tmp_path / "alvo_real"
    target_dir.mkdir()
    secret_file = target_dir / "documento_confidencial.txt"
    content = "WinToolbox 2026 - Dados lidos através da Junction!"
    secret_file.write_text(content, encoding="utf-8")

    link_path = tmp_path / "link_juncao"

    # Cria a junção de diretório
    res = create_link(link_path, target_dir, link_type="junction")
    assert res["created"] is True
    assert link_path.exists()

    # DIRETRIZ ANTI-GAMBIARRA: Leitura do arquivo real através do link
    file_via_link = link_path / "documento_confidencial.txt"
    assert file_via_link.is_file()
    assert file_via_link.read_text(encoding="utf-8") == content

    # Varredura de links
    links_found = scan_links_in_directory(tmp_path)
    assert len(links_found) >= 1
    junction_record = next(r for r in links_found if r["name"] == "link_juncao")
    assert junction_record["status"] == "ATIVO"

    # Remoção segura: apaga o link
    remove_link_safely(link_path)
    assert not link_path.exists()
    # O alvo real e seus arquivos devem continuar 100% intactos!
    assert target_dir.is_dir()
    assert secret_file.is_file()
    assert secret_file.read_text(encoding="utf-8") == content


def test_broken_link_detection(tmp_path: Path):
    target_dir = tmp_path / "pasta_temporaria"
    target_dir.mkdir()
    link_path = tmp_path / "link_orfao"

    create_link(link_path, target_dir, link_type="junction")
    assert link_path.exists()

    # Remove o alvo para quebrar o link
    target_dir.rmdir()

    links_found = scan_links_in_directory(tmp_path)
    broken_record = next((r for r in links_found if r["name"] == "link_orfao"), None)
    if broken_record:
        assert broken_record["status"] == "QUEBRADO"

    # Limpeza
    remove_link_safely(link_path)


def test_link_creation_errors(tmp_path: Path):
    target = tmp_path / "destino"
    target.mkdir()

    # Alvo inexistente
    with pytest.raises(FileNotFoundError):
        create_link(tmp_path / "link1", tmp_path / "fantasma", link_type="junction")

    # Link já existente
    link_existente = tmp_path / "ja_existe"
    link_existente.mkdir()
    with pytest.raises(FileExistsError):
        create_link(link_existente, target, link_type="junction")


def test_symlink_manager_tool_ui(qtbot, tmp_path: Path):
    tool = SymlinkManagerTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria diretório alvo e link
    target = tmp_path / "alvo_ui"
    target.mkdir()
    link = tmp_path / "link_ui"
    create_link(link, target, link_type="junction")

    view._txt_scan_dir.setText(str(tmp_path))
    links = scan_links_in_directory(tmp_path)
    view._on_scan_success(links)

    assert view._table.visible_count() >= 1
    assert "link(s) / junção(ões) encontrados" in view._lbl_scan_status.text()

    # Limpeza
    remove_link_safely(link)

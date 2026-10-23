"""
Testes unitários das 7 ferramentas da Fase 6 (Arquivos Avançados e Organização Inteligente).
Testa lógicas puras de organização, pesquisa, sincronização, criptografia, timestamp, watcher e backup.
"""
from pathlib import Path
import time
import pytest
import zipfile

from wintoolbox.tools.files.auto_organize.logic import (
    plan_organization,
    execute_organization,
    get_category_for_extension,
)
from wintoolbox.tools.files.search.logic import search_files
from wintoolbox.tools.files.sync.logic import compare_directories, execute_sync
from wintoolbox.tools.files.encrypt.logic import encrypt_file, decrypt_file, is_wintoolbox_encrypted
from wintoolbox.tools.files.timestamp_editor.logic import (
    get_file_timestamps,
    set_file_timestamps,
    batch_update_timestamps,
)
from wintoolbox.tools.files.folder_watcher.logic import (
    take_directory_snapshot,
    compute_snapshot_diff,
)
from wintoolbox.tools.files.backup.logic import run_incremental_backup


def test_auto_organize_logic(tmp_path: Path):
    # Cria arquivos simulados
    f_img = tmp_path / "foto.png"
    f_doc = tmp_path / "manual.pdf"
    f_code = tmp_path / "script.py"
    f_img.write_text("fake image", encoding="utf-8")
    f_doc.write_text("fake doc", encoding="utf-8")
    f_code.write_text("fake code", encoding="utf-8")

    assert get_category_for_extension(".png") == "Imagens"
    assert get_category_for_extension(".pdf") == "Documentos"
    assert get_category_for_extension(".py") == "Código"

    # Simulação por categoria
    actions = plan_organization(tmp_path, mode="category")
    assert len(actions) == 3

    # Execução (copiar)
    succ, fail = execute_organization(actions, move_files=False)
    assert succ == 3
    assert fail == 0
    assert (tmp_path / "Imagens" / "foto.png").exists()
    assert (tmp_path / "Documentos" / "manual.pdf").exists()


def test_search_files_logic(tmp_path: Path):
    f1 = tmp_path / "relatorio_financeiro.txt"
    f2 = tmp_path / "notas.txt"
    f1.write_text("Conteúdo confidencial com palavra CHAVE_SECRETA aqui.", encoding="utf-8")
    f2.write_text("Apenas notas comuns.", encoding="utf-8")

    # Busca por nome com wildcard
    res_name = search_files(tmp_path, name_pattern="*financeiro*")
    assert len(res_name) == 1
    assert res_name[0].name == "relatorio_financeiro.txt"

    # Busca por texto interno
    res_text = search_files(tmp_path, content_query="CHAVE_SECRETA")
    assert len(res_text) == 1
    assert "CHAVE_SECRETA" in (res_text[0].matched_snippet or "")


def test_sync_directories_logic(tmp_path: Path):
    dir_a = tmp_path / "origem"
    dir_b = tmp_path / "destino"
    dir_a.mkdir()
    dir_b.mkdir()

    (dir_a / "comum.txt").write_text("v1", encoding="utf-8")
    (dir_a / "novo_em_a.txt").write_text("novo", encoding="utf-8")
    (dir_b / "comum.txt").write_text("v1", encoding="utf-8")
    (dir_b / "orfao_em_b.txt").write_text("orfao", encoding="utf-8")

    # Comparação no modo mirror
    diffs = compare_directories(dir_a, dir_b, mode="mirror")
    actions = {d.rel_path.name: d.action_type for d in diffs}
    assert actions.get("novo_em_a.txt") == "copy_to_dst"
    assert actions.get("orfao_em_b.txt") == "delete_dst"

    # Execução do sync
    succ, fail = execute_sync(diffs)
    assert succ >= 2
    assert (dir_b / "novo_em_a.txt").exists()
    assert not (dir_b / "orfao_em_b.txt").exists()


def test_encrypt_decrypt_aes(tmp_path: Path):
    plain_file = tmp_path / "segredo.txt"
    enc_file = tmp_path / "segredo.txt.wtx_enc"
    dec_file = tmp_path / "restaurado.txt"

    original_content = "Texto super secreto que precisa de AES-256 militar!"
    plain_file.write_text(original_content, encoding="utf-8")

    # Criptografa
    encrypt_file(plain_file, enc_file, password="SenhaSuperSegura123!")
    assert enc_file.exists()
    assert is_wintoolbox_encrypted(enc_file) is True

    # Falha esperada com senha incorreta
    with pytest.raises(ValueError):
        decrypt_file(enc_file, dec_file, password="SenhaInvalidaErrada!")

    # Descriptografa com sucesso
    decrypt_file(enc_file, dec_file, password="SenhaSuperSegura123!")
    assert dec_file.exists()
    assert dec_file.read_text(encoding="utf-8") == original_content


def test_timestamp_editor_logic(tmp_path: Path):
    target = tmp_path / "documento.txt"
    target.write_text("teste de timestamp", encoding="utf-8")

    ts_antigo = 1500000000.0  # Julho de 2017
    res = set_file_timestamps(target, ctime=ts_antigo, mtime=ts_antigo, atime=ts_antigo)
    assert res is True

    curr = get_file_timestamps(target)
    assert abs(curr.mtime - ts_antigo) < 5.0

    # Teste em lote
    batch_res = batch_update_timestamps([target], offset_seconds=3600.0)
    assert len(batch_res) == 1
    assert batch_res[0].success is True


def test_folder_watcher_logic(tmp_path: Path):
    f1 = tmp_path / "arquivo1.txt"
    f1.write_text("conteúdo 1", encoding="utf-8")

    snap1 = take_directory_snapshot(tmp_path)
    assert f1 in snap1

    # Cria f2 e altera f1
    time.sleep(0.05)
    f2 = tmp_path / "arquivo2.txt"
    f2.write_text("conteúdo 2", encoding="utf-8")
    f1.write_text("conteúdo 1 modificado", encoding="utf-8")

    snap2 = take_directory_snapshot(tmp_path)
    diffs = compute_snapshot_diff(snap1, snap2)

    ev_types = [d.event_type for d in diffs]
    assert "Criado" in ev_types


def test_backup_logic(tmp_path: Path):
    src = tmp_path / "dados"
    dst = tmp_path / "destinos"
    src.mkdir()
    dst.mkdir()

    (src / "arquivo_a.txt").write_text("conteudo a", encoding="utf-8")
    (src / "subpasta").mkdir()
    (src / "subpasta" / "arquivo_b.txt").write_text("conteudo b", encoding="utf-8")

    # 1. Backup para pasta espelhada incremental
    rep_folder = run_incremental_backup(src, dst, backup_mode="folder")
    assert rep_folder.files_copied == 2
    assert (dst / "dados" / "arquivo_a.txt").exists()
    assert (dst / "dados" / "subpasta" / "arquivo_b.txt").exists()

    # Segundo backup imediato: nada alterado, deve pular
    rep_second = run_incremental_backup(src, dst, backup_mode="folder")
    assert rep_second.files_copied == 0
    assert rep_second.files_skipped == 2

    # 2. Backup para arquivo ZIP
    rep_zip = run_incremental_backup(src, dst, backup_mode="zip")
    assert rep_zip.files_copied == 2
    assert rep_zip.target_path.exists()
    assert zipfile.is_zipfile(rep_zip.target_path)

"""
Testes automatizados da Fase 2: Ferramentas de Arquivos e Compactação.
Valida o registro, divisão/junção, renomeação, duplicados, shredder e compactação ZIP/TAR.
"""
import os
import hashlib
from pathlib import Path
import pytest

import wintoolbox.tools.files
import wintoolbox.tools.archive

from wintoolbox.core.registry import get_tool
from wintoolbox.tools.files.rename.tool import compute_new_name
from wintoolbox.tools.files.split_merge.tool import split_file, merge_files
from wintoolbox.tools.files.duplicates.tool import scan_duplicates
from wintoolbox.tools.files.shredder.tool import shred_single_file
from wintoolbox.tools.archive.manager.tool import compress_items, extract_archive, inspect_archive


def test_registry_phase_2_tools():
    """Valida se todas as 7 ferramentas da Fase 2 estão registradas no catálogo."""
    tool_ids = [
        "files.rename",
        "files.duplicates",
        "files.disk_usage",
        "files.shredder",
        "files.split_merge",
        "files.lock_checker",
        "archive.manager",
    ]
    from wintoolbox.core.registry import Tool
    for tid in tool_ids:
        tool = get_tool(tid)
        assert isinstance(tool, Tool), f"Ferramenta {tid} não foi registrada no sistema."
        assert len(tool.name) > 0
        assert tool.category in ["Arquivos e Pastas", "Compactação"]


def test_compute_new_name_rules():
    """Testa as regras de renomeação em lote de arquivos."""
    # 1. Prefixo e Sufixo
    res1 = compute_new_name("documento.pdf", prefix="relatorio_", suffix="_final")
    assert res1 == "relatorio_documento_final.pdf"

    # 2. Localizar e substituir normal
    res2 = compute_new_name("foto_2024_viagem.jpg", find_str="2024", replace_str="2026")
    assert res2 == "foto_2026_viagem.jpg"

    # 3. Localizar e substituir com Regex
    res3 = compute_new_name("item_0042_teste.txt", find_str=r"\d+", replace_str="num", is_regex=True)
    assert res3 == "item_num_teste.txt"

    # 4. Numeração sequencial com dígitos
    res4 = compute_new_name("imagem.png", index=2, add_number=True, start_num=10, digits=4)
    assert res4 == "imagem_0012.png"

    # 5. Alteração de caixa
    assert compute_new_name("meu arquivo.txt", case_opt="MAIÚSCULAS") == "MEU ARQUIVO.txt"
    assert compute_new_name("MEU ARQUIVO.txt", case_opt="minúsculas") == "meu arquivo.txt"
    assert compute_new_name("meu arquivo.txt", case_opt="Primeira Maiúscula") == "Meu Arquivo.txt"


def test_split_and_merge_files(tmp_path: Path):
    """Testa a divisão de arquivos volumosos em partes e reconstrução com integridade byte a byte."""
    # Gera arquivo de teste com 500 KB de dados binários pseudoaleatórios
    orig_file = tmp_path / "original_payload.bin"
    content = os.urandom(512 * 1024)  # 512 KB
    orig_file.write_bytes(content)
    orig_hash = hashlib.sha256(content).hexdigest()

    # Divide em pedaços de 150 KB (deve gerar 4 partes: 150, 150, 150, 62 KB)
    chunk_size = 150 * 1024
    parts = split_file(orig_file, chunk_size, tmp_path)
    assert len(parts) == 4
    for p in parts:
        assert p.exists()
        assert p.name.startswith("original_payload.bin.part")

    # Reconstitui em arquivo de saída
    merged_file = tmp_path / "reconstructed.bin"
    merge_files(parts, merged_file)
    assert merged_file.exists()

    merged_content = merged_file.read_bytes()
    merged_hash = hashlib.sha256(merged_content).hexdigest()
    assert orig_hash == merged_hash
    assert len(merged_content) == len(content)


def test_duplicates_scanner(tmp_path: Path):
    """Testa detecção de arquivos duplicados por tamanho e SHA-256."""
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    # Cria dois arquivos com mesmo conteúdo
    payload_a = b"Conteudo identico para deteccao de duplicidade 12345"
    f1 = dir1 / "file1.txt"
    f2 = dir2 / "file1_copy.txt"
    f1.write_bytes(payload_a)
    f2.write_bytes(payload_a)

    # Cria arquivo com conteúdo diferente
    f3 = dir1 / "different.txt"
    f3.write_bytes(b"Outro conteudo completamente diferente")

    # Varre diretório
    dup_groups = scan_duplicates(tmp_path, recursive=True)
    assert len(dup_groups) == 1
    dup_names = [p.name for p in dup_groups[0]]
    assert "file1.txt" in dup_names
    assert "file1_copy.txt" in dup_names
    assert "different.txt" not in dup_names


def test_shredder_single_file(tmp_path: Path):
    """Testa sobrescrita segura e exclusão definitiva de arquivo."""
    secret_file = tmp_path / "dados_confidenciais.txt"
    secret_file.write_bytes(b"Chave privada super secreta do usuario")
    assert secret_file.exists()

    shred_single_file(secret_file, passes=1)
    assert not secret_file.exists()


def test_archive_compress_inspect_extract(tmp_path: Path):
    """Testa compactação ZIP, inspeção de itens e extração fiel."""
    source_dir = tmp_path / "origem"
    source_dir.mkdir()

    file_a = source_dir / "nota.txt"
    file_a.write_text("Texto simples dentro do pacote zip", encoding="utf-8")
    sub = source_dir / "subpasta"
    sub.mkdir()
    file_b = sub / "dados.csv"
    file_b.write_text("id;nome\n1;WinToolbox", encoding="utf-8")

    # Compacta em ZIP
    zip_out = tmp_path / "backup.zip"
    compress_items([file_a, sub], zip_out, fmt="ZIP")
    assert zip_out.exists()
    assert zip_out.stat().st_size > 0

    # Inspeciona conteúdo sem extrair
    inspected = inspect_archive(zip_out)
    item_names = [it["name"] for it in inspected]
    assert any("nota.txt" in n for n in item_names)
    assert any("dados.csv" in n for n in item_names)

    # Extrai em nova pasta
    extract_dir = tmp_path / "destino_extraido"
    extract_dir.mkdir()
    extracted_count = extract_archive(zip_out, extract_dir)
    assert extracted_count == 2

    # Verifica integridade com leitura real de conteúdo
    assert (extract_dir / "nota.txt").is_file()
    assert (extract_dir / "nota.txt").read_text(encoding="utf-8") == "Texto simples dentro do pacote zip"
    assert (extract_dir / "subpasta" / "dados.csv").is_file()
    assert (extract_dir / "subpasta" / "dados.csv").read_text(encoding="utf-8") == "id;nome\n1;WinToolbox"


def test_archive_compress_tar_gz(tmp_path: Path):
    """Testa compactação e extração no formato TAR.GZ com validação de conteúdo."""
    source_file = tmp_path / "arquivo_tar.txt"
    source_file.write_text("Conteudo para tar gz comprimido", encoding="utf-8")

    tar_out = tmp_path / "pacote.tar.gz"
    compress_items([source_file], tar_out, fmt="TAR.GZ")
    assert tar_out.is_file()

    extract_tar_dir = tmp_path / "extraido_tar"
    extract_tar_dir.mkdir()
    extracted_count = extract_archive(tar_out, extract_tar_dir)
    assert extracted_count == 1
    
    # Validação do Efeito Real: ler o arquivo extraído
    extracted_tar_file = extract_tar_dir / "arquivo_tar.txt"
    assert extracted_tar_file.is_file()
    assert extracted_tar_file.read_text(encoding="utf-8") == "Conteudo para tar gz comprimido"

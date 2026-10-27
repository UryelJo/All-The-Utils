"""
Testes unitários rigorosos para data.csv_tools.logic.
Validação em disco de arquivos reais (Black-Box testing) com asserções determinísticas.
"""
import csv
from pathlib import Path
import pytest
from wintoolbox.tools.data.csv_tools.logic import (
    convert_csv_delimiter,
    detect_delimiter,
    merge_csv_files,
    remove_csv_duplicates,
    split_csv_by_rows,
)


def test_detect_delimiter(tmp_path: Path):
    f_comma = tmp_path / "comma.csv"
    f_comma.write_text("id,nome,idade\n1,Ana,25\n2,Carlos,30", encoding="utf-8")
    assert detect_delimiter(str(f_comma)) == ","

    f_semi = tmp_path / "semi.csv"
    f_semi.write_text("id;nome;valor\n10;Serviço;150,00\n20;Produto;80,50", encoding="utf-8")
    assert detect_delimiter(str(f_semi)) == ";"

    f_tab = tmp_path / "tab.tsv"
    f_tab.write_text("colA\tcolB\tcolC\n1\t2\t3", encoding="utf-8")
    assert detect_delimiter(str(f_tab)) == "\t"


def test_split_csv_by_rows(tmp_path: Path):
    src = tmp_path / "dataset.csv"
    rows = [["id", "nome", "categoria"]]
    for i in range(1, 26):  # 25 linhas de dados
        rows.append([str(i), f"Item {i}", "Hardware"])

    with open(src, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    out_dir = tmp_path / "split_output"
    generated = split_csv_by_rows(str(src), str(out_dir), rows_per_file=10)

    # 25 linhas com 10 por arquivo geram 3 arquivos (10 + 10 + 5)
    assert len(generated) == 3

    # Validação do conteúdo real dos arquivos gerados (Black-Box)
    with open(generated[0], "r", encoding="utf-8") as f1:
        lines1 = list(csv.reader(f1))
        assert len(lines1) == 11  # cabeçalho + 10 linhas
        assert lines1[0] == ["id", "nome", "categoria"]
        assert lines1[1] == ["1", "Item 1", "Hardware"]
        assert lines1[-1] == ["10", "Item 10", "Hardware"]

    with open(generated[1], "r", encoding="utf-8") as f2:
        lines2 = list(csv.reader(f2))
        assert len(lines2) == 11  # cabeçalho + 10 linhas
        assert lines2[0] == ["id", "nome", "categoria"]
        assert lines2[1] == ["11", "Item 11", "Hardware"]
        assert lines2[-1] == ["20", "Item 20", "Hardware"]

    with open(generated[2], "r", encoding="utf-8") as f3:
        lines3 = list(csv.reader(f3))
        assert len(lines3) == 6   # cabeçalho + 5 linhas
        assert lines3[0] == ["id", "nome", "categoria"]
        assert lines3[1] == ["21", "Item 21", "Hardware"]
        assert lines3[-1] == ["25", "Item 25", "Hardware"]


def test_merge_csv_files(tmp_path: Path):
    f1 = tmp_path / "part1.csv"
    f2 = tmp_path / "part2.csv"
    f1.write_text("id,nome\n1,Lucas\n2,Marina\n", encoding="utf-8")
    f2.write_text("id,nome\n2,Marina\n3,Roberto\n", encoding="utf-8")

    out_merged = tmp_path / "merged.csv"
    metrics = merge_csv_files([str(f1), str(f2)], str(out_merged), deduplicate=True)

    assert metrics["files_merged"] == 2
    assert metrics["total_source_rows"] == 4
    assert metrics["written_rows"] == 3
    assert metrics["duplicates_removed"] == 1

    with open(out_merged, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
        assert rows == [
            ["id", "nome"],
            ["1", "Lucas"],
            ["2", "Marina"],
            ["3", "Roberto"],
        ]


def test_convert_csv_delimiter(tmp_path: Path):
    src = tmp_path / "input_comma.csv"
    src.write_text("cidade,estado,populacao\nCampinas,SP,1200000\nCuritiba,PR,1900000", encoding="utf-8")

    dst = tmp_path / "output_semi.csv"
    rows_processed = convert_csv_delimiter(str(src), str(dst), target_delimiter=";")
    assert rows_processed == 3

    content = dst.read_text(encoding="utf-8")
    expected = "cidade;estado;populacao\nCampinas;SP;1200000\nCuritiba;PR;1900000\n"
    # Normaliza quebras de linha para comparação
    assert content.replace("\r\n", "\n") == expected


def test_remove_csv_duplicates(tmp_path: Path):
    src = tmp_path / "com_dups.csv"
    src.write_text("cpf,nome\n111,Pedro\n222,Tiago\n111,Pedro\n333,Joao\n", encoding="utf-8")

    dst = tmp_path / "sem_dups.csv"
    res = remove_csv_duplicates(str(src), str(dst))

    assert res["total_rows"] == 4
    assert res["written_rows"] == 3
    assert res["duplicates_removed"] == 1

    with open(dst, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
        assert rows == [
            ["cpf", "nome"],
            ["111", "Pedro"],
            ["222", "Tiago"],
            ["333", "Joao"],
        ]


def test_split_csv_invalid_rows():
    with pytest.raises(ValueError, match="maior que zero"):
        split_csv_by_rows("fake.csv", "out", rows_per_file=0)

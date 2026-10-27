"""
Testes unitários para dev.line_counter.
Valida análise determinística de código efetivo, comentários e tarefas TODO/FIXME.
"""
import pytest
from pathlib import Path

from wintoolbox.tools.dev.line_counter.logic import (
    analyze_file,
    count_project_lines,
    detect_language,
)


def test_detect_language():
    """Valida mapeamento de extensões para linguagens."""
    assert detect_language(".py") == "Python"
    assert detect_language(".ts") == "JavaScript / TypeScript"
    assert detect_language(".cs") == "C# (.NET)"
    assert detect_language(".rs") == "Rust"
    assert detect_language(".xyz") is None


def test_analyze_file_python(tmp_path: Path):
    """Testa contagem exata de linhas em arquivo Python."""
    code = """# Comentario de cabecalho
def soma(a, b):
    # TODO: implementar validacao de tipo
    return a + b

'''
Bloco de documentacao
multilinha
'''
print(soma(2, 3))
"""
    f = tmp_path / "modulo.py"
    f.write_text(code, encoding="utf-8")

    stats = analyze_file(f, "Python")
    assert stats.total_lines == 10
    assert stats.lines_blank == 1
    # Comentários: linha 1 (#), linha 3 (# TODO), linha 6 ('''), linha 7, linha 8, linha 9 (''') = 6
    assert stats.lines_comment == 6
    # Código: def (linha 2), return (linha 4), print (linha 10) = 3
    assert stats.lines_code == 3

    # Anotações de tarefa
    assert len(stats.markers) == 1
    assert stats.markers[0].marker_type == "TODO"
    assert "implementar validacao" in stats.markers[0].content


def test_count_project_lines_aggregation(tmp_path: Path):
    """Valida agregação completa em diretório de projeto."""
    p_src = tmp_path / "src"
    p_src.mkdir()
    (p_src / "main.py").write_text("print('a')\nprint('b')\n", encoding="utf-8")
    (p_src / "style.css").write_text("body { margin: 0; }\n/* FIXME: ajustar fonte */\n", encoding="utf-8")

    langs, files, markers = count_project_lines(tmp_path)
    assert "Python" in langs
    assert "CSS / SCSS" in langs
    assert len(files) == 2
    assert len(markers) == 1
    assert markers[0].marker_type == "FIXME"

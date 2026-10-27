"""
Testes unitários para dev.minifier.
Valida minificação e embelezamento de HTML, CSS e JavaScript.
"""
from wintoolbox.tools.dev.minifier.logic import (
    format_css,
    format_html,
    get_compression_stats,
    minify_css,
    minify_html,
    minify_js,
)


def test_minify_and_format_css():
    """Valida minificação e formatação de regras CSS."""
    raw = """
    /* Estilos do cabeçalho */
    .header {
        color: #ffffff;
        font-size: 16px;
    }
    """
    mini = minify_css(raw)
    assert "/*" not in mini
    assert mini == ".header{color:#ffffff;font-size:16px}"

    fmt = format_css(mini)
    assert ".header {" in fmt
    assert "color: #ffffff;" in fmt


def test_minify_and_format_html():
    """Valida minificação e identação de marcação HTML."""
    raw = """
    <!-- Comentario de pagina -->
    <div class="container">
        <h1>Titulo Principal</h1>
        <p>Paragrafo explicativo.</p>
    </div>
    """
    mini = minify_html(raw)
    assert "<!--" not in mini
    assert "><" in mini

    fmt = format_html(mini)
    assert "<div" in fmt
    assert "<h1" in fmt


def test_minify_js_basic():
    """Valida remoção de comentários e espaços em script JS."""
    raw = """
    // Funcao de soma
    function somar(a, b) {
        /* Retorna valor */
        return a + b;
    }
    """
    mini = minify_js(raw)
    assert "//" not in mini
    assert "/*" not in mini
    assert "function somar(a,b)" in mini


def test_compression_stats():
    """Valida métricas percentuais de economia de bytes."""
    stats = get_compression_stats("1234567890", "12345")
    assert stats["original_bytes"] == 10
    assert stats["processed_bytes"] == 5
    assert stats["saved_bytes"] == 5
    assert stats["reduction_percentage"] == 50.0

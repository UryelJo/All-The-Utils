"""
Lógica pura para minificação e formatação local de arquivos HTML, CSS e JavaScript.
Opera 100% offline sem depender de ecossistemas externos baseados em Node.js.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import re
from typing import Any, Dict


def get_compression_stats(original: str, processed: str) -> Dict[str, Any]:
    """Calcula estatísticas de economia de bytes entre a entrada e a saída."""
    orig_bytes = len(original.encode("utf-8"))
    proc_bytes = len(processed.encode("utf-8"))
    saved_bytes = max(0, orig_bytes - proc_bytes)
    ratio = (saved_bytes / orig_bytes * 100.0) if orig_bytes > 0 else 0.0

    return {
        "original_bytes": orig_bytes,
        "processed_bytes": proc_bytes,
        "saved_bytes": saved_bytes,
        "reduction_percentage": ratio
    }


def minify_css(css: str) -> str:
    """Minifica código CSS removendo comentários e espaços desnecessários."""
    # 1. Remove comentários de bloco /* ... */
    css = re.sub(r'/\*[\s\S]*?\*/', '', css)

    # 2. Normaliza quebras de linha e múltiplos espaços
    css = re.sub(r'\s+', ' ', css)

    # 3. Remove espaços ao redor de delimitadores e operadores
    css = re.sub(r'\s*([\{\}\:\;\,])\s*', r'\1', css)

    # 4. Remove último ponto-e-vírgula antes de fechar bloco
    css = re.sub(r';\}', '}', css)

    return css.strip()


def format_css(css: str, indent: str = "  ") -> str:
    """Formata e indenta código CSS de forma limpa e legível."""
    # Primeiro minifica para padronizar
    minified = minify_css(css)

    formatted = []
    depth = 0
    in_media = False

    tokens = re.split(r'([\{\}\;])', minified)
    for token in tokens:
        t = token.strip()
        if not t:
            continue

        if t == '{':
            formatted.append(" {\n")
            depth += 1
        elif t == '}':
            depth = max(0, depth - 1)
            formatted.append("\n" + (indent * depth) + "}\n")
        elif t == ';':
            formatted.append(";\n")
        else:
            # Se for uma propriedade CSS (contém ':')
            if depth > 0 and ':' in t:
                parts = t.split(':', 1)
                prop = parts[0].strip()
                val = parts[1].strip()
                formatted.append((indent * depth) + f"{prop}: {val}")
            else:
                formatted.append((indent * depth) + t)

    res = "".join(formatted)
    # Remove linhas vazias consecutivas
    return re.sub(r'\n{3,}', '\n\n', res).strip()


def minify_html(html: str, keep_comments: bool = False) -> str:
    """Minifica código HTML removendo espaços redundantes e comentários."""
    if not keep_comments:
        html = re.sub(r'<!--(?!\[if)[\s\S]*?-->', '', html)

    # Colapsa múltiplos espaços e quebras
    html = re.sub(r'\s+', ' ', html)
    # Remove espaços entre tags contíguas
    html = re.sub(r'>\s+<', '><', html)
    return html.strip()


def format_html(html: str, indent: str = "  ") -> str:
    """Formata e indenta código HTML hierarquicamente."""
    # Minifica inicialmente
    cleaned = minify_html(html, keep_comments=True)

    void_elements = {
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr'
    }

    tokens = re.findall(r'(<[^>]+>|[^<]+)', cleaned)
    lines = []
    depth = 0

    for token in tokens:
        t = token.strip()
        if not t:
            continue

        # Tag de fechamento </tag>
        if t.startswith('</'):
            depth = max(0, depth - 1)
            lines.append((indent * depth) + t)
        # Tag de abertura <tag ...>
        elif t.startswith('<') and not t.startswith('<!') and not t.startswith('<?'):
            tag_name = re.match(r'<([a-zA-Z0-9\-_]+)', t)
            name = tag_name.group(1).lower() if tag_name else ""
            is_self_closing = t.endswith('/>') or name in void_elements

            lines.append((indent * depth) + t)
            if not is_self_closing:
                depth += 1
        # Comentário ou declaração <!DOCTYPE ...>
        elif t.startswith('<!'):
            lines.append((indent * depth) + t)
        # Conteúdo de texto
        else:
            lines.append((indent * depth) + t)

    return "\n".join(lines)


def minify_js(js: str) -> str:
    """
    Minificador básico seguro de JavaScript.
    Remove comentários e espaços redundantes mantendo strings literais intactas.
    """
    # 1. Remove comentários de bloco
    js = re.sub(r'/\*[\s\S]*?\*/', '', js)

    # 2. Remove comentários de linha única (linhas que começam com //)
    lines = []
    for line in js.splitlines():
        line_s = line.strip()
        if line_s.startswith("//"):
            continue
        # Se houver // no final da linha sem estar dentro de aspas
        if "//" in line and not ('"' in line or "'" in line or '`' in line):
            line = line.split("//", 1)[0]
        lines.append(line)

    joined = "\n".join(lines)

    # 3. Colapsa espaços e quebras
    joined = re.sub(r'[ \t]+', ' ', joined)
    # Remove espaços ao redor de operadores comuns
    joined = re.sub(r'\s*([\{\}\(\)\;\,\:\=\+\-\*\/])\s*', r'\1', joined)
    # Remove quebras de linha residuais
    joined = re.sub(r'\n+', '\n', joined)

    return joined.strip()

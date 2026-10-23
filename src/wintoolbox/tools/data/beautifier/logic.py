"""
Lógica pura da ferramenta Formatador e Minificador de Dados (JSON, XML, SQL).
Sem acoplamento com interface gráfica.
"""
import json
from defusedxml import minidom as defused_minidom


def beautify_code(text: str, code_type: str, indent: int = 2) -> str:
    """Formata e indenta o código/dado estruturado."""
    t = code_type.upper()
    if t == "JSON":
        parsed = json.loads(text)
        return json.dumps(parsed, indent=indent, ensure_ascii=False)
    elif t == "XML":
        dom = defused_minidom.parseString(text.encode("utf-8"))
        pretty = dom.toprettyxml(indent=" " * indent)
        return "\n".join([line for line in pretty.splitlines() if line.strip()])
    elif t == "SQL":
        try:
            import sqlparse
            return sqlparse.format(
                text,
                reindent=True,
                keyword_case="upper",
                indent_width=indent,
            )
        except ImportError:
            return text
    return text


def minify_code(text: str, code_type: str) -> str:
    """Minifica e compacta o código removendo espaços e quebras supérfluas."""
    t = code_type.upper()
    if t == "JSON":
        parsed = json.loads(text)
        return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
    elif t == "XML":
        dom = defused_minidom.parseString(text.encode("utf-8"))
        return "".join([l.strip() for l in dom.toxml().splitlines() if l.strip()])
    elif t == "SQL":
        try:
            import sqlparse
            return sqlparse.format(text, strip_comments=True)
        except ImportError:
            return " ".join(text.split())
    return " ".join(text.split())

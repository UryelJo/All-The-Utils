"""
Lógica pura para formatação, embelezamento e minificação de consultas e scripts SQL.
Preserva strings literais entre aspas, comentários (-- e /* */), formata cláusulas
principais com indentação hierárquica e padroniza palavras-chave em maiúsculas.

Zero dependências de interface gráfica.
"""
import re
from typing import List, Tuple

# Principais palavras-chave do padrão SQL ANSI e dialetos modernos
SQL_KEYWORDS = [
    "SELECT", "DISTINCT", "FROM", "WHERE", "GROUP BY", "ORDER BY",
    "HAVING", "LIMIT", "OFFSET", "INSERT INTO", "VALUES", "UPDATE",
    "SET", "DELETE", "CREATE TABLE", "ALTER TABLE", "DROP TABLE",
    "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL JOIN", "CROSS JOIN", "JOIN",
    "ON", "USING", "AND", "OR", "NOT", "IN", "IS NULL", "IS NOT NULL",
    "LIKE", "ILIKE", "BETWEEN", "CASE", "WHEN", "THEN", "ELSE", "END",
    "UNION ALL", "UNION", "EXCEPT", "INTERSECT", "BEGIN TRANSACTION", "COMMIT", "ROLLBACK",
    "PRIMARY KEY", "FOREIGN KEY", "REFERENCES", "CASCADE", "DEFAULT", "ASC", "DESC"
]

CLAUSES_ON_NEW_LINE = [
    "SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING",
    "LIMIT", "OFFSET", "INSERT INTO", "VALUES", "UPDATE", "SET",
    "DELETE", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL JOIN",
    "CROSS JOIN", "JOIN", "UNION ALL", "UNION"
]


def _mask_literals_and_comments(sql: str) -> Tuple[str, List[str]]:
    """
    Substitui strings literais ('...') e comentários por marcadores temporários
    para proteger contra alterações indevidas.
    """
    placeholders: List[str] = []

    def replacer(match: re.Match) -> str:
        token = match.group(0)
        idx = len(placeholders)
        placeholders.append(token)
        return f"__SQL_LITERAL_{idx}__"

    # Regex para strings com aspas simples, comentários de linha -- e bloco /* */
    pattern = r"'(?:''|[^'])*'|--[^\n]*|/\*[\s\S]*?\*/"
    masked = re.sub(pattern, replacer, sql)
    return masked, placeholders


def _unmask_literals(sql: str, placeholders: List[str]) -> str:
    """Restaura as strings literais e comentários mascarados."""
    for idx, token in enumerate(placeholders):
        sql = sql.replace(f"__SQL_LITERAL_{idx}__", token)
    return sql


def format_sql(
    sql_query: str,
    uppercase_keywords: bool = True,
    indent_spaces: int = 2,
) -> str:
    """
    Formata e embeleza uma instrução SQL com indentação e quebras de linha nas cláusulas principais.
    """
    cleaned = sql_query.strip()
    if not cleaned:
        return ""

    masked, placeholders = _mask_literals_and_comments(cleaned)

    # 1. Normaliza espaçamentos e quebras
    masked = re.sub(r"\s+", " ", masked)

    # 2. Converte palavras-chave para maiúsculas (ou minúsculas)
    # Ordena por comprimento decrescente para que "LEFT JOIN" venha antes de "JOIN"
    sorted_keywords = sorted(SQL_KEYWORDS, key=len, reverse=True)
    for kw in sorted_keywords:
        pattern = r"\b" + re.escape(kw) + r"\b"
        replacement = kw.upper() if uppercase_keywords else kw.lower()
        masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)

    # 3. Insere quebras de linha antes das cláusulas principais
    indent = " " * indent_spaces
    for clause in sorted(CLAUSES_ON_NEW_LINE, key=len, reverse=True):
        if clause == "JOIN":
            pattern = r"(?<!INNER\s)(?<!LEFT\s)(?<!RIGHT\s)(?<!CROSS\s)(?<!FULL\s)\bJOIN\b\s*"
        else:
            pattern = r"\s*\b(" + re.escape(clause) + r")\b\s*"
        masked = re.sub(pattern, r"\n\1 " if clause != "JOIN" else r"\nJOIN ", masked, flags=re.IGNORECASE)

    # 4. Formata vírgulas em listas de colunas (quebra ou espaçamento)
    masked = re.sub(r"\s*,\s*", f",\n{indent}", masked)

    # 5. Ajusta linhas e identações
    lines = [line.strip() for line in masked.splitlines() if line.strip()]
    formatted_lines = []

    for line in lines:
        first_word = line.split()[0].upper() if line.split() else ""
        if any(first_word == cl.split()[0].upper() for cl in CLAUSES_ON_NEW_LINE):
            formatted_lines.append(line)
        else:
            formatted_lines.append(f"{indent}{line}")

    result = "\n".join(formatted_lines)
    return _unmask_literals(result, placeholders)


def minify_sql(sql_query: str) -> str:
    """
    Minifica uma consulta SQL removendo comentários, quebras de linha e espaços redundantes.
    """
    cleaned = sql_query.strip()
    if not cleaned:
        return ""

    # Remove comentários de linha --
    sql_no_line_comments = re.sub(r"--[^\n]*", "", cleaned)
    # Remove comentários de bloco /* */
    sql_no_block_comments = re.sub(r"/\*[\s\S]*?\*/", "", sql_no_line_comments)

    masked, placeholders = _mask_literals_and_comments(sql_no_block_comments)

    # Reduz espaços múltiplos para um único espaço
    minified = re.sub(r"\s+", " ", masked).strip()

    # Remove espaços desnecessários ao redor de operadores e vírgulas
    minified = re.sub(r"\s*([,;=()])\s*", r"\1", minified)

    return _unmask_literals(minified, placeholders)

"""
Lógica pura para gerenciamento e expansão de trechos de texto frequentes (Snippets).
Suporta substituição dinâmica de placeholders ({date}, {time}, {datetime}, {clipboard}, {uuid})
e persistência JSON desacoplada de interface gráfica.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class Snippet:
    id: str
    shortcut: str
    title: str
    body: str
    category: str = "Geral"
    usage_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


def expand_snippet_body(body: str, clipboard_text: str = "") -> str:
    """
    Expande variáveis e placeholders dinâmicos presentes no corpo do snippet.
    Placeholders suportados:
    - {date}: Data atual no formato YYYY-MM-DD
    - {time}: Hora atual no formato HH:MM:SS
    - {datetime}: Data e hora no formato YYYY-MM-DD HH:MM:SS
    - {clipboard}: Conteúdo atual da área de transferência
    - {uuid}: Novo identificador UUIDv4
    """
    now = datetime.now()
    res = body
    res = res.replace("{date}", now.strftime("%Y-%m-%d"))
    res = res.replace("{time}", now.strftime("%H:%M:%S"))
    res = res.replace("{datetime}", now.strftime("%Y-%m-%d %H:%M:%S"))
    res = res.replace("{clipboard}", clipboard_text)
    if "{uuid}" in res:
        res = re.sub(r"\{uuid\}", lambda _: str(uuid.uuid4()), res)
    return res


def get_default_snippets() -> List[Snippet]:
    """Retorna uma lista padrão de trechos úteis."""
    return [
        Snippet(
            id=str(uuid.uuid4()),
            shortcut=":email",
            title="E-mail de Apresentação Profissional",
            body="Olá,\n\nEspero que este e-mail o encontre bem.\n\nEstou entrando em contato para apresentar nossa proposta referente ao projeto discutido.\n\nQualquer dúvida estou à disposição.\n\nAtenciosamente,\n[Seu Nome]",
            category="Comunicação"
        ),
        Snippet(
            id=str(uuid.uuid4()),
            shortcut=":reuniao",
            title="Ata de Reunião Rápida",
            body="### Ata de Reunião - {date}\n\n**Participantes:**\n- \n\n**Pautas Discutidas:**\n1. \n\n**Ações e Responsáveis:**\n- [ ] ",
            category="Trabalho"
        ),
        Snippet(
            id=str(uuid.uuid4()),
            shortcut=":agradecimento",
            title="Agradecimento Formal",
            body="Muito obrigado pela atenção e pelo pronto atendimento.\nTenha uma excelente semana!",
            category="Comunicação"
        ),
        Snippet(
            id=str(uuid.uuid4()),
            shortcut=":datahora",
            title="Timestamp ISO",
            body="{datetime}",
            category="Dev"
        )
    ]


def filter_snippets(snippets: List[Snippet], query: str = "", category: Optional[str] = None) -> List[Snippet]:
    """Filtra snippets por texto de busca e categoria."""
    query = query.strip().lower()
    res = []
    for s in snippets:
        if category and category != "Todas" and s.category != category:
            continue
        if not query:
            res.append(s)
            continue
        if (
            query in s.shortcut.lower()
            or query in s.title.lower()
            or query in s.body.lower()
            or query in s.category.lower()
        ):
            res.append(s)
    return res


def snippets_to_dict(snippets: List[Snippet]) -> List[Dict[str, Any]]:
    """Converte lista de snippets para dicionários serializáveis."""
    return [asdict(s) for s in snippets]


def snippets_from_dict(data: List[Dict[str, Any]]) -> List[Snippet]:
    """Reconstrói lista de snippets a partir de dicionários."""
    snippets = []
    for item in data:
        snippets.append(Snippet(
            id=item.get("id", str(uuid.uuid4())),
            shortcut=item.get("shortcut", ""),
            title=item.get("title", ""),
            body=item.get("body", ""),
            category=item.get("category", "Geral"),
            usage_count=item.get("usage_count", 0),
            created_at=item.get("created_at", "")
        ))
    return snippets


def save_snippets_to_json(snippets: List[Snippet], path: Path) -> None:
    """Salva a coleção de trechos em formato JSON."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snippets_to_dict(snippets), f, ensure_ascii=False, indent=2)


def load_snippets_from_json(path: Path) -> List[Snippet]:
    """Carrega trechos do arquivo JSON local. Se não existir, retorna os snippets padrão."""
    path = Path(path).resolve()
    if not path.is_file():
        return get_default_snippets()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return snippets_from_dict(data)

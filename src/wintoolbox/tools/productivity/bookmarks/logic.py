"""
Lógica pura para gerenciamento local de favoritos web (Bookmarks).
Suporta categorização por tags, verificação de integridade de links (HTTP status),
parsing de exportação Netscape Bookmark HTML e persistência JSON desacoplada de GUI.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request
import uuid


@dataclass
class Bookmark:
    id: str
    title: str
    url: str
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    status: str = "unchecked"  # 'unchecked', 'active', 'broken'
    status_code: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


def filter_bookmarks(bookmarks: List[Bookmark], query: str = "", tag: Optional[str] = None) -> List[Bookmark]:
    """Filtra favoritos por termo de busca e/ou tag específica."""
    query = query.strip().lower()
    res = []
    for b in bookmarks:
        if tag and tag != "Todas" and tag not in b.tags:
            continue
        if not query:
            res.append(b)
            continue
        if (
            query in b.title.lower()
            or query in b.url.lower()
            or query in b.notes.lower()
            or any(query in t.lower() for t in b.tags)
        ):
            res.append(b)
    return res


def check_url_status(url: str, timeout: float = 5.0) -> Tuple[bool, int, str]:
    """
    Verifica se uma URL está ativa fazendo requisição HEAD (ou GET).
    Retorna: (is_active, status_code, mensagem_status).
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WinToolbox/1.0"}
    )
    req.get_method = lambda: "HEAD"

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            code = response.getcode()
            return (code < 400, code, f"OK ({code})")
    except urllib.error.HTTPError as e:
        return (False, e.code, f"Erro HTTP {e.code}")
    except urllib.error.URLError as e:
        return (False, 0, f"Falha de Conexão: {e.reason}")
    except Exception as e:
        return (False, 0, f"Erro: {str(e)}")


def import_netscape_bookmarks_html(html_content: str) -> List[Bookmark]:
    """
    Interpreta o padrão clássico Netscape Bookmark HTML usado por
    Google Chrome, Mozilla Firefox, Microsoft Edge e Safari.
    """
    bookmarks: List[Bookmark] = []
    # Expressão regular para casar tags <A HREF="url" ...>Título</A>
    pattern = re.compile(r'<A\s+[^>]*HREF=["\'](.*?)["\'][^>]*>(.*?)</A>', re.IGNORECASE)

    for match in pattern.finditer(html_content):
        url = match.group(1).strip()
        title = match.group(2).strip() or url
        if url.startswith("http://") or url.startswith("https://"):
            bookmarks.append(
                Bookmark(
                    id=str(uuid.uuid4()),
                    title=title,
                    url=url,
                    tags=["Importado"]
                )
            )
    return bookmarks


def export_netscape_bookmarks_html(bookmarks: List[Bookmark]) -> str:
    """Gera arquivo HTML de favoritos no padrão universal Netscape."""
    lines = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Favoritos WinToolbox</TITLE>",
        "<H1>Favoritos</H1>",
        "<DL><p>"
    ]
    for b in bookmarks:
        tags_str = ",".join(b.tags)
        lines.append(f'    <DT><A HREF="{b.url}" TAGS="{tags_str}">{b.title}</A>')
    lines.append("</DL><p>")
    return "\n".join(lines)


def get_default_bookmarks() -> List[Bookmark]:
    """Retorna favoritos úteis de referência padrão."""
    return [
        Bookmark(
            id=str(uuid.uuid4()),
            title="Documentação Oficial Python",
            url="https://docs.python.org/3/",
            tags=["Dev", "Python", "Documentação"],
            notes="Referência da biblioteca padrão"
        ),
        Bookmark(
            id=str(uuid.uuid4()),
            title="Documentação Oficial Qt para Python",
            url="https://doc.qt.io/qtforpython-6/",
            tags=["Dev", "Qt", "UI"],
            notes="Documentação de classes e componentes de interface gráfica"
        ),
        Bookmark(
            id=str(uuid.uuid4()),
            title="Microsoft Learn - Design do Windows",
            url="https://learn.microsoft.com/windows/apps/design/",
            tags=["Design", "Fluent"],
            notes="Diretrizes de design do Windows 11"
        ),
    ]


def bookmarks_to_dict(bookmarks: List[Bookmark]) -> List[Dict[str, Any]]:
    """Serializa lista de favoritos."""
    return [asdict(b) for b in bookmarks]


def bookmarks_from_dict(data: List[Dict[str, Any]]) -> List[Bookmark]:
    """Reconstrói lista de favoritos a partir de dicionários."""
    items = []
    for d in data:
        items.append(Bookmark(
            id=d.get("id", str(uuid.uuid4())),
            title=d.get("title", "Sem título"),
            url=d.get("url", ""),
            tags=d.get("tags", []),
            notes=d.get("notes", ""),
            status=d.get("status", "unchecked"),
            status_code=d.get("status_code"),
            created_at=d.get("created_at", "")
        ))
    return items


def save_bookmarks_json(bookmarks: List[Bookmark], path: Path) -> None:
    """Salva favoritos em formato JSON."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bookmarks_to_dict(bookmarks), f, ensure_ascii=False, indent=2)


def load_bookmarks_json(path: Path) -> List[Bookmark]:
    """Carrega favoritos do disco. Cria padrão caso não exista."""
    path = Path(path).resolve()
    if not path.is_file():
        return get_default_bookmarks()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return bookmarks_from_dict(data)

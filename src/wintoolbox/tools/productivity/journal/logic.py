"""
Lógica pura para diário pessoal offline e anotações cronológicas.
Suporta busca de registros por período e texto, categorização por humor/tags,
exportação para Markdown estruturado e persistência JSON desacoplada de GUI.
"""
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class JournalEntry:
    id: str
    date: str  # YYYY-MM-DD
    title: str
    content: str
    mood: str = "😊 Produtivo"
    tags: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


def get_entry_by_date(entries: List[JournalEntry], target_date: str) -> Optional[JournalEntry]:
    """Retorna o registro correspondente à data informada, se existir."""
    for e in entries:
        if e.date == target_date:
            return e
    return None


def filter_entries(
    entries: List[JournalEntry],
    query: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tag: Optional[str] = None
) -> List[JournalEntry]:
    """Filtra registros do diário por texto, faixa de datas e tags."""
    q = query.strip().lower()
    res = []
    for e in entries:
        if start_date and e.date < start_date:
            continue
        if end_date and e.date > end_date:
            continue
        if tag and tag != "Todas" and tag not in e.tags:
            continue
        if not q:
            res.append(e)
            continue
        if q in e.title.lower() or q in e.content.lower() or any(q in t.lower() for t in e.tags):
            res.append(e)
    # Ordena por data decrescente
    res.sort(key=lambda x: x.date, reverse=True)
    return res


def export_journal_to_markdown(entries: List[JournalEntry], journal_title: str = "Diário Pessoal") -> str:
    """Gera um documento consolidado em Markdown estruturado com índice cronológico."""
    lines = [
        f"# {journal_title}",
        f"*Exportado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}*",
        "",
        "---",
        ""
    ]

    # Ordena por data ascendente para leitura cronológica no arquivo
    sorted_entries = sorted(entries, key=lambda x: x.date)
    for e in sorted_entries:
        dt_fmt = e.date
        try:
            d_obj = date.fromisoformat(e.date)
            dt_fmt = d_obj.strftime("%d/%m/%Y (%A)")
        except Exception:
            pass

        lines.append(f"## {dt_fmt} - {e.title}")
        lines.append(f"**Humor:** {e.mood} | **Tags:** {', '.join(e.tags) if e.tags else 'Nenhuma'}")
        lines.append("")
        lines.append(e.content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def get_default_journal_entries() -> List[JournalEntry]:
    """Retorna registros de boas-vindas para o diário."""
    today = date.today().isoformat()
    return [
        JournalEntry(
            id=str(uuid.uuid4()),
            date=today,
            title="Primeiro registro no diário",
            content="Começando a registrar minhas reflexões diárias e o progresso dos meus projetos no WinToolbox. Privacidade total e foco absoluto!",
            mood="😊 Produtivo",
            tags=["Início", "Produtividade", "Metas"]
        )
    ]


def save_journal(entries: List[JournalEntry], path: Path) -> None:
    """Salva todas as entradas do diário em formato JSON."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(e) for e in entries]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_journal(path: Path) -> List[JournalEntry]:
    """Carrega as entradas do diário do disco."""
    path = Path(path).resolve()
    if not path.is_file():
        return get_default_journal_entries()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = []
    for d in data:
        entries.append(JournalEntry(
            id=d.get("id", str(uuid.uuid4())),
            date=d.get("date", date.today().isoformat()),
            title=d.get("title", "Sem título"),
            content=d.get("content", ""),
            mood=d.get("mood", "😊 Neutro"),
            tags=d.get("tags", []),
            updated_at=d.get("updated_at", "")
        ))
    return entries

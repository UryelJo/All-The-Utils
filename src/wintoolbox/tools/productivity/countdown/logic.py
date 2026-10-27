"""
Lógica pura para painel de contagens regressivas e cálculo de prazos.
Calcula dias, horas, minutos e segundos restantes até eventos futuros ou tempo decorrido de eventos passados.
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class CountdownItem:
    id: str
    title: str
    target_datetime: str  # Formato ISO: YYYY-MM-DDTHH:MM:SS
    category: str = "Geral"
    color: str = "#0284c7"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


def calculate_time_remaining(target_dt_str: str, reference_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calcula o tempo restante ou decorrido a partir de uma data/hora alvo.
    Retorna dicionário com dias, horas, minutos, segundos e formato textual.
    """
    ref = reference_dt or datetime.now()
    try:
        target = datetime.fromisoformat(target_dt_str)
    except Exception:
        target = ref

    delta = target - ref
    is_past = delta.total_seconds() < 0
    total_sec = abs(delta.total_seconds())

    days = int(total_sec // 86400)
    rem_sec = total_sec % 86400
    hours = int(rem_sec // 3600)
    rem_sec = rem_sec % 3600
    minutes = int(rem_sec // 60)
    seconds = int(rem_sec % 60)

    if is_past:
        if days > 0:
            formatted = f"Concluído há {days}d {hours}h"
        elif hours > 0:
            formatted = f"Concluído há {hours}h {minutes}m"
        else:
            formatted = f"Concluído há {minutes}m {seconds}s"
    else:
        if days > 0:
            formatted = f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
        else:
            formatted = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

    return {
        "is_past": is_past,
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
        "total_seconds": total_sec,
        "formatted": formatted
    }


def get_default_countdowns() -> List[CountdownItem]:
    """Retorna itens padrão de exemplo para novos usuários."""
    now = datetime.now()
    ano_novo = datetime(now.year + 1, 1, 1, 0, 0, 0)
    lancamento = now + timedelta(days=14, hours=8)
    revisao = now + timedelta(days=2, hours=4, minutes=30)

    return [
        CountdownItem(
            id=str(uuid.uuid4()),
            title="Ano Novo",
            target_datetime=ano_novo.isoformat(),
            category="Celebração",
            color="#eab308"
        ),
        CountdownItem(
            id=str(uuid.uuid4()),
            title="Lançamento da Versão Final",
            target_datetime=lancamento.isoformat(),
            category="Trabalho",
            color="#3b82f6"
        ),
        CountdownItem(
            id=str(uuid.uuid4()),
            title="Entrega de Relatório",
            target_datetime=revisao.isoformat(),
            category="Projeto",
            color="#ef4444"
        ),
    ]


def countdowns_to_dict(items: List[CountdownItem]) -> List[Dict[str, Any]]:
    """Serializa contagens regressivas para lista de dicionários."""
    return [asdict(i) for i in items]


def countdowns_from_dict(data: List[Dict[str, Any]]) -> List[CountdownItem]:
    """Desserializa contagens regressivas a partir de lista de dicionários."""
    items = []
    for d in data:
        items.append(CountdownItem(
            id=d.get("id", str(uuid.uuid4())),
            title=d.get("title", "Sem título"),
            target_datetime=d.get("target_datetime", datetime.now().isoformat()),
            category=d.get("category", "Geral"),
            color=d.get("color", "#0284c7"),
            created_at=d.get("created_at", "")
        ))
    return items


def save_countdowns(items: List[CountdownItem], path: Path) -> None:
    """Salva itens no disco em formato JSON."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(countdowns_to_dict(items), f, ensure_ascii=False, indent=2)


def load_countdowns(path: Path) -> List[CountdownItem]:
    """Carrega itens do disco. Cria padrão caso não exista."""
    path = Path(path).resolve()
    if not path.is_file():
        return get_default_countdowns()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return countdowns_from_dict(data)

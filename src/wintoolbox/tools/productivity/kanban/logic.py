"""
Lógica pura para o quadro Kanban offline com persistência JSON.
Suporta colunas dinâmicas, cartões com checklists, etiquetas e datas de entrega.
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class ChecklistItem:
    id: str
    title: str
    completed: bool = False


@dataclass
class KanbanCard:
    id: str
    title: str
    description: str = ""
    due_date: Optional[str] = None  # YYYY-MM-DD
    tags: List[str] = field(default_factory=list)
    checklist: List[ChecklistItem] = field(default_factory=list)
    color: str = "#0284c7"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class KanbanColumn:
    id: str
    title: str
    cards: List[KanbanCard] = field(default_factory=list)


@dataclass
class KanbanBoard:
    id: str
    title: str
    columns: List[KanbanColumn] = field(default_factory=list)


def create_default_board() -> KanbanBoard:
    """Cria um quadro Kanban padrão com colunas e cartões de exemplo."""
    return KanbanBoard(
        id=str(uuid.uuid4()),
        title="Meu Quadro de Produtividade",
        columns=[
            KanbanColumn(
                id="col_todo",
                title="A Fazer",
                cards=[
                    KanbanCard(
                        id=str(uuid.uuid4()),
                        title="Revisar especificações do projeto",
                        description="Conferir escopo e prazos de entrega com a equipe.",
                        tags=["Projeto", "Planejamento"],
                        checklist=[
                            ChecklistItem(id=str(uuid.uuid4()), title="Levantar requisitos", completed=True),
                            ChecklistItem(id=str(uuid.uuid4()), title="Definir entregáveis", completed=False),
                        ],
                        color="#0284c7"
                    ),
                    KanbanCard(
                        id=str(uuid.uuid4()),
                        title="Configurar ambiente de homologação",
                        description="Garantir servidores locais rodando.",
                        tags=["DevOps"],
                        color="#7c3aed"
                    )
                ]
            ),
            KanbanColumn(
                id="col_in_progress",
                title="Em Andamento",
                cards=[
                    KanbanCard(
                        id=str(uuid.uuid4()),
                        title="Implementar novos componentes",
                        description="Criar telas com Fluent Design e testes unitários.",
                        tags=["Desenvolvimento"],
                        color="#ea580c"
                    )
                ]
            ),
            KanbanColumn(
                id="col_done",
                title="Concluído",
                cards=[
                    KanbanCard(
                        id=str(uuid.uuid4()),
                        title="Estruturação inicial da arquitetura",
                        description="Separação rigorosa entre logic.py e tool.py concluída.",
                        tags=["Arquitetura"],
                        color="#16a34a"
                    )
                ]
            )
        ]
    )


def board_to_dict(board: KanbanBoard) -> Dict[str, Any]:
    """Converte a estrutura do quadro para dicionário serializável."""
    return asdict(board)


def board_from_dict(data: Dict[str, Any]) -> KanbanBoard:
    """Reconstrói um quadro Kanban a partir de um dicionário."""
    cols = []
    for c_data in data.get("columns", []):
        cards = []
        for crd in c_data.get("cards", []):
            chk_items = [
                ChecklistItem(
                    id=ch.get("id", str(uuid.uuid4())),
                    title=ch.get("title", ""),
                    completed=ch.get("completed", False)
                )
                for ch in crd.get("checklist", [])
            ]
            cards.append(KanbanCard(
                id=crd.get("id", str(uuid.uuid4())),
                title=crd.get("title", "Sem título"),
                description=crd.get("description", ""),
                due_date=crd.get("due_date"),
                tags=crd.get("tags", []),
                checklist=chk_items,
                color=crd.get("color", "#0284c7"),
                created_at=crd.get("created_at", "")
            ))
        cols.append(KanbanColumn(
            id=c_data.get("id", str(uuid.uuid4())),
            title=c_data.get("title", "Coluna"),
            cards=cards
        ))

    return KanbanBoard(
        id=data.get("id", str(uuid.uuid4())),
        title=data.get("title", "Quadro Kanban"),
        columns=cols
    )


def save_board_to_json(board: KanbanBoard, path: Path) -> None:
    """Salva o quadro em formato JSON no disco."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(board_to_dict(board), f, ensure_ascii=False, indent=2)


def load_board_from_json(path: Path) -> KanbanBoard:
    """Carrega o quadro do arquivo JSON. Se não existir, retorna um novo quadro padrão."""
    path = Path(path).resolve()
    if not path.is_file():
        return create_default_board()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return board_from_dict(data)


def move_card(board: KanbanBoard, card_id: str, target_column_id: str, new_index: int = -1) -> bool:
    """Move um cartão entre colunas ou dentro da mesma coluna."""
    found_card: Optional[KanbanCard] = None
    # Remove do local original
    for col in board.columns:
        for idx, card in enumerate(col.cards):
            if card.id == card_id:
                found_card = col.cards.pop(idx)
                break
        if found_card:
            break

    if not found_card:
        return False

    # Insere na coluna destino
    for col in board.columns:
        if col.id == target_column_id:
            if new_index < 0 or new_index >= len(col.cards):
                col.cards.append(found_card)
            else:
                col.cards.insert(new_index, found_card)
            return True

    return False


def add_card(board: KanbanBoard, column_id: str, card: KanbanCard) -> bool:
    """Adiciona um novo cartão à coluna especificada."""
    for col in board.columns:
        if col.id == column_id:
            col.cards.append(card)
            return True
    return False


def remove_card(board: KanbanBoard, card_id: str) -> bool:
    """Remove um cartão por ID de qualquer coluna."""
    for col in board.columns:
        for idx, card in enumerate(col.cards):
            if card.id == card_id:
                col.cards.pop(idx)
                return True
    return False


def update_card(board: KanbanBoard, updated_card: KanbanCard) -> bool:
    """Atualiza as propriedades de um cartão existente."""
    for col in board.columns:
        for idx, card in enumerate(col.cards):
            if card.id == updated_card.id:
                col.cards[idx] = updated_card
                return True
    return False


def add_column(board: KanbanBoard, title: str) -> KanbanColumn:
    """Adiciona uma nova coluna ao final do quadro."""
    new_col = KanbanColumn(id=str(uuid.uuid4()), title=title, cards=[])
    board.columns.append(new_col)
    return new_col


def remove_column(board: KanbanBoard, column_id: str) -> bool:
    """Remove uma coluna pelo ID."""
    for idx, col in enumerate(board.columns):
        if col.id == column_id:
            board.columns.pop(idx)
            return True
    return False

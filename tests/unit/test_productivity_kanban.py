"""
Testes unitários para o quadro Kanban offline.
Diretrizes Anti-Gambiarra: Validação real de persistência em arquivo e asserções determinísticas.
"""
from pathlib import Path
from wintoolbox.tools.productivity.kanban.logic import (
    ChecklistItem,
    KanbanBoard,
    KanbanCard,
    KanbanColumn,
    add_card,
    add_column,
    create_default_board,
    load_board_from_json,
    move_card,
    remove_card,
    remove_column,
    save_board_to_json,
    update_card,
)


def test_kanban_board_manipulation():
    board = KanbanBoard(
        id="board_1",
        title="Quadro de Teste",
        columns=[
            KanbanColumn(id="col_1", title="A Fazer", cards=[]),
            KanbanColumn(id="col_2", title="Concluído", cards=[]),
        ]
    )

    card = KanbanCard(
        id="card_100",
        title="Estudar PySide6",
        description="Aprender padrões Fluent",
        tags=["Estudo", "Qt"],
        checklist=[
            ChecklistItem(id="c1", title="Ler documentação", completed=True),
            ChecklistItem(id="c2", title="Fazer exercícios", completed=False)
        ]
    )

    # Adicionar card na coluna 1
    assert add_card(board, "col_1", card) is True
    assert len(board.columns[0].cards) == 1
    assert board.columns[0].cards[0].id == "card_100"

    # Mover card da coluna 1 para a coluna 2
    assert move_card(board, "card_100", "col_2") is True
    assert len(board.columns[0].cards) == 0
    assert len(board.columns[1].cards) == 1
    assert board.columns[1].cards[0].id == "card_100"

    # Atualizar card
    card.title = "Dominar PySide6 e Fluent"
    assert update_card(board, card) is True
    assert board.columns[1].cards[0].title == "Dominar PySide6 e Fluent"

    # Adicionar e remover coluna
    new_col = add_column(board, "Em Revisão")
    assert len(board.columns) == 3
    assert new_col.title == "Em Revisão"

    assert remove_column(board, new_col.id) is True
    assert len(board.columns) == 2

    # Remover card
    assert remove_card(board, "card_100") is True
    assert len(board.columns[1].cards) == 0


def test_kanban_json_persistence(tmp_path: Path):
    board = create_default_board()
    json_file = tmp_path / "board_teste.json"

    save_board_to_json(board, json_file)
    assert json_file.is_file()

    loaded_board = load_board_from_json(json_file)
    assert loaded_board.id == board.id
    assert loaded_board.title == board.title
    assert len(loaded_board.columns) == len(board.columns)
    assert loaded_board.columns[0].title == board.columns[0].title
    assert len(loaded_board.columns[0].cards) == len(board.columns[0].cards)
    assert loaded_board.columns[0].cards[0].title == board.columns[0].cards[0].title

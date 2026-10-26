"""
Testes unitários rigorosos para SortableTableWidget e SmartTableWidgetItem.
Valida ordenação real (numérica, tamanhos em bytes e alfabética), preservação de dados
associados via UserRole (evitando bugs de mapeamento de índice) e context manager de atualização em lote.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from wintoolbox.ui.widgets.sortable_table import (
    SortableTableWidget, SmartTableWidgetItem, enable_sorting_on_table, batch_table_update, parse_sort_key
)


def _get_app():
    return QApplication.instance() or QApplication([])


def test_parse_sort_key_types_and_edge_cases():
    """Valida o parser inteligente de chaves de ordenação."""
    # Números puros
    assert parse_sort_key(42) == 42
    assert parse_sort_key(3.14) == 3.14
    assert parse_sort_key(True) == 1
    assert parse_sort_key(False) == 0

    # Tamanhos de arquivo
    assert parse_sort_key("10 KB") == 10 * 1024
    assert parse_sort_key("2 MB") == 2 * 1024 * 1024
    assert parse_sort_key("500 B") == 500
    assert parse_sort_key("1.5 GB") == 1.5 * 1024 * 1024 * 1024
    assert parse_sort_key("1,5 GB") == 1.5 * 1024 * 1024 * 1024

    # Números formatados
    assert parse_sort_key("1.234,50") == 1234.50
    assert parse_sort_key("1,234.50") == 1234.50

    # Texto alfabético normal
    assert parse_sort_key("Programa Alpha") == "programa alpha"

    # Casos de borda: vazios e traço
    assert parse_sort_key("") == -float("inf")
    assert parse_sort_key("-") == -float("inf")
    assert parse_sort_key(None) == ""


def test_smart_item_comparison():
    """Valida comparação real entre itens com tamanhos, números e strings."""
    _get_app()

    # Tamanhos em bytes ("2 MB" vs "10 MB" vs "500 KB")
    item_500k = SmartTableWidgetItem("500 KB")
    item_2m = SmartTableWidgetItem("2 MB")
    item_10m = SmartTableWidgetItem("10 MB")

    assert item_500k < item_2m
    assert item_2m < item_10m
    assert not (item_10m < item_2m)

    # Números ("100" vs "25")
    item_25 = SmartTableWidgetItem("25")
    item_100 = SmartTableWidgetItem("100")
    assert item_25 < item_100
    assert not (item_100 < item_25)

    # Texto
    item_a = SmartTableWidgetItem("Abacaxi")
    item_b = SmartTableWidgetItem("banana")
    assert item_a < item_b


def test_sortable_table_sorting_and_user_data_integrity():
    """
    Teste de caixa preta:
    1. Preenche a tabela com 3 registros desordenados.
    2. Ordena por tamanho de arquivo de forma ascendente e descendente.
    3. Confere a ordem física das células e comprova que os dados associados
       (user_data) continuam perfeitamente ligados aos seus respectivos itens.
    """
    _get_app()

    table = SortableTableWidget(0, 3)
    records = [
        {"id": 1, "name": "Video.mp4", "size": "500 MB", "bytes": 500 * 1024 * 1024},
        {"id": 2, "name": "Doc.pdf", "size": "2 MB", "bytes": 2 * 1024 * 1024},
        {"id": 3, "name": "Backup.zip", "size": "4 GB", "bytes": 4 * 1024 * 1024 * 1024},
    ]

    with table.updating():
        table.setRowCount(len(records))
        for r, rec in enumerate(records):
            table.set_cell(r, 0, rec["name"], user_data=rec)
            table.set_cell(r, 1, rec["size"], sort_value=rec["bytes"])
            table.set_cell(r, 2, rec["id"])

    # Ordenação Ascendente por Tamanho (Coluna 1)
    table.sortItems(1, Qt.AscendingOrder)
    assert table.item(0, 0).text() == "Doc.pdf"
    assert table.item(1, 0).text() == "Video.mp4"
    assert table.item(2, 0).text() == "Backup.zip"

    # Validação de integridade do dado associado (não deve ser o ID original da linha 0, mas sim o rec do Doc.pdf)
    assert table.get_row_data(0, col=0) == records[1]  # Doc.pdf
    assert table.get_row_data(1, col=0) == records[0]  # Video.mp4
    assert table.get_row_data(2, col=0) == records[2]  # Backup.zip

    # Ordenação Descendente por Tamanho (Coluna 1)
    table.sortItems(1, Qt.DescendingOrder)
    assert table.item(0, 0).text() == "Backup.zip"
    assert table.item(1, 0).text() == "Video.mp4"
    assert table.item(2, 0).text() == "Doc.pdf"
    assert table.get_row_data(0, col=0) == records[2]  # Backup.zip

    # Ordenação Alfabética por Nome (Coluna 0)
    table.sortItems(0, Qt.AscendingOrder)
    assert table.item(0, 0).text() == "Backup.zip"
    assert table.item(1, 0).text() == "Doc.pdf"
    assert table.item(2, 0).text() == "Video.mp4"


def test_batch_table_update_and_enable_sorting():
    """Valida os helpers de compatibilidade para QTableWidget comum."""
    _get_app()

    from PySide6.QtWidgets import QTableWidget
    legacy_table = QTableWidget(0, 2)
    enable_sorting_on_table(legacy_table)
    assert legacy_table.isSortingEnabled() is True
    assert legacy_table.horizontalHeader().isSortIndicatorShown() is True

    # Preenchimento em lote com batch_table_update
    items = [("Zebra", 10), ("Antílope", 50), ("Macaco", 2)]
    with batch_table_update(legacy_table):
        # Durante o contexto, sorting deve estar desativado
        assert legacy_table.isSortingEnabled() is False
        legacy_table.setRowCount(len(items))
        for r, (animal, qty) in enumerate(items):
            legacy_table.setItem(r, 0, SmartTableWidgetItem(animal))
            legacy_table.setItem(r, 1, SmartTableWidgetItem(str(qty), sort_value=qty))

    # Após o bloco, sorting deve ser reativado automaticamente
    assert legacy_table.isSortingEnabled() is True

    # Ordenação numérica da coluna 1
    legacy_table.sortItems(1, Qt.AscendingOrder)
    assert legacy_table.item(0, 0).text() == "Macaco"
    assert legacy_table.item(1, 0).text() == "Zebra"
    assert legacy_table.item(2, 0).text() == "Antílope"

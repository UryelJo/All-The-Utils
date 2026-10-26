"""
Componentes e utilitários de ordenação inteligente para QTableWidget e DataTableView.

Resolve os 3 problemas clássicos do QTableWidget no Qt:
  1. Ordenação lexicográfica vs numérica ("10 MB" antes de "2 MB", "100" antes de "25").
     SmartTableWidgetItem compara valores tipados brutos (int, float, bytes, datetime)
     através de sobrescrita de __lt__ e fallback com parsing automático de tamanhos e números.
  2. Dessincronização de índices Python ao ordenar linhas na interface:
     Armazena o objeto ou dicionário real no próprio item (Qt.UserRole). Métodos seguros
     como get_selected_data() e get_row_data() garantem que ações (abrir, excluir, copiar)
     operem SEMPRE no registro correto, independente de cliques de ordenação.
  3. Reordenação prematura e lentidão a cada setItem():
     O context manager table.updating() ou métodos begin_update() e end_update()
     desativam a ordenação durante a inserção e restauram a ordenação ativa ao finalizar.
"""
from contextlib import contextmanager
import re
from typing import Any, Generator, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

# Padrão para detecção e conversão de tamanhos de arquivo em bytes: "12.5 MB", "500 KB", "1.2 GB"
_SIZE_RE = re.compile(r"^([\d.,]+)\s*([KMGTPE]?B)$", re.IGNORECASE)
_UNIT_MULTIPLIERS = {
    "B": 1,
    "KB": 1024,
    "MB": 1024 ** 2,
    "GB": 1024 ** 3,
    "TB": 1024 ** 4,
    "PB": 1024 ** 5,
}


def _clean_number_str(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    # Se tem tanto ponto quanto vírgula
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if s.count(",") == 1:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "." in s:
        if s.count(".") > 1:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_sort_key(value: Any) -> Any:
    """Extrai uma chave comparável para ordenação natural e numérica."""
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, bool):
        return int(value)

    # Strings: tentar converter tamanho ("10.5 MB"), número ("1.234,50" ou "123.45") ou texto
    s = str(value).strip()
    if not s or s == "-":
        return -float("inf")  # valores vazios/nulos ordenam no início/fim de forma consistente

    # 1. Tamanho em bytes/KB/MB/GB
    m = _SIZE_RE.match(s)
    if m:
        num_val = _clean_number_str(m.group(1))
        if num_val is not None:
            unit = m.group(2).upper()
            return num_val * _UNIT_MULTIPLIERS.get(unit, 1)

    # 2. Número decimal simples ou formatado
    num_val = _clean_number_str(s)
    if num_val is not None:
        return num_val

    # 3. Fallback string case-insensitive
    return s.lower()


class SmartTableWidgetItem(QTableWidgetItem):
    """
    QTableWidgetItem com suporte a ordenação natural por tipo real ou custom sort_key,
    e armazenamento seguro de dados de entidade no Qt.UserRole.
    """

    def __init__(self, text: str = "", sort_value: Any = None, user_data: Any = None):
        super().__init__(str(text) if text is not None else "")
        self._sort_value = sort_value
        if user_data is not None:
            self.setData(Qt.UserRole, user_data)

    @property
    def sort_value(self) -> Any:
        if self._sort_value is not None:
            return self._sort_value
        # Se não fornecido explicitamente, infere do texto exibido
        return parse_sort_key(self.text())

    @sort_value.setter
    def sort_value(self, val: Any) -> None:
        self._sort_value = val

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, SmartTableWidgetItem):
            v1, v2 = self.sort_value, other.sort_value
        elif isinstance(other, QTableWidgetItem):
            v1, v2 = self.sort_value, parse_sort_key(other.text())
        else:
            return super().__lt__(other)

        # Se tipos forem compatíveis para comparação direta
        try:
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                return v1 < v2
            if isinstance(v1, type(v2)):
                return v1 < v2
            # Tipos heterogêneos: converte para str como fallback seguro
            return str(v1) < str(v2)
        except TypeError:
            return str(v1) < str(v2)


class SortableTableWidget(QTableWidget):
    """
    QTableWidget pronto com ordenação segura, indicadores visuais nas colunas
    e contexto de atualização de dados em lote.
    """

    def __init__(self, rows: int = 0, columns: int = 0, parent: Optional[Any] = None):
        super().__init__(rows, columns, parent)
        self._setup_sorting()

    def _setup_sorting(self) -> None:
        self.setSortingEnabled(True)
        hh = self.horizontalHeader()
        hh.setSortIndicatorShown(True)
        hh.setSectionsClickable(True)
        self._sorting_enabled_flag = True

    @contextmanager
    def updating(self) -> Generator[None, None, None]:
        """
        Desativa ordenação temporariamente durante o preenchimento de linhas,
        evitando reordenações a cada setItem() e preservando performance.
        Restaura o estado e reaplica a ordenação ativa ao sair do bloco.
        """
        was_enabled = self.isSortingEnabled()
        if was_enabled:
            self.setSortingEnabled(False)
        try:
            yield
        finally:
            if was_enabled:
                self.setSortingEnabled(True)

    def set_cell(
        self,
        row: int,
        col: int,
        text: Any,
        sort_value: Any = None,
        user_data: Any = None,
        align: Optional[int] = None,
    ) -> SmartTableWidgetItem:
        """Cria e atribui um SmartTableWidgetItem configurado."""
        item = SmartTableWidgetItem(str(text) if text is not None else "", sort_value=sort_value, user_data=user_data)
        if align is not None:
            item.setTextAlignment(align)
        self.setItem(row, col, item)
        return item

    def get_selected_data(self, col: int = 0, role: int = Qt.UserRole) -> Optional[Any]:
        """
        Retorna os dados (user_data) da linha atualmente selecionada,
        independentemente da ordem em que as linhas foram reordenadas.
        """
        row = self.currentRow()
        if row < 0:
            selected = self.selectedItems()
            if not selected:
                return None
            row = selected[0].row()
        item = self.item(row, col)
        return item.data(role) if item else None

    def get_row_data(self, row: int, col: int = 0, role: int = Qt.UserRole) -> Optional[Any]:
        """Retorna os dados (user_data) da linha especificada."""
        item = self.item(row, col)
        return item.data(role) if item else None

    def get_all_selected_data(self, col: int = 0, role: int = Qt.UserRole) -> List[Any]:
        """Retorna lista de dados (user_data) de todas as linhas selecionadas."""
        rows = {item.row() for item in self.selectedItems()}
        out = []
        for r in sorted(rows):
            item = self.item(r, col)
            if item:
                d = item.data(role)
                if d is not None:
                    out.append(d)
        return out


def enable_sorting_on_table(table: QTableWidget) -> None:
    """Configura ordenação e indicadores visuais em uma tabela QTableWidget existente."""
    table.setSortingEnabled(True)
    hh = table.horizontalHeader()
    hh.setSortIndicatorShown(True)
    hh.setSectionsClickable(True)


@contextmanager
def batch_table_update(table: QTableWidget) -> Generator[None, None, None]:
    """Context manager para atualizar qualquer QTableWidget com segurança."""
    was_enabled = table.isSortingEnabled()
    if was_enabled:
        table.setSortingEnabled(False)
    try:
        yield
    finally:
        if was_enabled:
            table.setSortingEnabled(True)

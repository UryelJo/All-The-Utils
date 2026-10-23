"""
Tabelas de dados de alto desempenho (Model/View) reutilizáveis.

Por que não QTableWidget: cada atualização recriava milhares de QTableWidgetItem,
recalculava colunas ResizeToContents e perdia seleção/rolagem. Aqui:
  - RecordTableModel guarda dicts e aplica atualizações incrementais por chave
    (dataChanged/insert/remove), preservando seleção e posição de rolagem;
  - RecordFilterProxy filtra e ordena localmente (sem reconsultar o Windows a cada tecla),
    ordenando números como números;
  - BackgroundLoader executa a consulta fora da thread da UI, sem sobrepor execuções;
  - bind_timer_to_visibility só deixa timers de atualização rodando com a tela visível.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from PySide6.QtCore import (
    QAbstractTableModel, QEvent, QModelIndex, QObject, QSortFilterProxyModel, Qt, QTimer, Signal
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QWidget

from wintoolbox.core.logging_setup import get_logger

SORT_ROLE = Qt.UserRole + 1

_log = get_logger("ui.data_table")


@dataclass
class Column:
    """Definição de coluna: chave no dict, título, alinhamento e formatação opcional."""
    key: str
    title: str
    align: str = "left"  # 'left' | 'right' | 'center'
    fmt: Optional[Callable[[Any], str]] = None
    width: Optional[int] = None
    stretch: bool = False
    tooltip: bool = False


_PT_BR_DIGITS = str.maketrans({",": ".", ".": ","})


def fmt_number(decimals: int = 1, empty_if_zero: bool = False) -> Callable[[Any], str]:
    """Formatador numérico pt-BR para colunas: 1234.5 -> '1.234,5'."""
    def fmt(value: Any) -> str:
        if value is None or (empty_if_zero and not value):
            return "-"
        text = f"{value:,.{decimals}f}"
        return text.translate(_PT_BR_DIGITS)  # 1,234.5 -> 1.234,5
    return fmt


_ALIGN = {
    "left": int(Qt.AlignLeft | Qt.AlignVCenter),
    "right": int(Qt.AlignRight | Qt.AlignVCenter),
    "center": int(Qt.AlignCenter),
}


class RecordTableModel(QAbstractTableModel):
    """Modelo de tabela sobre uma lista de dicts, com atualização incremental por chave."""

    def __init__(self, columns: List[Column], key: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.columns = columns
        self.key = key
        self._rows: List[Dict[str, Any]] = []
        self._index: Dict[Any, int] = {}
        # Texto de busca por linha (id do dict -> texto); limpo a cada mudança de dados
        self._search_cache: Dict[int, str] = {}
        self.foreground: Optional[Callable[[Dict[str, Any], str], Optional[str]]] = None

    # -- API Qt --
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section: int, orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and 0 <= section < len(self.columns):
            return self.columns[section].title
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        rec = self._rows[index.row()]
        col = self.columns[index.column()]
        value = rec.get(col.key)
        if role == Qt.DisplayRole or (role == Qt.ToolTipRole and col.tooltip):
            return self.display_text(col, value)
        if role == SORT_ROLE:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
            return "" if value is None else str(value).lower()
        if role == Qt.TextAlignmentRole:
            return _ALIGN.get(col.align, _ALIGN["left"])
        if role == Qt.ForegroundRole and self.foreground:
            color = self.foreground(rec, col.key)
            return QColor(color) if color else None
        return None

    @staticmethod
    def display_text(col: Column, value: Any) -> str:
        if col.fmt:
            try:
                return col.fmt(value)
            except Exception:
                return str(value)
        return "" if value is None else str(value)

    # -- API de dados --
    def search_text(self, row: int) -> str:
        """Texto exibido de todas as colunas, em minúsculas (usado pelo filtro)."""
        rec = self._rows[row]
        text = self._search_cache.get(id(rec))
        if text is None:
            text = "".join(self.display_text(c, rec.get(c.key)) for c in self.columns).lower()
            self._search_cache[id(rec)] = text
        return text

    def record_at(self, row: int) -> Optional[Dict[str, Any]]:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def records(self) -> List[Dict[str, Any]]:
        return list(self._rows)

    def clear(self) -> None:
        self._search_cache.clear()
        self.beginResetModel()
        self._rows, self._index = [], {}
        self.endResetModel()

    def set_records(self, records: Iterable[Dict[str, Any]]) -> None:
        """Substitui os dados. Com 'key', aplica só as diferenças (mantém seleção e rolagem)."""
        records = list(records)
        self._search_cache.clear()
        if self.key is None or not self._rows:
            self.beginResetModel()
            self._rows = records
            self._rebuild_index()
            self.endResetModel()
            return

        key = self.key
        new_keys = {r.get(key) for r in records}

        # 1. Remoções em blocos contíguos, de baixo para cima
        removed = [i for i, r in enumerate(self._rows) if r.get(key) not in new_keys]
        for start, end in reversed(_ranges(removed)):
            self.beginRemoveRows(QModelIndex(), start, end)
            del self._rows[start:end + 1]
            self.endRemoveRows()
        if removed:
            self._rebuild_index()

        # 2. Atualizações no lugar + coleta das novas linhas
        first_changed, last_changed = None, None
        appended: List[Dict[str, Any]] = []
        for rec in records:
            row = self._index.get(rec.get(key))
            if row is None:
                appended.append(rec)
            elif self._rows[row] != rec:
                self._rows[row] = rec
                first_changed = row if first_changed is None else min(first_changed, row)
                last_changed = row if last_changed is None else max(last_changed, row)
        if first_changed is not None:
            self.dataChanged.emit(self.index(first_changed, 0), self.index(last_changed, len(self.columns) - 1))

        # 3. Inserções no fim
        if appended:
            start = len(self._rows)
            self.beginInsertRows(QModelIndex(), start, start + len(appended) - 1)
            self._rows.extend(appended)
            for i, rec in enumerate(appended, start):
                self._index[rec.get(key)] = i
            self.endInsertRows()

    def append_records(self, records: List[Dict[str, Any]], max_rows: Optional[int] = None) -> None:
        """Acrescenta linhas (ex: log ao vivo), descartando as mais antigas acima de max_rows."""
        if not records:
            return
        self._search_cache.clear()
        if max_rows and len(self._rows) + len(records) > max_rows:
            overflow = len(self._rows) + len(records) - max_rows
            overflow = min(overflow, len(self._rows))
            if overflow:
                self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
                del self._rows[:overflow]
                self.endRemoveRows()
        start = len(self._rows)
        self.beginInsertRows(QModelIndex(), start, start + len(records) - 1)
        self._rows.extend(records)
        self.endInsertRows()
        if self.key is not None:
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._index = {r.get(self.key): i for i, r in enumerate(self._rows)} if self.key else {}


def _ranges(indices: List[int]) -> List[tuple]:
    """[1,2,3,7,8] -> [(1,3),(7,8)]"""
    out: List[tuple] = []
    for i in indices:
        if out and out[-1][1] == i - 1:
            out[-1] = (out[-1][0], i)
        else:
            out.append((i, i))
    return out


class RecordFilterProxy(QSortFilterProxyModel):
    """Filtro de texto em todas as colunas + predicado opcional, com ordenação por valor bruto."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._needle = ""
        self._predicate: Optional[Callable[[Dict[str, Any]], bool]] = None
        self.setSortRole(SORT_ROLE)
        self.setDynamicSortFilter(True)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def set_text_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        if needle != self._needle:
            self._change_filter(lambda: setattr(self, "_needle", needle))

    def set_predicate(self, predicate: Optional[Callable[[Dict[str, Any]], bool]]) -> None:
        self._change_filter(lambda: setattr(self, "_predicate", predicate))

    def _change_filter(self, mutate: Callable[[], None]) -> None:
        # Qt 6.10+ depreciou invalidateFilter()/invalidateRowsFilter() em favor deste par
        if hasattr(self, "beginFilterChange"):
            self.beginFilterChange()
            mutate()
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:
            mutate()
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model: RecordTableModel = self.sourceModel()
        rec = model.record_at(source_row)
        if rec is None:
            return False
        if self._predicate is not None and not self._predicate(rec):
            return False
        if not self._needle:
            return True
        return self._needle in model.search_text(source_row)


class DataTableView(QTableView):
    """QTableView configurada para listas grandes: ordenável, linhas de altura fixa, sem auto-resize."""

    def __init__(self, columns: List[Column], key: Optional[str] = None, parent: Optional[QWidget] = None,
                 multi_select: bool = False):
        super().__init__(parent)
        self.source_model = RecordTableModel(columns, key=key, parent=self)
        self.proxy = RecordFilterProxy(self)
        self.proxy.setSourceModel(self.source_model)
        self.setModel(self.proxy)

        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection if multi_select else QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(QHeaderView.Fixed)  # evita medir a altura de cada linha
        vh.setDefaultSectionSize(26)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setHighlightSections(False)
        hh.setSortIndicatorShown(True)
        stretch_set = False
        for i, col in enumerate(columns):
            if col.width:
                self.setColumnWidth(i, col.width)
            if col.stretch and not stretch_set:
                hh.setSectionResizeMode(i, QHeaderView.Stretch)
                stretch_set = True
        if not stretch_set:
            hh.setStretchLastSection(True)

    def set_records(self, records: Iterable[Dict[str, Any]]) -> None:
        self.source_model.set_records(records)

    def current_record(self) -> Optional[Dict[str, Any]]:
        idx = self.currentIndex()
        if not idx.isValid() or not self.selectionModel().isRowSelected(idx.row(), QModelIndex()):
            rows = self.selectionModel().selectedRows()
            if not rows:
                return None
            idx = rows[0]
        return self.source_model.record_at(self.proxy.mapToSource(idx).row())

    def selected_records(self) -> List[Dict[str, Any]]:
        out = []
        for idx in self.selectionModel().selectedRows():
            rec = self.source_model.record_at(self.proxy.mapToSource(idx).row())
            if rec is not None:
                out.append(rec)
        return out

    def visible_count(self) -> int:
        return self.proxy.rowCount()


class BackgroundLoader(QObject):
    """
    Executa uma função de consulta numa thread do pool e entrega o resultado na thread da UI.
    Pedidos feitos enquanto uma execução está em andamento são agrupados em uma única repetição.
    """
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], Any], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._fn = fn
        self._busy = False
        self._pending = False

    @property
    def busy(self) -> bool:
        return self._busy

    def request(self) -> None:
        if self._busy:
            self._pending = True
            return
        self._busy = True
        from wintoolbox.core.tasks import run_task
        run_task(lambda ctx: self._fn(), on_done=self._on_done)

    def _on_done(self, result: Any, exc: Optional[Exception]) -> None:
        self._busy = False
        if exc is not None:
            _log.warning("Falha ao carregar dados de %s: %s", getattr(self._fn, "__qualname__", self._fn), exc)
            self.failed.emit(str(exc))
        else:
            self.loaded.emit(result)
        if self._pending:
            self._pending = False
            self.request()


class _VisibilityTimerBinder(QObject):
    def __init__(self, widget: QWidget, timer: QTimer, interval_ms: int, on_show: Optional[Callable[[], None]]):
        super().__init__(widget)
        self._timer, self._interval, self._on_show = timer, interval_ms, on_show
        widget.installEventFilter(self)
        if widget.isVisible():
            timer.start(interval_ms)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Show:
            if not self._timer.isActive():
                self._timer.start(self._interval)
                if self._on_show:
                    self._on_show()
        elif event.type() == QEvent.Hide:
            self._timer.stop()
        return False


def bind_timer_to_visibility(widget: QWidget, timer: QTimer, interval_ms: int,
                             on_show: Optional[Callable[[], None]] = None) -> None:
    """
    Liga o timer só enquanto o widget está visível. As telas ficam em cache na janela
    principal: sem isso, um timer de atualização seguia consumindo CPU após sair da tela
    (ou com o app minimizado na bandeja).
    """
    _VisibilityTimerBinder(widget, timer, interval_ms, on_show)

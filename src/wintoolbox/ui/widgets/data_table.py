"""
Tabelas de dados de alto desempenho (Model/View) reutilizáveis.

Por que não QTableWidget: cada atualização recriava milhares de QTableWidgetItem,
recalculava colunas ResizeToContents e perdia seleção/rolagem. Aqui:
  - RecordTableModel guarda dicts e aplica atualizações incrementais por chave
    (dataChanged/insert/remove), preservando seleção, checkboxes e posição de rolagem;
  - RecordFilterProxy filtra e ordena localmente (sem reconsultar o Windows a cada tecla),
    ordenando números como números;
  - BackgroundLoader executa a consulta fora da thread da UI, sem sobrepor execuções;
  - bind_timer_to_visibility só deixa timers de atualização rodando com a tela visível.
"""
from dataclasses import dataclass
import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from PySide6.QtCore import (
    QAbstractTableModel, QEvent, QFileInfo, QModelIndex, QObject, QSortFilterProxyModel, Qt, QTimer, Signal
)
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileIconProvider, QHeaderView, QStyle, QTableView, QWidget
)

from wintoolbox.core.logging_setup import get_logger

SORT_ROLE = Qt.UserRole + 1

_log = get_logger("ui.data_table")

_ICON_PROVIDER: Optional[QFileIconProvider] = None
_ICON_CACHE: Dict[str, Optional[QIcon]] = {}


def get_file_icon(path_str: Optional[str], fallback_app_icon: bool = True) -> Optional[QIcon]:
    """
    Obtém e armazena em cache o ícone nativo do Windows para um executável/arquivo.
    Caso o caminho não exista ou seja inacessível, retorna ícone padrão de executável se fallback_app_icon=True.
    """
    global _ICON_PROVIDER
    app = QApplication.instance()
    if app is None:
        return None

    clean_path = (path_str or "").strip().strip('"')
    # Remove índice de ícone do registro se presente (ex: "C:\\app.exe,0")
    if "," in clean_path and not os.path.exists(clean_path):
        clean_path = clean_path.rsplit(",", 1)[0].strip().strip('"')

    cache_key = clean_path.lower() if clean_path else ("__fallback__" if fallback_app_icon else "__none__")
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    icon: Optional[QIcon] = None
    try:
        if _ICON_PROVIDER is None:
            _ICON_PROVIDER = QFileIconProvider()
        if clean_path and os.path.exists(clean_path):
            fi = QFileInfo(clean_path)
            ic = _ICON_PROVIDER.icon(fi)
            if not ic.isNull():
                icon = ic
    except Exception:
        icon = None

    if icon is None and fallback_app_icon:
        try:
            style = QApplication.style()
            if style is not None:
                icon = style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        except Exception:
            icon = None

    if len(_ICON_CACHE) < 2048:
        _ICON_CACHE[cache_key] = icon
    return icon


@dataclass
class Column:
    """Definição de coluna: chave no dict, título, alinhamento, ícone e formatação opcional."""
    key: str
    title: str
    align: str = "left"  # 'left' | 'right' | 'center'
    fmt: Optional[Callable[[Any], str]] = None
    width: Optional[int] = None
    stretch: bool = False
    tooltip: bool = False
    icon_key: Optional[str] = None
    fallback_icon: bool = True


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

    checkedChanged = Signal(int)

    def __init__(
        self,
        columns: List[Column],
        key: Optional[str] = None,
        parent: Optional[QObject] = None,
        checkable: bool = False,
    ):
        super().__init__(parent)
        self.columns = columns
        self.key = key
        self.checkable = checkable
        self._rows: List[Dict[str, Any]] = []
        self._index: Dict[Any, int] = {}
        self._checked_keys: Set[Any] = set()
        # Texto de busca por linha (id do dict -> texto); limpo a cada mudança de dados
        self._search_cache: Dict[int, str] = {}
        self.foreground: Optional[Callable[[Dict[str, Any], str], Optional[str]]] = None

    def _row_key(self, row: int) -> Any:
        if 0 <= row < len(self._rows):
            rec = self._rows[row]
            return rec.get(self.key) if self.key else id(rec)
        return None

    # -- API Qt --
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section: int, orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and 0 <= section < len(self.columns):
            return self.columns[section].title
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self.checkable and index.column() == 0:
            base |= Qt.ItemIsUserCheckable
        return base

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        rec = self._rows[index.row()]
        col = self.columns[index.column()]
        value = rec.get(col.key)
        if role == Qt.CheckStateRole and self.checkable and index.column() == 0:
            rk = self._row_key(index.row())
            return Qt.Checked if rk in self._checked_keys else Qt.Unchecked
        if role == Qt.DecorationRole and col.icon_key is not None:
            return get_file_icon(rec.get(col.icon_key), fallback_app_icon=col.fallback_icon)
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

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        if self.checkable and index.column() == 0 and role == Qt.CheckStateRole:
            rk = self._row_key(index.row())
            if rk is None:
                return False
            # Em PySide6, value pode vir como Qt.CheckState ou int (2 = Checked, 0 = Unchecked)
            is_checked = (value == Qt.Checked or value == Qt.CheckState.Checked or value == 2)
            if is_checked:
                self._checked_keys.add(rk)
            else:
                self._checked_keys.discard(rk)
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            self.checkedChanged.emit(len(self._checked_keys))
            return True
        return False

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
            text = " ".join(self.display_text(c, rec.get(c.key)) for c in self.columns).lower()
            self._search_cache[id(rec)] = text
        return text

    def record_at(self, row: int) -> Optional[Dict[str, Any]]:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def records(self) -> List[Dict[str, Any]]:
        return list(self._rows)

    def checked_records(self) -> List[Dict[str, Any]]:
        if not self._checked_keys:
            return []
        out: List[Dict[str, Any]] = []
        for i, rec in enumerate(self._rows):
            rk = rec.get(self.key) if self.key else id(rec)
            if rk in self._checked_keys:
                out.append(rec)
        return out

    def clear_checked(self) -> None:
        if not self._checked_keys:
            return
        self._checked_keys.clear()
        if self._rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, 0), [Qt.CheckStateRole])
        self.checkedChanged.emit(0)

    def clear(self) -> None:
        self._search_cache.clear()
        self._checked_keys.clear()
        self.beginResetModel()
        self._rows, self._index = [], {}
        self.endResetModel()
        self.checkedChanged.emit(0)

    def set_records(self, records: Iterable[Dict[str, Any]]) -> None:
        """Substitui os dados. Com 'key', aplica só as diferenças (mantém seleção, checkboxes e rolagem)."""
        records = list(records)
        self._search_cache.clear()
        if self.key is None or not self._rows:
            self.beginResetModel()
            self._rows = records
            self._rebuild_index()
            if self.key is not None and self._checked_keys:
                valid = {r.get(self.key) for r in records}
                self._checked_keys &= valid
            self.endResetModel()
            self.checkedChanged.emit(len(self._checked_keys))
            return

        key = self.key
        new_keys = {r.get(key) for r in records}
        if self._checked_keys:
            self._checked_keys &= new_keys

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
        self.checkedChanged.emit(len(self._checked_keys))

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

    checkedChanged = Signal(int)

    def __init__(
        self,
        columns: List[Column],
        key: Optional[str] = None,
        parent: Optional[QWidget] = None,
        multi_select: bool = False,
        checkable: bool = False,
    ):
        super().__init__(parent)
        self.source_model = RecordTableModel(columns, key=key, parent=self, checkable=checkable)
        self.source_model.checkedChanged.connect(self.checkedChanged.emit)
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
        vh.setDefaultSectionSize(28)

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

    def record_at_pos(self, pos) -> Optional[Dict[str, Any]]:
        """Retorna o registro na posição de clique (ex: para menu de contexto)."""
        proxy_idx = self.indexAt(pos)
        if not proxy_idx.isValid():
            return None
        src_idx = self.proxy.mapToSource(proxy_idx)
        return self.source_model.record_at(src_idx.row())

    def selected_records(self) -> List[Dict[str, Any]]:
        out = []
        for idx in self.selectionModel().selectedRows():
            rec = self.source_model.record_at(self.proxy.mapToSource(idx).row())
            if rec is not None:
                out.append(rec)
        return out

    def checked_records(self) -> List[Dict[str, Any]]:
        """Retorna todos os registros marcados via checkbox."""
        return self.source_model.checked_records()

    def target_records(self) -> List[Dict[str, Any]]:
        """Retorna os registros marcados via checkbox; se nenhum estiver marcado, retorna o selecionado."""
        checked = self.checked_records()
        if checked:
            return checked
        selected = self.selected_records()
        if selected:
            return selected
        cur = self.current_record()
        return [cur] if cur else []

    def is_record_checked(self, rec: Dict[str, Any]) -> bool:
        rk = rec.get(self.source_model.key) if self.source_model.key else id(rec)
        return rk in self.source_model._checked_keys

    def set_record_checked(self, rec: Dict[str, Any], checked: bool = True) -> None:
        rk = rec.get(self.source_model.key) if self.source_model.key else id(rec)
        if rk is None:
            return
        if checked:
            self.source_model._checked_keys.add(rk)
        else:
            self.source_model._checked_keys.discard(rk)
        if self.source_model._rows:
            self.source_model.dataChanged.emit(
                self.source_model.index(0, 0),
                self.source_model.index(len(self.source_model._rows) - 1, 0),
                [Qt.CheckStateRole],
            )
        self.source_model.checkedChanged.emit(len(self.source_model._checked_keys))

    def toggle_record_checked(self, rec: Dict[str, Any]) -> bool:
        new_state = not self.is_record_checked(rec)
        self.set_record_checked(rec, new_state)
        return new_state

    def set_all_visible_checked(self, checked: bool) -> None:
        """Marca ou desmarca todas as linhas visíveis no filtro atual."""
        for r in range(self.proxy.rowCount()):
            src_idx = self.proxy.mapToSource(self.proxy.index(r, 0))
            rec = self.source_model.record_at(src_idx.row())
            if rec is not None:
                rk = rec.get(self.source_model.key) if self.source_model.key else id(rec)
                if checked:
                    self.source_model._checked_keys.add(rk)
                else:
                    self.source_model._checked_keys.discard(rk)
        if self.source_model._rows:
            self.source_model.dataChanged.emit(
                self.source_model.index(0, 0),
                self.source_model.index(len(self.source_model._rows) - 1, 0),
                [Qt.CheckStateRole],
            )
        self.source_model.checkedChanged.emit(len(self.source_model._checked_keys))

    def clear_checked(self) -> None:
        self.source_model.clear_checked()

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
            self.timer_stop()
        return False

    def timer_stop(self) -> None:
        self._timer.stop()


def bind_timer_to_visibility(widget: QWidget, timer: QTimer, interval_ms: int,
                             on_show: Optional[Callable[[], None]] = None) -> None:
    """
    Liga o timer só enquanto o widget está visível. As telas ficam em cache na janela
    principal: sem isso, um timer de atualização seguia consumindo CPU após sair da tela
    (ou com o app minimizado na bandeja).
    """
    _VisibilityTimerBinder(widget, timer, interval_ms, on_show)

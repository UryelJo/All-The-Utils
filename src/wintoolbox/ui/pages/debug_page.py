"""
Página de Depuração: central de logs ao vivo, verbosidade por biblioteca e diagnóstico do ambiente.
Pensada para testar o app em outros computadores: tudo pode ser exportado em um único .zip.
"""
import json
import logging
import os
import time
import zipfile
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from PySide6.QtCore import QModelIndex, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core import logging_setup as ls
from wintoolbox.core.settings import get_settings_dir, load_settings
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import BackgroundLoader, Column, DataTableView, bind_timer_to_visibility

_log = ls.get_logger("debug")

MAX_VIEW_ROWS = 5000
LEVEL_FILTERS = [("Todos os níveis", 0), ("INFO ou acima", logging.INFO), ("WARNING ou acima", logging.WARNING),
                 ("Somente erros", logging.ERROR)]

LOG_COLUMNS = [
    Column("time", "Hora", width=95),
    Column("level", "Nível", width=80),
    Column("logger", "Origem / Biblioteca", width=190, tooltip=True),
    Column("location", "Local (arquivo:linha)", width=230, tooltip=True),
    Column("message", "Mensagem", stretch=True, tooltip=True),
]

ENV_COLUMNS = [Column("key", "Item", width=220), Column("value", "Valor", stretch=True, tooltip=True)]


class DebugPage(QWidget):
    """Central de logs e diagnóstico."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # Limitado: enquanto a página está oculta os registros acumulam aqui
        self._pending: Deque[Dict[str, Any]] = deque(maxlen=MAX_VIEW_ROWS)
        self._handler = ls.get_memory_handler()
        self._known_origins: set = set()
        self._build_ui()

        if self._handler:
            self._handler.subscribe(self._pending.append)  # chamado de qualquer thread; deque é thread-safe
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_pending)
        bind_timer_to_visibility(self, self._flush_timer, 250, on_show=self._reload_from_buffer)
        self._reload_from_buffer()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(10)

        title = QLabel("Depuração e Logs")
        title.setProperty("class", "title")
        root.addWidget(title)
        desc = QLabel(
            "Logs de todo o aplicativo e das bibliotecas, com origem e local exato de cada erro. "
            f"Arquivo: {ls.get_log_file()}"
        )
        desc.setProperty("class", "secondary")
        desc.setWordWrap(True)
        desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(desc)

        tabs = QTabWidget()
        tabs.addTab(self._build_logs_tab(), "Logs ao Vivo")
        tabs.addTab(self._build_levels_tab(), "Verbosidade das Bibliotecas")
        tabs.addTab(self._build_env_tab(), "Ambiente e Diagnóstico")
        tabs.currentChanged.connect(lambda i: i == 2 and not self._env_loaded and self._env_loader.request())
        root.addWidget(tabs, stretch=1)

    def _build_logs_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.cmb_level = QComboBox()
        for label, lvl in LEVEL_FILTERS:
            self.cmb_level.addItem(label, lvl)
        self.cmb_level.setCurrentIndex(1)
        self.cmb_level.currentIndexChanged.connect(self._apply_filters)
        bar.addWidget(self.cmb_level)

        self.cmb_origin = QComboBox()
        self.cmb_origin.addItem("Todas as origens", "")
        self.cmb_origin.setMinimumWidth(190)
        self.cmb_origin.currentIndexChanged.connect(self._apply_filters)
        bar.addWidget(self.cmb_origin)

        self.txt_search = QLineEdit()
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setPlaceholderText("Buscar na mensagem, arquivo ou biblioteca...")
        self.txt_search.textChanged.connect(self._apply_filters)
        bar.addWidget(self.txt_search, stretch=1)

        self.chk_pause = QCheckBox("Pausar")
        bar.addWidget(self.chk_pause)
        self.chk_follow = QCheckBox("Seguir o fim")
        self.chk_follow.setChecked(True)
        bar.addWidget(self.chk_follow)
        lay.addLayout(bar)

        split = QSplitter(Qt.Vertical)
        self.table = DataTableView(LOG_COLUMNS, parent=self, multi_select=True)
        self.table.setSortingEnabled(False)
        self.table.proxy.sort(-1)  # desfaz a ordenação inicial: ordem cronológica de chegada
        self.table.horizontalHeader().setSortIndicatorShown(False)
        t = get_current_tokens()
        colors = {"WARNING": t.status_warning, "ERROR": t.status_danger, "CRITICAL": t.status_danger,
                  "DEBUG": t.text_muted}
        self.table.source_model.foreground = lambda rec, key: colors.get(rec["level"]) if key in ("level", "message") else None
        self.table.selectionModel().currentRowChanged.connect(self._show_details)
        split.addWidget(self.table)

        self.txt_details = QPlainTextEdit()
        self.txt_details.setReadOnly(True)
        self.txt_details.setPlaceholderText("Selecione um registro para ver a mensagem completa e o traceback.")
        self.txt_details.setStyleSheet("font-family: 'Cascadia Mono', Consolas, monospace; font-size: 12px;")
        split.addWidget(self.txt_details)
        split.setSizes([420, 160])
        lay.addWidget(split, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.lbl_count = QLabel("")
        self.lbl_count.setProperty("class", "secondary")
        actions.addWidget(self.lbl_count)
        actions.addStretch()
        for text, slot in (
            ("Gerar Eventos de Teste", self._emit_test_events),
            ("Copiar Selecionados", self._copy_selected),
            ("Limpar Visualização", self._clear_view),
            ("Abrir Pasta de Logs", lambda: os.startfile(str(ls.get_logs_dir()))),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            actions.addWidget(b)
        lay.addLayout(actions)
        return w

    def _build_levels_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        info = QLabel(
            "Defina quanto cada biblioteca registra. DEBUG mostra tudo (útil para investigar um problema "
            "em outro PC); WARNING mostra só avisos e erros. As alterações valem na hora e ficam salvas. "
            "Também é possível iniciar com '--debug' ou com a variável WINTOOLBOX_DEBUG=1."
        )
        info.setWordWrap(True)
        info.setProperty("class", "secondary")
        lay.addWidget(info)

        card = QFrame()
        card.setProperty("class", "card")
        form = QFormLayout(card)
        form.setContentsMargins(16, 14, 16, 14)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(8)
        self._level_combos: Dict[str, QComboBox] = {}
        current = ls.get_configured_levels()
        for name, label in ls.LIBRARY_LOGGERS:
            cmb = QComboBox()
            cmb.addItems(ls.LEVELS)
            cmb.setCurrentText(current.get(name, "WARNING"))
            cmb.setMinimumWidth(140)
            cmb.currentTextChanged.connect(self._on_level_changed)
            self._level_combos[name] = cmb
            lbl = QLabel(f"{label}")
            lbl.setToolTip(f"logger: {name}")
            form.addRow(lbl, cmb)
        lay.addWidget(card)

        row = QHBoxLayout()
        b_all = QPushButton("Modo Detalhado (tudo em DEBUG)")
        b_all.clicked.connect(lambda: self._set_all_levels("DEBUG"))
        row.addWidget(b_all)
        b_reset = QPushButton("Restaurar Padrões")
        b_reset.clicked.connect(lambda: self._set_levels(dict(ls.DEFAULT_LEVELS)))
        row.addWidget(b_reset)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch()
        return w

    def _build_env_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self._env_loaded = False
        self._env_loader = BackgroundLoader(ls.collect_environment_info, self)
        self._env_loader.loaded.connect(self._on_env_loaded)

        self.env_table = DataTableView(ENV_COLUMNS, key="key", parent=self)
        self.env_table.setSortingEnabled(False)
        self.env_table.proxy.sort(-1)
        self.env_table.horizontalHeader().setSortIndicatorShown(False)
        lay.addWidget(self.env_table, stretch=1)

        row = QHBoxLayout()
        b_refresh = QPushButton("Atualizar")
        b_refresh.clicked.connect(self._env_loader.request)
        row.addWidget(b_refresh)
        b_copy = QPushButton("Copiar Relatório")
        b_copy.clicked.connect(self._copy_env)
        row.addWidget(b_copy)
        row.addStretch()
        b_zip = QPushButton("Exportar Pacote de Diagnóstico (.zip)")
        b_zip.setProperty("class", "primary")
        b_zip.clicked.connect(self._export_bundle)
        row.addWidget(b_zip)
        lay.addLayout(row)
        return w

    # ------------------------------------------------------------- Logs
    def _reload_from_buffer(self) -> None:
        self._pending.clear()
        records = list(self._handler.records) if self._handler else []
        self.table.source_model.clear()
        self._add_records(records[-MAX_VIEW_ROWS:])

    def _flush_pending(self) -> None:
        if self.chk_pause.isChecked() or not self._pending:
            return
        batch = []
        while self._pending and len(batch) < 2000:
            batch.append(self._pending.popleft())
        self._add_records(batch)

    def _add_records(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            self._update_count()
            return
        for rec in records:
            root_name = rec["logger"].split(".")[0]
            origin = rec["logger"] if root_name == ls.APP_LOGGER else root_name
            if origin not in self._known_origins:
                self._known_origins.add(origin)
                self.cmb_origin.addItem(origin, origin)
        self.table.source_model.append_records(records, max_rows=MAX_VIEW_ROWS)
        if self.chk_follow.isChecked():
            self.table.scrollToBottom()
        self._update_count()

    def _apply_filters(self) -> None:
        min_level = self.cmb_level.currentData() or 0
        origin = self.cmb_origin.currentData() or ""

        def predicate(rec: Dict[str, Any]) -> bool:
            if rec["levelno"] < min_level:
                return False
            return not origin or rec["logger"] == origin or rec["logger"].startswith(origin + ".")

        self.table.proxy.set_predicate(predicate)
        self.table.proxy.set_text_filter(self.txt_search.text())
        self._update_count()

    def _update_count(self) -> None:
        total = self.table.source_model.rowCount()
        shown = self.table.visible_count()
        self.lbl_count.setText(f"{shown} de {total} registros")

    def _show_details(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            self.txt_details.clear()
            return
        rec = self.table.source_model.record_at(self.table.proxy.mapToSource(current).row())
        if rec:
            self.txt_details.setPlainText(self._format_record(rec))

    @staticmethod
    def _format_record(rec: Dict[str, Any]) -> str:
        text = (f"[{rec['time']}] {rec['level']}  {rec['logger']}  ({rec['location']})  thread={rec['thread']}\n"
                f"{rec['message']}")
        if rec.get("details"):
            text += f"\n\n{rec['details']}"
        return text

    def _copy_selected(self) -> None:
        recs = self.table.selected_records()
        if recs:
            QApplication.clipboard().setText("\n\n".join(self._format_record(r) for r in recs))

    def _clear_view(self) -> None:
        self.table.source_model.clear()
        self.txt_details.clear()
        self._update_count()

    def _emit_test_events(self) -> None:
        """Gera um registro de cada tipo para validar a captura em outro computador."""
        from wintoolbox.core.tasks import run_task
        _log.debug("Evento de teste: DEBUG")
        _log.info("Evento de teste: INFO")
        _log.warning("Evento de teste: WARNING")
        logging.getLogger("PIL").warning("Evento de teste vindo da biblioteca Pillow")

        def failing_task(ctx):
            raise RuntimeError("Erro de teste lançado em uma tarefa em segundo plano")

        run_task(failing_task)

    # --------------------------------------------------------- Verbosidade
    def _on_level_changed(self, _text: str) -> None:
        ls.apply_levels({name: cmb.currentText() for name, cmb in self._level_combos.items()}, persist=True)

    def _set_levels(self, levels: Dict[str, str]) -> None:
        for name, cmb in self._level_combos.items():
            cmb.blockSignals(True)
            cmb.setCurrentText(levels.get(name, "WARNING"))
            cmb.blockSignals(False)
        self._on_level_changed("")

    def _set_all_levels(self, level: str) -> None:
        self._set_levels({name: level for name in self._level_combos})

    # ------------------------------------------------------------ Ambiente
    def _on_env_loaded(self, info: Dict[str, str]) -> None:
        self._env_loaded = True
        self._env_info = info
        self.env_table.set_records([{"key": k, "value": v} for k, v in info.items()])

    def _env_report(self) -> str:
        info = getattr(self, "_env_info", None) or ls.collect_environment_info()
        return "\n".join(f"{k}: {v}" for k, v in info.items())

    def _copy_env(self) -> None:
        QApplication.clipboard().setText(self._env_report())

    def _export_bundle(self) -> None:
        default = Path.home() / "Desktop" / f"diagnostico_alltheutils_{time.strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Pacote de Diagnóstico", str(default), "ZIP (*.zip)")
        if not path:
            return
        try:
            export_diagnostics_bundle(Path(path), self._env_report())
            _log.info("Pacote de diagnóstico exportado: %s", path)
            QMessageBox.information(self, "Diagnóstico", f"Pacote gerado em:\n{path}")
        except Exception as e:
            _log.exception("Falha ao exportar pacote de diagnóstico")
            QMessageBox.critical(self, "Erro", f"Não foi possível gerar o pacote:\n{e}")


def export_diagnostics_bundle(target: Path, env_report: str) -> Path:
    """ZIP com ambiente, logs (inclusive rotacionados e crash.log) e configurações sem segredos."""
    for h in logging.getLogger().handlers:
        try:
            h.flush()
        except Exception:
            pass
    settings = load_settings()
    if isinstance(settings.get("api_tokens"), dict):
        settings["api_tokens"] = {k: "***" for k in settings["api_tokens"]}
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ambiente.txt", env_report)
        zf.writestr("configuracoes_sem_segredos.json", json.dumps(settings, indent=2, ensure_ascii=False))
        for f in sorted(ls.get_logs_dir().glob("*.log*")):
            zf.write(f, f"logs/{f.name}")
        hist = get_settings_dir() / "history.db"
        if hist.exists():
            zf.write(hist, "history.db")
    return target

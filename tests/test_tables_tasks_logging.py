"""
Testes do núcleo de desempenho e diagnóstico: entrega de tarefas em segundo plano,
modelo de tabela incremental, amostrador nativo de processos e captura de logs.
"""
import logging
import time

import psutil
from PySide6.QtCore import Qt

from wintoolbox.core.logging_setup import MemoryLogHandler
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.system.process_manager.logic import ProcessSampler
from wintoolbox.ui.widgets.data_table import Column, DataTableView


def test_run_task_delivers_result_of_slow_tasks(qtbot):
    """Regressão: sem referência forte ao worker, tarefas com mais de alguns ms nunca entregavam."""
    results = []
    for i in range(10):
        run_task(lambda ctx, i=i: (time.sleep(0.05), i)[1], on_done=lambda r, e: results.append((r, e)))
    qtbot.waitUntil(lambda: len(results) == 10, timeout=5000)
    assert sorted(r for r, _ in results) == list(range(10))
    assert all(e is None for _, e in results)


def test_record_model_incremental_update_keeps_rows(qtbot):
    view = DataTableView([Column("id", "ID"), Column("v", "Valor", align="right")], key="id")
    qtbot.addWidget(view)
    view.set_records([{"id": 1, "v": 10}, {"id": 2, "v": 20}, {"id": 3, "v": 30}])
    view.selectRow(view.proxy.mapFromSource(view.source_model.index(1, 0)).row())
    assert view.current_record()["id"] == 2

    # remove 1, altera 2, adiciona 4
    view.set_records([{"id": 2, "v": 25}, {"id": 3, "v": 30}, {"id": 4, "v": 40}])
    model = view.source_model
    assert model.rowCount() == 3
    assert {model.record_at(r)["id"] for r in range(3)} == {2, 3, 4}
    assert view.current_record() == {"id": 2, "v": 25}  # seleção preservada e atualizada


def test_filter_proxy_text_predicate_and_numeric_sort(qtbot):
    view = DataTableView([Column("name", "Nome"), Column("mem", "Memória", fmt=lambda v: f"{v:.1f}")], key="name")
    qtbot.addWidget(view)
    view.set_records([{"name": "chrome.exe", "mem": 9.0}, {"name": "Code.exe", "mem": 100.0},
                      {"name": "chromedriver", "mem": 50.0}])
    view.proxy.set_text_filter("CHROME")
    assert view.visible_count() == 2
    view.proxy.set_predicate(lambda r: r["mem"] > 10)
    assert view.visible_count() == 1
    view.proxy.set_text_filter("")
    view.proxy.set_predicate(None)
    view.sortByColumn(1, Qt.DescendingOrder)  # decrescente: 100 > 50 > 9 (como número, não como texto)
    names = [view.proxy.index(r, 0).data() for r in range(view.visible_count())]
    assert names == ["Code.exe", "chromedriver", "chrome.exe"]


def test_process_sampler_matches_system_and_computes_cpu():
    sampler = ProcessSampler()
    first = sampler.sample()
    time.sleep(0.3)
    second = sampler.sample()
    pids = {p["pid"] for p in second}
    assert abs(len(second) - len(psutil.pids())) <= 15
    assert psutil.Process().pid in pids
    assert all(p["memory_mb"] >= 0 and 0 <= p["cpu_percent"] <= 100 for p in second)
    assert len(first) > 0


def test_memory_log_handler_captures_location_and_traceback():
    handler = MemoryLogHandler(capacity=10)
    handler.setFormatter(logging.Formatter())
    log = logging.getLogger("wintoolbox.test_capture")
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    seen = []
    handler.subscribe(seen.append)
    try:
        try:
            raise ValueError("falha de teste")
        except ValueError:
            log.exception("erro capturado")
    finally:
        log.removeHandler(handler)
    rec = handler.records[-1]
    assert rec["level"] == "ERROR" and rec["logger"] == "wintoolbox.test_capture"
    assert "ValueError: falha de teste" in rec["details"]
    assert seen and seen[-1] is rec

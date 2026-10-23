"""
Gerenciador de Tarefas em Segundo Plano com Sinais Qt.
Garante que a UI nunca trave e nunca seja modificada fora da thread principal.
"""
from typing import Any, Callable, Dict, Optional
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from wintoolbox.core.registry import TaskContext, ToolResult

class WorkerSignals(QObject):
    """Sinais Qt emitidos pelo Worker para comunicação segura com a UI."""
    progress = Signal(int, int, str)   # (atual, total, mensagem)
    log = Signal(str, str)             # (nível, mensagem)
    finished = Signal(object)          # (ToolResult)
    error = Signal(str)                # (mensagem de erro)

class TaskWorker(QRunnable):
    """Executa uma função em segundo plano com controle de cancelamento e pausa."""
    def __init__(self, task_fn: Callable[[TaskContext], ToolResult]):
        super().__init__()
        self.task_fn = task_fn
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._is_paused = False

    def cancel(self):
        self._is_cancelled = True

    def pause(self):
        self._is_paused = True

    def resume(self):
        self._is_paused = False

    def is_paused(self) -> bool:
        return self._is_paused

    @Slot()
    def run(self):
        ctx = TaskContext(
            on_progress=lambda cur, tot, msg: self.signals.progress.emit(cur, tot, msg),
            on_log=lambda lvl, msg: self.signals.log.emit(lvl, msg),
            is_cancelled=lambda: self._is_cancelled,
            is_paused=lambda: self._is_paused
        )
        try:
            result = self.task_fn(ctx)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))

class TaskRunner:
    """Gerenciador de execução assíncrona usando QThreadPool."""
    def __init__(self, max_threads: Optional[int] = None):
        self.pool = QThreadPool.globalInstance()
        if max_threads:
            self.pool.setMaxThreadCount(max_threads)
        self.current_worker: Optional[TaskWorker] = None

    def start_task(
        self,
        task_fn: Callable[[TaskContext], ToolResult],
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_finished: Optional[Callable[[ToolResult], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ) -> TaskWorker:
        worker = TaskWorker(task_fn)
        if on_progress:
            worker.signals.progress.connect(on_progress)
        if on_log:
            worker.signals.log.connect(on_log)
        if on_finished:
            worker.signals.finished.connect(on_finished)
        if on_error:
            worker.signals.error.connect(on_error)

        self.current_worker = worker
        self.pool.start(worker)
        return worker

    def cancel_current(self):
        if self.current_worker:
            self.current_worker.cancel()

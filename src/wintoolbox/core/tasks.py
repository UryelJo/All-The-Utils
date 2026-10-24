"""
Gerenciador de Tarefas em Segundo Plano com Sinais Qt.
Garante que a UI nunca trave e nunca seja modificada fora da thread principal.
"""
import logging
from typing import Any, Callable, Dict, Optional, Set
from PySide6.QtCore import QObject, QThreadPool, Signal
from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import TaskContext, ToolResult

_log = get_logger("tasks")
_task_log = get_logger("task")
_LEVEL_MAP = {"WARN": logging.WARNING, "WARNING": logging.WARNING, "ERROR": logging.ERROR,
              "CRITICAL": logging.CRITICAL, "DEBUG": logging.DEBUG}


def _forward_task_log(level: str, message: str) -> None:
    """Espelha na central de logs as mensagens que as tarefas enviam aos painéis de log."""
    _task_log.log(_LEVEL_MAP.get(str(level).upper(), logging.INFO), message)

class WorkerSignals(QObject):
    """Sinais Qt emitidos pelo Worker para comunicação segura com a UI."""
    progress = Signal(int, int, str)   # (atual, total, mensagem)
    log = Signal(str, str)             # (nível, mensagem)
    finished = Signal(object)          # (ToolResult)
    error = Signal(str)                # (mensagem de erro)

class TaskWorker:
    """
    Executa uma função em segundo plano com controle de cancelamento e pausa.
    Não herda de QRunnable: o pool recebe o callable `run` (QThreadPool.start(callable)).
    Com QRunnable, o pool apagava o objeto C++ (autoDelete) enquanto o Python ainda o
    referenciava, gerando liberação dupla intermitente (0xC0000005).
    """
    def __init__(self, task_fn: Callable[[TaskContext], ToolResult]):
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

    def run(self):
        def on_log(lvl: str, msg: str) -> None:
            _forward_task_log(lvl, msg)
            self.signals.log.emit(lvl, msg)

        ctx = TaskContext(
            on_progress=lambda cur, tot, msg: self.signals.progress.emit(cur, tot, msg),
            on_log=on_log,
            is_cancelled=lambda: self._is_cancelled,
            is_paused=lambda: self._is_paused
        )
        name = getattr(self.task_fn, "__qualname__", repr(self.task_fn))
        try:
            result = self.task_fn(ctx)
            self.signals.finished.emit(result)
        except Exception as e:
            # Traceback completo na central de logs; a UI continua recebendo a mensagem curta
            _log.exception("Falha na tarefa em segundo plano '%s'", name)
            self.signals.error.emit(f"{type(e).__name__}: {e}")

# Workers em execução: mantêm os sinais vivos até a entrega do resultado. Sem esta referência,
# quando ninguém guardava o TaskRunner (run_task) ou um novo start_task substituía
# current_worker, os sinais eram coletados e o resultado nunca chegava à UI.
_ACTIVE_WORKERS: Set["TaskWorker"] = set()


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

        # Mantém o worker (e seus sinais) vivo até a entrega do resultado. Conectado por
        # último para rodar depois dos callbacks do chamador.
        _ACTIVE_WORKERS.add(worker)
        worker.signals.finished.connect(lambda _res, w=worker: _ACTIVE_WORKERS.discard(w))
        worker.signals.error.connect(lambda _err, w=worker: _ACTIVE_WORKERS.discard(w))

        self.current_worker = worker
        self.pool.start(worker.run)
        return worker

    def cancel_current(self):
        if self.current_worker:
            self.current_worker.cancel()

    @classmethod
    def run(
        cls,
        task_fn: Callable[..., Any],
        on_success: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Any], None]] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> "TaskWorker":
        """Executa uma função em segundo plano com suporte a on_success e on_error."""
        def _wrapper(ctx: TaskContext):
            try:
                import inspect
                sig = inspect.signature(task_fn)
                if len(sig.parameters) > 0:
                    return task_fn(ctx)
                return task_fn()
            except (TypeError, ValueError):
                return task_fn()

        def _on_done(result, exc):
            if exc is not None:
                if on_error:
                    on_error(exc)
            else:
                if on_success:
                    on_success(result)

        return run_task(_wrapper, on_done=_on_done, on_progress=on_progress)

def run_task(
    task_fn: Callable[[TaskContext], Any],
    on_done: Optional[Callable[[Any, Optional[Exception]], None]] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> TaskWorker:
    """Helper global para disparar uma tarefa assíncrona no pool com callback unificado on_done(result, exc)."""
    runner = TaskRunner()
    def _finished(res):
        if on_done:
            on_done(res, None)
    def _error(err_msg):
        if on_done:
            on_done(None, Exception(err_msg))
    return runner.start_task(task_fn, on_progress=on_progress, on_finished=_finished, on_error=_error)


def shutdown_tasks(timeout_ms: int = 3000) -> bool:
    """
    Cancela as tarefas em andamento e aguarda o pool. Chamado ao encerrar o app: uma thread
    ainda rodando durante a finalização do Python derruba o processo (código 3 / crash.log).
    """
    for worker in list(_ACTIVE_WORKERS):
        worker.cancel()
    finished = QThreadPool.globalInstance().waitForDone(timeout_ms)
    if not finished:
        _log.warning("Encerrando com tarefas ainda em execução após %d ms", timeout_ms)
    return finished

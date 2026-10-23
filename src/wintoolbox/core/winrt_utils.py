"""
Execução segura de APIs WinRT (pacotes `winrt-*`: OCR, síntese de voz...).

Chamadas assíncronas WinRT travam para sempre numa thread que outra biblioteca já inicializou
como STA sem laço de mensagens (ex: pyttsx3/comtypes para SAPI). Como o QThreadPool reaproveita
threads entre tarefas, cada chamada WinRT roda numa thread própria e efêmera, que nasce sem
apartment e é inicializada pelo winrt como MTA.
"""
import asyncio
import threading
from typing import Any, Awaitable, Callable, Dict

DEFAULT_TIMEOUT_S = 120.0


def run_winrt(fn: Callable[[], Awaitable[Any]], timeout: float = DEFAULT_TIMEOUT_S) -> Any:
    """Executa `await fn()` numa thread dedicada e devolve o resultado (ou relança a exceção)."""
    outcome: Dict[str, Any] = {}

    def target() -> None:
        try:
            outcome["value"] = asyncio.run(fn())
        except BaseException as e:  # repassa inclusive KeyboardInterrupt/SystemExit ao chamador
            outcome["error"] = e

    worker = threading.Thread(target=target, name="WinRT", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise TimeoutError(f"A operação do Windows (WinRT) não respondeu em {timeout:.0f} s.")
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")

"""
Instância única do aplicativo via QLocalServer (named pipe no Windows).
Uma segunda execução (ex: "Enviar para" com o app na bandeja) entrega os argumentos à
instância já aberta e encerra, em vez de abrir outra janela e disputar o atalho global.
"""
import getpass
import json
from typing import List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("single_instance")


def _server_name() -> str:
    # Por usuário: sessões diferentes (troca rápida de usuário) não se misturam
    user = "".join(ch for ch in getpass.getuser() if ch.isalnum()) or "user"
    return f"AllTheUtils-WinToolbox-{user}"


def send_to_running_instance(args: List[str], timeout_ms: int = 400) -> bool:
    """Tenta entregar os argumentos a uma instância já aberta. True = entregue (pode encerrar)."""
    sock = QLocalSocket()
    sock.connectToServer(_server_name())
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write(json.dumps(args).encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    _log.info("Argumentos encaminhados para a instância já aberta: %s", args)
    return True


class SingleInstanceServer(QObject):
    """Recebe argumentos de execuções posteriores do app."""
    message_received = Signal(list)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.UserAccessOption)
        if not self._server.listen(_server_name()):
            _log.warning("Servidor de instância única indisponível: %s", self._server.errorString())
        self._server.newConnection.connect(self._on_new_connection)

    def _on_new_connection(self) -> None:
        sock = self._server.nextPendingConnection()
        if sock is None:
            return
        buffer = bytearray()

        def read() -> None:
            buffer.extend(bytes(sock.readAll()))

        def finished() -> None:
            read()
            try:
                args = json.loads(buffer.decode("utf-8") or "[]")
                self.message_received.emit([str(a) for a in args] if isinstance(args, list) else [])
            except Exception:
                _log.warning("Mensagem inválida recebida de outra instância", exc_info=True)
            sock.deleteLater()

        sock.readyRead.connect(read)
        sock.disconnected.connect(finished)

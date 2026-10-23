"""
Central de Logs do All the Utils.
Reúne em um só lugar os logs do app, das bibliotecas (Pillow, pypdf, paramiko, yt-dlp...),
do Qt, de warnings e de exceções não tratadas (inclusive em threads).

Destinos:
  - Arquivo rotativo em %APPDATA%/AllTheUtils/logs/app.log (para enviar ao testar em outros PCs)
  - Buffer em memória consumido pela tela "Depuração" (atualização ao vivo)
  - crash.log via faulthandler para falhas nativas (Qt/DLLs) que derrubam o processo
"""
import faulthandler
import logging
import logging.handlers
import os
import platform
import sys
import threading
import warnings
from collections import deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

from wintoolbox.core.settings import get_settings_dir, load_settings, save_settings

APP_LOGGER = "wintoolbox"

# Loggers configuráveis na tela de Depuração: (nome do logger, rótulo exibido)
LIBRARY_LOGGERS: List[tuple] = [
    (APP_LOGGER, "All the Utils (app)"),
    ("qt", "Qt / PySide6"),
    ("py.warnings", "Avisos do Python (warnings)"),
    ("PIL", "Pillow (imagens)"),
    ("pypdf", "pypdf (PDF)"),
    ("paramiko", "paramiko (SFTP/SSH)"),
    ("yt_dlp", "yt-dlp (downloads)"),
    ("comtypes", "comtypes (SAPI / voz)"),
    ("urllib3", "urllib3 / requests (HTTP)"),
    ("MARKDOWN", "Markdown"),
    ("asyncio", "asyncio"),
]

LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Padrões: o app em INFO; bibliotecas só a partir de WARNING para não poluir
DEFAULT_LEVELS: Dict[str, str] = {name: "WARNING" for name, _ in LIBRARY_LOGGERS}
DEFAULT_LEVELS[APP_LOGGER] = "INFO"
DEFAULT_LEVELS["qt"] = "WARNING"

FILE_FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(threadName)s | %(location)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_installed = False
_memory_handler: Optional["MemoryLogHandler"] = None
_file_handler: Optional[logging.Handler] = None
_crash_file = None


class _LocationFilter(logging.Filter):
    """Adiciona 'arquivo.py:linha (função)' a cada registro, para saber onde o erro ocorreu."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "location"):
            fname = os.path.basename(record.pathname) if record.pathname else "?"
            record.location = f"{fname}:{record.lineno} ({record.funcName})"
        return True


class MemoryLogHandler(logging.Handler):
    """Mantém os últimos N registros em memória e notifica assinantes (a tela de Depuração)."""

    def __init__(self, capacity: int = 5000):
        super().__init__(level=logging.DEBUG)
        self.records: Deque[Dict[str, Any]] = deque(maxlen=capacity)
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._sub_lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "time": self.formatter.formatTime(record, "%H:%M:%S") + f".{int(record.msecs):03d}"
                if self.formatter else "",
                "created": record.created,
                "level": record.levelname,
                "levelno": record.levelno,
                "logger": record.name,
                "location": getattr(record, "location", ""),
                "thread": record.threadName,
                "message": record.getMessage(),
                "details": self.formatter.formatException(record.exc_info)
                if record.exc_info and self.formatter else (record.stack_info or ""),
            }
        except Exception:
            self.handleError(record)
            return
        self.records.append(entry)
        with self._sub_lock:
            subscribers = list(self._subscribers)
        for cb in subscribers:
            try:
                cb(entry)
            except Exception:
                pass

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._sub_lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._sub_lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)


def get_logs_dir() -> Path:
    d = get_settings_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_log_file() -> Path:
    return get_logs_dir() / "app.log"


def get_crash_file() -> Path:
    return get_logs_dir() / "crash.log"


def get_memory_handler() -> Optional[MemoryLogHandler]:
    return _memory_handler


def get_logger(name: str = "") -> logging.Logger:
    """Logger do app: get_logger('batch') -> 'wintoolbox.batch'."""
    return logging.getLogger(f"{APP_LOGGER}.{name}" if name else APP_LOGGER)


def get_configured_levels() -> Dict[str, str]:
    levels = dict(DEFAULT_LEVELS)
    saved = load_settings().get("log_levels")
    if isinstance(saved, dict):
        levels.update({k: str(v).upper() for k, v in saved.items() if str(v).upper() in LEVELS})
    return levels


def apply_levels(levels: Dict[str, str], persist: bool = False) -> None:
    """Aplica (e opcionalmente salva) o nível de verbosidade de cada biblioteca."""
    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)
    if persist:
        st = load_settings()
        st["log_levels"] = dict(levels)
        save_settings(st)


def _debug_forced() -> bool:
    return "--debug" in sys.argv or os.environ.get("WINTOOLBOX_DEBUG", "") not in ("", "0")


def _excepthook(exc_type, exc, tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    logging.getLogger(APP_LOGGER).critical("Exceção não tratada", exc_info=(exc_type, exc, tb))


def _thread_excepthook(args) -> None:
    if args.exc_type is SystemExit:
        return
    logging.getLogger(APP_LOGGER).critical(
        "Exceção não tratada na thread '%s'", getattr(args.thread, "name", "?"),
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def install_qt_message_handler() -> None:
    """Redireciona qDebug/qWarning/qCritical do Qt para o logger 'qt'."""
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:
        return
    qt_log = logging.getLogger("qt")
    level_map = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def handler(msg_type, context, message):
        file = os.path.basename(context.file) if context and context.file else "qt"
        line = context.line if context else 0
        category = f"{context.category}: " if context and context.category and context.category != "default" else ""
        qt_log.log(level_map.get(msg_type, logging.INFO), f"{category}{message}",
                   extra={"location": f"{file}:{line}"})

    qInstallMessageHandler(handler)


def uninstall_qt_message_handler() -> None:
    """
    Remove o handler Python do Qt ao encerrar: o Qt ainda emite mensagens enquanto destrói
    objetos, e chamar Python nessa fase (interpretador finalizando) causa 0xC0000005.
    """
    try:
        from PySide6.QtCore import qInstallMessageHandler
        qInstallMessageHandler(None)
    except Exception:
        pass


def install_dialog_logging() -> None:
    """
    Registra na central todo QMessageBox.critical/warning exibido ao usuário, com o arquivo e a
    linha de quem chamou: erros mostrados em diálogo deixam de se perder.
    """
    try:
        from PySide6.QtWidgets import QMessageBox
    except Exception:
        return
    ui_log = logging.getLogger(f"{APP_LOGGER}.ui")

    def wrap(original, level):
        def dialog(parent, title, text, *args, **kwargs):
            ui_log.log(level, "Diálogo '%s': %s", title, text, stacklevel=2)
            return original(parent, title, text, *args, **kwargs)
        dialog._wtbx_wrapped = True
        return staticmethod(dialog)

    for name, level in (("critical", logging.ERROR), ("warning", logging.WARNING)):
        current = getattr(QMessageBox, name)
        if not getattr(current, "_wtbx_wrapped", False):
            setattr(QMessageBox, name, wrap(current, level))


def setup_logging() -> None:
    """Configura a central de logs (idempotente). Deve ser chamada antes de criar a UI."""
    global _installed, _memory_handler, _file_handler, _crash_file
    if _installed:
        return
    _installed = True

    root = logging.getLogger()
    # Libs não listadas em LIBRARY_LOGGERS ficam em WARNING; as listadas têm nível próprio
    root.setLevel(logging.WARNING)
    location = _LocationFilter()
    formatter = logging.Formatter(FILE_FORMAT, DATE_FORMAT)

    try:
        _file_handler = logging.handlers.RotatingFileHandler(
            get_log_file(), maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8", delay=True
        )
        _file_handler.setFormatter(formatter)
        _file_handler.addFilter(location)
        root.addHandler(_file_handler)
    except Exception:
        _file_handler = None

    _memory_handler = MemoryLogHandler()
    _memory_handler.setFormatter(formatter)
    _memory_handler.addFilter(location)
    root.addHandler(_memory_handler)

    # Executável --windowed do PyInstaller não tem console (sys.stderr é None)
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        console.addFilter(location)
        console.setLevel(logging.WARNING)
        root.addHandler(console)

    levels = get_configured_levels()
    if _debug_forced():
        levels[APP_LOGGER] = "DEBUG"
    apply_levels(levels)

    logging.captureWarnings(True)
    warnings.simplefilter("default")
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook

    try:
        _crash_file = open(get_crash_file(), "a", encoding="utf-8")
        faulthandler.enable(file=_crash_file, all_threads=True)
    except Exception:
        _crash_file = None

    log = get_logger()
    log.info("=" * 60)
    log.info("Iniciando All the Utils | %s", environment_summary_line())


def environment_summary_line() -> str:
    return (f"Windows {platform.version()} | Python {platform.python_version()} "
            f"({platform.architecture()[0]}) | frozen={getattr(sys, 'frozen', False)}")


def collect_environment_info() -> Dict[str, str]:
    """Dados do ambiente para diagnóstico em outros computadores (sem segredos)."""
    from importlib import metadata

    info: Dict[str, str] = {}
    try:
        ver = sys.getwindowsversion()
        build = ver.build
        edition = platform.win32_edition() if hasattr(platform, "win32_edition") else ""
        name = "Windows 11" if build >= 22000 else "Windows 10" if ver.major == 10 else f"Windows {ver.major}"
        info["Sistema"] = f"{name} {edition} (build {build}.{_ubr()})".strip()
    except Exception:
        info["Sistema"] = platform.platform()
    info["Arquitetura"] = f"{platform.machine()} / Python {platform.architecture()[0]}"
    info["Python"] = sys.version.split()[0]
    info["Executável"] = sys.executable
    info["Empacotado (PyInstaller)"] = "Sim" if getattr(sys, "frozen", False) else "Não"
    try:
        import ctypes
        info["Administrador"] = "Sim" if ctypes.windll.shell32.IsUserAnAdmin() else "Não"
        info["Página de código (ANSI/OEM)"] = f"cp{ctypes.windll.kernel32.GetACP()} / cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        pass
    try:
        import locale
        info["Idioma"] = str(locale.getlocale()[0])
    except Exception:
        pass
    try:
        from PySide6 import __version__ as pyside_ver
        from PySide6.QtCore import qVersion
        from PySide6.QtWidgets import QApplication
        info["Qt / PySide6"] = f"{qVersion()} / {pyside_ver}"
        app = QApplication.instance()
        if app:
            info["Estilo Qt"] = app.style().name()
            screens = []
            for s in app.screens():
                g = s.geometry()
                screens.append(f"{s.name()} {g.width()}x{g.height()} @ {s.devicePixelRatio():.2f}x")
            info["Telas (escala DPI)"] = "; ".join(screens)
    except Exception:
        pass
    for dist in ("Pillow", "psutil", "pywin32", "pypdf", "cryptography", "paramiko", "yt-dlp", "mutagen",
                 "PyYAML", "pyttsx3", "qrcode", "rapidfuzz", "sqlparse", "markdown", "speedtest-cli",
                 "Send2Trash", "opencv-python-headless", "opencv-python", "static-ffmpeg"):
        try:
            info[f"lib: {dist}"] = metadata.version(dist)
        except Exception:
            info[f"lib: {dist}"] = "não instalada"
    try:
        from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe
        info["ffmpeg"] = get_ffmpeg_exe()
    except Exception as e:
        info["ffmpeg"] = f"indisponível ({e})"
    info["Pasta de dados"] = str(get_settings_dir())
    info["Arquivo de log"] = str(get_log_file())
    return info


def _ubr() -> str:
    """Update Build Revision (ex: 19045.4291) lido do registro."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as k:
            return str(winreg.QueryValueEx(k, "UBR")[0])
    except Exception:
        return "?"


class YtDlpLogger:
    """Adaptador para a opção 'logger' do yt-dlp, que não usa o módulo logging diretamente."""

    def __init__(self) -> None:
        self._log = logging.getLogger("yt_dlp")

    def debug(self, msg: str) -> None:
        # yt-dlp manda mensagens informativas pelo debug com prefixo "[...]"
        self._log.debug(msg)

    def info(self, msg: str) -> None:
        self._log.info(msg)

    def warning(self, msg: str) -> None:
        self._log.warning(msg)

    def error(self, msg: str) -> None:
        self._log.error(msg)

"""
Verificação e elevação de privilégios de Administrador (UAC) no Windows.
"""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional


def is_admin() -> bool:
    """Verifica se o processo atual possui privilégios de administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_elevation(extra_args: str = "") -> bool:
    """
    Solicita elevação UAC para reiniciar o processo atual como Administrador.
    Preserva aspas em caminhos com espaços.
    """
    if is_admin():
        return True

    try:
        executable = sys.executable
        if getattr(sys, "frozen", False):
            # Executável do PyInstaller: sys.executable já é o app; repassar argv[0]
            # faria o novo processo receber o próprio .exe como "arquivo" de entrada.
            params = f"{subprocess.list2cmdline(sys.argv[1:])} {extra_args}".strip()
        else:
            script = Path(sys.argv[0]).resolve()
            params = f"{subprocess.list2cmdline([str(script), *sys.argv[1:]])} {extra_args}".strip()

        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            params,
            None,
            1  # SW_SHOWNORMAL
        )
        if ret > 32:
            sys.exit(0)
        return False
    except Exception:
        return False


def is_headless_or_test() -> bool:
    """Retorna True se estiver rodando em autoteste ou pytest."""
    return (
        "--self-test" in sys.argv
        or bool(os.environ.get("PYTEST_CURRENT_TEST"))
        or os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    )


def prompt_elevation_dialog(
    parent: Optional[object] = None,
    tool_name: str = "Esta ferramenta",
    reason: str = "",
) -> bool:
    """
    Se não estiver como Administrador, exibe um diálogo claro solicitando elevação UAC.
    Retorna True se já for Admin (ou se a elevação foi disparada).
    """
    if is_admin():
        return True
    if is_headless_or_test():
        return False

    from PySide6.QtWidgets import QMessageBox, QWidget

    parent_widget = parent if isinstance(parent, QWidget) else None
    detalhe = f"\n\nMotivo: {reason}" if reason else ""
    texto = (
        f"'{tool_name}' necessita de privilégios de Administrador para consultar ou "
        f"modificar configurações protegidas do sistema operacional.{detalhe}\n\n"
        "Deseja reiniciar o aplicativo como Administrador agora?"
    )
    ans = QMessageBox.question(
        parent_widget,
        "Privilégios de Administrador Necessários",
        texto,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if ans == QMessageBox.StandardButton.Yes:
        return request_elevation()
    return False


def bind_admin_prompt_on_show(widget: object, tool_name: str, reason: str = "") -> None:
    """
    Exibe automaticamente o diálogo de solicitação de Administrador na primeira vez
    que a tela for exibida ao usuário caso o app não esteja rodando elevado.
    """
    if is_admin() or is_headless_or_test():
        return

    from PySide6.QtCore import QEvent, QObject, QTimer
    from PySide6.QtWidgets import QWidget

    if not isinstance(widget, QWidget):
        return

    class _AdminShowFilter(QObject):
        def __init__(self, target: QWidget):
            super().__init__(target)
            self._prompted = False

        def eventFilter(self, obj: QObject, event: QEvent) -> bool:
            if event.type() == QEvent.Type.Show and not self._prompted:
                if not is_admin() and not is_headless_or_test():
                    self._prompted = True
                    QTimer.singleShot(
                        120,
                        lambda: prompt_elevation_dialog(widget, tool_name=tool_name, reason=reason),
                    )
            return False

    flt = _AdminShowFilter(widget)
    setattr(widget, "_admin_show_filter", flt)
    widget.installEventFilter(flt)


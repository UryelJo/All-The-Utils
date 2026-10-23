"""
Gerenciamento de Atalhos Globais no Windows via RegisterHotKey (Win32 API).
Leve, seguro e sem dependências pesadas externas.
"""
import ctypes
import threading
from typing import Callable, Optional
from ctypes import wintypes

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

class GlobalHotkeyManager:
    """Registra uma combinação de teclas global no Windows para restaurar a janela."""
    def __init__(self, callback: Callable[[], None]):
        self.callback = callback
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._hotkey_id = 9999

    def start(self, modifiers: int = (MOD_CONTROL | MOD_ALT), vk_code: int = 0x54):
        """
        Inicia a escuta do atalho global.
        Padrão: Ctrl + Alt + T (0x54 = tecla 'T')
        """
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._worker,
            args=(modifiers, vk_code),
            daemon=True
        )
        self._thread.start()

    def _worker(self, modifiers: int, vk_code: int):
        user32 = ctypes.windll.user32
        # Tenta registrar o atalho global
        if not user32.RegisterHotKey(None, self._hotkey_id, modifiers | MOD_NOREPEAT, vk_code):
            self._running = False
            return

        msg = wintypes.MSG()
        while self._running:
            # GetMessage bloqueia aguardando mensagens da fila da thread
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret <= 0:
                break
            if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                try:
                    self.callback()
                except Exception:
                    pass

        user32.UnregisterHotKey(None, self._hotkey_id)

    def stop(self):
        self._running = False
        # Envia mensagem WM_NULL para desbloquear GetMessage
        if self._thread and self._thread.is_alive():
            ctypes.windll.user32.PostThreadMessageW(
                self._thread.ident,
                0x0000,  # WM_NULL
                0,
                0
            )

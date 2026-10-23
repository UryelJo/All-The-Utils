"""
Bandeja do Sistema (System Tray) e Notificações Nativas com PySide6.
Extremamente leve, sem dependências adicionais como pystray ou win10toast.
"""
from typing import Callable, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from wintoolbox.core.registry import get_tool
from wintoolbox.core.settings import load_settings

def create_tray_icon_pixmap() -> QIcon:
    """Cria um ícone procedural nítido e leve de 32x32 para a bandeja."""
    pix = QPixmap(32, 32)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    # Fundo azul accent
    painter.setBrush(QColor("#0078d4"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 6, 6)

    # Letra 'A' centralizada em branco
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setPixelSize(18)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignCenter, "A")
    painter.end()

    return QIcon(pix)

class SystemTrayManager:
    """Gerencia o ícone da bandeja, menu de contexto e notificações."""
    def __init__(self, on_show_window: Callable[[], None], on_open_tool: Callable[[str], None], on_search: Callable[[], None]):
        self.on_show_window = on_show_window
        self.on_open_tool = on_open_tool
        self.on_search = on_search

        self.tray = QSystemTrayIcon(create_tray_icon_pixmap(), QApplication.instance())
        self.tray.setToolTip("All the Utils - Caixa de Ferramentas")
        self.tray.activated.connect(self._on_tray_activated)

        self._build_menu()
        self.tray.show()

    def _build_menu(self):
        menu = QMenu()

        # Abrir All the Utils
        act_open = QAction("Abrir All the Utils", menu)
        act_open.triggered.connect(self.on_show_window)
        menu.addAction(act_open)

        # Buscar (Ctrl+K)
        act_search = QAction("Buscar Ferramentas... (Ctrl+K)", menu)
        act_search.triggered.connect(self.on_search)
        menu.addAction(act_search)

        menu.addSeparator()

        # Submenu de Favoritos
        st = load_settings()
        fav_menu = menu.addMenu("Favoritos")
        favs = st.get("favorites", [])
        if favs:
            for fid in favs:
                t = get_tool(fid)
                if t:
                    act_fav = QAction(t.name, fav_menu)
                    act_fav.triggered.connect(lambda chk=False, tid=fid: self.on_open_tool(tid))
                    fav_menu.addAction(act_fav)
        else:
            act_empty = QAction("(Nenhum favorito)", fav_menu)
            act_empty.setEnabled(False)
            fav_menu.addAction(act_empty)

        # Submenu de Recentes
        rec_menu = menu.addMenu("Recentes")
        recents = st.get("recent_tools", [])
        if recents:
            for rid in recents:
                t = get_tool(rid)
                if t:
                    act_rec = QAction(t.name, rec_menu)
                    act_rec.triggered.connect(lambda chk=False, tid=rid: self.on_open_tool(tid))
                    rec_menu.addAction(act_rec)
        else:
            act_empty2 = QAction("(Nenhum recente)", rec_menu)
            act_empty2.setEnabled(False)
            rec_menu.addAction(act_empty2)

        menu.addSeparator()

        # Sair
        act_exit = QAction("Sair", menu)
        act_exit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_exit)

        self.tray.setContextMenu(menu)

    def refresh_menu(self):
        self._build_menu()

    def _on_tray_activated(self, reason):
        # Clique duplo ou clique simples restaura a janela
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.on_show_window()

    def notify(self, title: str, message: str, is_error: bool = False):
        """Exibe uma notificação nativa do Windows."""
        st = load_settings()
        if not st.get("notifications_enabled", True):
            return

        icon_type = QSystemTrayIcon.Critical if is_error else QSystemTrayIcon.Information
        self.tray.showMessage(title, message, icon_type, 4000)

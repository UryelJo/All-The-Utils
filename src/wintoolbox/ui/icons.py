"""
Utilitários Visuais e Vetoriais Limpos (Zero Emojis / Zero Glifos de Fonte).
Gerencia o carregamento e cache em múltiplas resoluções do ícone oficial do app (ui/Icon.png),
desenha indicadores geométricos vetoriais via QPainter para categorias e fornece
normalização de texto sem acentos para buscas.
"""
import math
from pathlib import Path
import sys
import unicodedata
from typing import Dict, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap

# Metadados de categorias com chaves semânticas e cor neutra profissional (sem arco-íris de cores)
NEUTRAL_ICON_COLOR = "#a1a1aa"

CATEGORY_META: Dict[str, Tuple[str, str]] = {
    "Imagens": ("cat_images", NEUTRAL_ICON_COLOR),
    "Arquivos e Pastas": ("cat_files", NEUTRAL_ICON_COLOR),
    "Rede e Internet": ("cat_network", NEUTRAL_ICON_COLOR),
    "PDF e Documentos": ("cat_pdf", NEUTRAL_ICON_COLOR),
    "Documentos e PDF": ("cat_pdf", NEUTRAL_ICON_COLOR),
    "Texto e Redação": ("cat_text", NEUTRAL_ICON_COLOR),
    "Codificação e Hash": ("cat_encode", NEUTRAL_ICON_COLOR),
    "Dados e Estruturas": ("cat_data", NEUTRAL_ICON_COLOR),
    "Áudio e Vídeo": ("cat_media", NEUTRAL_ICON_COLOR),
    "Mídia": ("cat_media", NEUTRAL_ICON_COLOR),
    "Sistema": ("cat_system", NEUTRAL_ICON_COLOR),
    "Sistema Windows": ("cat_system", NEUTRAL_ICON_COLOR),
    "Compactação": ("cat_archive", NEUTRAL_ICON_COLOR),
}

_CACHED_APP_ICON: Optional[QIcon] = None
_CACHED_BASE_PIXMAP: Optional[QPixmap] = None
_ICON_CACHE: Dict[Tuple[str, str, int], QIcon] = {}


def get_app_icon_path() -> Optional[Path]:
    """Localiza o arquivo de ícone oficial da aplicação (ui/Icon.png ou src/wintoolbox/ui/icon.png)."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        meipass = Path(getattr(sys, "_MEIPASS"))
        candidates.extend([
            meipass / "ui" / "Icon.png",
            meipass / "ui" / "icon.png",
            meipass / "ui" / "icon.ico",
        ])

    here = Path(__file__).resolve().parent
    repo_root = here.parent.parent.parent
    candidates.extend([
        repo_root / "ui" / "Icon.png",
        repo_root / "ui" / "icon.png",
        here / "icon.png",
        repo_root / "ui" / "icon.ico",
        here / "icon.ico",
    ])

    for p in candidates:
        if p.exists():
            return p
    return None


def _get_base_app_pixmap() -> QPixmap:
    """Carrega em cache o QPixmap base do ícone oficial."""
    global _CACHED_BASE_PIXMAP
    if _CACHED_BASE_PIXMAP is not None and not _CACHED_BASE_PIXMAP.isNull():
        return _CACHED_BASE_PIXMAP

    icon_path = get_app_icon_path()
    if icon_path is not None:
        pix = QPixmap(str(icon_path))
        if not pix.isNull():
            _CACHED_BASE_PIXMAP = pix
            return _CACHED_BASE_PIXMAP

    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#0078d4"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    painter.setPen(QColor("#ffffff"))
    f = QFont("Segoe UI", 24, QFont.Bold)
    painter.setFont(f)
    painter.drawText(pix.rect(), Qt.AlignCenter, "A")
    painter.end()
    _CACHED_BASE_PIXMAP = pix
    return _CACHED_BASE_PIXMAP


def get_app_pixmap(size: int = 32) -> QPixmap:
    """Retorna um QPixmap nítido com interpolação suave (High-DPI) do ícone do app."""
    base = _get_base_app_pixmap()
    dpr = 2.0
    target_px = int(size * dpr)
    scaled = base.scaled(
        target_px,
        target_px,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )
    scaled.setDevicePixelRatio(dpr)
    return scaled


def get_app_icon() -> QIcon:
    """Retorna o QIcon oficial multi-resolução da aplicação."""
    global _CACHED_APP_ICON
    if _CACHED_APP_ICON is not None and not _CACHED_APP_ICON.isNull():
        return _CACHED_APP_ICON

    base = _get_base_app_pixmap()
    icon = QIcon()
    for sz in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        scaled = base.scaled(sz, sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon.addPixmap(scaled)

    _CACHED_APP_ICON = icon
    return _CACHED_APP_ICON


def get_icon_font(pixel_size: int = 13) -> QFont:
    """Retorna a fonte padrão limpa do sistema (Segoe UI)."""
    return QFont("Segoe UI", pixel_size)


def get_glyph(name: str) -> str:
    """Retorna string vazia para garantir ausência de emojis em botões."""
    return ""


def make_fluent_icon(name: str, color: str = NEUTRAL_ICON_COLOR, size: int = 16) -> QIcon:
    """
    Desenha ícones vetoriais monocromáticos nítidos e geométricos via QPainter.
    Visual sóbrio, limpo e profissional (estilo Windows 11 Fluent).
    """
    cache_key = (name, color, size)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    dpr = 2.0
    px_size = int(size * dpr)
    pixmap = QPixmap(px_size, px_size)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    pen = QPen(c, 1.4)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    s = float(size)
    pad = s * 0.14
    w = s - 2 * pad
    h = s - 2 * pad

    if name == "home":
        # Casinha minimalista
        pts = [
            QPointF(s * 0.5, pad),
            QPointF(s - pad, s * 0.45),
            QPointF(s - pad * 1.5, s * 0.45),
            QPointF(s - pad * 1.5, s - pad),
            QPointF(pad * 1.5, s - pad),
            QPointF(pad * 1.5, s * 0.45),
            QPointF(pad, s * 0.45),
        ]
        p.drawPolygon(pts)
        # Portinha
        p.drawRect(QRectF(s * 0.4, s * 0.65, s * 0.2, s * 0.35 - pad))

    elif name == "history":
        # Relógio minimalista
        p.drawEllipse(QRectF(pad, pad, w, h))
        p.drawLine(QPointF(s * 0.5, s * 0.5), QPointF(s * 0.5, s * 0.3))
        p.drawLine(QPointF(s * 0.5, s * 0.5), QPointF(s * 0.7, s * 0.5))

    elif name == "settings":
        # Engrenagem geométrica limpa
        r_outer = w * 0.48
        r_inner = w * 0.22
        cx, cy = s * 0.5, s * 0.5
        p.drawEllipse(QPointF(cx, cy), r_inner, r_inner)
        # 6 dentes discretos
        p.drawRoundedRect(QRectF(cx - w * 0.48, cy - h * 0.15, w * 0.96, h * 0.3), 1.5, 1.5)
        p.drawRoundedRect(QRectF(cx - w * 0.15, cy - h * 0.48, w * 0.3, h * 0.96), 1.5, 1.5)

    elif name == "search":
        # Lupa minimalista
        r_lens = w * 0.36
        cx, cy = pad + r_lens, pad + r_lens
        p.drawEllipse(QPointF(cx, cy), r_lens, r_lens)
        p.drawLine(QPointF(cx + r_lens * 0.7, cy + r_lens * 0.7), QPointF(s - pad, s - pad))

    elif name in ("star", "star_filled"):
        # Estrela de 5 pontas geométrica limpa
        cx, cy = s * 0.5, s * 0.5
        r_out = w * 0.48
        r_in = r_out * 0.42
        pts = []
        for i in range(10):
            r = r_out if i % 2 == 0 else r_in
            angle = (i * 36 - 90) * math.pi / 180.0
            pts.append(QPointF(cx + r * math.cos(angle), cy + r * math.sin(angle)))
        if name == "star_filled":
            p.setBrush(c)
        else:
            p.setBrush(Qt.NoBrush)
        p.drawPolygon(pts)

    elif name == "cat_images":
        # Imagem (quadro + montanha + sol)
        p.drawRoundedRect(QRectF(pad, pad, w, h), 2.0, 2.0)
        p.drawEllipse(QPointF(pad + w * 0.3, pad + h * 0.35), 1.5, 1.5)
        p.drawLine(QPointF(pad + 1, s - pad - 2), QPointF(pad + w * 0.45, pad + h * 0.55))
        p.drawLine(QPointF(pad + w * 0.45, pad + h * 0.55), QPointF(pad + w * 0.7, pad + h * 0.7))
        p.drawLine(QPointF(pad + w * 0.7, pad + h * 0.7), QPointF(s - pad - 1, s - pad - 2))

    elif name == "cat_files":
        # Pasta de arquivos
        p.drawRoundedRect(QRectF(pad, pad + h * 0.22, w, h * 0.78), 2.0, 2.0)
        p.drawLine(QPointF(pad + 1, pad + h * 0.22), QPointF(pad + w * 0.45, pad + h * 0.22))
        p.drawLine(QPointF(pad + w * 0.45, pad + h * 0.22), QPointF(pad + w * 0.55, pad + 1))
        p.drawLine(QPointF(pad + w * 0.55, pad + 1), QPointF(pad + 1, pad + 1))

    elif name == "cat_network":
        # Globo / Rede
        p.drawEllipse(QRectF(pad, pad, w, h))
        p.drawEllipse(QRectF(pad + w * 0.25, pad, w * 0.5, h))
        p.drawLine(QPointF(pad, s * 0.5), QPointF(s - pad, s * 0.5))

    elif name == "cat_pdf":
        # Documento / PDF (folha dobrada)
        p.drawRoundedRect(QRectF(pad + 1, pad, w - 2, h), 2.0, 2.0)
        p.drawLine(QPointF(pad + 3, pad + h * 0.35), QPointF(s - pad - 3, pad + h * 0.35))
        p.drawLine(QPointF(pad + 3, pad + h * 0.6), QPointF(s - pad - 5, pad + h * 0.6))

    elif name == "cat_text":
        # Linhas de texto
        p.drawRoundedRect(QRectF(pad + 1, pad, w - 2, h), 2.0, 2.0)
        p.drawLine(QPointF(pad + 3, pad + h * 0.28), QPointF(s - pad - 3, pad + h * 0.28))
        p.drawLine(QPointF(pad + 3, pad + h * 0.5), QPointF(s - pad - 3, pad + h * 0.5))
        p.drawLine(QPointF(pad + 3, pad + h * 0.72), QPointF(pad + w * 0.6, pad + h * 0.72))

    elif name in ("cat_encode", "cat_hash"):
        # Cadeado / Chave
        p.drawRoundedRect(QRectF(pad + 1, pad + h * 0.38, w - 2, h * 0.62), 2.0, 2.0)
        p.drawArc(QRectF(pad + w * 0.25, pad + 1, w * 0.5, h * 0.65), 0, 180 * 16)

    elif name == "cat_data":
        # Gráfico de barras
        p.drawRect(QRectF(pad + 1, s - pad - h * 0.45, w * 0.22, h * 0.45))
        p.drawRect(QRectF(pad + w * 0.38, s - pad - h * 0.85, w * 0.22, h * 0.85))
        p.drawRect(QRectF(pad + w * 0.75, s - pad - h * 0.65, w * 0.22, h * 0.65))

    elif name == "cat_media":
        # Vídeo / Mídia (triângulo play discreto)
        p.drawRoundedRect(QRectF(pad, pad, w, h), 2.0, 2.0)
        tri = [
            QPointF(pad + w * 0.4, pad + h * 0.3),
            QPointF(pad + w * 0.7, s * 0.5),
            QPointF(pad + w * 0.4, s - pad - h * 0.3),
        ]
        p.drawPolygon(tri)

    elif name == "cat_system":
        # Sistema / Engrenagem sutil
        cx, cy = s * 0.5, s * 0.5
        p.drawEllipse(QPointF(cx, cy), w * 0.26, h * 0.26)
        p.drawRoundedRect(QRectF(cx - w * 0.45, cy - h * 0.15, w * 0.9, h * 0.3), 1.5, 1.5)
        p.drawRoundedRect(QRectF(cx - w * 0.15, cy - h * 0.45, w * 0.3, h * 0.9), 1.5, 1.5)

    elif name == "cat_archive":
        # Caixa / Pacote
        p.drawRect(QRectF(pad, pad + h * 0.2, w, h * 0.8))
        p.drawLine(QPointF(pad, pad + h * 0.2), QPointF(s - pad, pad + h * 0.2))
        p.drawRect(QRectF(pad + w * 0.35, pad + h * 0.15, w * 0.3, h * 0.25))

    else:
        # Fallback geométrico limpo (quadradinho arredondado discreto)
        p.drawRoundedRect(QRectF(pad + 1, pad + 1, w - 2, h - 2), 2.5, 2.5)

    p.end()
    icon = QIcon(pixmap)
    _ICON_CACHE[cache_key] = icon
    return icon


def get_category_meta(category_name: str) -> Tuple[str, str]:
    """Retorna (icon_key, hex_color) correspondente à categoria."""
    return CATEGORY_META.get(category_name, ("cat_default", NEUTRAL_ICON_COLOR))


def get_category_icon(category_name: str, color: str = "", size: int = 14) -> QIcon:
    """Retorna um QIcon geométrico minimalista e monocromático."""
    icon_name, default_color = get_category_meta(category_name)
    return make_fluent_icon(icon_name, color or default_color, size=size)


def normalize_text(text: str) -> str:
    """Remove acentos e converte para minúsculas para buscas tolerantes."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

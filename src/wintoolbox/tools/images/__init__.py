"""Módulo de ferramentas de Imagens do WinToolbox."""
# HEIC/HEIF (fotos de iPhone): o Pillow só lê com o plugin pillow-heif registrado.
# AVIF já é nativo no Pillow 11.3+.
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# Ferramentas ativas e consolidadas da categoria Imagens
import wintoolbox.tools.images.convert
import wintoolbox.tools.images.resize
import wintoolbox.tools.images.compress
import wintoolbox.tools.images.watermark
import wintoolbox.tools.images.effects
import wintoolbox.tools.images.exif
import wintoolbox.tools.images.palette
import wintoolbox.tools.images.gif_tools
import wintoolbox.tools.images.collage
import wintoolbox.tools.images.color_picker
import wintoolbox.tools.images.qrcode
import wintoolbox.tools.images.screenshot
import wintoolbox.tools.images.ocr
import wintoolbox.tools.images.remove_bg
import wintoolbox.tools.images.annotate
import wintoolbox.tools.images.compare
import wintoolbox.tools.images.border_shadow
import wintoolbox.tools.images.split_grid

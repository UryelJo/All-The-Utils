"""Módulo de ferramentas de Imagens do WinToolbox."""
# HEIC/HEIF (fotos de iPhone): o Pillow só lê com o plugin pillow-heif registrado.
# AVIF já é nativo no Pillow 11.3+.
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

import wintoolbox.tools.images.convert
import wintoolbox.tools.images.resize
import wintoolbox.tools.images.compress
import wintoolbox.tools.images.watermark
import wintoolbox.tools.images.effects
import wintoolbox.tools.images.exif
import wintoolbox.tools.images.favicon
import wintoolbox.tools.images.palette

# Fase 8: Ferramentas Adicionais de Imagem e Desktop
import wintoolbox.tools.images.gif_tools
import wintoolbox.tools.images.collage
import wintoolbox.tools.images.color_picker
import wintoolbox.tools.images.qrcode
import wintoolbox.tools.images.screenshot
import wintoolbox.tools.images.ocr
import wintoolbox.tools.images.remove_bg
import wintoolbox.tools.images.crop_editor
import wintoolbox.tools.images.annotate
import wintoolbox.tools.images.text_extractor
import wintoolbox.tools.images.compare
import wintoolbox.tools.images.svg_convert
import wintoolbox.tools.images.border_shadow
import wintoolbox.tools.images.barcode
import wintoolbox.tools.images.split_grid

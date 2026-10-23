"""
Lógica pura de geração de ícones ICO multi-resolução e pacotes Web Favicon.
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple
from PIL import Image

DEFAULT_ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

def generate_multi_size_ico(src: Path, dst: Path, sizes: List[int] = None) -> None:
    """Gera um arquivo .ico do Windows contendo múltiplos tamanhos embutidos."""
    if sizes is None:
        sizes = DEFAULT_ICO_SIZES

    dst.parent.mkdir(parents=True, exist_ok=True)
    size_tuples = [(s, s) for s in sizes]

    with Image.open(src) as im:
        rgba = im.convert("RGBA")
        rgba.save(dst, format="ICO", sizes=size_tuples)

def generate_web_favicon_package(
    src: Path,
    out_dir: Path,
    app_name: str = "All the Utils App",
    theme_color: str = "#0078D4"
) -> Dict[str, str]:
    """Gera o pacote completo de favicons para web e mobile com manifest e snippet HTML."""
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as im:
        rgba = im.convert("RGBA")

        # 1. favicon.ico
        generate_multi_size_ico(src, out_dir / "favicon.ico", [16, 32, 48])

        # 2. Ícones PNG
        sizes_png = {
            "favicon-16x16.png": 16,
            "favicon-32x32.png": 32,
            "apple-touch-icon.png": 180,
            "android-chrome-192x192.png": 192,
            "android-chrome-512x512.png": 512,
        }

        for fname, sz in sizes_png.items():
            resized = rgba.resize((sz, sz), resample=Image.Resampling.LANCZOS)
            resized.save(out_dir / fname, format="PNG", optimize=True)

    # 3. site.webmanifest
    manifest_data = {
        "name": app_name,
        "short_name": app_name,
        "icons": [
            {
                "src": "/android-chrome-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/android-chrome-512x512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ],
        "theme_color": theme_color,
        "background_color": "#ffffff",
        "display": "standalone"
    }

    manifest_path = out_dir / "site.webmanifest"
    manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # 4. Snippet HTML
    html_snippet = f"""<!-- Favicon gerado pelo All the Utils -->
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="{theme_color}">"""

    return {
        "manifest_path": str(manifest_path),
        "html_snippet": html_snippet
    }

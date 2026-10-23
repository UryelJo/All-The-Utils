"""
Lógica pura para Reconhecimento Óptico de Caracteres (OCR) 100% offline local.
Utiliza a API nativa do Windows (Windows.Media.Ocr via WinRT) com fallback para pytesseract caso instalado.
Isolada de qualquer interface gráfica.
"""
from pathlib import Path
import subprocess
from typing import Optional


PS_SCRIPT_PATH = Path(__file__).parent / "win_ocr.ps1"


def perform_ocr_on_image(image_path: Path) -> str:
    """
    Extrai texto legível de um arquivo de imagem de forma 100% local e offline.
    """
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Arquivo de imagem não encontrado: {image_path}")

    # 1. Tenta pytesseract se o usuário tiver instalado
    try:
        import importlib
        pytesseract = importlib.import_module("pytesseract")
        from PIL import Image
        with Image.open(image_path) as img:
            txt = pytesseract.image_to_string(img, lang="por+eng")
            if txt and txt.strip():
                return txt.strip()
    except Exception:
        pass

    # 2. Utiliza a API nativa do Windows (Windows.Media.Ocr.OcrEngine)
    if PS_SCRIPT_PATH.exists():
        try:
            # CREATE_NO_WINDOW = 0x08000000 no Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", str(PS_SCRIPT_PATH),
                "-ImagePath", str(image_path.resolve())
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                startupinfo=startupinfo,
                timeout=45
            )
            if res.returncode == 0 and res.stdout:
                extracted = res.stdout.strip()
                if extracted:
                    return extracted
        except Exception:
            pass

    return "Nenhum texto legível foi detectado nesta imagem."

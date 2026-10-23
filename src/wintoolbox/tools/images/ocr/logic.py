"""
Lógica pura para Reconhecimento Óptico de Caracteres (OCR) 100% offline local.
Ordem dos motores:
  1. pytesseract, se o usuário o instalou (escolha explícita);
  2. Windows.Media.Ocr via WinRT, direto no processo (sem PowerShell, ~3x mais rápido);
  3. o mesmo motor via script PowerShell (reserva quando os pacotes winrt não estão presentes).
Isolada de qualquer interface gráfica.
"""
import importlib
from pathlib import Path
import subprocess

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.winrt_utils import run_winrt

PS_SCRIPT_PATH = Path(__file__).parent / "win_ocr.ps1"
NO_TEXT_MESSAGE = "Nenhum texto legível foi detectado nesta imagem."

_log = get_logger("ocr")


def _ocr_pytesseract(image_path: Path) -> str:
    pytesseract = importlib.import_module("pytesseract")
    from PIL import Image
    with Image.open(image_path) as img:
        return (pytesseract.image_to_string(img, lang="por+eng") or "").strip()


def _ocr_winrt(image_path: Path) -> str:
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage import FileAccessMode, StorageFile

    async def run() -> str:
        file = await StorageFile.get_file_from_path_async(str(image_path))
        stream = await file.open_async(FileAccessMode.READ)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("Nenhum pacote de idioma de OCR instalado no Windows "
                               "(Configurações > Hora e idioma > Idioma > Recursos opcionais).")
        result = await engine.recognize_async(bitmap)
        return (result.text or "").strip()

    return run_winrt(run)


def _ocr_powershell(image_path: Path) -> str:
    if not PS_SCRIPT_PATH.exists():
        return ""
    cmd = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(PS_SCRIPT_PATH), "-ImagePath", str(image_path),
    ]
    res = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"PowerShell retornou {res.returncode}")
    return res.stdout.strip()


def perform_ocr_on_image(image_path: Path) -> str:
    """
    Extrai texto legível de um arquivo de imagem de forma 100% local e offline.
    """
    image_path = Path(image_path).resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Arquivo de imagem não encontrado: {image_path}")

    for name, engine in (("pytesseract", _ocr_pytesseract), ("WinRT", _ocr_winrt), ("PowerShell", _ocr_powershell)):
        try:
            text = engine(image_path)
        except ModuleNotFoundError:
            continue  # motor opcional não instalado
        except Exception:
            _log.warning("Motor de OCR %s falhou para %s", name, image_path.name, exc_info=True)
            continue
        if text:
            _log.debug("OCR via %s: %d caracteres", name, len(text))
            return text

    return NO_TEXT_MESSAGE

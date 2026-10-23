"""
Lógica pura para geração e leitura de QR Codes via biblioteca qrcode e Pillow.
Isolada de qualquer interface gráfica.
"""
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import qrcode


def generate_qrcode(
    content: str,
    output_path: Optional[Path] = None,
    box_size: int = 10,
    border: int = 4,
    fill_color: str = "#000000",
    back_color: str = "#FFFFFF",
    error_correction: str = "M"
) -> Image.Image:
    """
    Gera uma imagem de QR Code a partir de texto, URL ou dados arbitrários.
    """
    clean_text = content.strip()
    if not clean_text:
        raise ValueError("O conteúdo para o QR Code não pode ser vazio.")

    # Níveis de correção de erro: L (7%), M (15%), Q (25%), H (30%)
    err_map = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
    err_level = err_map.get(error_correction.upper(), qrcode.constants.ERROR_CORRECT_M)

    qr = qrcode.QRCode(
        version=None,  # Ajuste automático do tamanho
        error_correction=err_level,
        box_size=max(2, min(50, box_size)),
        border=max(0, min(20, border)),
    )
    qr.add_data(clean_text)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color).convert("RGB")

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_p)

    return img


def decode_qrcode_from_image(image_path: Path) -> Optional[str]:
    """
    Tenta decodificar o conteúdo de um QR Code (ou código de barras) em um arquivo de imagem.
    Motor principal: zxing-cpp (~2 MB, QR/DataMatrix/EAN/Code128...). pyzbar e OpenCV
    (este com ~110 MB) continuam aceitos como alternativas se estiverem instalados.
    """
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {image_path}")

    # 1. zxing-cpp
    try:
        import zxingcpp
        with Image.open(image_path) as img:
            results = zxingcpp.read_barcodes(img.convert("RGB"))
        for r in results:
            if r.valid and r.text:
                return r.text
    except ImportError:
        pass
    except Exception:
        pass

    # 2. Tenta pyzbar se instalado
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        with Image.open(image_path) as img:
            decoded = pyzbar_decode(img)
            if decoded:
                return decoded[0].data.decode("utf-8", errors="ignore")
    except Exception:
        pass

    # 3. Tenta OpenCV se instalado
    try:
        import cv2
        img_cv = cv2.imread(str(image_path))
        if img_cv is not None:
            detector = cv2.QRCodeDetector()
            val, pts, st = detector.detectAndDecode(img_cv)
            if val:
                return val
    except Exception:
        pass

    return None

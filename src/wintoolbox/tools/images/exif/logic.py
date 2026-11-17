"""
Lógica pura de extração, inspeção e remoção de metadados EXIF/GPS em imagens.
Inclui decodificação semântica em português de tags técnicas de câmeras, iPhones e Androids.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import ExifTags, Image

# Dicionários de tradução amigável para tags EXIF padrão
ORIENTATION_TRANSLATION = {
    1: "Normal (Horizontal)",
    2: "Espelhada Horizontal",
    3: "Rotacionada 180°",
    4: "Espelhada Vertical",
    5: "Espelhada e Rotacionada 90° Anti-horário",
    6: "Rotacionada 90° Horário (Foto Vertical)",
    7: "Espelhada e Rotacionada 90° Horário",
    8: "Rotacionada 90° Anti-horário",
}

FLASH_TRANSLATION = {
    0: "Flash não disparado",
    1: "Flash disparado (Modo manual)",
    5: "Flash disparado, luz estroboscópica não detectada",
    7: "Flash disparado, luz estroboscópica detectada",
    9: "Flash disparado (Obrigatório)",
    16: "Flash desligado (Modo forçado)",
    24: "Flash não disparado (Modo automático)",
    25: "Flash disparado (Modo automático)",
    32: "Sem função de flash",
}

EXPOSURE_PROGRAM_TRANSLATION = {
    0: "Não definido",
    1: "Manual",
    2: "Programa Normal (P)",
    3: "Prioridade de Abertura (Av)",
    4: "Prioridade de Obturador (Tv)",
    5: "Programa Criativo (Profundidade de campo)",
    6: "Programa Ação (Alta velocidade)",
    7: "Modo Retrato",
    8: "Modo Paisagem",
}

METERING_MODE_TRANSLATION = {
    0: "Desconhecido",
    1: "Média",
    2: "Ponderada ao Centro",
    3: "Pontual (Spot)",
    4: "Multi-pontual",
    5: "Matricial / Multi-segmento",
    6: "Parcial",
}

COLOR_SPACE_TRANSLATION = {
    1: "sRGB (Padrão Web/PC)",
    65535: "Display P3 / Amplo Gamut (iPhone/Mac)",
}

SCENE_CAPTURE_TRANSLATION = {
    0: "Padrão",
    1: "Paisagem",
    2: "Retrato",
    3: "Cena Noturna",
}

WHITE_BALANCE_TRANSLATION = {
    0: "Automático (AWB)",
    1: "Manual",
}


def translate_exif_value(tag_name: str, value: Any) -> str:
    """Traduz códigos numéricos obscuros em texto compreensível em português."""
    val_int = None
    try:
        val_int = int(value)
    except Exception:
        pass

    if tag_name == "Orientation" and val_int in ORIENTATION_TRANSLATION:
        return f"{val_int} — {ORIENTATION_TRANSLATION[val_int]}"
    if tag_name == "Flash" and val_int in FLASH_TRANSLATION:
        return f"{val_int} — {FLASH_TRANSLATION[val_int]}"
    if tag_name == "ExposureProgram" and val_int in EXPOSURE_PROGRAM_TRANSLATION:
        return f"{val_int} — {EXPOSURE_PROGRAM_TRANSLATION[val_int]}"
    if tag_name == "MeteringMode" and val_int in METERING_MODE_TRANSLATION:
        return f"{val_int} — {METERING_MODE_TRANSLATION[val_int]}"
    if tag_name == "ColorSpace" and val_int in COLOR_SPACE_TRANSLATION:
        return f"{val_int} — {COLOR_SPACE_TRANSLATION[val_int]}"
    if tag_name == "SceneCaptureType" and val_int in SCENE_CAPTURE_TRANSLATION:
        return f"{val_int} — {SCENE_CAPTURE_TRANSLATION[val_int]}"
    if tag_name == "WhiteBalance" and val_int in WHITE_BALANCE_TRANSLATION:
        return f"{val_int} — {WHITE_BALANCE_TRANSLATION[val_int]}"

    # Formatação de frações para tempo de exposição
    if tag_name == "ExposureTime":
        try:
            val_f = float(value)
            if 0 < val_f < 1:
                return f"1/{round(1 / val_f)} s ({val_f:.4f} s)"
            return f"{val_f} s"
        except Exception:
            pass

    if tag_name == "FNumber":
        try:
            return f"f/{float(value):.1f}"
        except Exception:
            pass

    if tag_name == "FocalLength":
        try:
            return f"{float(value):.1f} mm"
        except Exception:
            pass

    val_str = str(value)
    if len(val_str) > 120:
        return val_str[:117] + "..."
    return val_str


def _convert_to_degrees(value) -> float:
    """Converte coordenadas GPS em tuplas (graus, minutos, segundos) para graus decimais."""
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        return 0.0


def get_exif_info(image_path: Path) -> Dict[str, Any]:
    """Extrai informações amigáveis e estruturadas de metadados EXIF e GPS da imagem."""
    info = {
        "has_exif": False,
        "camera_make": "-",
        "camera_model": "-",
        "lens_model": "-",
        "dimensions": "-",
        "date_time": "-",
        "exposure": "-",
        "f_number": "-",
        "iso": "-",
        "focal_length": "-",
        "orientation": "-",
        "gps_lat": None,
        "gps_lon": None,
        "gps_url": None,
        "raw_tags": []  # List[Tuple[tag_id, tag_name, tag_value]]
    }

    try:
        with Image.open(image_path) as im:
            info["dimensions"] = f"{im.width} × {im.height} px"
            exif = im.getexif()
            if not exif:
                return info

            info["has_exif"] = True

            # Processa tags padrão
            for tag_id, val in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                translated_val = translate_exif_value(tag_name, val)
                info["raw_tags"].append((tag_id, tag_name, translated_val))

                if tag_name == "Make":
                    info["camera_make"] = str(val).strip()
                elif tag_name == "Model":
                    info["camera_model"] = str(val).strip()
                elif tag_name == "DateTime":
                    info["date_time"] = str(val).strip()
                elif tag_name == "Orientation":
                    info["orientation"] = translated_val

            # Processa IFD EXIF detalhado (dados de lente, velocidade, etc.)
            try:
                exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
                for tag_id, val in exif_ifd.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    translated_val = translate_exif_value(tag_name, val)
                    info["raw_tags"].append((tag_id, tag_name, translated_val))

                    if tag_name == "DateTimeOriginal":
                        info["date_time"] = str(val).strip()
                    elif tag_name == "ExposureTime":
                        info["exposure"] = translated_val
                    elif tag_name == "FNumber":
                        info["f_number"] = translated_val
                    elif tag_name in ("ISOSpeedRatings", "PhotographicSensitivity"):
                        info["iso"] = f"ISO {val}"
                    elif tag_name == "FocalLength":
                        info["focal_length"] = translated_val
                    elif tag_name == "LensModel":
                        info["lens_model"] = str(val).strip()
            except Exception:
                pass

            # Processa GPS IFD
            try:
                gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
                if gps_ifd:
                    gps_data = {}
                    for k, v in gps_ifd.items():
                        sub_tag = ExifTags.GPSTAGS.get(k, k)
                        gps_data[sub_tag] = v
                        info["raw_tags"].append((k, f"GPS_{sub_tag}", str(v)))

                    lat_raw = gps_data.get("GPSLatitude")
                    lat_ref = gps_data.get("GPSLatitudeRef", "N")
                    lon_raw = gps_data.get("GPSLongitude")
                    lon_ref = gps_data.get("GPSLongitudeRef", "W")

                    if lat_raw and lon_raw:
                        lat = _convert_to_degrees(lat_raw)
                        if lat_ref != "N":
                            lat = -lat
                        lon = _convert_to_degrees(lon_raw)
                        if lon_ref != "W":
                            lon = -lon

                        info["gps_lat"] = f"{lat:.6f}°"
                        info["gps_lon"] = f"{lon:.6f}°"
                        info["gps_url"] = f"https://www.google.com/maps?q={lat},{lon}"
            except Exception:
                pass

    except Exception:
        pass

    return info


def strip_metadata(src: Path, dst: Path, remove_gps_only: bool = False) -> bool:
    """Remove metadados EXIF, GPS e perfis mantendo a qualidade dos pixels."""
    try:
        with Image.open(src) as im:
            if remove_gps_only:
                exif = im.getexif()
                if 0x8825 in exif:
                    del exif[0x8825]
                dst.parent.mkdir(parents=True, exist_ok=True)
                im.save(dst, exif=exif)
                return True

            data = list(im.getdata())
            clean_im = Image.new(im.mode, im.size)
            clean_im.putdata(data)

            dst.parent.mkdir(parents=True, exist_ok=True)
            ext = dst.suffix.lower()

            if ext in (".jpg", ".jpeg"):
                if clean_im.mode in ("RGBA", "LA", "P"):
                    rgb = Image.new("RGB", clean_im.size, (255, 255, 255))
                    rgb.paste(clean_im.convert("RGB"))
                    rgb.save(dst, format="JPEG", quality=95, optimize=True)
                else:
                    clean_im.save(dst, format="JPEG", quality=95, optimize=True)
            elif ext == ".png":
                clean_im.save(dst, format="PNG", optimize=True)
            elif ext == ".webp":
                clean_im.save(dst, format="WEBP", quality=95)
            else:
                clean_im.save(dst)
        return True
    except Exception:
        return False

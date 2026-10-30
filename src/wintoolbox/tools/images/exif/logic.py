"""
Lógica pura de extração, inspeção e remoção de metadados EXIF/GPS em imagens.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import ExifTags, Image

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
        "camera_make": "Desconhecido",
        "camera_model": "Desconhecido",
        "date_time": "Não disponível",
        "exposure": "Não disponível",
        "f_number": "Não disponível",
        "iso": "Não disponível",
        "focal_length": "Não disponível",
        "gps_lat": None,
        "gps_lon": None,
        "gps_url": None,
        "raw_tags": []  # List[Tuple[tag_id, tag_name, tag_value]]
    }

    try:
        with Image.open(image_path) as im:
            exif = im.getexif()
            if not exif:
                return info

            info["has_exif"] = True

            # Processa tags padrão
            for tag_id, val in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                val_str = str(val)
                if len(val_str) > 100:
                    val_str = val_str[:97] + "..."
                info["raw_tags"].append((tag_id, tag_name, val_str))

                if tag_name == "Make":
                    info["camera_make"] = str(val).strip()
                elif tag_name == "Model":
                    info["camera_model"] = str(val).strip()
                elif tag_name == "DateTime":
                    info["date_time"] = str(val).strip()

            # Processa IFD EXIF detalhado (dados de lente, velocidade, etc.)
            try:
                exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
                for tag_id, val in exif_ifd.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    val_str = str(val)
                    if len(val_str) > 100:
                        val_str = val_str[:97] + "..."
                    info["raw_tags"].append((tag_id, tag_name, val_str))

                    if tag_name == "DateTimeOriginal":
                        info["date_time"] = str(val).strip()
                    elif tag_name == "ExposureTime":
                        info["exposure"] = f"{val} s"
                    elif tag_name == "FNumber":
                        info["f_number"] = f"f/{val}"
                    elif tag_name in ("ISOSpeedRatings", "PhotographicSensitivity"):
                        info["iso"] = f"ISO {val}"
                    elif tag_name == "FocalLength":
                        info["focal_length"] = f"{val} mm"
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
                        if lon_ref != "E":
                            lon = -lon

                        info["gps_lat"] = round(lat, 6)
                        info["gps_lon"] = round(lon, 6)
                        info["gps_url"] = f"https://www.google.com/maps?q={round(lat, 6)},{round(lon, 6)}"
            except Exception:
                pass

    except Exception:
        pass

    return info

def get_exif_capture_date(image_path: Path) -> Optional[datetime]:
    """Tenta obter a data de captura original da foto."""
    try:
        with Image.open(image_path) as im:
            exif = im.getexif()
            if not exif:
                return None
            val = None
            try:
                exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
                val = exif_ifd.get(36867)  # DateTimeOriginal
            except Exception:
                pass
            if not val:
                val = exif.get(306)  # DateTime

            if val:
                # Formato comum: "YYYY:MM:DD HH:MM:SS"
                clean_str = str(val).strip()
                return datetime.strptime(clean_str, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None

def strip_metadata(src: Path, dst: Path, remove_gps_only: bool = False) -> None:
    """Remove metadados da imagem garantindo privacidade."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        if remove_gps_only:
            exif = im.getexif()
            if exif:
                # Remove apenas a referência GPS
                if ExifTags.IFD.GPSInfo in exif:
                    del exif[ExifTags.IFD.GPSInfo]
                if hasattr(exif, "_ifds") and ExifTags.IFD.GPSInfo in exif._ifds:
                    del exif._ifds[ExifTags.IFD.GPSInfo]
                im.save(dst, exif=exif.tobytes())
                return

        # Remoção Total: copia os pixels para uma nova imagem limpa
        clean_im = Image.frombytes(im.mode, im.size, im.tobytes())
        clean_im.save(dst)

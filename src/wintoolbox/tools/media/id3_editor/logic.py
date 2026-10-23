"""
Lógica pura para edição de metadados e tags ID3 em arquivos de áudio MP3 utilizando mutagen.
"""
from pathlib import Path
from typing import Any, Dict, Optional
import mutagen
from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.easyid3 import EasyID3


def read_mp3_tags(file_path: Path) -> Dict[str, str]:
    """Lê as tags básicas de um arquivo MP3."""
    file_path = Path(file_path)
    try:
        audio = EasyID3(str(file_path))
        return {
            "title": audio.get("title", [""])[0],
            "artist": audio.get("artist", [""])[0],
            "album": audio.get("album", [""])[0],
            "date": audio.get("date", [""])[0],
            "genre": audio.get("genre", [""])[0],
        }
    except Exception:
        return {}


def edit_mp3_tags(
    file_path: Path,
    title: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    year: Optional[str] = None,
    genre: Optional[str] = None,
    cover_image_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Grava metadados ID3v2 no arquivo MP3.
    """
    file_path = Path(file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    # 1. Tags de texto via EasyID3
    try:
        audio = EasyID3(str(file_path))
    except ID3NoHeaderError:
        audio = mutagen.File(str(file_path), easy=True)
        audio.add_tags()

    if title and title.strip():
        audio["title"] = title.strip()
    if artist and artist.strip():
        audio["artist"] = artist.strip()
    if album and album.strip():
        audio["album"] = album.strip()
    if year and year.strip():
        audio["date"] = year.strip()
    if genre and genre.strip():
        audio["genre"] = genre.strip()

    audio.save()

    # 2. Imagem de capa (APIC frame)
    if cover_image_path:
        cov_p = Path(cover_image_path)
        if cov_p.is_file():
            id3 = ID3(str(file_path))
            mime = "image/jpeg" if cov_p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
            with open(cov_p, "rb") as f_cov:
                id3.delall("APIC")
                id3.add(APIC(
                    encoding=3, # UTF-8
                    mime=mime,
                    type=3,     # Capa frontal
                    desc="Cover",
                    data=f_cov.read()
                ))
            id3.save()

    return read_mp3_tags(file_path)

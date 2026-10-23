"""
Lógica pura para download de mídia multiplataforma utilizando yt-dlp local.
"""
from pathlib import Path
from typing import Any, Callable, Dict, Optional
import yt_dlp

from wintoolbox.core.logging_setup import YtDlpLogger

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe


def download_media_url(
    url: str,
    output_dir: Path,
    audio_only: bool = False,
    quality: str = "best",
    progress_hook: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Baixa vídeo ou áudio de uma URL usando a biblioteca yt-dlp.
    """
    url = url.strip()
    if not url:
        raise ValueError("A URL de download não pode estar vazia.")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = get_ffmpeg_exe()
    ffmpeg_dir = str(Path(ffmpeg_path).parent)

    ydl_opts: Dict[str, Any] = {
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "ffmpeg_location": ffmpeg_dir,
        "quiet": True,
        "no_warnings": False,
        # Avisos e erros do yt-dlp vão para a central de logs (logger 'yt_dlp')
        "logger": YtDlpLogger(),
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    if audio_only:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        if quality == "1080p":
            ydl_opts["format"] = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]"
        elif quality == "720p":
            ydl_opts["format"] = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]"
        elif quality == "480p":
            ydl_opts["format"] = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]"
        else:
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "midia_baixada")
        # O yt-dlp sanitiza o título (remove / : ? etc.); o caminho real vem do próprio info
        downloads = info.get("requested_downloads") or []
        if downloads and downloads[-1].get("filepath"):
            expected_file = Path(downloads[-1]["filepath"])
        else:
            expected_file = Path(ydl.prepare_filename(info))
            if audio_only:
                expected_file = expected_file.with_suffix(".mp3")

        return {
            "title": title,
            "uploader": info.get("uploader", "Desconhecido"),
            "duration": info.get("duration", 0),
            "output_path": str(expected_file),
        }

"""
Lógica pura da ferramenta Transcrição de Áudio Offline (media.transcribe).
Suporta execução via faster-whisper / whisper ou fallback gracioso, 100% offline.
"""
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe


def is_whisper_available() -> bool:
    """Verifica se faster-whisper ou openai-whisper está instalado no ambiente."""
    try:
        import faster_whisper
        return True
    except ImportError:
        pass
    try:
        import whisper
        return True
    except ImportError:
        pass
    return False


def get_available_engine() -> str:
    """Retorna o nome do motor de transcrição detectado ('faster-whisper', 'whisper' ou 'none')."""
    try:
        import faster_whisper
        return "faster-whisper"
    except ImportError:
        pass
    try:
        import whisper
        return "whisper"
    except ImportError:
        pass
    return "none"


def extract_audio_wav(input_media: Path, output_wav: Path) -> Path:
    """Converte qualquer arquivo de áudio/vídeo em WAV mono 16kHz para alimentar o modelo."""
    input_media = Path(input_media)
    output_wav = Path(output_wav)
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-i", str(input_media),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_wav),
    ]

    flags = 0x08000000 if os.name == "nt" else 0
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags
    )
    if res.returncode != 0:
        raise RuntimeError(f"Falha ao extrair áudio com FFmpeg:\n{res.stderr[-300:]}")

    return output_wav


def transcribe_audio_file(
    media_path: Path,
    model_size: str = "base",
    language: str = "pt",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Transcreve áudio localmente retornando lista de segmentos com timestamps e texto.
    """
    media_path = Path(media_path)
    if not media_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {media_path}")

    engine = get_available_engine()
    if engine == "none":
        raise RuntimeError(
            "O motor de IA 'faster-whisper' não está instalado no ambiente.\n"
            "Instale-o executando: pip install faster-whisper"
        )

    with tempfile.TemporaryDirectory(prefix="wtbx_transcribe_") as tmp_dir:
        temp_wav = Path(tmp_dir) / "extracted_audio.wav"
        if progress_cb:
            progress_cb("Extraindo áudio do arquivo...")
        extract_audio_wav(media_path, temp_wav)

        segments_data = []

        if engine == "faster-whisper":
            from faster_whisper import WhisperModel
            if progress_cb:
                progress_cb(f"Carregando modelo '{model_size}' na memória...")

            model = WhisperModel(model_size, device="cpu", compute_type="int8")

            if progress_cb:
                progress_cb("Transcrevendo áudio com Inteligência Artificial...")

            lang = None if language == "auto" else language
            segments, info = model.transcribe(
                str(temp_wav),
                language=lang,
                beam_size=5,
                vad_filter=True
            )

            for seg in segments:
                segments_data.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                })
        else:
            import whisper
            if progress_cb:
                progress_cb(f"Carregando modelo Whisper '{model_size}'...")

            model = whisper.load_model(model_size, device="cpu")
            if progress_cb:
                progress_cb("Transcrevendo áudio...")

            lang = None if language == "auto" else language
            result = model.transcribe(str(temp_wav), language=lang)
            for seg in result.get("segments", []):
                segments_data.append({
                    "start": round(seg["start"], 2),
                    "end": round(seg["end"], 2),
                    "text": seg["text"].strip(),
                })

        return segments_data


def format_srt_timestamp(seconds: float) -> str:
    """Converte segundos float para formato de tempo SRT: 00:00:00,000"""
    total_ms = int(seconds * 1000)
    h = total_ms // 3600000
    total_ms %= 3600000
    m = total_ms // 60000
    total_ms %= 60000
    s = total_ms // 1000
    ms = total_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_plain_text(segments: List[Dict[str, Any]]) -> str:
    """Converte segmentos de áudio em texto corrido contínuo."""
    return "\n\n".join(seg["text"] for seg in segments if seg["text"])


def segments_to_srt(segments: List[Dict[str, Any]]) -> str:
    """Converte segmentos de transcrição em arquivo de legenda SRT válido."""
    blocks = []
    for idx, seg in enumerate(segments, 1):
        t_start = format_srt_timestamp(seg["start"])
        t_end = format_srt_timestamp(seg["end"])
        text = seg["text"]
        blocks.append(f"{idx}\n{t_start} --> {t_end}\n{text}")
    return "\n\n".join(blocks) + "\n"

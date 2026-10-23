"""
Lógica pura para Texto para Fala (TTS) 100% offline local via pyttsx3 e SAPI do Windows.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import pyttsx3


def get_available_voices() -> List[Dict[str, str]]:
    """Retorna a lista de vozes do sintetizador de fala instaladas no Windows."""
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    voice_list = []
    for v in voices:
        voice_list.append({
            "id": v.id,
            "name": v.name,
            "languages": getattr(v, "languages", []),
        })
    return voice_list


def speak_text(
    text: str,
    voice_id: Optional[str] = None,
    rate: int = 150,
    volume: float = 1.0
) -> None:
    """Sintetiza e reproduz o texto imediatamente nas caixas de som."""
    text = text.strip()
    if not text:
        return

    engine = pyttsx3.init()
    if voice_id:
        engine.setProperty("voice", voice_id)
    engine.setProperty("rate", rate)
    engine.setProperty("volume", max(0.0, min(1.0, volume)))

    engine.say(text)
    engine.runAndWait()


def save_speech_to_file(
    text: str,
    dst_path: Path,
    voice_id: Optional[str] = None,
    rate: int = 150,
    volume: float = 1.0
) -> Path:
    """Grava a síntese de voz em um arquivo de áudio (.wav)."""
    text = text.strip()
    if not text:
        raise ValueError("O texto para síntese de voz não pode estar vazio.")

    dst_path = Path(dst_path).resolve()
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    engine = pyttsx3.init()
    if voice_id:
        engine.setProperty("voice", voice_id)
    engine.setProperty("rate", rate)
    engine.setProperty("volume", max(0.0, min(1.0, volume)))

    engine.save_to_file(text, str(dst_path))
    engine.runAndWait()

    if not dst_path.is_file() or dst_path.stat().st_size == 0:
        raise RuntimeError("O arquivo de áudio de fala não foi gravado.")

    return dst_path

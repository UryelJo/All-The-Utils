"""
Lógica pura para Texto para Fala (TTS) 100% offline.
Motor principal: Windows.Media.SpeechSynthesis (WinRT), que enxerga as vozes OneCore do
Windows 10/11 (inclusive as vozes naturais instaladas). Reserva: SAPI5 via pyttsx3, que só
enxerga as vozes SAPI clássicas.
"""
import winsound
from pathlib import Path
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.winrt_utils import run_winrt

_log = get_logger("speech")

WINRT_PREFIX = "winrt:"
DEFAULT_RATE_PPM = 160  # velocidade "normal" exibida na interface


def _winrt_available() -> bool:
    try:
        import winrt.windows.media.speechsynthesis  # noqa: F401
        return True
    except Exception:
        return False


def _list_winrt_voices() -> List[Dict[str, Any]]:
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer

    async def run() -> List[Dict[str, Any]]:
        return [
            {"id": f"{WINRT_PREFIX}{v.id}", "name": f"{v.display_name} ({v.language})", "languages": [v.language]}
            for v in SpeechSynthesizer.all_voices
        ]

    return run_winrt(run)


def _list_sapi_voices() -> List[Dict[str, Any]]:
    import pyttsx3
    engine = pyttsx3.init()
    return [
        {"id": v.id, "name": f"{v.name} (SAPI)", "languages": getattr(v, "languages", [])}
        for v in engine.getProperty("voices")
    ]


def get_available_voices() -> List[Dict[str, Any]]:
    """Vozes WinRT/OneCore primeiro; vozes SAPI que não estejam duplicadas em seguida."""
    voices: List[Dict[str, Any]] = []
    if _winrt_available():
        try:
            voices.extend(_list_winrt_voices())
        except Exception:
            _log.warning("Falha ao listar vozes WinRT", exc_info=True)
    try:
        known = {v["name"].split(" (")[0].lower() for v in voices}
        voices.extend(v for v in _list_sapi_voices() if v["name"].split(" (")[0].lower() not in known)
    except Exception:
        _log.warning("Falha ao listar vozes SAPI (pyttsx3)", exc_info=True)
    return voices


def _synthesize_winrt(text: str, voice_id: Optional[str], rate: int, volume: float) -> bytes:
    """Sintetiza para WAV em memória via WinRT."""
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer
    from winrt.windows.storage.streams import DataReader

    async def run() -> bytes:
        synth = SpeechSynthesizer()
        if voice_id:
            wanted = voice_id[len(WINRT_PREFIX):]
            for v in SpeechSynthesizer.all_voices:
                if v.id == wanted:
                    synth.voice = v
                    break
        # A interface usa "palavras por minuto"; o WinRT usa multiplicador (0,5 a 6,0)
        synth.options.speaking_rate = max(0.5, min(6.0, rate / DEFAULT_RATE_PPM))
        synth.options.audio_volume = max(0.0, min(1.0, volume))
        stream = await synth.synthesize_text_to_stream_async(text)
        size = stream.size
        reader = DataReader(stream.get_input_stream_at(0))
        await reader.load_async(size)
        buf = bytearray(size)
        reader.read_bytes(buf)
        return bytes(buf)

    return run_winrt(run)


def _sapi_engine(voice_id: Optional[str], rate: int, volume: float):
    import pyttsx3
    engine = pyttsx3.init()
    if voice_id:
        engine.setProperty("voice", voice_id)
    engine.setProperty("rate", rate)
    engine.setProperty("volume", max(0.0, min(1.0, volume)))
    return engine


def _use_winrt(voice_id: Optional[str]) -> bool:
    if voice_id:
        return voice_id.startswith(WINRT_PREFIX)
    return _winrt_available()


def speak_text(
    text: str,
    voice_id: Optional[str] = None,
    rate: int = DEFAULT_RATE_PPM,
    volume: float = 1.0
) -> None:
    """Sintetiza e reproduz o texto imediatamente nas caixas de som."""
    text = text.strip()
    if not text:
        return
    if _use_winrt(voice_id):
        wav = _synthesize_winrt(text, voice_id, rate, volume)
        winsound.PlaySound(wav, winsound.SND_MEMORY)
        return
    engine = _sapi_engine(voice_id, rate, volume)
    engine.say(text)
    engine.runAndWait()


def save_speech_to_file(
    text: str,
    dst_path: Path,
    voice_id: Optional[str] = None,
    rate: int = DEFAULT_RATE_PPM,
    volume: float = 1.0
) -> Path:
    """Grava a síntese de voz em um arquivo de áudio (.wav)."""
    text = text.strip()
    if not text:
        raise ValueError("O texto para síntese de voz não pode estar vazio.")

    dst_path = Path(dst_path).resolve()
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if _use_winrt(voice_id):
        dst_path.write_bytes(_synthesize_winrt(text, voice_id, rate, volume))
    else:
        engine = _sapi_engine(voice_id, rate, volume)
        engine.save_to_file(text, str(dst_path))
        engine.runAndWait()

    if not dst_path.is_file() or dst_path.stat().st_size == 0:
        raise RuntimeError("O arquivo de áudio de fala não foi gravado.")

    return dst_path

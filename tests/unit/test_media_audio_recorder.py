"""
Testes unitários para a ferramenta Gravador de Áudio (media.audio_recorder).
Valida listagem de dispositivos, manipulação de arquivos de gravação e sessão.
"""
import pytest
from pathlib import Path

from wintoolbox.tools.media.audio_recorder.logic import (
    AudioRecorderSession,
    generate_synthetic_audio,
    get_audio_info,
    list_audio_input_devices,
)


def test_list_audio_input_devices():
    """Valida execução da listagem de dispositivos de entrada de áudio."""
    devices = list_audio_input_devices()
    assert isinstance(devices, list)
    # Se houver dispositivos listados, nenhum deve ser string vazia
    for dev in devices:
        assert isinstance(dev, str)
        assert len(dev.strip()) > 0


def test_generate_synthetic_audio_and_info(tmp_path: Path):
    """Testa geração e inspeção de áudio real de 2.0 segundos."""
    audio_file = tmp_path / "gravacao_teste.wav"
    res = generate_synthetic_audio(audio_file, duration_seconds=2.0, frequency=440, sample_rate=44100)
    assert res == audio_file
    assert audio_file.is_file()

    info = get_audio_info(audio_file)
    assert info["sample_rate"] == 44100
    assert info["channels"] == 1
    assert round(info["duration"], 1) == 2.0
    assert info["size_bytes"] > 0


def test_audio_recorder_session_lifecycle():
    """Valida controle de estado e proteção contra chamadas inválidas da sessão."""
    session = AudioRecorderSession()
    assert not session.is_recording
    assert session.elapsed_seconds == 0.0

    # Chamar stop_recording sem ter iniciado deve disparar RuntimeError
    with pytest.raises(RuntimeError):
        session.stop_recording()

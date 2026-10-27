"""
Lógica pura para gravação de áudio utilizando subprocesso FFmpeg (DirectShow / WASAPI).
Gerencia listagem de dispositivos de áudio, sessões de gravação ativas e finalização limpa.
Isolado de qualquer dependência com frameworks de interface gráfica.
"""
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_info


def list_audio_input_devices() -> List[str]:
    """
    Lista os dispositivos de entrada de áudio (microfones / placas) disponíveis no sistema
    via DirectShow do FFmpeg.
    """
    ffmpeg = get_ffmpeg_exe()
    cmd = [ffmpeg, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]

    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    output = res.stderr or ""
    devices: List[str] = []

    # O ffmpeg exibe dispositivos no padrão: [dshow @ ...]  "Nome do Dispositivo" (audio)
    pattern = re.compile(r'\[dshow @ [^\]]+\]\s+"([^"]+)"\s+\(audio\)')
    for match in pattern.finditer(output):
        name = match.group(1).strip()
        if name and name not in devices:
            devices.append(name)

    return devices


class AudioRecorderSession:
    """Gerencia uma sessão ativa de gravação de áudio via subprocesso FFmpeg."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._output_path: Optional[Path] = None
        self._start_time: float = 0.0

    @property
    def is_recording(self) -> bool:
        """Verifica se o processo de gravação está ativo no momento."""
        return self._process is not None and self._process.poll() is None

    @property
    def elapsed_seconds(self) -> float:
        """Retorna os segundos decorridos desde o início da gravação."""
        if not self.is_recording:
            return 0.0
        return max(0.0, time.time() - self._start_time)

    def start_recording(
        self,
        output_path: Path,
        device_name: Optional[str] = None,
        sample_rate: int = 44100,
        channels: int = 2
    ) -> None:
        """
        Inicia o processo de captura e gravação de áudio.
        """
        if self.is_recording:
            raise RuntimeError("Já existe uma gravação de áudio em andamento.")

        ffmpeg = get_ffmpeg_exe()
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd: List[str] = [ffmpeg, "-y"]

        if device_name:
            cmd.extend(["-f", "dshow", "-i", f"audio={device_name}"])
        else:
            # Se nenhum dispositivo for especificado, tenta capturar dispositivo padrão
            cmd.extend(["-f", "dshow", "-i", "audio=default"])

        cmd.extend([
            "-ar", str(sample_rate),
            "-ac", str(channels),
            str(output_path)
        ])

        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        self._output_path = output_path
        self._start_time = time.time()

    def stop_recording(self, timeout: float = 5.0) -> Path:
        """
        Finaliza a gravação enviando o comando 'q' para o FFmpeg para salvar os cabeçalhos.
        """
        if not self._process:
            raise RuntimeError("Nenhuma gravação ativa para finalizar.")

        out_path = self._output_path

        try:
            # Envia 'q' para fechar de forma limpa os headers do arquivo de áudio
            if self._process.poll() is None and self._process.stdin:
                self._process.stdin.write("q")
                self._process.stdin.flush()
            self._process.wait(timeout=timeout)
        except Exception:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                self._process.wait(timeout=2.0)
        finally:
            self._process = None
            self._output_path = None
            self._start_time = 0.0

        if not out_path or not out_path.is_file() or out_path.stat().st_size == 0:
            raise RuntimeError("Arquivo de áudio gravado não foi gerado ou está corrompido.")

        return out_path


def generate_synthetic_audio(
    output_path: Path,
    duration_seconds: float = 2.0,
    frequency: int = 440,
    sample_rate: int = 44100
) -> Path:
    """
    Gera um áudio sintético determinístico com FFmpeg lavfi (útil para testes de gravação).
    """
    ffmpeg = get_ffmpeg_exe()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={frequency}:duration={duration_seconds}",
        "-ar", str(sample_rate),
        str(output_path)
    ]

    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    if res.returncode != 0 or not output_path.is_file():
        raise RuntimeError(f"Falha ao gerar áudio sintético: {res.stderr}")

    return output_path


def get_audio_info(file_path: Path) -> Dict[str, Any]:
    """Obtém resumo das propriedades do arquivo de áudio gravado."""
    info = get_media_info(file_path)
    fmt = info.get("format", {})
    audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]

    duration = float(fmt.get("duration", 0.0))
    size_bytes = int(fmt.get("size", file_path.stat().st_size if file_path.is_file() else 0))

    sample_rate = 0
    channels = 0
    codec_name = "desconhecido"

    if audio_streams:
        st = audio_streams[0]
        sample_rate = int(st.get("sample_rate", 0))
        channels = int(st.get("channels", 0))
        codec_name = st.get("codec_name", "")

    return {
        "duration": duration,
        "size_bytes": size_bytes,
        "sample_rate": sample_rate,
        "channels": channels,
        "codec_name": codec_name
    }

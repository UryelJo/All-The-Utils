"""
Lógica para gravação de tela nativa no Windows usando gdigrab do ffmpeg.
"""
import subprocess
import time
from pathlib import Path
from typing import Optional

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe


class ScreenRecorder:
    """Gerenciador do processo ffmpeg para gravação contínua da área de trabalho."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._output_file: Optional[Path] = None
        self._start_time: float = 0.0

    def start_recording(
        self,
        dst_path: Path,
        fps: int = 30
    ) -> None:
        """Inicia a gravação da tela inteira."""
        if self.is_recording():
            raise RuntimeError("Uma gravação de tela já está em andamento.")

        ffmpeg = get_ffmpeg_exe()
        dst_path = Path(dst_path).resolve()
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            ffmpeg, "-y",
            "-f", "gdigrab",
            "-framerate", str(fps),
            "-i", "desktop",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "24",
            "-pix_fmt", "yuv420p",
            str(dst_path)
        ]

        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        self._output_file = dst_path
        self._start_time = time.time()

    def stop_recording(self) -> Path:
        """Encerra a gravação de forma segura e garante a integridade do arquivo MP4."""
        if not self._process or not self.is_recording():
            raise RuntimeError("Nenhuma gravação de tela ativa para encerrar.")

        try:
            # Envia 'q' para o ffmpeg finalizar o container MP4
            if self._process.stdin:
                self._process.stdin.write("q\n")
                self._process.stdin.flush()
            self._process.wait(timeout=5)
        except Exception:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except Exception:
                self._process.kill()
        finally:
            self._process = None

        if not self._output_file or not self._output_file.is_file():
            raise RuntimeError("O arquivo de gravação não foi gerado.")

        return self._output_file

    def is_recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def get_elapsed_seconds(self) -> float:
        if not self.is_recording():
            return 0.0
        return time.time() - self._start_time

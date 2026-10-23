"""
Lógica para gravação de tela nativa no Windows usando o ffmpeg.
Motor principal: ddagrab (Desktop Duplication API, captura pela GPU no Windows 10/11), que
mantém a taxa de quadros real com pouca CPU. Reserva: gdigrab (GDI), com dimensões
ajustadas para valores pares (o libx264 recusa alturas ímpares, comuns em multi-monitor).
"""
import subprocess
import time
from pathlib import Path
from typing import IO, List, Optional

from wintoolbox.core.logging_setup import get_logger, get_logs_dir
from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe

_log = get_logger("recorder")

ENCODE_ARGS = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p"]
STARTUP_CHECK_SECONDS = 1.5


class ScreenRecorder:
    """Gerenciador do processo ffmpeg para gravação contínua da área de trabalho."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._output_file: Optional[Path] = None
        self._start_time: float = 0.0
        self._log_file: Optional[IO] = None
        self.engine: str = ""

    @staticmethod
    def _capture_args(engine: str, fps: int, monitor: int) -> List[str]:
        if engine == "ddagrab":
            return ["-f", "lavfi", "-i", f"ddagrab=output_idx={monitor}:framerate={fps}",
                    "-vf", "hwdownload,format=bgra"]
        return ["-f", "gdigrab", "-framerate", str(fps), "-i", "desktop",
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]

    def _launch(self, engine: str, dst_path: Path, fps: int, monitor: int) -> subprocess.Popen:
        ffmpeg = get_ffmpeg_exe()
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
               *self._capture_args(engine, fps, monitor), *ENCODE_ARGS, str(dst_path)]
        # stderr em arquivo: um PIPE sem leitor enche e congela o ffmpeg em gravações longas
        self._log_file = open(get_logs_dir() / "ffmpeg_recorder.log", "w", encoding="utf-8", errors="replace")
        return subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=self._log_file,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    def start_recording(
        self,
        dst_path: Path,
        fps: int = 30,
        monitor: int = 0
    ) -> None:
        """Inicia a gravação do monitor indicado (ddagrab) ou da área de trabalho inteira (gdigrab)."""
        if self.is_recording():
            raise RuntimeError("Uma gravação de tela já está em andamento.")

        dst_path = Path(dst_path).resolve()
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        for engine in ("ddagrab", "gdigrab"):
            self._process = self._launch(engine, dst_path, fps, monitor)
            deadline = time.time() + STARTUP_CHECK_SECONDS
            while time.time() < deadline and self._process.poll() is None:
                time.sleep(0.1)
            if self._process.poll() is None:
                self.engine = engine
                self._output_file = dst_path
                self._start_time = time.time()
                _log.info("Gravação iniciada com %s em %s", engine, dst_path)
                return
            self._close_log()
            _log.warning("Captura via %s falhou (código %s); veja ffmpeg_recorder.log",
                         engine, self._process.returncode)
        self._process = None
        raise RuntimeError("Não foi possível iniciar a gravação (ddagrab e gdigrab falharam). "
                           "Detalhes em logs/ffmpeg_recorder.log.")

    def stop_recording(self) -> Path:
        """Encerra a gravação de forma segura e garante a integridade do arquivo MP4."""
        if not self._process or not self.is_recording():
            raise RuntimeError("Nenhuma gravação de tela ativa para encerrar.")

        try:
            # Envia 'q' para o ffmpeg finalizar o container MP4
            if self._process.stdin:
                self._process.stdin.write("q\n")
                self._process.stdin.flush()
            self._process.wait(timeout=10)
        except Exception:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except Exception:
                self._process.kill()
        finally:
            self._process = None
            self._close_log()

        if not self._output_file or not self._output_file.is_file():
            raise RuntimeError("O arquivo de gravação não foi gerado.")

        return self._output_file

    def _close_log(self) -> None:
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None

    def is_recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def get_elapsed_seconds(self) -> float:
        if not self.is_recording():
            return 0.0
        return time.time() - self._start_time

"""
Lógica pura da máquina de estados do Timer Pomodoro.
Isolada de bibliotecas de interface visual.
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("productivity.pomodoro")

MODE_FOCUS = "focus"
MODE_SHORT_BREAK = "short_break"
MODE_LONG_BREAK = "long_break"

MODE_LABELS: Dict[str, str] = {
    MODE_FOCUS: "Foco no Trabalho",
    MODE_SHORT_BREAK: "Pausa Curta",
    MODE_LONG_BREAK: "Pausa Longa"
}


@dataclass
class PomodoroConfig:
    focus_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    long_break_interval: int = 4


class PomodoroManager:
    """Gerenciador determinístico de ciclos Pomodoro."""

    def __init__(self, config: Optional[PomodoroConfig] = None):
        self.config = config or PomodoroConfig()
        self.mode = MODE_FOCUS
        self.remaining_seconds = self.config.focus_minutes * 60
        self.is_running = False
        self.cycles_completed = 0
        self.total_focus_seconds = 0

    def start(self) -> None:
        self.is_running = True

    def pause(self) -> None:
        self.is_running = False

    def reset_current_mode(self) -> None:
        self.is_running = False
        self.remaining_seconds = self.get_duration_for_mode(self.mode)

    def get_duration_for_mode(self, mode: str) -> int:
        if mode == MODE_FOCUS:
            return max(1, self.config.focus_minutes) * 60
        elif mode == MODE_SHORT_BREAK:
            return max(1, self.config.short_break_minutes) * 60
        elif mode == MODE_LONG_BREAK:
            return max(1, self.config.long_break_minutes) * 60
        return 25 * 60

    def tick(self, step_seconds: int = 1) -> Tuple[bool, Optional[str]]:
        """
        Avança o cronômetro. Se o tempo zerar, conclui a etapa, calcula a próxima
        e retorna (etapa_concluida=True, mensagem_de_notificacao).
        """
        if not self.is_running:
            return False, None

        self.remaining_seconds -= step_seconds
        if self.mode == MODE_FOCUS:
            self.total_focus_seconds += step_seconds

        if self.remaining_seconds <= 0:
            self.remaining_seconds = 0
            self.is_running = False
            return self._advance_to_next_phase()

        return False, None

    def _advance_to_next_phase(self) -> Tuple[bool, str]:
        """Avança de Foco -> Pausa ou de Pausa -> Foco."""
        if self.mode == MODE_FOCUS:
            self.cycles_completed += 1
            if self.cycles_completed % self.config.long_break_interval == 0:
                self.mode = MODE_LONG_BREAK
                msg = "Sessão de foco concluída! Você completou um grande ciclo. Aproveite sua Pausa Longa."
            else:
                self.mode = MODE_SHORT_BREAK
                msg = "Tempo de foco finalizado! Faça uma pausa curta para descansar."
        else:
            self.mode = MODE_FOCUS
            msg = "A pausa terminou! Hora de voltar ao foco total."

        self.remaining_seconds = self.get_duration_for_mode(self.mode)
        return True, msg

    def skip_to_next_phase(self) -> None:
        """Pula manualmente para a próxima etapa."""
        self.is_running = False
        if self.mode == MODE_FOCUS:
            if (self.cycles_completed + 1) % self.config.long_break_interval == 0:
                self.mode = MODE_LONG_BREAK
            else:
                self.mode = MODE_SHORT_BREAK
        else:
            self.mode = MODE_FOCUS

        self.remaining_seconds = self.get_duration_for_mode(self.mode)

    def set_durations(self, focus_min: int, short_min: int, long_min: int) -> None:
        self.config.focus_minutes = max(1, focus_min)
        self.config.short_break_minutes = max(1, short_min)
        self.config.long_break_minutes = max(1, long_min)
        if not self.is_running:
            self.remaining_seconds = self.get_duration_for_mode(self.mode)

    def get_progress_percentage(self) -> float:
        total = self.get_duration_for_mode(self.mode)
        if total <= 0:
            return 0.0
        elapsed = total - self.remaining_seconds
        return min(1.0, max(0.0, elapsed / total))

    @staticmethod
    def format_time(seconds: int) -> str:
        s = max(0, seconds)
        mins = s // 60
        secs = s % 60
        return f"{mins:02d}:{secs:02d}"

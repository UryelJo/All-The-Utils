"""
Testes unitários das ferramentas de Produtividade (Fase 10).
Testa a lógica de:
- productivity.clipboard_history
- productivity.todo
- productivity.pomodoro
- productivity.reminders
- productivity.quick_notes
- productivity.time_tracker
"""
from datetime import datetime, timedelta
from pathlib import Path
import pytest

# 1. Clipboard History
from wintoolbox.tools.productivity.clipboard_history.logic import (
    add_clipboard_item, clear_clipboard_history, delete_clipboard_item,
    list_clipboard_items, toggle_clipboard_favorite
)

# 2. To-Do
from wintoolbox.tools.productivity.todo.logic import (
    add_todo, delete_todo, get_todo_categories, get_todo_stats,
    list_todos, toggle_todo_completed, update_todo
)

# 3. Pomodoro
from wintoolbox.tools.productivity.pomodoro.logic import (
    MODE_FOCUS, MODE_LONG_BREAK, MODE_SHORT_BREAK, PomodoroConfig,
    PomodoroManager
)

# 4. Reminders
from wintoolbox.tools.productivity.reminders.logic import (
    add_reminder, check_due_reminders, delete_reminder, list_reminders,
    toggle_reminder_active
)

# 5. Quick Notes
from wintoolbox.tools.productivity.quick_notes.logic import (
    count_words_and_chars, create_note, delete_note, export_note_text,
    get_note_by_id, list_notes, toggle_note_pin, update_note
)

# 6. Time Tracker
from wintoolbox.tools.productivity.time_tracker.logic import (
    add_manual_time_entry, delete_time_entry, export_time_entries_csv,
    format_duration, get_active_time_entry, get_project_time_summary,
    list_time_entries, start_time_entry, stop_time_entry
)


# ==========================================
# TESTES: 1. Clipboard History
# ==========================================
def test_clipboard_history_logic(tmp_path: Path):
    db_file = tmp_path / "clip.db"

    # Adiciona itens
    id1 = add_clipboard_item("Texto 1", db_path=db_file)
    id2 = add_clipboard_item("Texto 2", db_path=db_file)
    assert id1 is not None and id2 is not None

    # Deduplicação consecutiva
    id2_again = add_clipboard_item("Texto 2", db_path=db_file)
    assert id2_again == id2

    # Listagem
    items = list_clipboard_items(db_path=db_file)
    assert len(items) == 2
    assert items[0]["content"] == "Texto 2"

    # Favoritar
    new_fav = toggle_clipboard_favorite(id1, db_path=db_file)
    assert new_fav is True
    fav_items = list_clipboard_items(favorites_only=True, db_path=db_file)
    assert len(fav_items) == 1
    assert fav_items[0]["id"] == id1

    # Limpar preservando favoritos
    cleared = clear_clipboard_history(keep_favorites=True, db_path=db_file)
    assert cleared == 1
    remaining = list_clipboard_items(db_path=db_file)
    assert len(remaining) == 1
    assert remaining[0]["id"] == id1


# ==========================================
# TESTES: 2. To-Do
# ==========================================
def test_todo_logic(tmp_path: Path):
    db_file = tmp_path / "todo.db"

    t1 = add_todo("Comprar café", category="Compras", priority="Alta", db_path=db_file)
    t2 = add_todo("Reunião semanal", category="Trabalho", priority="Média", due_date="25/10/2026", db_path=db_file)
    assert t1 and t2

    # Categorias
    cats = get_todo_categories(db_path=db_file)
    assert "Compras" in cats and "Trabalho" in cats

    # Concluir
    comp = toggle_todo_completed(t1, db_path=db_file)
    assert comp is True

    # Listar pendentes
    pending = list_todos(filter_status="pending", db_path=db_file)
    assert len(pending) == 1
    assert pending[0]["id"] == t2

    # Estatísticas
    stats = get_todo_stats(db_path=db_file)
    assert stats["total"] == 2
    assert stats["completed"] == 1
    assert stats["pending"] == 1

    # Excluir
    del_ok = delete_todo(t2, db_path=db_file)
    assert del_ok is True
    assert len(list_todos(db_path=db_file)) == 1


# ==========================================
# TESTES: 3. Pomodoro
# ==========================================
def test_pomodoro_logic():
    cfg = PomodoroConfig(focus_minutes=25, short_break_minutes=5, long_break_minutes=15, long_break_interval=4)
    pm = PomodoroManager(cfg)

    assert pm.mode == MODE_FOCUS
    assert pm.remaining_seconds == 1500

    # Iniciar e tick
    pm.start()
    assert pm.is_running is True

    finished, _ = pm.tick(step_seconds=10)
    assert finished is False
    assert pm.remaining_seconds == 1490
    assert pm.total_focus_seconds == 10

    # Pula etapa -> vai para pausa curta
    pm.skip_to_next_phase()
    assert pm.mode == MODE_SHORT_BREAK
    assert pm.remaining_seconds == 300

    # Formatação de tempo
    formatted = PomodoroManager.format_time(125)
    assert formatted == "02:05"

    # Percentual
    pm.remaining_seconds = 150
    pct = pm.get_progress_percentage()
    assert 0.49 <= pct <= 0.51


# ==========================================
# TESTES: 4. Reminders
# ==========================================
def test_reminders_logic(tmp_path: Path):
    db_file = tmp_path / "reminders.db"

    # Lembrete no futuro
    future_time = datetime.now() + timedelta(hours=2)
    r1 = add_reminder("Consulta médica", future_time, message="Levar exames", db_path=db_file)
    assert r1

    # Lembrete vencido no passado
    past_time = datetime.now() - timedelta(minutes=5)
    r2 = add_reminder("Beber água", past_time, repeat_mode="daily", db_path=db_file)
    assert r2

    all_rem = list_reminders(db_path=db_file)
    assert len(all_rem) == 2

    # Checar vencidos
    due = check_due_reminders(db_path=db_file)
    assert len(due) == 1
    assert due[0]["title"] == "Beber água"

    # Como r2 era repetição diária, seu target_time deve ter avançado para o futuro
    all_rem_after = list_reminders(db_path=db_file)
    for rem in all_rem_after:
        if rem["id"] == r2:
            new_dt = datetime.fromisoformat(rem["target_time"])
            assert new_dt > datetime.now()

    # Excluir
    assert delete_reminder(r1, db_path=db_file) is True


# ==========================================
# TESTES: 5. Quick Notes
# ==========================================
def test_quick_notes_logic(tmp_path: Path):
    db_file = tmp_path / "notes.db"

    n1 = create_note("Ideias do Projeto", "Primeiro parágrafo de texto.", category="Projetos", db_path=db_file)
    assert n1

    # Contagem de palavras
    w, c = count_words_and_chars("Este é um teste com sete palavras.")
    assert w == 7

    # Atualização
    update_note(n1, "Ideias do Projeto V2", "Texto expandido e revisado.", db_path=db_file)
    note = get_note_by_id(n1, db_path=db_file)
    assert note["title"] == "Ideias do Projeto V2"
    assert note["content"] == "Texto expandido e revisado."

    # Fixar
    pinned = toggle_note_pin(n1, db_path=db_file)
    assert pinned is True

    # Exportar
    md = export_note_text(note, format_type="md")
    assert "# Ideias do Projeto V2" in md

    # Excluir
    assert delete_note(n1, db_path=db_file) is True
    assert len(list_notes(db_path=db_file)) == 0


# ==========================================
# TESTES: 6. Time Tracker
# ==========================================
def test_time_tracker_logic(tmp_path: Path):
    db_file = tmp_path / "tracker.db"

    # Iniciar atividade
    t_id = start_time_entry("Codificando testes", project="WinToolbox", db_path=db_file)
    assert t_id

    active = get_active_time_entry(db_path=db_file)
    assert active is not None
    assert active["activity"] == "Codificando testes"

    # Parar
    stopped = stop_time_entry(t_id, db_path=db_file)
    assert stopped == t_id
    assert get_active_time_entry(db_path=db_file) is None

    # Adicionar manual
    m_id = add_manual_time_entry("Revisão de design", "WinToolbox", duration_minutes=45, db_path=db_file)
    assert m_id

    # Listar e resumo
    entries = list_time_entries(db_path=db_file)
    assert len(entries) >= 2

    summary = get_project_time_summary(db_path=db_file)
    assert "WinToolbox" in summary
    assert summary["WinToolbox"] >= 45 * 60

    # Formatar duração
    dur_str = format_duration(3665)
    assert "01h 01m 05s" in dur_str

    # Exportar CSV
    csv_str = export_time_entries_csv(entries)
    assert "Codificando testes" in csv_str
    assert "Revisão de design" in csv_str

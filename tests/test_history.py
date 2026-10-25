"""
Testes unitários do histórico de tarefas no SQLite.
Isolado em tmp_path para não modificar a base do usuário.
"""
from pathlib import Path
import sqlite3
import pytest

from wintoolbox.core.history import clear_history, get_history_db_path, get_recent_jobs, record_job


@pytest.fixture(autouse=True)
def isolate_history_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Garante que o banco de histórico sqlite seja criado exclusivamente no tmp_path."""
    monkeypatch.setattr("wintoolbox.core.history.get_settings_dir", lambda: tmp_path)
    monkeypatch.setattr("wintoolbox.core.settings.get_settings_dir", lambda: tmp_path)
    return tmp_path


def test_record_and_get_jobs(tmp_path: Path):
    assert len(get_recent_jobs()) == 0

    record_job(
        tool_id="images.convert",
        items_total=5,
        items_success=5,
        items_failed=0,
        duration_sec=1.2,
        status="Sucesso",
        message="5 arquivos convertidos"
    )

    jobs = get_recent_jobs(limit=10)
    assert len(jobs) == 1
    j = jobs[0]
    assert j["tool_id"] == "images.convert"
    assert j["items_total"] == 5
    assert j["items_success"] == 5
    assert j["items_failed"] == 0
    assert j["duration_sec"] == pytest.approx(1.2)
    assert j["status"] == "Sucesso"
    assert j["message"] == "5 arquivos convertidos"

    # Validação do Efeito Real diretamente na tabela do SQLite
    db_file = get_history_db_path()
    assert db_file.is_file()
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tool_id, items_total, status FROM job_history")
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0] == ("images.convert", 5, "Sucesso")

    # Limpeza
    clear_history()
    assert len(get_recent_jobs()) == 0
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM job_history")
        assert cursor.fetchone()[0] == 0


def test_history_limit_and_ordering():
    """Valida respeito estrito ao limite e ordenação do histórico."""
    for i in range(5):
        record_job(
            tool_id=f"tool_{i}",
            items_total=i + 1,
            items_success=i + 1,
            items_failed=0,
            duration_sec=0.1 * (i + 1),
            status="Sucesso",
            message=f"job {i}"
        )

    # Consulta com limite de 2 deve retornar os 2 mais recentes (tool_4 e tool_3)
    recent = get_recent_jobs(limit=2)
    assert len(recent) == 2
    assert recent[0]["tool_id"] == "tool_4"
    assert recent[1]["tool_id"] == "tool_3"

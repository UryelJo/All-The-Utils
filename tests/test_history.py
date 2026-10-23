"""
Testes unitários do histórico de tarefas no SQLite.
"""
from wintoolbox.core.history import clear_history, get_recent_jobs, record_job

def test_record_and_get_jobs():
    clear_history()
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
    assert j["status"] == "Sucesso"

    clear_history()
    assert len(get_recent_jobs()) == 0

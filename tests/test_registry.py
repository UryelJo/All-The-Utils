"""
Testes unitários do registro e catálogo de ferramentas.
"""
from wintoolbox.core.registry import FileTool, Tool, get_all_tools, get_categories, get_tool
from wintoolbox.tools.images.convert.tool import ImageConverterTool
from wintoolbox.tools.system.tools.tool import SystemToolsTool
from wintoolbox.tools.system.monitor.tool import HardwareMonitorTool

def test_tools_registered():
    tools = get_all_tools()
    assert len(tools) >= 3
    tool_ids = [t.id for t in tools]
    assert "images.convert" in tool_ids
    assert "system.tools" in tool_ids
    assert "system.monitor" in tool_ids

def test_image_tool_is_file_tool():
    tool = get_tool("images.convert")
    assert isinstance(tool, FileTool)
    assert ".png" in tool.accepts
    assert ".jpg" in tool.accepts
    assert tool.batch_kind == "per_file"

def test_categories_grouped():
    cats = get_categories()
    assert "Imagens" in cats
    assert "Sistema" in cats
    assert any(t.id == "images.convert" for t in cats["Imagens"])

def test_task_context_helpers():
    from wintoolbox.core.registry import TaskContext

    progress_called = []
    log_called = []

    ctx = TaskContext(
        on_progress=lambda cur, tot, msg: progress_called.append((cur, tot, msg)),
        on_log=lambda lvl, msg: log_called.append((lvl, msg)),
        is_cancelled=lambda: False,
        is_paused=lambda: True,
    )

    ctx.progress(50, 100, "Metade")
    assert progress_called == [(50, 100, "Metade")]

    ctx.log("INFO", "Tudo ok")
    assert log_called == [("INFO", "Tudo ok")]

    assert ctx.cancelled() is False
    assert ctx.paused() is True


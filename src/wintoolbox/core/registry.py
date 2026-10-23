"""
Sistema de Registro e Contrato de Ferramentas do WinToolbox.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
from PySide6.QtWidgets import QWidget

@dataclass
class TaskContext:
    """Contexto passado para a execução de uma tarefa/lote."""
    on_progress: Callable[[int, int, str], None]
    on_log: Callable[[str, str], None]  # (nível, mensagem)
    is_cancelled: Callable[[], bool]
    is_paused: Callable[[], bool] = lambda: False

    def progress(self, current: int, total: int, message: str = "") -> None:
        """Reporta progresso para a UI de forma thread-safe."""
        if callable(self.on_progress):
            self.on_progress(current, total, message)

    def log(self, level: str, message: str) -> None:
        """Envia mensagem de log thread-safe."""
        if callable(self.on_log):
            self.on_log(level, message)

    def cancelled(self) -> bool:
        """Verifica se a tarefa foi cancelada."""
        return self.is_cancelled() if callable(self.is_cancelled) else bool(self.is_cancelled)

    def paused(self) -> bool:
        """Verifica se a tarefa foi pausada."""
        return self.is_paused() if callable(self.is_paused) else bool(self.is_paused)


@dataclass
class ItemResult:
    """Resultado do processamento de um único arquivo/item."""
    success: bool
    source_path: Path
    output_path: Optional[Path] = None
    message: str = ""
    error: Optional[str] = None
    bytes_in: int = 0
    bytes_out: int = 0

@dataclass
class ToolResult:
    """Resultado consolidado da execução de uma ferramenta."""
    success: bool
    message: str = ""
    items_total: int = 0
    items_success: int = 0
    items_failed: int = 0
    items_skipped: int = 0
    details: List[ItemResult] = field(default_factory=list)

class BaseTool:
    """Classe base abstrata para todas as ferramentas."""
    id: str = ""
    name: str = ""
    category: str = "Geral"
    description: str = ""
    keywords: List[str] = []
    requires_admin: bool = False
    optional_deps: List[str] = []

    def is_available(self) -> bool:
        """Verifica se dependências necessárias estão instaladas."""
        return True

class Tool(BaseTool):
    """Ferramenta com interface gráfica e execução genérica."""
    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        raise NotImplementedError

    def run(self, params: Dict[str, Any], ctx: TaskContext) -> ToolResult:
        raise NotImplementedError

class FileTool(BaseTool):
    """
    Ferramenta baseada em arquivos com suporte nativo e automático
    ao motor de processamento em lote (Batch Engine).
    """
    accepts: List[str] = []         # Extensões suportadas, ex: ['.png', '.jpg']
    batch_kind: str = "per_file"    # 'per_file', 'per_folder', 'many_to_one'
    parallel_mode: str = "process"  # 'thread', 'process', 'serial'
    name_vars: List[str] = []       # Variáveis extras disponíveis no template de saída

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        """Constrói o formulário de opções da ferramenta."""
        raise NotImplementedError

    def get_options(self) -> Dict[str, Any]:
        """Lê os parâmetros atuais do formulário de opções."""
        return {}

    def output_ext(self, params: Dict[str, Any]) -> str:
        """Extensão de saída prevista baseada nas opções."""
        return ""

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        """
        Processa um único item. Esta função deve ser pura e independente de UI,
        pois será executada em background/threads/processos.
        """
        raise NotImplementedError


# Registro global de ferramentas
_TOOLS: Dict[str, BaseTool] = {}
_CATEGORIES: Dict[str, List[str]] = {}
_LOADED: bool = False


def _ensure_loaded() -> None:
    """Garante que todos os pacotes de ferramentas foram importados e registrados."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    for pkg in (
        "wintoolbox.tools.images",
        "wintoolbox.tools.system",
        "wintoolbox.tools.network",
        "wintoolbox.tools.text",
        "wintoolbox.tools.encode",
        "wintoolbox.tools.data",
        "wintoolbox.tools.files",
        "wintoolbox.tools.archive",
        "wintoolbox.tools.pdf",
        "wintoolbox.tools.media",
    ):
        try:
            __import__(pkg)
        except Exception:
            pass


def register(tool_cls: Type[BaseTool]):
    """Decorador para registrar uma ferramenta automaticamente."""
    instance = tool_cls()
    if not instance.id:
        raise ValueError(f"Ferramenta {tool_cls.__name__} precisa ter um 'id' único.")
    _TOOLS[instance.id] = instance
    if instance.id not in _CATEGORIES.setdefault(instance.category, []):
        _CATEGORIES[instance.category].append(instance.id)
    return tool_cls


def get_tool(tool_id: str) -> Optional[BaseTool]:
    """Retorna uma ferramenta registrada pelo seu ID."""
    if not _LOADED:
        _ensure_loaded()
    return _TOOLS.get(tool_id)


def get_all_tools() -> List[BaseTool]:
    """Retorna todas as ferramentas registradas."""
    if not _LOADED:
        _ensure_loaded()
    return list(_TOOLS.values())


def get_categories() -> Dict[str, List[BaseTool]]:
    """Retorna as ferramentas agrupadas por categoria."""
    if not _LOADED:
        _ensure_loaded()
    grouped: Dict[str, List[BaseTool]] = {}
    for cat, tool_ids in _CATEGORIES.items():
        grouped[cat] = [_TOOLS[tid] for tid in tool_ids if tid in _TOOLS]
    return grouped

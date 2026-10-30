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

    def send_progress(self, percent: int, message: str = "") -> None:
        """Reporta progresso percentual (0-100); equivale a progress(percent, 100, message)."""
        self.progress(int(percent), 100, message)

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
        if hasattr(self, "build_ui") and callable(getattr(self, "build_ui")):
            return self.build_ui()
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
        if hasattr(self, "build_options_widget"):
            return getattr(self, "build_options_widget")(parent)
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
        "wintoolbox.tools.dev",
        "wintoolbox.tools.productivity",
        "wintoolbox.tools.calc",
        "wintoolbox.tools.automation",
        "wintoolbox.tools.security",
        "wintoolbox.tools.crypto",
        "wintoolbox.tools.web",
        "wintoolbox.tools.forensics",
        "wintoolbox.tools.osint",
        "wintoolbox.tools.rev",
    ):
        try:
            __import__(pkg)
        except Exception:
            # Import tardio: logging_setup depende de settings, que não depende do registro
            from wintoolbox.core.logging_setup import get_logger
            get_logger("registry").exception("Categoria '%s' não carregada (dependência ausente?)", pkg)


CANONICAL_CATEGORIES: Dict[str, str] = {
    # Calculadoras
    "calc": "Calculadoras",
    "calculator": "Calculadoras",
    "calculadoras": "Calculadoras",
    "calculadora": "Calculadoras",

    # Desenvolvimento
    "dev": "Desenvolvimento",
    "desenvolvedores": "Desenvolvimento",
    "desenvolvimento": "Desenvolvimento",
    "developer": "Desenvolvimento",

    # Áudio e Vídeo
    "media": "Áudio e Vídeo",
    "mídia": "Áudio e Vídeo",
    "midia": "Áudio e Vídeo",
    "audio e video": "Áudio e Vídeo",
    "áudio e vídeo": "Áudio e Vídeo",
    "audio": "Áudio e Vídeo",
    "video": "Áudio e Vídeo",

    # Produtividade
    "productivity": "Produtividade",
    "produtividade": "Produtividade",

    # Automação
    "automation": "Automação",
    "automação": "Automação",
    "automacao": "Automação",
    "automações": "Automação",

    # Dados e Estruturas
    "data": "Dados e Estruturas",
    "dados e estruturas": "Dados e Estruturas",
    "dados": "Dados e Estruturas",

    # Arquivos e Pastas
    "files": "Arquivos e Pastas",
    "arquivos e pastas": "Arquivos e Pastas",
    "arquivos": "Arquivos e Pastas",

    # Compactação
    "archive": "Compactação",
    "compactação": "Compactação",
    "compactacao": "Compactação",
    "compressão": "Compactação",

    # PDF
    "pdf": "PDF",
    "pdf e documentos": "PDF",
    "documentos e pdf": "PDF",

    # Imagens
    "imagens": "Imagens",
    "imagens e mídia": "Imagens",
    "imagens e midia": "Imagens",
    "images": "Imagens",

    # Rede e Internet
    "rede": "Rede e Internet",
    "rede e internet": "Rede e Internet",
    "network": "Rede e Internet",

    # Sistema
    "sistema": "Sistema",
    "sistema windows": "Sistema",
    "system": "Sistema",

    # Texto e Redação
    "texto e redação": "Texto e Redação",
    "texto e redacao": "Texto e Redação",
    "texto": "Texto e Redação",
    "text": "Texto e Redação",

    # Codificação e Hash
    "codificação e hash": "Codificação e Hash",
    "codificacao e hash": "Codificação e Hash",
    "encode": "Codificação e Hash",
    "hash": "Codificação e Hash",

    # Segurança
    "segurança": "Segurança",
    "seguranca": "Segurança",
    "segurança e auditoria": "Segurança",
    "security": "Segurança",

    # Criptografia
    "criptografia": "Criptografia",
    "crypto": "Criptografia",
    "criptografia e esteganografia": "Criptografia",

    # Web
    "web": "Web",
    "ofensiva web": "Web",
    "testes web": "Web",

    # Forense
    "forense": "Forense",
    "forensics": "Forense",
    "análise forense": "Forense",
    "analise forense": "Forense",

    # OSINT
    "osint": "OSINT",
    "inteligência de fontes abertas": "OSINT",
    "inteligencia de fontes abertas": "OSINT",

    # Engenharia reversa
    "reverse engineering": "Reverse Engineering",
    "engenharia reversa": "Reverse Engineering",
    "rev": "Reverse Engineering",
    "reversing": "Reverse Engineering",
}


def normalize_category(category_name: str) -> str:
    """Normaliza o nome da categoria para a nomenclatura canônica oficial em Português do Brasil."""
    if not category_name:
        return "Geral"
    cleaned = category_name.strip().lower()
    return CANONICAL_CATEGORIES.get(cleaned, category_name.strip())


def register(tool_cls: Type[BaseTool]):
    """Decorador para registrar uma ferramenta automaticamente."""
    instance = tool_cls()
    if not instance.id:
        raise ValueError(f"Ferramenta {tool_cls.__name__} precisa ter um 'id' único.")

    # Garante coerência entre name e title para exibição na UI
    if not getattr(instance, "name", "").strip():
        if getattr(instance, "title", "").strip():
            instance.name = instance.title.strip()
        elif hasattr(instance, "tool_name") and getattr(instance, "tool_name", "").strip():
            instance.name = getattr(instance, "tool_name").strip()
        else:
            instance.name = instance.id
    if not getattr(instance, "title", "").strip():
        instance.title = instance.name

    instance.category = normalize_category(instance.category)
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

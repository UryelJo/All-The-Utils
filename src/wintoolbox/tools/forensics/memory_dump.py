"""Captura forense de memória de processos do Windows, estritamente somente leitura.

A ferramenta abre o processo alvo com ``PROCESS_VM_READ``, percorre as regiões
comprometidas e legíveis com ``VirtualQueryEx`` e copia os bytes com
``ReadProcessMemory`` em streaming para um arquivo ``.dmp`` bruto. Nenhuma
memória do processo é alterada e nenhum módulo é injetado.

O arquivo gerado é um despejo bruto concatenado das regiões legíveis. O
manifesto JSON ao lado do ``.dmp`` descreve o deslocamento de cada região, o
endereço base, a proteção e o tipo de memória, permitindo a análise posterior
sem inventar estrutura de minidump que o Windows não produziu.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.tools._helpers import (
    confirmar_termo_etico,
    dependencia_disponivel,
    extrair_strings,
    formatar_bytes,
    formatar_numero,
    garantir_admin,
)
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    botao_copiar,
    criar_aviso,
    criar_card,
    criar_saida_texto,
    criar_tabela,
    executar_assincrono,
    mostrar_erro,
    preencher_tabela,
)

_log = get_logger("forensics.memory_dump")

# Constantes da API de memória do Windows.
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010

MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
MEM_MAPPED = 0x40000
MEM_IMAGE = 0x1000000

PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100

_PROTECOES_LEGIVEIS = {
    PAGE_READONLY,
    PAGE_READWRITE,
    PAGE_WRITECOPY,
    PAGE_EXECUTE_READ,
    PAGE_EXECUTE_READWRITE,
    PAGE_EXECUTE_WRITECOPY,
}

_PADROES_CLASSIFICACAO: Dict[str, re.Pattern[str]] = {
    "URL": re.compile(r"https?://[^\s\"'<>]{4,}", re.IGNORECASE),
    "Endereco IP": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "E-mail": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "Chave de registro": re.compile(
        r"\b(?:HKEY_[A-Z_]+|HKLM|HKCU|HKCR|HKU|HKCC)\\[^\s\"'<>]{2,}"
    ),
    "Cabecalho Authorization": re.compile(
        r"(?i)\bAuthorization\s*:\s*(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=\-]{4,}"
    ),
}


class _MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    """Estrutura MEMORY_BASIC_INFORMATION para processos de 64 bits."""

    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", wintypes.DWORD),
        ("__alignment1", wintypes.DWORD),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("__alignment2", wintypes.DWORD),
    ]


class _MEMORY_BASIC_INFORMATION32(ctypes.Structure):
    """Estrutura MEMORY_BASIC_INFORMATION para processos de 32 bits."""

    _fields_ = [
        ("BaseAddress", wintypes.DWORD),
        ("AllocationBase", wintypes.DWORD),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", wintypes.DWORD),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def _carregar_kernel32() -> Optional[ctypes.WinDLL]:
    """Carrega a kernel32 e declara as assinaturas usadas na captura."""
    if os.name != "nt":
        return None
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    except OSError:
        return None

    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.VirtualQueryEx.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        ctypes.c_void_p,
        ctypes.c_size_t,
    ]
    kernel.VirtualQueryEx.restype = ctypes.c_size_t
    kernel.ReadProcessMemory.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel.ReadProcessMemory.restype = wintypes.BOOL

    # EnumProcesses vive na psapi em versões antigas e como K32EnumProcesses
    # na kernel32 em versões recentes. O fallback só é usado sem psutil.
    enum_processes = getattr(kernel, "K32EnumProcesses", None)
    if enum_processes is None:
        try:
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            enum_processes = psapi.EnumProcesses
        except OSError:
            enum_processes = None
    if enum_processes is not None:
        enum_processes.argtypes = [
            ctypes.POINTER(wintypes.DWORD),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        enum_processes.restype = wintypes.BOOL
        kernel.EnumProcesses = enum_processes
    return kernel


_KERNEL32 = _carregar_kernel32()


@dataclass
class ProcessoInfo:
    """Processo visível para seleção na interface."""

    pid: int
    nome: str
    caminho: str = ""
    memoria_residente: int = 0
    usuario: str = ""


@dataclass
class ResultadoDump:
    """Resultado de uma captura de memória."""

    pid: int
    nome: str
    caminho: str
    manifesto: str
    bytes_lidos: int
    regioes: int
    strings: Dict[str, List[str]] = field(default_factory=dict)
    cancelado: bool = False


class ClassificadorStrings:
    """Classifica strings sensíveis encontradas durante a leitura da memória.

    O alimentador recebe blocos de bytes e mantém um conjunto de valores únicos
    por categoria, com limite configurável para não consumir memória sem
    controle durante despejos de vários gigabytes.
    """

    def __init__(self, limite_por_tipo: int = 300) -> None:
        self.limite_por_tipo = max(1, int(limite_por_tipo))
        self.categorias: Dict[str, List[str]] = {
            chave: [] for chave in _PADROES_CLASSIFICACAO
        }
        self._vistos: Dict[str, set[str]] = {
            chave: set() for chave in _PADROES_CLASSIFICACAO
        }
        self.total_strings = 0

    def alimentar(self, dados: bytes) -> None:
        """Extrai strings ASCII/UTF-16LE do bloco e classifica os padrões."""
        if not dados:
            return
        for _offset, _codificacao, texto in extrair_strings(dados, minimo=6, utf16=True):
            self.total_strings += 1
            self._classificar(texto)

    def _classificar(self, texto: str) -> None:
        for categoria, padrao in _PADROES_CLASSIFICACAO.items():
            for achado in padrao.findall(texto):
                valor = str(achado).strip()
                if not valor or valor in self._vistos[categoria]:
                    continue
                if categoria == "Endereco IP" and not _ip_valido(valor):
                    continue
                if len(self.categorias[categoria]) >= self.limite_por_tipo:
                    continue
                self._vistos[categoria].add(valor)
                self.categorias[categoria].append(valor)

    def resumo(self) -> Dict[str, List[str]]:
        """Devolve cópia das listas classificadas."""
        return {chave: list(valores) for chave, valores in self.categorias.items()}


def _ip_valido(texto: str) -> bool:
    """Valida um endereço IPv4 para evitar falsos positivos de versões."""
    partes = texto.split(".")
    if len(partes) != 4:
        return False
    try:
        return all(0 <= int(parte) <= 255 for parte in partes)
    except ValueError:
        return False


def _protecao_legivel(protecao: int) -> bool:
    """Indica se a proteção permite leitura sem disparar PAGE_GUARD."""
    if protecao & PAGE_GUARD or protecao & PAGE_NOACCESS:
        return False
    return (protecao & 0xFF) in _PROTECOES_LEGIVEIS


def _nome_tipo_memoria(tipo: int) -> str:
    """Traduz o campo Type de MEMORY_BASIC_INFORMATION."""
    return {
        MEM_PRIVATE: "Privada",
        MEM_MAPPED: "Mapeada",
        MEM_IMAGE: "Imagem",
    }.get(tipo, "Desconhecida")


def listar_processos(incluir_kernel: bool = False) -> List[ProcessoInfo]:
    """Lista processos em execução, do maior consumo de memória para o menor.

    Usa ``psutil`` quando disponível e cai para ``EnumProcesses`` quando a
    dependência opcional não estiver instalada. Processos do kernel (PID 0 e 4)
    são omitidos por padrão.
    """
    processos: List[ProcessoInfo] = []
    if dependencia_disponivel("psutil"):
        import psutil  # importação tardia

        for proc in psutil.process_iter(
            ["pid", "name", "exe", "memory_info", "username"]
        ):
            try:
                info = proc.info
                pid = int(info.get("pid") or 0)
                if not incluir_kernel and pid in (0, 4):
                    continue
                memoria = 0
                mem_info = info.get("memory_info")
                if mem_info is not None:
                    memoria = int(getattr(mem_info, "rss", 0) or 0)
                processos.append(
                    ProcessoInfo(
                        pid=pid,
                        nome=str(info.get("name") or f"PID {pid}"),
                        caminho=str(info.get("exe") or ""),
                        memoria_residente=memoria,
                        usuario=str(info.get("username") or ""),
                    )
                )
            except Exception:
                continue
        processos.sort(key=lambda item: item.memoria_residente, reverse=True)
        return processos

    if _KERNEL32 is None:
        return processos
    if not hasattr(_KERNEL32, "EnumProcesses"):
        return processos

    # Alternativa nativa mínima quando psutil não está instalado.
    arr = (wintypes.DWORD * 4096)()
    usados = wintypes.DWORD()
    if not _KERNEL32.EnumProcesses(
        ctypes.byref(arr), ctypes.sizeof(arr), ctypes.byref(usados)
    ):
        return processos
    quantidade = usados.value // ctypes.sizeof(wintypes.DWORD)
    for indice in range(quantidade):
        pid = int(arr[indice])
        if not incluir_kernel and pid in (0, 4):
            continue
        processos.append(ProcessoInfo(pid=pid, nome=f"PID {pid}"))
    return processos


def _nome_processo(pid: int) -> str:
    """Obtém o nome do processo sem depender de privilégios elevados."""
    if dependencia_disponivel("psutil"):
        try:
            import psutil

            return psutil.Process(pid).name()
        except Exception:
            pass
    return f"PID {pid}"


def _abrir_processo(pid: int) -> int:
    """Abre o processo para leitura, tentando as combinações de acesso usuais."""
    if _KERNEL32 is None:
        raise OSError("A captura de memória está disponível apenas no Windows.")
    if pid <= 0:
        raise ValueError("Informe um PID válido maior que zero.")

    tentativas = [
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ,
    ]
    ultimo_erro = 0
    for acesso in tentativas:
        handle = _KERNEL32.OpenProcess(acesso, False, pid)
        if handle:
            return int(handle)
        ultimo_erro = ctypes.get_last_error()
    raise OSError(
        ultimo_erro,
        "Não foi possível abrir o processo para leitura. "
        "Execute como Administrador e verifique se o processo ainda existe. "
        "Processos protegidos do sistema podem negar acesso mesmo com elevação.",
    )


def _regioes_legiveis(handle: int) -> List[Dict[str, int]]:
    """Percorre o espaço de endereçamento e devolve as regiões legíveis."""
    if _KERNEL32 is None:
        return []

    usar_64 = ctypes.sizeof(ctypes.c_void_p) == 8
    estrutura = (
        _MEMORY_BASIC_INFORMATION64() if usar_64 else _MEMORY_BASIC_INFORMATION32()
    )
    endereco = 0
    limite = 0x7FFFFFFFFFFF if usar_64 else 0x7FFFFFFF
    regioes: List[Dict[str, int]] = []

    while endereco < limite:
        retorno = _KERNEL32.VirtualQueryEx(
            handle,
            ctypes.c_void_p(endereco),
            ctypes.byref(estrutura),
            ctypes.sizeof(estrutura),
        )
        if not retorno:
            break
        base = int(estrutura.BaseAddress)
        tamanho = int(estrutura.RegionSize)
        if tamanho <= 0:
            endereco += 0x1000
            continue
        if estrutura.State == MEM_COMMIT and _protecao_legivel(estrutura.Protect):
            regioes.append(
                {
                    "base": base,
                    "tamanho": tamanho,
                    "protecao": int(estrutura.Protect),
                    "tipo": int(estrutura.Type),
                }
            )
        proximo = base + tamanho
        if proximo <= endereco:
            endereco += 0x1000
        else:
            endereco = proximo
    return regioes


def _ler_memoria(handle: int, endereco: int, tamanho: int) -> Optional[bytes]:
    """Lê um bloco de memória; devolve None quando a página não é acessível."""
    if _KERNEL32 is None or tamanho <= 0:
        return None
    buffer = ctypes.create_string_buffer(tamanho)
    lidos = ctypes.c_size_t(0)
    sucesso = _KERNEL32.ReadProcessMemory(
        handle,
        ctypes.c_void_p(endereco),
        buffer,
        tamanho,
        ctypes.byref(lidos),
    )
    if not sucesso:
        return None
    return buffer.raw[: lidos.value]


def classificar_strings(dados: bytes, limite_por_tipo: int = 300) -> Dict[str, List[str]]:
    """Classifica strings de um bloco de bytes em URLs, IPs, e-mails e segredos.

    API pública usada pela interface e por testes. Não grava nada em disco.
    """
    classificador = ClassificadorStrings(limite_por_tipo=limite_por_tipo)
    classificador.alimentar(dados)
    return classificador.resumo()


def dump_processo(
    pid: int,
    destino: Path | str,
    ctx: Optional[TaskContext] = None,
    tamanho_maximo: int = 0,
    limite_strings: int = 300,
) -> ResultadoDump:
    """Captura as regiões legíveis de um processo para um arquivo ``.dmp``.

    Parâmetros:
        pid: identificador do processo alvo.
        destino: caminho do arquivo ``.dmp`` a criar.
        ctx: contexto opcional para progresso, log e cancelamento.
        tamanho_maximo: limite em bytes (0 significa sem limite explícito).
        limite_strings: máximo de valores únicos por categoria classificada.

    O processo é aberto apenas com permissão de leitura. O arquivo de destino
    nunca é aberto antes de o processo ser validado, e um manifesto JSON é
    gravado ao lado do despejo.
    """
    if _KERNEL32 is None:
        raise OSError("A captura de memória está disponível apenas no Windows.")

    caminho = Path(destino).expanduser().resolve()
    if caminho.exists() and caminho.stat().st_size > 0:
        raise FileExistsError(
            f"O arquivo de destino já existe: {caminho}. Escolha outro nome para não sobrescrever evidências."
        )
    caminho.parent.mkdir(parents=True, exist_ok=True)

    nome = _nome_processo(pid)
    handle = _abrir_processo(pid)
    regioes = _regioes_legiveis(handle)
    if not regioes:
        _KERNEL32.CloseHandle(handle)
        raise RuntimeError(
            "Nenhuma região de memória legível foi encontrada. "
            "O processo pode ter encerrado ou estar protegido pelo sistema."
        )

    classificador = ClassificadorStrings(limite_por_tipo=limite_strings)
    manifesto: Dict[str, Any] = {
        "ferramenta": "forensics.memory_dump",
        "formato": "despejo bruto de regiões legíveis concatenadas",
        "pid": pid,
        "processo": nome,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "arquivo_dmp": caminho.name,
        "bytes_lidos": 0,
        "regioes": [],
        "strings": {},
    }
    total_regioes = len(regioes)
    bytes_lidos = 0
    regioes_capturadas = 0
    cancelado = False

    if ctx is not None:
        ctx.log("INFO", f"Iniciando captura do processo {nome} (PID {pid}).")
        ctx.progress(0, total_regioes, "Abrindo regiões de memória...")

    try:
        with open(caminho, "wb") as arquivo:
            for indice, regiao in enumerate(regioes):
                if ctx is not None and ctx.cancelled():
                    cancelado = True
                    if ctx is not None:
                        ctx.log("WARN", "Captura cancelada pelo usuário.")
                    break

                base = regiao["base"]
                tamanho = regiao["tamanho"]
                deslocamento_inicio = arquivo.tell()
                offset = 0
                while offset < tamanho:
                    if ctx is not None and ctx.cancelled():
                        cancelado = True
                        break
                    bloco = min(1024 * 1024, tamanho - offset)
                    pedaco = _ler_memoria(handle, base + offset, bloco)
                    if not pedaco:
                        # Página pode ter sido descomprometida entre a consulta e a leitura.
                        offset += max(0x1000, bloco)
                        continue
                    arquivo.write(pedaco)
                    bytes_lidos += len(pedaco)
                    classificador.alimentar(pedaco)
                    offset += len(pedaco)
                    if tamanho_maximo and bytes_lidos >= tamanho_maximo:
                        if ctx is not None:
                            ctx.log(
                                "INFO",
                                f"Limite configurado de {formatar_bytes(tamanho_maximo)} atingido.",
                            )
                        break

                escritos = arquivo.tell() - deslocamento_inicio
                if escritos > 0:
                    regioes_capturadas += 1
                    manifesto["regioes"].append(
                        {
                            "indice": regioes_capturadas,
                            "endereco_base": f"0x{base:016X}",
                            "tamanho_regiao": tamanho,
                            "deslocamento_dmp": deslocamento_inicio,
                            "bytes_escritos": escritos,
                            "protecao": f"0x{regiao['protecao']:08X}",
                            "tipo": _nome_tipo_memoria(regiao["tipo"]),
                        }
                    )

                if ctx is not None:
                    ctx.progress(
                        indice + 1,
                        total_regioes,
                        f"Região {indice + 1}/{total_regioes} - {formatar_bytes(bytes_lidos)}",
                    )
                if tamanho_maximo and bytes_lidos >= tamanho_maximo:
                    break
                if cancelado:
                    break
    finally:
        _KERNEL32.CloseHandle(handle)

    if bytes_lidos <= 0:
        try:
            caminho.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(
            "Nenhum byte pôde ser lido. Execute como Administrador e tente novamente."
        )

    manifesto["bytes_lidos"] = bytes_lidos
    manifesto["regioes_capturadas"] = regioes_capturadas
    manifesto["strings"] = classificador.resumo()
    manifesto["cancelado"] = cancelado

    caminho_manifesto = caminho.with_name(caminho.name + ".json")
    caminho_manifesto.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if ctx is not None:
        ctx.log(
            "INFO",
            f"Despejo concluído: {formatar_bytes(bytes_lidos)} em {regioes_capturadas} região(ões).",
        )

    return ResultadoDump(
        pid=pid,
        nome=nome,
        caminho=str(caminho),
        manifesto=str(caminho_manifesto),
        bytes_lidos=bytes_lidos,
        regioes=regioes_capturadas,
        strings=classificador.resumo(),
        cancelado=cancelado,
    )


def formatar_resultado_dump(resultado: ResultadoDump) -> str:
    """Monta o resumo textual exibido na interface."""
    linhas = [
        "Captura de memória concluída.",
        "",
        f"Processo: {resultado.nome} (PID {resultado.pid})",
        f"Arquivo de despejo: {resultado.caminho}",
        f"Manifesto: {resultado.manifesto}",
        f"Bytes lidos: {formatar_bytes(resultado.bytes_lidos)}",
        f"Regiões capturadas: {formatar_numero(resultado.regioes)}",
        f"Cancelado: {'sim' if resultado.cancelado else 'não'}",
        "",
        "Classificação de strings:",
    ]
    for categoria, valores in resultado.strings.items():
        linhas.append(f"- {categoria}: {formatar_numero(len(valores))}")
        for valor in valores[:10]:
            linhas.append(f"    {valor}")
        if len(valores) > 10:
            linhas.append(f"    ... e mais {len(valores) - 10} valor(es).")
    if not any(resultado.strings.values()):
        linhas.append("- Nenhuma string classificada foi encontrada.")
    return "\n".join(linhas)


@register
class MemoryDumpTool(Tool):
    """Ferramenta de captura de memória de processo."""

    id = "forensics.memory_dump"
    name = "Captura de Memória de Processo"
    category = "Forense"
    description = (
        "Captura somente leitura das regiões legíveis da memória de um processo "
        "para análise forense, classificando URLs, IPs, e-mails, chaves de registro "
        "e cabeçalhos Authorization"
    )
    keywords = [
        "memória",
        "memoria",
        "dump",
        "forense",
        "processo",
        "captura",
        "strings",
        "credenciais",
        "incidente",
    ]
    requires_admin = True

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return MemoryDumpView(self, parent)


class MemoryDumpView(PainelFerramenta):
    """Interface de seleção de processo, destino e exibição da captura."""

    def __init__(self, tool: MemoryDumpTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._processos: List[ProcessoInfo] = []
        self._montar()

    def _montar(self) -> None:
        self.adicionar_aviso(
            "Uso forense e autorizado: a captura lê a memória de um processo sem "
            "alterá-la. Execute apenas em sistemas próprios ou com autorização "
            "expressa. O acesso a processos protegidos exige Administrador.",
            destaque=True,
        )

        cartao, layout = self.adicionar_card("Processo alvo")
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Filtrar:"))
        self.txt_filtro = QLineEdit()
        self.txt_filtro.setPlaceholderText("Nome, PID ou caminho do processo...")
        self.txt_filtro.textChanged.connect(self._aplicar_filtro)
        linha.addWidget(self.txt_filtro, stretch=1)
        self.btn_atualizar = QPushButton("Atualizar Lista")
        self.btn_atualizar.clicked.connect(self._carregar_processos)
        linha.addWidget(self.btn_atualizar)
        layout.addLayout(linha)

        self.tabela = criar_tabela(
            ["PID", "Processo", "Memória residente", "Caminho", "Usuário"], self
        )
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabela.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.tabela.setMinimumHeight(190)
        layout.addWidget(self.tabela)

        cartao_destino, layout_destino = self.adicionar_card("Arquivo de destino")
        linha_destino = QHBoxLayout()
        self.txt_destino = QLineEdit()
        self.txt_destino.setPlaceholderText("Escolha onde gravar o arquivo .dmp")
        linha_destino.addWidget(self.txt_destino, stretch=1)
        self.btn_destino = QPushButton("Escolher...")
        self.btn_destino.clicked.connect(self._escolher_destino)
        linha_destino.addWidget(self.btn_destino)
        layout_destino.addLayout(linha_destino)

        linha_limite = QHBoxLayout()
        linha_limite.addWidget(QLabel("Limite opcional de captura (MB):"))
        self.spin_limite = QSpinBox()
        self.spin_limite.setRange(0, 8192)
        self.spin_limite.setValue(0)
        self.spin_limite.setSpecialValueText("Sem limite")
        linha_limite.addWidget(self.spin_limite)
        linha_limite.addStretch()
        self.btn_capturar = QPushButton("Iniciar Captura")
        self.btn_capturar.clicked.connect(self._capturar)
        linha_limite.addWidget(self.btn_capturar)
        layout_destino.addLayout(linha_limite)

        self.lbl_status = QLabel(
            "Selecione um processo na tabela e clique em 'Iniciar Captura'."
        )
        self.lbl_status.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        layout_destino.addWidget(self.lbl_status)

        cartao_saida, layout_saida = self.adicionar_card("Resultado da captura")
        self.txt_saida = criar_saida_texto(230, self)
        layout_saida.addWidget(self.txt_saida)
        linha_botoes = QHBoxLayout()
        linha_botoes.addWidget(
            botao_copiar(lambda: self.txt_saida.toPlainText(), self, "Copiar Resultado")
        )
        linha_botoes.addStretch()
        layout_saida.addLayout(linha_botoes)

        self.log = adicionar_log_painel(self, "Log da Captura de Memória")
        self.adicionar_espaco()
        self._carregar_processos()

    def _carregar_processos(self) -> None:
        """Carrega a lista de processos em segundo plano."""
        self.btn_atualizar.setEnabled(False)
        self.lbl_status.setText("Carregando processos...")

        def tarefa(ctx: TaskContext) -> List[ProcessoInfo]:
            ctx.log("INFO", "Consultando processos em execução.")
            return listar_processos()

        def concluiu(processos: Any) -> None:
            self.btn_atualizar.setEnabled(True)
            self._processos = list(processos or [])
            self._aplicar_filtro()
            self.lbl_status.setText(
                f"{formatar_numero(len(self._processos))} processo(s) encontrado(s)."
            )

        def falhou(erro: Exception) -> None:
            self.btn_atualizar.setEnabled(True)
            self.lbl_status.setText("Falha ao listar processos.")
            mostrar_erro(self, "Não foi possível listar processos", erro)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_logar=lambda nivel, msg: self.log.append_log(nivel, msg),
        )

    def _aplicar_filtro(self) -> None:
        """Filtra a tabela pelo texto digitado."""
        termo = self.txt_filtro.text().strip().lower()
        linhas: List[List[Any]] = []
        for processo in self._processos:
            texto = f"{processo.pid} {processo.nome} {processo.caminho} {processo.usuario}"
            if termo and termo not in texto.lower():
                continue
            linhas.append(
                [
                    processo.pid,
                    processo.nome,
                    formatar_bytes(processo.memoria_residente),
                    processo.caminho,
                    processo.usuario,
                ]
            )
        preencher_tabela(self.tabela, linhas)

    def _escolher_destino(self) -> None:
        """Solicita o arquivo de destino do despejo."""
        sugerido = str(Path.home() / "Documents" / "captura_memoria.dmp")
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar despejo de memória",
            sugerido,
            "Despejo de memória (*.dmp);;Todos os arquivos (*.*)",
        )
        if destino:
            if not destino.lower().endswith(".dmp"):
                destino += ".dmp"
            self.txt_destino.setText(destino)

    def _pid_selecionado(self) -> Optional[int]:
        """Obtém o PID da linha selecionada."""
        linha = self.tabela.currentRow()
        if linha < 0:
            return None
        item = self.tabela.item(linha, 0)
        if item is None:
            return None
        try:
            return int(item.text())
        except ValueError:
            return None

    def _capturar(self) -> None:
        """Valida consentimento e privilégios e dispara a captura."""
        pid = self._pid_selecionado()
        if pid is None:
            QMessageBox.information(
                self,
                "Selecione um processo",
                "Escolha uma linha da tabela antes de iniciar a captura.",
            )
            return

        destino = self.txt_destino.text().strip()
        if not destino:
            self._escolher_destino()
            destino = self.txt_destino.text().strip()
        if not destino:
            return

        if not confirmar_termo_etico(self, "forensics.memory_dump"):
            return
        if not garantir_admin(self, self.tool.name, permitir_continuar=True):
            return

        limite_mb = int(self.spin_limite.value())
        limite_bytes = limite_mb * 1024 * 1024 if limite_mb > 0 else 0
        self.btn_capturar.setEnabled(False)
        self.btn_atualizar.setEnabled(False)
        self.lbl_status.setText(f"Capturando memória do PID {pid}...")

        def tarefa(ctx: TaskContext) -> ResultadoDump:
            return dump_processo(
                pid,
                destino,
                ctx=ctx,
                tamanho_maximo=limite_bytes,
                limite_strings=300,
            )

        def concluiu(resultado: ResultadoDump) -> None:
            self.btn_capturar.setEnabled(True)
            self.btn_atualizar.setEnabled(True)
            self.lbl_status.setText("Captura concluída.")
            self.txt_saida.setPlainText(formatar_resultado_dump(resultado))

        def falhou(erro: Exception) -> None:
            self.btn_capturar.setEnabled(True)
            self.btn_atualizar.setEnabled(True)
            self.lbl_status.setText("Falha na captura.")
            self.txt_saida.setPlainText(
                "A captura não foi concluída.\n\n"
                f"{erro}\n\n"
                "Verifique se o aplicativo está elevado, se o processo continua em "
                "execução e se o destino é gravável."
            )
            mostrar_erro(self, "Falha na captura de memória", erro)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_progredir=lambda atual, total, msg: self.lbl_status.setText(msg),
            ao_logar=lambda nivel, msg: self.log.append_log(nivel, msg),
        )

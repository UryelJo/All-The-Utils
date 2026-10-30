"""Descompilação e desmontagem de arquivos .pyc.

O cabeçalho é interpretado manualmente (magic number, flags, data de compilação e
tamanho). Quando a versão do bytecode coincide com a do interpretador atual, o
objeto de código é lido com `marshal` e desmontado com `dis`. Descompiladores
opcionais (decompyle3, uncompyle6 e pycdc) são tentados na ordem escolhida; sem
eles, a ferramenta ainda entrega a desmontagem completa, sem falhar.
"""
from __future__ import annotations

import dis
import importlib.util
import io
import marshal
import shutil
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools._helpers import dependencia_disponivel
from wintoolbox.tools._widgets import criar_aviso

_log = get_logger("rev.pyc_decompiler")

LIMITE_BYTES = 32 * 1024 * 1024

# magic number (2 bytes, little endian) -> versão do CPython
MAGIC_NUMBERS: Dict[int, str] = {
    62211: "2.7",
    3350: "3.5",
    3361: "3.6",
    3379: "3.6",
    3394: "3.7",
    3413: "3.8",
    3425: "3.9",
    3439: "3.10",
    3495: "3.11",
    3531: "3.12",
    3550: "3.13",
    3571: "3.13",
    3600: "3.14",
}

_TAMANHO_CABECALHO = {
    "2.7": 8,
    "3.5": 12,
    "3.6": 12,
    "3.7": 16,
    "3.8": 16,
    "3.9": 16,
    "3.10": 16,
    "3.11": 16,
    "3.12": 16,
    "3.13": 16,
    "3.14": 16,
}

OPCOES_MODO: Tuple[Tuple[str, str], ...] = (
    ("Automático (tenta todos)", "auto"),
    ("decompyle3 (se instalado)", "decompyle3"),
    ("uncompyle6 (se instalado)", "uncompyle6"),
    ("pycdc (se instalado)", "pycdc"),
    ("Somente desmontagem (dis)", "dis"),
)


def magic_atual() -> int:
    """Magic number do interpretador em execução."""
    return int.from_bytes(importlib.util.MAGIC_NUMBER[:2], "little")


def versao_atual() -> str:
    """Versão do interpretador em execução, em formato curto."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def identificar_magic(dados: bytes) -> Dict[str, Any]:
    """Interpreta o cabeçalho do .pyc e identifica a versão do CPython."""
    if len(dados) < 4:
        raise ValueError("Arquivo .pyc muito curto para conter um magic number.")
    numero = int.from_bytes(dados[:2], "little")
    bruto = dados[:4]
    atual = magic_atual()
    versao = MAGIC_NUMBERS.get(numero)
    suportado = numero == atual
    cabecalho = _TAMANHO_CABECALHO.get(versao or "", 16)

    info: Dict[str, Any] = {
        "magic_numero": numero,
        "magic_hex": bruto.hex(" "),
        "versao": versao or "desconhecida",
        "versao_atual": versao_atual(),
        "compilado_com_atual": suportado,
        "tamanho_cabecalho": cabecalho,
        "flags": None,
        "compilado_em": "",
        "tamanho_origem": None,
    }
    if len(dados) >= 8 and versao and versao != "2.7":
        info["flags"] = struct.unpack("<I", dados[4:8])[0]
    if len(dados) >= 12 and versao and versao != "2.7":
        carimbo = struct.unpack("<I", dados[8:12])[0]
        if carimbo:
            try:
                info["compilado_em"] = datetime.fromtimestamp(
                    carimbo, tz=timezone.utc
                ).isoformat(timespec="seconds")
            except (OverflowError, OSError, ValueError):
                info["compilado_em"] = f"timestamp inválido ({carimbo})"
    if len(dados) >= 16 and versao and versao != "2.7":
        info["tamanho_origem"] = struct.unpack("<I", dados[12:16])[0]
    return info


def _cabecalho_texto(caminho: Path, info: Dict[str, Any]) -> str:
    linhas = [
        f"Arquivo: {caminho.name}",
        f"Magic number: {info['magic_numero']} ({info['magic_hex']})",
        f"Versão detectada: Python {info['versao']}",
        f"Interpretador atual: Python {info['versao_atual']}",
        f"Compatível com o interpretador atual: {'sim' if info['compilado_com_atual'] else 'não'}",
    ]
    if info.get("flags") is not None:
        linhas.append(f"Flags do cabeçalho: 0x{int(info['flags']):08X}")
    if info.get("compilado_em"):
        linhas.append(f"Compilado em: {info['compilado_em']}")
    if info.get("tamanho_origem") is not None:
        linhas.append(f"Tamanho do .py de origem: {info['tamanho_origem']} byte(s)")
    return "\n".join(linhas)


def _extrair_codigo(dados: bytes, info: Dict[str, Any]):
    """Lê o objeto de código com marshal, exigindo compatibilidade de versão."""
    if not info.get("compilado_com_atual"):
        raise RuntimeError(
            "O bytecode foi gerado por outra versão do Python "
            f"({info.get('versao')}); use um descompilador da mesma versão."
        )
    inicio = int(info.get("tamanho_cabecalho") or 16)
    return marshal.loads(dados[inicio:])


def desmontar_pyc(dados: bytes, info: Dict[str, Any]) -> str:
    """Produz a desmontagem completa com o módulo `dis`."""
    codigo = _extrair_codigo(dados, info)
    buffer = io.StringIO()
    buffer.write(_cabecalho_texto(Path("<memoria>"), info))
    buffer.write("\n\n")
    metadados = [
        f"co_filename: {getattr(codigo, 'co_filename', '')}",
        f"co_name: {getattr(codigo, 'co_name', '')}",
        f"co_argcount: {getattr(codigo, 'co_argcount', 0)}",
        f"co_nlocals: {getattr(codigo, 'co_nlocals', 0)}",
        f"co_stacksize: {getattr(codigo, 'co_stacksize', 0)}",
        f"co_code: {len(getattr(codigo, 'co_code', b''))} byte(s)",
    ]
    buffer.write("Metadados do objeto de código:\n")
    for linha in metadados:
        buffer.write(f"  {linha}\n")
    buffer.write("\n")
    nomes = list(getattr(codigo, "co_names", ()) or ())
    if nomes:
        buffer.write(f"Nomes globais referenciados ({len(nomes)}):\n")
        buffer.write("  " + ", ".join(str(nome) for nome in nomes[:200]) + "\n\n")
    buffer.write("Desmontagem:\n")
    dis.dis(codigo, file=buffer, depth=None)
    return buffer.getvalue()


def _tentar_decompilador_import(pacote: str, caminho: Path) -> Tuple[str, str]:
    """Tenta decompyle3/uncompyle6 pela API Python e devolve (texto, motor)."""
    if not dependencia_disponivel(pacote):
        return "", ""
    try:
        if pacote == "decompyle3":
            from decompyle3.main import decompile_file
        else:
            from uncompyle6.main import decompile_file

        buffer = io.StringIO()
        decompile_file(str(caminho), buffer)
        texto = buffer.getvalue()
        if texto.strip():
            return texto, pacote
    except Exception as exc:  # noqa: BLE001
        _log.info("%s não conseguiu descompilar %s: %s", pacote, caminho, exc)
    return "", ""


def _tentar_pycdc(caminho: Path, timeout: int = 60) -> Tuple[str, str]:
    """Executa o descompilador externo pycdc quando disponível no PATH."""
    executavel = shutil.which("pycdc") or shutil.which("pycdc.exe")
    if not executavel:
        return "", ""
    try:
        processo = subprocess.run(
            [executavel, str(caminho)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if processo.returncode == 0 and processo.stdout.strip():
            return processo.stdout, "pycdc"
    except (OSError, subprocess.SubprocessError) as exc:
        _log.info("pycdc indisponível na prática: %s", exc)
    return "", ""


def decompilar_pyc(
    caminho: Path,
    dados: bytes,
    modo: str = "auto",
    ao_log: Optional[Any] = None,
) -> Dict[str, Any]:
    """Tenta descompilar; sempre devolve um texto de desmontagem como reserva."""
    caminho = Path(caminho)
    info = identificar_magic(dados)
    resultado: Dict[str, Any] = {
        "info": info,
        "motor": "",
        "codigo": "",
        "desmontagem": "",
        "avisos": [],
    }

    if modo != "dis":
        ordem = ["decompyle3", "uncompyle6", "pycdc"] if modo == "auto" else [modo]
        for pacote in ordem:
            if pacote == "pycdc":
                texto, motor = _tentar_pycdc(caminho)
            else:
                texto, motor = _tentar_decompilador_import(pacote, caminho)
            if texto:
                resultado["codigo"] = texto
                resultado["motor"] = motor
                if ao_log is not None:
                    ao_log("INFO", f"{caminho.name}: descompilado com {motor}.")
                break
        if not resultado["codigo"]:
            resultado["avisos"].append(
                "Nenhum descompilador disponível ou compatível; gerando desmontagem com dis."
            )

    if not resultado["codigo"]:
        try:
            resultado["desmontagem"] = desmontar_pyc(dados, info)
            resultado["motor"] = resultado["motor"] or "dis"
        except RuntimeError as exc:
            resultado["avisos"].append(str(exc))
            resultado["desmontagem"] = (
                _cabecalho_texto(caminho, info)
                + "\n\nNão foi possível desmontar: o bytecode pertence a outra versão do Python.\n"
                "Alternativas:\n"
                "  - executar este WinToolbox com a mesma versão usada para compilar o .pyc;\n"
                "  - instalar um descompilador compatível (decompyle3, uncompyle6 ou pycdc);\n"
                "  - converter o .pyc com a ferramenta oficial daquela versão.\n"
            )
        except (EOFError, ValueError, TypeError) as exc:
            resultado["avisos"].append(f"Falha ao ler o objeto de código: {exc}")
            resultado["desmontagem"] = _cabecalho_texto(caminho, info) + f"\n\nFalha: {exc}\n"
    return resultado


def montar_conteudo(resultado: Dict[str, Any], formato_py: bool, incluir_cabecalho: bool) -> str:
    """Monta o conteúdo final no formato escolhido."""
    info = resultado.get("info", {})
    cabecalho = [
        f"# Gerado pelo WinToolbox em {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Versão detectada: Python {info.get('versao')}",
        f"# Magic number: {info.get('magic_numero')} ({info.get('magic_hex')})",
        f"# Motor: {resultado.get('motor') or 'desconhecido'}",
        "#",
    ]
    if formato_py and resultado.get("codigo"):
        corpo = resultado["codigo"]
        if not incluir_cabecalho:
            return corpo
        return "\n".join(cabecalho) + "\n" + corpo

    texto = resultado.get("desmontagem") or ""
    avisos = resultado.get("avisos") or []
    if formato_py:
        linhas = cabecalho + ["# Desmontagem (o código-fonte não pôde ser recuperado):", "#"]
        for aviso in avisos:
            linhas.append(f"# Aviso: {aviso}")
        linhas.append("#")
        for linha in texto.splitlines():
            linhas.append(f"# {linha}")
        return "\n".join(linhas) + "\n"

    partes: List[str] = []
    if incluir_cabecalho:
        partes.append("\n".join(linha.lstrip("# ").rstrip() for linha in cabecalho[:-1]))
        partes.append("")
    if avisos:
        partes.extend(f"Aviso: {aviso}" for aviso in avisos)
        partes.append("")
    partes.append(texto)
    return "\n".join(partes).strip() + "\n"


@register
class PycDecompilerTool(FileTool):
    """Ferramenta de descompilação de arquivos .pyc."""

    id = "rev.pyc_decompiler"
    name = "Descompilador de Bytecode Python (.pyc)"
    category = "Reverse Engineering"
    description = (
        "Identifica o magic number e a versão do CPython, tenta decompyle3, uncompyle6 "
        "ou pycdc e, sem eles, entrega a desmontagem completa com dis em .txt ou .py"
    )
    keywords = [
        "pyc", "python", "bytecode", "descompilar", "decompyle3", "uncompyle6",
        "pycdc", "dis", "marshal", "magic number", "engenharia reversa",
    ]
    optional_deps = ["decompyle3", "uncompyle6"]

    accepts = [".pyc", ".pyo"]
    batch_kind = "per_file"
    parallel_mode = "thread"

    def __init__(self) -> None:
        self._cmb_modo: Optional[QComboBox] = None
        self._cmb_formato: Optional[QComboBox] = None
        self._chk_cabecalho: Optional[QCheckBox] = None

    # --------------------------------------------------------------- opções UI
    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        disponiveis = [
            nome for nome in ("decompyle3", "uncompyle6") if dependencia_disponivel(nome)
        ]
        pycdc = shutil.which("pycdc") or shutil.which("pycdc.exe")
        motores = ", ".join(disponiveis) if disponiveis else "nenhum"
        aviso = (
            f"Descompiladores Python detectados: {motores}. pycdc: {'presente' if pycdc else 'ausente'}.\n\n"
            "Sem um descompilador compatível com a versão do bytecode, a ferramenta gera a "
            "desmontagem com dis em um arquivo .txt (ou .py comentado). Isso é esperado e não é erro."
        )
        layout.addWidget(criar_aviso(aviso, container, destaque=not disponiveis and not pycdc))

        linha_1 = QWidget(container)
        lay_1 = QHBoxLayout(linha_1)
        lay_1.setContentsMargins(0, 0, 0, 0)
        lay_1.addWidget(QLabel("Modo:", linha_1))
        self._cmb_modo = QComboBox(linha_1)
        for rotulo, chave in OPCOES_MODO:
            self._cmb_modo.addItem(rotulo, chave)
        lay_1.addWidget(self._cmb_modo)
        lay_1.addWidget(QLabel("Saída:", linha_1))
        self._cmb_formato = QComboBox(linha_1)
        self._cmb_formato.addItem("Desmontagem (.txt)", "txt")
        self._cmb_formato.addItem("Código Python (.py)", "py")
        lay_1.addWidget(self._cmb_formato)
        lay_1.addStretch()
        layout.addWidget(linha_1)

        self._chk_cabecalho = QCheckBox("Incluir cabeçalho com magic number e versão", container)
        self._chk_cabecalho.setChecked(True)
        layout.addWidget(self._chk_cabecalho)

        return container

    def get_options(self) -> Dict[str, Any]:
        return {
            "modo": (self._cmb_modo.currentData() if self._cmb_modo else "auto") or "auto",
            "formato": (self._cmb_formato.currentData() if self._cmb_formato else "txt") or "txt",
            "cabecalho": self._chk_cabecalho.isChecked() if self._chk_cabecalho else True,
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ".py" if (params or {}).get("formato", "txt") == "py" else ".txt"

    # ------------------------------------------------------------ processamento
    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            tamanho = src.stat().st_size
            if tamanho > LIMITE_BYTES:
                return ItemResult(
                    success=False,
                    source_path=src,
                    error=f"Arquivo acima do limite de {LIMITE_BYTES // (1024 * 1024)} MB.",
                )
            if ctx is not None and ctx.cancelled():
                return ItemResult(success=False, source_path=src, error="Operação cancelada.")
            dados = src.read_bytes()
            opcoes = params or {}
            resultado = decompilar_pyc(
                src,
                dados,
                modo=opcoes.get("modo", "auto"),
                ao_log=(ctx.log if ctx is not None else None),
            )
            formato_py = opcoes.get("formato", "txt") == "py"
            conteudo = montar_conteudo(resultado, formato_py, opcoes.get("cabecalho", True))
            Path(dst).write_text(conteudo, encoding="utf-8")
            motor = resultado.get("motor") or "desconhecido"
            mensagem = f"{motor}; Python {resultado['info'].get('versao')}"
            if ctx is not None:
                ctx.log("INFO", f"{src.name}: {mensagem}.")
            return ItemResult(
                success=True,
                source_path=src,
                output_path=Path(dst),
                message=mensagem,
                bytes_in=tamanho,
                bytes_out=Path(dst).stat().st_size,
            )
        except Exception as exc:  # noqa: BLE001
            return ItemResult(success=False, source_path=src, error=str(exc))

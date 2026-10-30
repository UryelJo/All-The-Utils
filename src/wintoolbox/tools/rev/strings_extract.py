"""Extração e classificação de strings de qualquer arquivo.

As strings ASCII e UTF-16LE são extraídas com o auxiliar compartilhado do projeto
e classificadas por padrões (URL, IP, e-mail, domínio, caminhos, chaves de API,
JWT, Base64 e hashes). O resultado pode ser exportado em texto, JSON ou CSV.
"""
from __future__ import annotations

import base64
import binascii
import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools._helpers import extrair_strings
from wintoolbox.tools._widgets import criar_aviso

_log = get_logger("rev.strings_extract")

LIMITE_PADRAO = 50_000
LIMITE_BYTES = 256 * 1024 * 1024

TEXTO_ETICO = (
    "A extração de strings expõe conteúdo embutido em binários de terceiros, que pode "
    "incluir segredos, dados pessoais, caminhos internos e chaves de licença.\n\n"
    "Analise apenas arquivos próprios ou para os quais você possui autorização. "
    "Não publique nem reutilize credenciais encontradas: comunique o responsável e "
    "siga o processo de resposta a incidentes. O tratamento de dados pessoais deve "
    "observar a Lei 13.709/2018 (LGPD).\n\n"
    "A ferramenta não executa o arquivo: apenas lê os bytes e produz um relatório local."
)

_PADRAO_URL = re.compile(r"https?://[^\s\"'<>\\]{3,}", re.IGNORECASE)
_PADRAO_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PADRAO_DOMINIO = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+(?:com|net|org|br|io|dev|app|info|gov|edu|co|uk|de|fr|jp|ru|cn|xyz|online|site|tech|cloud|ai|me|tv|us)\b",
    re.IGNORECASE,
)
_PADRAO_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PADRAO_IPV6 = re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{0,4}\b")
_PADRAO_CAMINHO_WIN = re.compile(r"\b[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*")
_PADRAO_CAMINHO_UNIX = re.compile(r"(?<![\w.])/(?:[\w.\-]+/){1,}[\w.\-]*")
_PADRAO_HASH = re.compile(r"^[A-Fa-f0-9]{32}$|^[A-Fa-f0-9]{40}$|^[A-Fa-f0-9]{64}$|^[A-Fa-f0-9]{128}$")
_PADRAO_JWT = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")
_PADRAO_BASE64 = re.compile(r"^[A-Za-z0-9+/]{16,}={0,2}$")
_PADRAO_CHAVE = re.compile(
    r"(?:AKIA[0-9A-Z]{16})"
    r"|(?:ASIA[0-9A-Z]{16})"
    r"|(?:gh[pousr]_[A-Za-z0-9]{20,})"
    r"|(?:github_pat_[A-Za-z0-9_]{20,})"
    r"|(?:xox[baprs]-[A-Za-z0-9-]{10,})"
    r"|(?:sk-[A-Za-z0-9]{20,})"
    r"|(?:rk_live_[A-Za-z0-9]{16,})"
    r"|(?:AIza[0-9A-Za-z_\-]{35})"
    r"|(?:-----BEGIN [A-Z ]*PRIVATE KEY-----)"
    r"|(?:eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
)
_PADRAO_TOKEN_GENERICO = re.compile(
    r"(?i)\b(?:api[_-]?key|apikey|secret|token|senha|password|passwd|bearer)\b\s*[:=]\s*['\"]?([A-Za-z0-9._\-]{12,})"
)

ROTULOS_CLASSE = {
    "url": "URL",
    "ipv4": "IPv4",
    "ipv6": "IPv6",
    "email": "E-mail",
    "dominio": "Domínio",
    "caminho_windows": "Caminho Windows",
    "caminho_unix": "Caminho POSIX",
    "chave_api": "Chave ou segredo",
    "jwt": "JWT",
    "base64": "Base64",
    "hash_hex": "Hash hexadecimal",
}


def _ipv4_valido(texto: str) -> bool:
    partes = texto.split(".")
    if len(partes) != 4:
        return False
    return all(parte.isdigit() and 0 <= int(parte) <= 255 for parte in partes)


def _base64_legivel(texto: str) -> bool:
    if len(texto) < 16 or len(texto) % 4 != 0:
        return False
    try:
        decodificado = base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError):
        return False
    if len(decodificado) < 8:
        return False
    imprimiveis = sum(1 for byte in decodificado if 32 <= byte <= 126 or byte in (9, 10, 13))
    return imprimiveis / len(decodificado) >= 0.85


def _jwt_valido(texto: str) -> bool:
    partes = texto.split(".")
    if len(partes) != 3:
        return False
    try:
        cabecalho = partes[0].replace("-", "+").replace("_", "/")
        cabecalho += "=" * (-len(cabecalho) % 4)
        conteudo = base64.b64decode(cabecalho)
        dados = json.loads(conteudo.decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return False
    return isinstance(dados, dict) and ("alg" in dados or "typ" in dados)


def classificar_string(texto: str) -> List[str]:
    """Devolve as classes detectadas para uma string (lista vazia se neutra)."""
    valor = str(texto or "").strip()
    if not valor:
        return []
    classes: List[str] = []

    urls = _PADRAO_URL.findall(valor)
    if urls:
        classes.append("url")
    if _PADRAO_EMAIL.search(valor):
        classes.append("email")
    if _PADRAO_IPV4.fullmatch(valor) and _ipv4_valido(valor):
        classes.append("ipv4")
    if _PADRAO_IPV6.fullmatch(valor) and valor.count(":") >= 2:
        classes.append("ipv6")
    if _PADRAO_DOMINIO.fullmatch(valor):
        classes.append("dominio")
    if _PADRAO_CAMINHO_WIN.fullmatch(valor):
        classes.append("caminho_windows")
    elif _PADRAO_CAMINHO_UNIX.fullmatch(valor) and len(valor) > 3:
        classes.append("caminho_unix")
    if _PADRAO_JWT.fullmatch(valor) and _jwt_valido(valor):
        classes.append("jwt")
    if _PADRAO_HASH.fullmatch(valor):
        classes.append("hash_hex")
    if _PADRAO_CHAVE.search(valor):
        classes.append("chave_api")
    elif _PADRAO_TOKEN_GENERICO.search(valor):
        classes.append("chave_api")
    if not classes and _PADRAO_BASE64.fullmatch(valor) and _base64_legivel(valor):
        classes.append("base64")
    return classes


def extrair_classificadas(
    dados: bytes,
    minimo: int = 4,
    utf16: bool = True,
    incluir_sem_classe: bool = False,
    deduplicar: bool = True,
    limite: int = LIMITE_PADRAO,
    ao_progresso: Optional[Any] = None,
) -> Dict[str, Any]:
    """Extrai strings do bloco de bytes e classifica cada uma."""
    minimo = max(3, int(minimo))
    brutas = extrair_strings(dados, minimo=minimo, utf16=utf16)
    itens: List[Dict[str, Any]] = []
    vistos: set[str] = set()
    total_brutas = len(brutas)

    for indice, (deslocamento, codificacao, texto) in enumerate(brutas):
        if len(itens) >= limite:
            break
        limpo = texto.strip()
        if not limpo:
            continue
        if deduplicar:
            chave = limpo
            if chave in vistos:
                continue
            vistos.add(chave)
        classes = classificar_string(limpo)
        if not classes and not incluir_sem_classe:
            continue
        itens.append(
            {
                "offset": deslocamento,
                "offset_hex": f"0x{deslocamento:08X}",
                "codificacao": codificacao,
                "texto": limpo,
                "classes": classes,
            }
        )
        if ao_progresso is not None and indice % 5000 == 0 and total_brutas:
            ao_progresso(indice, total_brutas)

    contagem: Dict[str, int] = {}
    for item in itens:
        for classe in item["classes"]:
            contagem[classe] = contagem.get(classe, 0) + 1

    return {
        "total_strings_brutas": total_brutas,
        "total_selecionadas": len(itens),
        "truncado": len(itens) >= limite,
        "classes": contagem,
        "itens": itens,
    }


def montar_conteudo(resultado: Dict[str, Any], nome_arquivo: str, formato: str) -> str:
    """Serializa o resultado no formato escolhido (txt, json ou csv)."""
    if formato == "json":
        return json.dumps(
            {"arquivo": nome_arquivo, **resultado},
            ensure_ascii=False,
            indent=2,
        )
    if formato == "csv":
        buffer = io.StringIO()
        escritor = csv.writer(buffer, delimiter=";")
        escritor.writerow(["Offset", "Codificacao", "Classes", "Texto"])
        for item in resultado.get("itens", []):
            escritor.writerow(
                [
                    item.get("offset_hex", ""),
                    item.get("codificacao", ""),
                    "|".join(item.get("classes", [])),
                    item.get("texto", ""),
                ]
            )
        return buffer.getvalue()

    linhas = [
        f"Arquivo: {nome_arquivo}",
        f"Strings brutas encontradas: {resultado.get('total_strings_brutas', 0)}",
        f"Strings selecionadas: {resultado.get('total_selecionadas', 0)}",
    ]
    if resultado.get("truncado"):
        linhas.append("Aviso: limite de strings atingido; o relatório foi truncado.")
    linhas.append("")
    classes = resultado.get("classes", {})
    if classes:
        linhas.append("Resumo por classe:")
        for chave, quantidade in sorted(classes.items(), key=lambda par: -par[1]):
            linhas.append(f"  {ROTULOS_CLASSE.get(chave, chave)}: {quantidade}")
        linhas.append("")
    linhas.append("Strings:")
    for item in resultado.get("itens", []):
        etiquetas = ",".join(ROTULOS_CLASSE.get(classe, classe) for classe in item.get("classes", []))
        prefixo = f"[{item.get('offset_hex', '')}] ({item.get('codificacao', '')})"
        if etiquetas:
            prefixo += f" <{etiquetas}>"
        linhas.append(f"{prefixo} {item.get('texto', '')}")
    return "\n".join(linhas)


@register
class StringsExtractTool(FileTool):
    """Ferramenta de extração e classificação de strings."""

    id = "rev.strings_extract"
    name = "Extrator de Strings Classificadas"
    category = "Reverse Engineering"
    description = (
        "Extrai strings ASCII e UTF-16LE de qualquer arquivo e classifica URLs, IPs, "
        "e-mails, domínios, caminhos, chaves, JWT, Base64 e hashes, exportando em texto, JSON ou CSV"
    )
    keywords = [
        "strings", "extração", "binário", "ascii", "utf-16", "url", "ip", "jwt",
        "base64", "chave", "segredo", "engenharia reversa",
    ]
    optional_deps = []

    accepts: List[str] = []
    batch_kind = "per_file"
    parallel_mode = "thread"

    def __init__(self) -> None:
        self._spn_minimo: Optional[QSpinBox] = None
        self._spn_limite: Optional[QSpinBox] = None
        self._chk_utf16: Optional[QCheckBox] = None
        self._chk_sem_classe: Optional[QCheckBox] = None
        self._chk_dedupe: Optional[QCheckBox] = None
        self._cmb_formato: Optional[QComboBox] = None

    # --------------------------------------------------------------- opções UI
    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        aviso = criar_aviso(TEXTO_ETICO, container, destaque=True)
        layout.addWidget(aviso)

        linha_tamanho = QWidget(container)
        lay_tamanho = QHBoxLayout(linha_tamanho)
        lay_tamanho.setContentsMargins(0, 0, 0, 0)
        lay_tamanho.addWidget(QLabel("Tamanho mínimo:", linha_tamanho))
        self._spn_minimo = QSpinBox(linha_tamanho)
        self._spn_minimo.setRange(3, 64)
        self._spn_minimo.setValue(4)
        lay_tamanho.addWidget(self._spn_minimo)
        lay_tamanho.addWidget(QLabel("Limite de strings:", linha_tamanho))
        self._spn_limite = QSpinBox(linha_tamanho)
        self._spn_limite.setRange(100, 500_000)
        self._spn_limite.setSingleStep(1000)
        self._spn_limite.setValue(LIMITE_PADRAO)
        lay_tamanho.addWidget(self._spn_limite)
        lay_tamanho.addWidget(QLabel("Formato de saída:", linha_tamanho))
        self._cmb_formato = QComboBox(linha_tamanho)
        self._cmb_formato.addItem("Texto (.txt)", "txt")
        self._cmb_formato.addItem("JSON (.json)", "json")
        self._cmb_formato.addItem("CSV (.csv)", "csv")
        lay_tamanho.addWidget(self._cmb_formato)
        lay_tamanho.addStretch()
        layout.addWidget(linha_tamanho)

        self._chk_utf16 = QCheckBox("Incluir strings UTF-16LE (Unicode)", container)
        self._chk_utf16.setChecked(True)
        layout.addWidget(self._chk_utf16)

        self._chk_sem_classe = QCheckBox("Incluir strings sem classificação", container)
        self._chk_sem_classe.setChecked(False)
        layout.addWidget(self._chk_sem_classe)

        self._chk_dedupe = QCheckBox("Remover strings duplicadas", container)
        self._chk_dedupe.setChecked(True)
        layout.addWidget(self._chk_dedupe)

        return container

    def get_options(self) -> Dict[str, Any]:
        return {
            "minimo": self._spn_minimo.value() if self._spn_minimo else 4,
            "limite": self._spn_limite.value() if self._spn_limite else LIMITE_PADRAO,
            "utf16": self._chk_utf16.isChecked() if self._chk_utf16 else True,
            "sem_classe": self._chk_sem_classe.isChecked() if self._chk_sem_classe else False,
            "deduplicar": self._chk_dedupe.isChecked() if self._chk_dedupe else True,
            "formato": (self._cmb_formato.currentData() if self._cmb_formato else "txt") or "txt",
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        formato = (params or {}).get("formato", "txt")
        return {"json": ".json", "csv": ".csv"}.get(formato, ".txt")

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
            resultado = extrair_classificadas(
                dados,
                minimo=opcoes.get("minimo", 4),
                utf16=opcoes.get("utf16", True),
                incluir_sem_classe=opcoes.get("sem_classe", False),
                deduplicar=opcoes.get("deduplicar", True),
                limite=opcoes.get("limite", LIMITE_PADRAO),
            )
            formato = opcoes.get("formato", "txt")
            conteudo = montar_conteudo(resultado, src.name, formato)
            Path(dst).write_text(conteudo, encoding="utf-8")
            if ctx is not None:
                ctx.log(
                    "INFO",
                    f"{src.name}: {resultado['total_selecionadas']} string(s) de "
                    f"{resultado['total_strings_brutas']} bruta(s).",
                )
            return ItemResult(
                success=True,
                source_path=src,
                output_path=Path(dst),
                message=f"{resultado['total_selecionadas']} string(s) selecionada(s)",
                bytes_in=tamanho,
                bytes_out=Path(dst).stat().st_size,
            )
        except Exception as exc:  # noqa: BLE001
            return ItemResult(success=False, source_path=src, error=str(exc))

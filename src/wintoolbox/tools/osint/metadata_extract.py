"""Extração de metadados de imagens, PDF, Office Open XML, MP3 e MP4.

Todas as leituras usam bibliotecas já disponíveis ou a biblioteca padrão: Pillow
para EXIF/XMP/IPTC, pypdf para PDF, `zipfile` + `xml.etree` para OOXML, `mutagen`
para MP3 e um leitor de átomos próprio para MP4. Nada é enviado para a rede.
"""
from __future__ import annotations

import json
import os
import struct
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools._helpers import dependencia_disponivel, formatar_bytes
from wintoolbox.tools._widgets import criar_aviso

_log = get_logger("osint.metadata_extract")

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".webp", ".heic", ".heif"}
EXTENSOES_PDF = {".pdf"}
EXTENSOES_OOXML = {".docx", ".xlsx", ".pptx"}
EXTENSOES_AUDIO = {".mp3"}
EXTENSOES_VIDEO = {".mp4", ".m4a", ".m4v", ".mov"}

GRUPOS_PADRAO: Dict[str, bool] = {
    "imagem": True,
    "gps": True,
    "pdf": True,
    "ooxml": True,
    "midia": True,
}

TEXTO_PRIVACIDADE = (
    "Metadados podem revelar identidade, equipamento, localização exata (GPS), "
    "editores utilizados, caminhos internos e datas de criação. Revise o relatório "
    "antes de publicar ou compartilhar o arquivo original. A extração é local e "
    "nenhum dado sai da máquina."
)

# Nomes de tags EXIF mais consultadas (complementam o mapa oficial do Pillow).
_TAGS_EXIF_EXTRA = {
    0x010E: "ImageDescription",
    0x010F: "Make",
    0x0110: "Model",
    0x0112: "Orientation",
    0x011A: "XResolution",
    0x011B: "YResolution",
    0x0128: "ResolutionUnit",
    0x0131: "Software",
    0x0132: "DateTime",
    0x013B: "Artist",
    0x8298: "Copyright",
    0x8769: "ExifIFDPointer",
    0x8825: "GPSInfoIFDPointer",
    0x9003: "DateTimeOriginal",
    0x9004: "DateTimeDigitized",
    0x9201: "ShutterSpeedValue",
    0x9202: "ApertureValue",
    0x9204: "ExposureBiasValue",
    0x9207: "MeteringMode",
    0x9209: "Flash",
    0x920A: "FocalLength",
    0x9291: "SubsecTimeOriginal",
    0xA002: "PixelXDimension",
    0xA003: "PixelYDimension",
    0xA405: "FocalLengthIn35mmFilm",
    0xA430: "CameraOwnerName",
    0xA431: "BodySerialNumber",
    0xA433: "LensMake",
    0xA434: "LensModel",
    0xA435: "LensSerialNumber",
}

_ROTULOS_GPS = {
    0: "GPSVersionID",
    1: "GPSLatitudeRef",
    2: "GPSLatitude",
    3: "GPSLongitudeRef",
    4: "GPSLongitude",
    5: "GPSAltitudeRef",
    6: "GPSAltitude",
    7: "GPSTimeStamp",
    8: "GPSSatellites",
    9: "GPSStatus",
    11: "GPSDOP",
    12: "GPSSpeedRef",
    13: "GPSSpeed",
    16: "GPSImgDirectionRef",
    17: "GPSImgDirection",
    18: "GPSMapDatum",
    23: "GPSDestBearingRef",
    24: "GPSDestBearing",
    27: "GPSProcessingMethod",
    29: "GPSDateStamp",
}

_ATOMOS_MP4 = {
    b"\xa9nam": "Titulo",
    b"\xa9ART": "Artista",
    b"\xa9alb": "Album",
    b"\xa9day": "Ano",
    b"\xa9cmt": "Comentario",
    b"\xa9gen": "Genero",
    b"\xa9wrt": "Compositor",
    b"\xa9too": "Codificador",
    b"aART": "ArtistaDoAlbum",
    b"desc": "Descricao",
    b"trkn": "Faixa",
    b"disk": "Disco",
    b"covr": "CapaEmbutida",
    b"cpil": "Compilacao",
    b"tmpo": "Andamento",
}


# ------------------------------------------------------------------ utilidades
def _serializavel(valor: Any) -> Any:
    """Converte tipos exóticos de metadados em algo serializável em JSON."""
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    if isinstance(valor, bytes):
        try:
            texto = valor.decode("utf-8")
            if texto.isprintable():
                return texto
        except UnicodeDecodeError:
            pass
        return valor.hex()
    if isinstance(valor, (list, tuple)):
        return [_serializavel(item) for item in valor]
    if isinstance(valor, dict):
        return {str(chave): _serializavel(item) for chave, item in valor.items()}
    if isinstance(valor, datetime):
        return valor.isoformat()
    try:
        return float(valor)
    except (TypeError, ValueError):
        return str(valor)


def _tipo_arquivo(caminho: Path) -> str:
    extensao = caminho.suffix.lower()
    if extensao in EXTENSOES_IMAGEM:
        return "imagem"
    if extensao in EXTENSOES_PDF:
        return "pdf"
    if extensao in EXTENSOES_OOXML:
        return "ooxml"
    if extensao in EXTENSOES_AUDIO:
        return "audio"
    if extensao in EXTENSOES_VIDEO:
        return "video"
    return "desconhecido"


def _racional(valor: Any) -> Optional[float]:
    try:
        if isinstance(valor, tuple) and len(valor) == 2:
            numerador, denominador = valor
            if float(denominador) == 0:
                return None
            return float(numerador) / float(denominador)
        return float(valor)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _gms_para_decimal(componentes: Any) -> Optional[float]:
    if not componentes or len(componentes) != 3:
        return None
    graus = _racional(componentes[0])
    minutos = _racional(componentes[1])
    segundos = _racional(componentes[2])
    if graus is None or minutos is None or segundos is None:
        return None
    return round(graus + minutos / 60.0 + segundos / 3600.0, 7)


def extrair_gps(gps_info: Dict[int, Any]) -> Dict[str, Any]:
    """Converte o bloco GPS do EXIF em coordenadas decimais e link de mapa."""
    if not gps_info:
        return {}
    saida: Dict[str, Any] = {"bruto": {}, "latitude": None, "longitude": None}
    for chave, valor in gps_info.items():
        saida["bruto"][_ROTULOS_GPS.get(int(chave), f"GPS{chave}")] = _serializavel(valor)

    latitude = _gms_para_decimal(gps_info.get(2))
    longitude = _gms_para_decimal(gps_info.get(4))
    if latitude is not None and str(gps_info.get(1, "N")).upper().startswith("S"):
        latitude = -latitude
    if longitude is not None and str(gps_info.get(3, "E")).upper().startswith("W"):
        longitude = -longitude

    altitude = _racional(gps_info.get(6))
    if altitude is not None and int(gps_info.get(5, 0) or 0) == 1:
        altitude = -altitude

    saida.update({"latitude": latitude, "longitude": longitude, "altitude": altitude})
    if latitude is not None and longitude is not None:
        saida["mapa"] = f"https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=16/{latitude}/{longitude}"
    return saida


# ---------------------------------------------------------------------- imagens
def _extrair_imagem(caminho: Path, incluir_gps: bool) -> Dict[str, Any]:
    from PIL import ExifTags, Image, IptcImagePlugin

    dados: Dict[str, Any] = {}
    with Image.open(caminho) as imagem:
        dados["formato"] = imagem.format or caminho.suffix.lstrip(".").upper()
        dados["dimensoes"] = {"largura": imagem.width, "altura": imagem.height}
        dados["modo"] = imagem.mode
        dados["informacoes"] = {
            str(chave): _serializavel(valor)
            for chave, valor in (imagem.info or {}).items()
            if chave.lower() not in {"xmp", "exif", "photoshop", "icc_profile"}
        }

        exif: Dict[str, Any] = {}
        try:
            bruto = imagem.getexif()
            todos = dict(ExifTags.TAGS)
            todos.update({numero: nome for numero, nome in _TAGS_EXIF_EXTRA.items()})
            for chave, valor in bruto.items():
                nome = todos.get(chave, f"Tag_{chave}")
                exif[nome] = _serializavel(valor)
            for ifd_nome, ifd_chave in (("Exif", 0x8769), ("GPS", 0x8825)):
                try:
                    ifd = bruto.get_ifd(ifd_chave)
                except Exception:  # noqa: BLE001 - Pillow antigo
                    ifd = {}
                if ifd_nome == "GPS":
                    if incluir_gps:
                        bloco = {int(k): v for k, v in ifd.items()}
                        if bloco:
                            dados["gps"] = extrair_gps(bloco)
                    continue
                for chave, valor in (ifd or {}).items():
                    nome = todos.get(chave, f"Tag_{chave}")
                    exif[nome] = _serializavel(valor)
        except Exception as exc:  # noqa: BLE001
            dados["aviso_exif"] = f"Falha ao ler EXIF: {exc}"
        if exif:
            dados["exif"] = exif

        xmp = (imagem.info or {}).get("xmp")
        if xmp:
            if isinstance(xmp, bytes):
                dados["xmp"] = xmp.decode("utf-8", errors="replace")
            else:
                dados["xmp"] = str(xmp)

        try:
            iptc = IptcImagePlugin.getiptcinfo(imagem)
        except Exception:  # noqa: BLE001
            iptc = None
        if iptc:
            rotulos = {
                (2, 5): "ObjectName",
                (2, 25): "Keywords",
                (2, 40): "SpecialInstructions",
                (2, 55): "DateCreated",
                (2, 80): "Byline",
                (2, 85): "BylineTitle",
                (2, 90): "City",
                (2, 95): "ProvinceState",
                (2, 101): "Country",
                (2, 105): "Headline",
                (2, 110): "Credit",
                (2, 115): "Source",
                (2, 116): "CopyrightNotice",
            }
            bloco_iptc: Dict[str, Any] = {}
            for chave, valor in iptc.items():
                if isinstance(chave, tuple):
                    nome = rotulos.get(chave, f"IPTC_{chave[0]}_{chave[1]}")
                    bloco_iptc[nome] = _serializavel(valor)
            if bloco_iptc:
                dados["iptc"] = bloco_iptc
    return dados


# -------------------------------------------------------------------------- PDF
def _extrair_pdf(caminho: Path) -> Dict[str, Any]:
    from pypdf import PdfReader

    dados: Dict[str, Any] = {}
    leitor = PdfReader(str(caminho))
    if leitor.is_encrypted:
        try:
            leitor.decrypt("")
        except Exception as exc:  # noqa: BLE001
            return {"aviso": f"PDF protegido por senha: {exc}"}

    dados["paginas"] = len(leitor.pages)
    metadados = leitor.metadata
    if metadados:
        dados["documento"] = {str(chave): _serializavel(valor) for chave, valor in metadados.items()}
    try:
        xmp = leitor.xmp_metadata
        if xmp is not None:
            dados["xmp"] = str(xmp)
    except Exception:  # noqa: BLE001
        pass
    try:
        dados["criptografado"] = bool(leitor.is_encrypted)
    except Exception:  # noqa: BLE001
        pass
    return dados


# ------------------------------------------------------------------------- OOXML
_NS_CONHECIDOS = {
    "http://schemas.openxmlformats.org/package/2006/metadata/core-properties": "core",
    "http://purl.org/dc/elements/1.1/": "dc",
    "http://purl.org/dc/terms/": "dcterms",
    "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties": "app",
    "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties": "custom",
}


def _parsear_xml_plano(conteudo: bytes) -> Dict[str, str]:
    saida: Dict[str, str] = {}
    try:
        raiz = ElementTree.fromstring(conteudo)
    except ElementTree.ParseError:
        return saida
    for elemento in raiz.iter():
        texto = (elemento.text or "").strip()
        if not texto:
            continue
        chave = elemento.tag.split("}")[-1]
        prefixo = ""
        if "}" in elemento.tag:
            uri = elemento.tag.split("}")[0].lstrip("{")
            prefixo = _NS_CONHECIDOS.get(uri, "")
        nome = f"{prefixo}:{chave}" if prefixo else chave
        if nome in saida and len(saida[nome]) > len(texto):
            continue
        saida[nome] = texto
    return saida


def _extrair_ooxml(caminho: Path) -> Dict[str, Any]:
    dados: Dict[str, Any] = {}
    with zipfile.ZipFile(caminho) as pacote:
        nomes = set(pacote.namelist())
        for arquivo, rotulo in (
            ("docProps/core.xml", "nucleo"),
            ("docProps/app.xml", "aplicativo"),
            ("docProps/custom.xml", "personalizado"),
        ):
            if arquivo in nomes:
                bloco = _parsear_xml_plano(pacote.read(arquivo))
                if bloco:
                    dados[rotulo] = bloco
        if "docProps/thumbnail.jpeg" in nomes:
            dados["miniatura"] = "presente"
        dados["partes"] = len(nomes)
        if "word/document.xml" in nomes:
            dados["tipo_documento"] = "Word"
        elif "xl/workbook.xml" in nomes:
            dados["tipo_documento"] = "Excel"
        elif "ppt/presentation.xml" in nomes:
            dados["tipo_documento"] = "PowerPoint"
    return dados


# -------------------------------------------------------------------------- MP3
def _extrair_mp3(caminho: Path) -> Dict[str, Any]:
    dados: Dict[str, Any] = {}
    if dependencia_disponivel("mutagen"):
        from mutagen.id3 import ID3
        from mutagen.mp3 import MP3

        audio = MP3(str(caminho))
        dados["audio"] = {
            "duracao_s": round(float(audio.info.length), 2),
            "taxa_bits": getattr(audio.info, "bitrate", 0),
            "taxa_amostragem": getattr(audio.info, "sample_rate", 0),
            "canais": getattr(audio.info, "channels", 0),
            "modo": getattr(audio.info, "mode", ""),
            "protegido": bool(getattr(audio.info, "protected", False)),
        }
        try:
            tags = ID3(str(caminho))
            bloco: Dict[str, Any] = {}
            for chave, quadro in tags.items():
                try:
                    bloco[str(chave)] = _serializavel(quadro.text)
                except Exception:  # noqa: BLE001
                    bloco[str(chave)] = str(quadro)[:300]
            dados["tags"] = bloco
        except Exception as exc:  # noqa: BLE001
            dados["aviso_tags"] = f"Sem tags ID3 legíveis: {exc}"
    else:
        dados.update(_extrair_mp3_nativo(caminho))
    return dados


def _extrair_mp3_nativo(caminho: Path) -> Dict[str, Any]:
    """Leitor mínimo de ID3v2.3/2.4 usado quando `mutagen` não está instalado."""
    dados: Dict[str, Any] = {"motor": "nativo"}
    bruto = caminho.read_bytes()[:2_000_000]
    if len(bruto) >= 10 and bruto[:3] == b"ID3":
        versao = bruto[3]
        tamanho = ((bruto[6] & 0x7F) << 21) | ((bruto[7] & 0x7F) << 14) | ((bruto[8] & 0x7F) << 7) | (bruto[9] & 0x7F)
        dados["versao_id3"] = f"2.{versao}"
        dados["tamanho_id3"] = tamanho
        posicao = 10
        tags: Dict[str, str] = {}
        while posicao + 10 < len(bruto):
            quadro_id = bruto[posicao : posicao + 4]
            if not quadro_id.strip(b"\x00"):
                break
            tamanho_quadro = struct.unpack(">I", bruto[posicao + 4 : posicao + 8])[0]
            if tamanho_quadro <= 0 or posicao + 10 + tamanho_quadro > len(bruto):
                break
            conteudo = bruto[posicao + 10 : posicao + 10 + tamanho_quadro]
            if conteudo[:1] == b"\x00":
                texto = conteudo[1:].decode("latin-1", errors="replace").strip("\x00")
                tags[quadro_id.decode("latin-1")] = texto
            posicao += 10 + tamanho_quadro
        if tags:
            dados["tags"] = tags
    return dados


# -------------------------------------------------------------------------- MP4
def _ler_caixas(dados: bytes, inicio: int = 0, fim: Optional[int] = None) -> List[Tuple[bytes, int, int]]:
    """Lista (tipo, offset_do_conteudo, tamanho_do_conteudo) das caixas."""
    limite = len(dados) if fim is None else min(fim, len(dados))
    caixas: List[Tuple[bytes, int, int]] = []
    posicao = inicio
    while posicao + 8 <= limite:
        tamanho = struct.unpack(">I", dados[posicao : posicao + 4])[0]
        tipo = dados[posicao + 4 : posicao + 8]
        cabecalho = 8
        if tamanho == 1:
            if posicao + 16 > limite:
                break
            tamanho = struct.unpack(">Q", dados[posicao + 8 : posicao + 16])[0]
            cabecalho = 16
        elif tamanho == 0:
            tamanho = limite - posicao
        if tamanho < cabecalho or posicao + tamanho > limite:
            break
        caixas.append((tipo, posicao + cabecalho, tamanho - cabecalho))
        posicao += tamanho
    return caixas


def _valor_ilst(dados: bytes, inicio: int, tamanho: int) -> Any:
    for tipo, pos, tam in _ler_caixas(dados, inicio, inicio + tamanho):
        if tipo == b"data":
            if tam < 8:
                continue
            tipo_dado = struct.unpack(">I", dados[pos : pos + 4])[0] & 0x00FFFFFF
            conteudo = dados[pos + 8 : pos + tam]
            if tipo_dado == 1:
                return conteudo.decode("utf-8", errors="replace")
            if tipo_dado == 2:
                return conteudo.decode("utf-16-be", errors="replace")
            if tipo_dado in (13, 14):
                return f"imagem ({len(conteudo)} bytes)"
            if tipo_dado == 21 and len(conteudo) >= 2:
                return struct.unpack(">H", conteudo[:2])[0]
            if tipo_dado == 0:
                return int.from_bytes(conteudo, "big") if len(conteudo) <= 8 else conteudo.hex()
            return _serializavel(conteudo)
    return None


def _extrair_mp4(caminho: Path) -> Dict[str, Any]:
    dados: Dict[str, Any] = {}
    bruto = caminho.read_bytes()
    topo = _ler_caixas(bruto)
    dados["caixas_topo"] = [tipo.decode("latin-1", errors="replace") for tipo, _, _ in topo]

    for tipo, pos, tam in topo:
        if tipo != b"moov":
            continue
        for sub_tipo, sub_pos, sub_tam in _ler_caixas(bruto, pos, pos + tam):
            if sub_tipo == b"mvhd":
                versao = bruto[sub_pos]
                if versao == 0 and sub_tam >= 20:
                    escala, duracao = struct.unpack(">II", bruto[sub_pos + 12 : sub_pos + 20])
                elif versao == 1 and sub_tam >= 32:
                    escala, duracao = struct.unpack(">IQ", bruto[sub_pos + 20 : sub_pos + 32])
                else:
                    escala, duracao = 0, 0
                dados["duracao_s"] = round(duracao / escala, 2) if escala else None
            elif sub_tipo == b"udta":
                for udta_tipo, udta_pos, udta_tam in _ler_caixas(bruto, sub_pos, sub_pos + sub_tam):
                    if udta_tipo != b"meta":
                        continue
                    for meta_tipo, meta_pos, meta_tam in _ler_caixas(bruto, udta_pos + 4, udta_pos + udta_tam):
                        if meta_tipo != b"ilst":
                            continue
                        tags: Dict[str, Any] = {}
                        for item_tipo, item_pos, item_tam in _ler_caixas(bruto, meta_pos, meta_pos + meta_tam):
                            rotulo = _ATOMOS_MP4.get(item_tipo, item_tipo.decode("latin-1", errors="replace"))
                            valor = _valor_ilst(bruto, item_pos, item_tam)
                            if valor is not None:
                                tags[rotulo] = valor
                        if tags:
                            dados["tags"] = tags
    return dados


# ---------------------------------------------------------------- orquestração
def extrair_metadados(caminho: Path, grupos: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Extrai os metadados disponíveis conforme o tipo e os grupos habilitados."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    grupos = dict(GRUPOS_PADRAO, **(grupos or {}))
    tipo = _tipo_arquivo(caminho)
    estatistica = caminho.stat()
    resultado: Dict[str, Any] = {
        "arquivo": caminho.name,
        "caminho": str(caminho),
        "tipo": tipo,
        "extensao": caminho.suffix.lower(),
        "tamanho_bytes": estatistica.st_size,
        "tamanho_legivel": formatar_bytes(estatistica.st_size),
        "modificado_em": datetime.fromtimestamp(estatistica.st_mtime).isoformat(timespec="seconds"),
        "criado_em": datetime.fromtimestamp(estatistica.st_ctime).isoformat(timespec="seconds"),
        "grupos": {},
        "avisos": [],
    }

    try:
        if tipo == "imagem" and grupos.get("imagem", True):
            resultado["grupos"]["imagem"] = _extrair_imagem(caminho, grupos.get("gps", True))
        elif tipo == "pdf" and grupos.get("pdf", True):
            resultado["grupos"]["pdf"] = _extrair_pdf(caminho)
        elif tipo == "ooxml" and grupos.get("ooxml", True):
            resultado["grupos"]["ooxml"] = _extrair_ooxml(caminho)
        elif tipo == "audio" and grupos.get("midia", True):
            resultado["grupos"]["audio"] = _extrair_mp3(caminho)
        elif tipo == "video" and grupos.get("midia", True):
            resultado["grupos"]["video"] = _extrair_mp4(caminho)
        elif tipo == "desconhecido":
            resultado["avisos"].append(
                "Extensão não reconhecida; nenhum extrator específico foi aplicado."
            )
        elif not any(grupos.values()):
            resultado["avisos"].append("Todos os grupos de metadados estão desativados.")
    except ImportError as exc:
        raise RuntimeError(
            f"Biblioteca necessária ausente para {caminho.suffix}: {exc}. "
            "Instale as dependências do WinToolbox."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        resultado["avisos"].append(f"Falha parcial na extração: {exc}")
        _log.warning("Falha ao extrair metadados de %s: %s", caminho, exc)
    return resultado


def contar_campos(metadados: Dict[str, Any]) -> int:
    """Conta folhas do dicionário de metadados."""
    total = 0
    pilha: List[Any] = [metadados.get("grupos", {})]
    while pilha:
        atual = pilha.pop()
        if isinstance(atual, dict):
            pilha.extend(atual.values())
        elif isinstance(atual, list):
            total += len(atual)
        else:
            total += 1
    return total


def formatar_texto(metadados: Dict[str, Any], prefixo: str = "") -> str:
    """Serializa os metadados em texto hierárquico legível."""
    linhas: List[str] = []
    for chave, valor in metadados.items():
        rotulo = f"{prefixo}{chave}"
        if isinstance(valor, dict):
            linhas.append(f"{rotulo}:")
            linhas.append(formatar_texto(valor, prefixo + "  "))
        elif isinstance(valor, list):
            linhas.append(f"{rotulo}: {len(valor)} item(ns)")
            for indice, item in enumerate(valor):
                if isinstance(item, (dict, list)):
                    linhas.append(f"{prefixo}  [{indice}]")
                    linhas.append(formatar_texto(item, prefixo + "    "))
                else:
                    linhas.append(f"{prefixo}  - {item}")
        else:
            linhas.append(f"{rotulo}: {valor}")
    return "\n".join(linha for linha in linhas if linha.strip())


@register
class MetadataExtractTool(FileTool):
    """Ferramenta de extração de metadados de arquivos."""

    id = "osint.metadata_extract"
    name = "Extrator de Metadados"
    category = "OSINT"
    description = (
        "Lê EXIF, XMP e IPTC de imagens, propriedades de PDF e Office Open XML, "
        "tags de MP3 e átomos de MP4, incluindo coordenadas GPS, e exporta em JSON ou texto"
    )
    keywords = [
        "osint", "metadados", "exif", "xmp", "iptc", "gps", "pdf", "docx", "xlsx",
        "pptx", "mp3", "mp4", "privacidade", "forense",
    ]
    optional_deps = ["exifread", "hachoir"]

    accepts = sorted(
        EXTENSOES_IMAGEM | EXTENSOES_PDF | EXTENSOES_OOXML | EXTENSOES_AUDIO | EXTENSOES_VIDEO
    )
    batch_kind = "per_file"
    parallel_mode = "thread"

    def __init__(self) -> None:
        self._chk_imagem: Optional[QCheckBox] = None
        self._chk_gps: Optional[QCheckBox] = None
        self._chk_pdf: Optional[QCheckBox] = None
        self._chk_ooxml: Optional[QCheckBox] = None
        self._chk_midia: Optional[QCheckBox] = None
        self._cmb_formato: Optional[QComboBox] = None

    # --------------------------------------------------------------- opções UI
    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        aviso = criar_aviso(TEXTO_PRIVACIDADE, container, destaque=True)
        aviso.setProperty("class", "card")
        layout.addWidget(aviso)

        linha_formato = QWidget(container)
        from PySide6.QtWidgets import QHBoxLayout

        lay_formato = QHBoxLayout(linha_formato)
        lay_formato.setContentsMargins(0, 0, 0, 0)
        lay_formato.addWidget(QLabel("Formato de saída:", linha_formato))
        self._cmb_formato = QComboBox(linha_formato)
        self._cmb_formato.addItem("JSON (.json)", "json")
        self._cmb_formato.addItem("Texto (.txt)", "txt")
        lay_formato.addWidget(self._cmb_formato)
        lay_formato.addStretch()
        layout.addWidget(linha_formato)

        self._chk_imagem = QCheckBox("Imagens: EXIF, XMP e IPTC", container)
        self._chk_imagem.setChecked(True)
        layout.addWidget(self._chk_imagem)

        self._chk_gps = QCheckBox("Coordenadas GPS (quando presentes)", container)
        self._chk_gps.setChecked(True)
        layout.addWidget(self._chk_gps)

        self._chk_pdf = QCheckBox("PDF: propriedades do documento", container)
        self._chk_pdf.setChecked(True)
        layout.addWidget(self._chk_pdf)

        self._chk_ooxml = QCheckBox("Office Open XML: docx, xlsx e pptx", container)
        self._chk_ooxml.setChecked(True)
        layout.addWidget(self._chk_ooxml)

        self._chk_midia = QCheckBox("Mídia: tags de MP3 e átomos de MP4", container)
        self._chk_midia.setChecked(True)
        layout.addWidget(self._chk_midia)

        return container

    def get_options(self) -> Dict[str, Any]:
        formato = self._cmb_formato.currentData() if self._cmb_formato else "json"
        return {
            "formato": formato or "json",
            "grupos": {
                "imagem": self._chk_imagem.isChecked() if self._chk_imagem else True,
                "gps": self._chk_gps.isChecked() if self._chk_gps else True,
                "pdf": self._chk_pdf.isChecked() if self._chk_pdf else True,
                "ooxml": self._chk_ooxml.isChecked() if self._chk_ooxml else True,
                "midia": self._chk_midia.isChecked() if self._chk_midia else True,
            },
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ".json" if (params or {}).get("formato", "json") == "json" else ".txt"

    # ------------------------------------------------------------ processamento
    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            metadados = extrair_metadados(src, (params or {}).get("grupos"))
            formato = (params or {}).get("formato", "json")
            if formato == "txt":
                conteudo = formatar_texto(metadados)
            else:
                conteudo = json.dumps(metadados, ensure_ascii=False, indent=2)
            Path(dst).write_text(conteudo, encoding="utf-8")
            campos = contar_campos(metadados)
            if ctx is not None:
                ctx.log("INFO", f"{src.name}: {campos} campo(s) de metadados extraídos.")
            return ItemResult(
                success=True,
                source_path=src,
                output_path=Path(dst),
                message=f"{campos} campo(s) extraídos",
                bytes_in=src.stat().st_size,
                bytes_out=Path(dst).stat().st_size,
            )
        except Exception as exc:  # noqa: BLE001
            return ItemResult(success=False, source_path=src, error=str(exc))

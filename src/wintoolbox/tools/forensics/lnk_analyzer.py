"""Análise forense de atalhos do Windows no formato MS-SHLLINK.

O parser nativo lê o cabeçalho de 76 bytes, a lista de itens (IDList), o bloco
``LinkInfo`` (incluindo VolumeID e serial), os blocos ``StringData`` e os blocos
``ExtraData`` conhecidos. Timestamps FILETIME, volume serial, nome do
computador e identificadores de rastreamento são extraídos quando presentes.

``LnkParse3`` é usado apenas como acelerador opcional. Sem ele, o parser nativo
continua funcionando e não inventa campos ausentes.
"""
from __future__ import annotations

import json
import re
import struct
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtWidgets import QCheckBox, QLabel, QWidget

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools._helpers import dependencia_disponivel, formatar_bytes
from wintoolbox.tools._widgets import PainelOpcoes, criar_aviso

_log = get_logger("forensics.lnk_analyzer")

_LINK_FLAGS = (
    (0x00000001, "HasLinkTargetIDList"),
    (0x00000002, "HasLinkInfo"),
    (0x00000004, "HasName"),
    (0x00000008, "HasRelativePath"),
    (0x00000010, "HasWorkingDir"),
    (0x00000020, "HasArguments"),
    (0x00000040, "HasIconLocation"),
    (0x00000080, "IsUnicode"),
    (0x00000100, "ForceNoLinkInfo"),
    (0x00000200, "HasExpString"),
    (0x00000400, "RunInSeparateProcess"),
    (0x00000800, "Unused1"),
    (0x00001000, "HasDarwinID"),
    (0x00002000, "RunAsUser"),
    (0x00004000, "HasExpIcon"),
    (0x00008000, "NoPidlAlias"),
    (0x00010000, "Unused2"),
    (0x00020000, "RunWithShimLayer"),
    (0x00040000, "ForceNoLinkTrack"),
    (0x00080000, "EnableTargetMetadata"),
    (0x00100000, "DisableLinkPathTracking"),
    (0x00200000, "DisableKnownFolderTracking"),
    (0x00400000, "DisableKnownFolderAlias"),
    (0x00800000, "AllowLinkToLink"),
    (0x01000000, "UnaliasOnSave"),
    (0x02000000, "PreferEnvironmentPath"),
    (0x04000000, "KeepLocalIDListForUNCTarget"),
)

_LINK_INFO_FLAGS = (
    (0x00000001, "VolumeIDAndLocalBasePath"),
    (0x00000002, "CommonNetworkRelativeLinkAndPathSuffix"),
)

_DRIVE_TYPES = {
    0: "Desconhecido",
    1: "Sem raiz",
    2: "Removível",
    3: "Fixo",
    4: "Rede",
    5: "CD-ROM",
    6: "RAM disk",
}

_PADRAO_MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}[-:]){5}[0-9A-Fa-f]{2}\b")


def _u16(dados: bytes, posicao: int) -> int:
    """Lê um inteiro de 16 bits com validação de limites."""
    if posicao < 0 or posicao + 2 > len(dados):
        raise ValueError("Campo de 16 bits fora dos limites do arquivo LNK.")
    return struct.unpack_from("<H", dados, posicao)[0]


def _u32(dados: bytes, posicao: int) -> int:
    """Lê um inteiro de 32 bits com validação de limites."""
    if posicao < 0 or posicao + 4 > len(dados):
        raise ValueError("Campo de 32 bits fora dos limites do arquivo LNK.")
    return struct.unpack_from("<I", dados, posicao)[0]


def _i32(dados: bytes, posicao: int) -> int:
    """Lê um inteiro de 32 bits com sinal."""
    if posicao < 0 or posicao + 4 > len(dados):
        raise ValueError("Campo de 32 bits fora dos limites do arquivo LNK.")
    return struct.unpack_from("<i", dados, posicao)[0]


def _filetime_para_iso(valor: int) -> str:
    """Converte FILETIME em data ISO local."""
    if not valor:
        return ""
    try:
        base = datetime(1601, 1, 1, tzinfo=timezone.utc)
        return (base + timedelta(microseconds=int(valor) // 10)).astimezone().isoformat(
            timespec="seconds"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _ansi(dados: bytes, posicao: int) -> str:
    """Decodifica uma string ANSI terminada em NUL a partir da posição."""
    if posicao < 0 or posicao >= len(dados):
        return ""
    fim = dados.find(b"\x00", posicao)
    if fim < 0:
        fim = len(dados)
    return dados[posicao:fim].decode("cp1252", errors="replace")


def _unicode(dados: bytes, posicao: int) -> str:
    """Decodifica uma string UTF-16LE terminada em NUL duplo."""
    if posicao < 0 or posicao >= len(dados):
        return ""
    fim = posicao
    while fim + 1 < len(dados):
        if dados[fim] == 0 and dados[fim + 1] == 0:
            break
        fim += 2
    return dados[posicao:fim].decode("utf-16le", errors="replace")


def _texto_em(dados: bytes, posicao: int, tamanho: int, unicode: bool) -> str:
    """Decodifica um campo de tamanho fixo em ANSI ou UTF-16LE."""
    if posicao < 0 or posicao >= len(dados):
        return ""
    bruto = dados[posicao : posicao + tamanho]
    if unicode:
        return bruto.decode("utf-16le", errors="replace").split("\x00")[0]
    return bruto.decode("cp1252", errors="replace").split("\x00")[0]


def _flags_ativas(flags: int, tabela: Tuple[Tuple[int, str], ...]) -> List[str]:
    """Lista os nomes das flags ativas."""
    return [nome for bit, nome in tabela if flags & bit]


def _strings_ascii(dados: bytes, minimo: int = 5) -> List[str]:
    """Extrai strings ASCII para a busca de MAC e nomes de host."""
    return [
        achado.group().decode("ascii", errors="ignore")
        for achado in re.finditer(rb"[\x20-\x7e]{%d,}" % minimo, dados)
    ]


def _volume_id(dados: bytes, base_link_info: int, deslocamento: int) -> Dict[str, Any]:
    """Lê o VolumeID do LinkInfo, incluindo o serial do volume."""
    if not deslocamento:
        return {}
    posicao = base_link_info + deslocamento
    if posicao + 16 > len(dados):
        return {}
    tamanho = _u32(dados, posicao)
    if tamanho < 16 or posicao + tamanho > len(dados):
        return {}
    tipo_unidade = _u32(dados, posicao + 4)
    serial = _u32(dados, posicao + 8)
    deslocamento_rotulo = _u32(dados, posicao + 12)
    rotulo = ""
    if 0 < deslocamento_rotulo < tamanho:
        if deslocamento_rotulo == 0x14 and posicao + 20 <= len(dados):
            deslocamento_unicode = _u32(dados, posicao + 16)
            if 0 < deslocamento_unicode < tamanho:
                rotulo = _unicode(dados, posicao + deslocamento_unicode)
        else:
            rotulo = _ansi(dados, posicao + deslocamento_rotulo)

    return {
        "tamanho": tamanho,
        "tipo_unidade": _DRIVE_TYPES.get(tipo_unidade, f"Tipo {tipo_unidade}"),
        "serial": f"{serial:08X}" if serial else "",
        "serial_decimal": serial,
        "rotulo": rotulo,
    }


def _common_network(
    dados: bytes, base_link_info: int, deslocamento: int
) -> Dict[str, Any]:
    """Lê o bloco CommonNetworkRelativeLink do LinkInfo."""
    if not deslocamento:
        return {}
    posicao = base_link_info + deslocamento
    if posicao + 20 > len(dados):
        return {}
    tamanho = _u32(dados, posicao)
    flags = _u32(dados, posicao + 4)
    deslocamento_rede = _u32(dados, posicao + 8)
    deslocamento_dispositivo = _u32(dados, posicao + 12)
    provedor = _u32(dados, posicao + 16)
    if tamanho < 20 or posicao + tamanho > len(dados):
        return {}
    return {
        "tamanho": tamanho,
        "flags": flags,
        "nome_rede": _ansi(dados, posicao + deslocamento_rede)
        if deslocamento_rede
        else "",
        "nome_dispositivo": _ansi(dados, posicao + deslocamento_dispositivo)
        if deslocamento_dispositivo
        else "",
        "provedor": provedor,
    }


def _link_info(dados: bytes, posicao: int) -> Tuple[Dict[str, Any], int]:
    """Lê o bloco LinkInfo e devolve o dicionário e a posição final."""
    tamanho = _u32(dados, posicao)
    if tamanho < 0x1C or posicao + tamanho > len(dados):
        raise ValueError("Bloco LinkInfo inválido ou truncado.")
    cabecalho = _u32(dados, posicao + 4)
    flags = _u32(dados, posicao + 8)
    deslocamento_volume = _u32(dados, posicao + 12)
    deslocamento_local = _u32(dados, posicao + 16)
    deslocamento_rede = _u32(dados, posicao + 20)
    deslocamento_sufixo = _u32(dados, posicao + 24)
    deslocamento_local_unicode = 0
    deslocamento_sufixo_unicode = 0
    if cabecalho >= 0x24 and posicao + 36 <= len(dados):
        deslocamento_local_unicode = _u32(dados, posicao + 28)
        deslocamento_sufixo_unicode = _u32(dados, posicao + 32)

    volume = _volume_id(dados, posicao, deslocamento_volume)
    rede = _common_network(dados, posicao, deslocamento_rede)

    base_local = ""
    if deslocamento_local:
        base_local = (
            _unicode(dados, posicao + deslocamento_local_unicode)
            if deslocamento_local_unicode
            else _ansi(dados, posicao + deslocamento_local)
        )
    sufixo = ""
    if deslocamento_sufixo:
        sufixo = (
            _unicode(dados, posicao + deslocamento_sufixo_unicode)
            if deslocamento_sufixo_unicode
            else _ansi(dados, posicao + deslocamento_sufixo)
        )

    caminho_rede = str(rede.get("nome_rede") or "")
    caminho = caminho_rede + sufixo if caminho_rede else base_local + sufixo
    return (
        {
            "tamanho": tamanho,
            "tamanho_cabecalho": cabecalho,
            "flags": _flags_ativas(flags, _LINK_INFO_FLAGS),
            "volume": volume,
            "caminho_local": base_local,
            "caminho_rede": caminho_rede,
            "sufixo_comum": sufixo,
            "caminho_completo": caminho,
            "rede": rede,
        },
        posicao + tamanho,
    )


def _extrair_strings(
    dados: bytes,
    posicao: int,
    flags: int,
    is_unicode: bool,
) -> Tuple[Dict[str, str], int]:
    """Lê os blocos StringData conforme as flags do cabeçalho."""
    resultado = {
        "nome": "",
        "caminho_relativo": "",
        "diretorio_trabalho": "",
        "argumentos": "",
        "icone": "",
    }
    for bit, chave in (
        (0x00000004, "nome"),
        (0x00000008, "caminho_relativo"),
        (0x00000010, "diretorio_trabalho"),
        (0x00000020, "argumentos"),
        (0x00000040, "icone"),
    ):
        if not flags & bit:
            continue
        if posicao + 2 > len(dados):
            break
        caracteres = _u16(dados, posicao)
        posicao += 2
        if caracteres > 8192:
            break
        tamanho = caracteres * 2 if is_unicode else caracteres
        if posicao + tamanho > len(dados):
            break
        bruto = dados[posicao : posicao + tamanho]
        resultado[chave] = (
            bruto.decode("utf-16le", errors="replace")
            if is_unicode
            else bruto.decode("cp1252", errors="replace")
        )
        posicao += tamanho
    return resultado, posicao


def _extra_environment(dados: bytes) -> Dict[str, Any]:
    """Lê o bloco EnvironmentVariableDataBlock."""
    return {
        "tipo": "EnvironmentVariableDataBlock",
        "alvo_ansi": _texto_em(dados, 0, 260, False),
        "alvo_unicode": _texto_em(dados, 260, 520, True),
    }


def _extra_darwin(dados: bytes) -> Dict[str, Any]:
    """Lê o bloco DarwinDataBlock."""
    return {
        "tipo": "DarwinDataBlock",
        "alvo_ansi": _texto_em(dados, 0, 260, False),
        "alvo_unicode": _texto_em(dados, 260, 520, True),
    }


def _extra_tracker(dados: bytes) -> Dict[str, Any]:
    """Lê o bloco TrackerDataBlock, que contém o nome do computador de origem."""
    if len(dados) < 88:
        return {"tipo": "TrackerDataBlock", "aviso": "Bloco menor que o esperado."}
    maquina = dados[8:24].split(b"\x00")[0].decode("ascii", errors="replace")
    try:
        volume_rastreio = str(uuid.UUID(bytes_le=dados[24:40]))
        arquivo_rastreio = str(uuid.UUID(bytes_le=dados[40:56]))
        volume_nascimento = str(uuid.UUID(bytes_le=dados[56:72]))
        arquivo_nascimento = str(uuid.UUID(bytes_le=dados[72:88]))
    except ValueError:
        volume_rastreio = arquivo_rastreio = volume_nascimento = arquivo_nascimento = ""
    return {
        "tipo": "TrackerDataBlock",
        "comprimento": _u32(dados, 0) if len(dados) >= 4 else 0,
        "versao": _u32(dados, 4) if len(dados) >= 8 else 0,
        "maquina": maquina,
        "volume_rastreio": volume_rastreio,
        "arquivo_rastreio": arquivo_rastreio,
        "volume_nascimento": volume_nascimento,
        "arquivo_nascimento": arquivo_nascimento,
    }


def _extra_data(dados: bytes, posicao: int) -> Tuple[List[Dict[str, Any]], int]:
    """Percorre os blocos ExtraData e interpreta os tipos conhecidos."""
    blocos: List[Dict[str, Any]] = []
    while posicao + 8 <= len(dados):
        tamanho = _u32(dados, posicao)
        assinatura = _u32(dados, posicao + 4)
        if tamanho < 8 or posicao + tamanho > len(dados):
            break
        conteudo = dados[posicao + 8 : posicao + tamanho]

        if assinatura == 0xA0000001:
            bloco = _extra_environment(conteudo)
        elif assinatura == 0xA0000003:
            bloco = _extra_tracker(conteudo)
        elif assinatura == 0xA0000005:
            bloco = {
                "tipo": "SpecialFolderDataBlock",
                "id_pasta": _u32(conteudo, 0) if len(conteudo) >= 4 else 0,
                "deslocamento": _u32(conteudo, 4) if len(conteudo) >= 8 else 0,
            }
        elif assinatura == 0xA0000006:
            bloco = _extra_darwin(conteudo)
        elif assinatura == 0xA0000007:
            bloco = {
                "tipo": "IconEnvironmentDataBlock",
                "alvo_ansi": _texto_em(conteudo, 0, 260, False),
                "alvo_unicode": _texto_em(conteudo, 260, 520, True),
            }
        elif assinatura == 0xA0000008:
            bloco = {"tipo": "ShimDataBlock", "nome": _ansi(conteudo, 0)}
        elif assinatura == 0xA000000B:
            bloco = {
                "tipo": "KnownFolderDataBlock",
                "guid": str(uuid.UUID(bytes_le=conteudo[:16]))
                if len(conteudo) >= 16
                else "",
                "deslocamento": _u32(conteudo, 16) if len(conteudo) >= 20 else 0,
            }
        elif assinatura == 0xA0000009:
            bloco = {
                "tipo": "PropertyStoreDataBlock",
                "tamanho_conteudo": len(conteudo),
            }
        elif assinatura == 0xA000000C:
            bloco = {
                "tipo": "VistaAndAboveIDListDataBlock",
                "tamanho_conteudo": len(conteudo),
            }
        else:
            bloco = {
                "tipo": f"Bloco desconhecido 0x{assinatura:08X}",
                "tamanho_conteudo": len(conteudo),
                "previa": conteudo[:48].hex(" "),
            }
        bloco["assinatura"] = f"0x{assinatura:08X}"
        bloco["tamanho"] = tamanho
        blocos.append(bloco)
        posicao += tamanho
    return blocos, posicao


def _detectar_macs(resultado: Dict[str, Any], dados: bytes) -> List[str]:
    """Procura endereços MAC em campos textuais e no bloco Tracker."""
    textos: List[str] = [
        str(resultado.get("destino", {}).get("caminho", "")),
        str(resultado.get("destino", {}).get("caminho_relativo", "")),
        str(resultado.get("argumentos", "")),
        str(resultado.get("diretorio_trabalho", "")),
        str(resultado.get("hostname", "")),
    ]
    for bloco in resultado.get("blocos", []):
        textos.extend(str(valor) for valor in bloco.values())
    textos.extend(_strings_ascii(dados))
    encontrados: List[str] = []
    for texto in textos:
        for achado in _PADRAO_MAC.findall(texto):
            normalizado = achado.upper().replace(":", "-")
            if normalizado not in encontrados:
                encontrados.append(normalizado)
    return encontrados


def _acelerador_lnkparse3(caminho: Path) -> Tuple[Dict[str, Any], str]:
    """Tenta usar LnkParse3 como acelerador opcional."""
    if not dependencia_disponivel("LnkParse3"):
        return {}, "LnkParse3 não instalado; parser nativo utilizado."
    try:
        import LnkParse3  # importação tardia

        with open(caminho, "rb") as arquivo:
            analisador = LnkParse3.lnk_file(arquivo)
            dados = analisador.get_json()
        if isinstance(dados, dict):
            return dados, "LnkParse3 utilizado como acelerador."
        return {}, "LnkParse3 não devolveu um dicionário."
    except Exception as exc:
        return {}, f"LnkParse3 falhou ({exc}); parser nativo utilizado."


def analisar_lnk(
    caminho: Path | str,
    incluir_blocos: bool = True,
    usar_acelerador: bool = True,
) -> Dict[str, Any]:
    """Analisa um arquivo ``.lnk`` e devolve um dicionário serializável em JSON.

    A função é somente leitura. Campos ausentes permanecem vazios ou nulos; nada
    é inferido sem evidência no arquivo.
    """
    caminho = Path(caminho).expanduser()
    if not caminho.exists():
        raise FileNotFoundError(f"Atalho não encontrado: {caminho}")
    if not caminho.is_file():
        raise ValueError("O caminho deve apontar para um arquivo .lnk.")
    if caminho.suffix.lower() != ".lnk":
        raise ValueError("Selecione um arquivo com extensão .lnk.")

    dados = caminho.read_bytes()
    if len(dados) < 76:
        raise ValueError("Arquivo menor que o cabeçalho mínimo de 76 bytes do MS-SHLLINK.")
    if _u32(dados, 0) != 0x4C:
        raise ValueError(
            "Cabeçalho MS-SHLLINK inválido: esperado HeaderSize 0x4C. "
            "O arquivo pode estar corrompido ou não ser um atalho."
        )

    flags = _u32(dados, 0x14)
    is_unicode = bool(flags & 0x00000080)
    resultado: Dict[str, Any] = {
        "arquivo": str(caminho),
        "tamanho": len(dados),
        "cabecalho": {
            "tamanho": _u32(dados, 0),
            "clsid": dados[4:20].hex(),
            "flags": f"0x{flags:08X}",
            "flags_ativas": _flags_ativas(flags, _LINK_FLAGS),
            "atributos_arquivo": f"0x{_u32(dados, 0x18):08X}",
            "criacao": _filetime_para_iso(struct.unpack_from("<Q", dados, 0x1C)[0]),
            "acesso": _filetime_para_iso(struct.unpack_from("<Q", dados, 0x24)[0]),
            "modificacao": _filetime_para_iso(struct.unpack_from("<Q", dados, 0x2C)[0]),
            "tamanho_alvo": _u32(dados, 0x34),
            "indice_icone": _i32(dados, 0x38),
            "comando_exibicao": _u32(dados, 0x3C),
            "hotkey": f"0x{_u16(dados, 0x40):04X}",
            "reservado": _u16(dados, 0x42),
        },
        "destino": {
            "caminho": "",
            "caminho_local_base": "",
            "caminho_relativo": "",
            "diretorio_trabalho": "",
            "nome": "",
            "volume": {},
            "serial_volume": "",
            "rotulo_volume": "",
            "tipo_unidade": "",
            "nome_rede": "",
        },
        "argumentos": "",
        "icone": "",
        "hostname": "",
        "macs": [],
        "blocos": [],
        "idlist": {"tamanho": 0, "previa": ""},
        "acelerador": "",
        "avisos": [],
    }

    posicao = 0x4C
    try:
        if flags & 0x00000001:
            if posicao + 2 > len(dados):
                raise ValueError("LinkTargetIDList truncada.")
            tamanho_idlist = _u16(dados, posicao)
            posicao += 2
            bloco_idlist = dados[posicao : posicao + tamanho_idlist]
            resultado["idlist"] = {
                "tamanho": tamanho_idlist,
                "previa": bloco_idlist[:64].hex(" "),
            }
            posicao += tamanho_idlist

        if flags & 0x00000002:
            info, posicao = _link_info(dados, posicao)
            destino = resultado["destino"]
            destino["caminho"] = info.get("caminho_completo", "")
            destino["caminho_local_base"] = info.get("caminho_local", "")
            destino["nome_rede"] = info.get("caminho_rede", "")
            volume = info.get("volume", {}) or {}
            destino["volume"] = volume
            destino["serial_volume"] = volume.get("serial", "")
            destino["rotulo_volume"] = volume.get("rotulo", "")
            destino["tipo_unidade"] = volume.get("tipo_unidade", "")
            resultado["link_info"] = info
        else:
            resultado["link_info"] = {}

        strings, posicao = _extrair_strings(dados, posicao, flags, is_unicode)
        if strings.get("caminho_relativo"):
            resultado["destino"]["caminho_relativo"] = strings["caminho_relativo"]
        resultado["destino"]["nome"] = strings.get("nome", "")
        resultado["destino"]["diretorio_trabalho"] = strings.get("diretorio_trabalho", "")
        resultado["argumentos"] = strings.get("argumentos", "")
        resultado["icone"] = strings.get("icone", "")

        if incluir_blocos:
            blocos, posicao = _extra_data(dados, posicao)
            resultado["blocos"] = blocos
            for bloco in blocos:
                if bloco.get("tipo") == "TrackerDataBlock":
                    resultado["hostname"] = bloco.get("maquina", "")
                    break
        else:
            resultado["blocos"] = []

        resultado["macs"] = _detectar_macs(resultado, dados)
    except (ValueError, struct.error) as exc:
        resultado["avisos"].append(f"Parser nativo interrompido: {exc}")

    if usar_acelerador:
        dados_acelerador, mensagem = _acelerador_lnkparse3(caminho)
        resultado["acelerador"] = mensagem
        if dados_acelerador:
            # Preenche somente campos ainda vazios; o parser nativo tem prioridade.
            if not resultado["destino"].get("caminho"):
                alvo = dados_acelerador.get("link_info", {}).get("local_base_path", "")
                if alvo:
                    resultado["destino"]["caminho"] = str(alvo)
            if not resultado["hostname"]:
                maquina = dados_acelerador.get("extra", {}).get("machine_id", "")
                if maquina:
                    resultado["hostname"] = str(maquina)
    else:
        resultado["acelerador"] = "Acelerador desativado nas opções."

    if not resultado["destino"].get("caminho") and not resultado["destino"].get("nome_rede"):
        resultado["avisos"].append(
            "O atalho não contém LinkInfo nem caminho de rede legível. "
            "Nenhum destino foi inventado."
        )
    return resultado


def resumir_lnk(resultado: Dict[str, Any]) -> str:
    """Resumo textual de um atalho analisado."""
    destino = resultado.get("destino", {})
    linhas = [
        f"Arquivo: {resultado.get('arquivo', '')}",
        f"Tamanho: {formatar_bytes(int(resultado.get('tamanho', 0)))}",
        f"Destino: {destino.get('caminho') or destino.get('nome_rede') or 'não informado'}",
        f"Argumentos: {resultado.get('argumentos') or 'nenhum'}",
        f"Diretório de trabalho: {destino.get('diretorio_trabalho') or 'não informado'}",
        f"Serial do volume: {destino.get('serial_volume') or 'não informado'}",
        f"Tipo de unidade: {destino.get('tipo_unidade') or 'não informado'}",
        f"Computador de origem: {resultado.get('hostname') or 'não informado'}",
        f"MACs encontrados: {', '.join(resultado.get('macs', [])) or 'nenhum'}",
        f"Criação: {resultado.get('cabecalho', {}).get('criacao') or 'não informada'}",
        f"Modificação: {resultado.get('cabecalho', {}).get('modificacao') or 'não informada'}",
    ]
    return "\n".join(linhas)


@register
class LnkAnalyzerTool(FileTool):
    """FileTool de análise de atalhos LNK com saída JSON por arquivo."""

    id = "forensics.lnk_analyzer"
    name = "Analisador de Atalhos LNK"
    category = "Forense"
    description = (
        "Analisa atalhos MS-SHLLINK com parser nativo para extrair destino, "
        "argumentos, diretório de trabalho, timestamps, serial de volume, "
        "computador de origem e blocos ExtraData"
    )
    keywords = [
        "lnk",
        "atalho",
        "shortcut",
        "ms-shllink",
        "forense",
        "destino",
        "serial",
        "volume",
        "prefetch",
        "recentdocs",
    ]

    accepts = [".lnk"]
    batch_kind = "per_file"
    parallel_mode = "thread"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        """Formulário de opções da FileTool."""
        painel = PainelOpcoes(parent)
        aviso = criar_aviso(
            "O parser nativo MS-SHLLINK funciona sem dependências opcionais. "
            "LnkParse3 é usado apenas como acelerador quando instalado. "
            "Cada atalho gera um relatório JSON separado.",
            painel,
        )
        painel.adicionar(aviso)

        self.chk_blocos = QCheckBox(
            "Incluir blocos ExtraData (Tracker, Environment, Shim)", painel
        )
        self.chk_blocos.setChecked(True)
        painel.adicionar(self.chk_blocos)

        self.chk_acelerador = QCheckBox(
            "Tentar LnkParse3 como acelerador opcional", painel
        )
        self.chk_acelerador.setChecked(True)
        painel.adicionar(self.chk_acelerador)

        rotulo = QLabel(
            "Arraste arquivos .lnk ou uma pasta acima e clique em 'Executar em Lote'. "
            "A análise é somente leitura e não altera os atalhos.",
            painel,
        )
        rotulo.setWordWrap(True)
        rotulo.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        painel.adicionar(rotulo)
        return painel

    def get_options(self) -> Dict[str, Any]:
        """Lê as opções atuais do formulário."""
        blocos = getattr(self, "chk_blocos", None)
        acelerador = getattr(self, "chk_acelerador", None)
        return {
            "incluir_blocos": blocos.isChecked() if blocos else True,
            "usar_acelerador": acelerador.isChecked() if acelerador else True,
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        """Cada atalho produz um relatório JSON."""
        return ".json"

    def process(
        self,
        src: Path,
        dst: Path,
        params: Dict[str, Any],
        ctx: TaskContext,
    ) -> ItemResult:
        """Analisa um atalho e grava o relatório JSON no destino do lote."""
        try:
            if ctx is not None:
                ctx.log("INFO", f"Analisando atalho: {src.name}")
            resultado = analisar_lnk(
                src,
                incluir_blocos=bool(params.get("incluir_blocos", True)),
                usar_acelerador=bool(params.get("usar_acelerador", True)),
            )
            texto = json.dumps(resultado, ensure_ascii=False, indent=2)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(texto, encoding="utf-8")
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=f"Atalho analisado: {resumir_lnk(resultado)}",
                bytes_in=src.stat().st_size,
                bytes_out=len(texto.encode("utf-8")),
            )
        except Exception as exc:
            _log.exception("Falha ao analisar LNK %s", src)
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc),
            )

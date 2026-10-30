"""Núcleo puro da esteganografia LSB do WinToolbox (sem Qt e sem dependências pesadas no topo).

Formato de carga próprio (assinatura ``WTBXSTEG``)::

    bytes 0-7    assinatura b"WTBXSTEG"
    byte  8      versão do formato (1)
    byte  9      flags: bit 0 = protegido por senha, bit 1 = carga textual
    byte  10     profundidade em bits por amostra/canal (1 a 4)
    bytes 11-42  SHA-256 da carga em claro (calculado antes do XOR)
    bytes 43-50  tamanho da carga em bytes (inteiro de 8 bytes, big-endian)

O cabeçalho é sempre gravado com 1 bit por amostra e ocupa as primeiras
``BITS_CABECALHO`` posições do fluxo de bits. A carga começa imediatamente
depois e usa a profundidade escolhida pelo usuário.

Para imagens o fluxo percorre os canais R, G e B na ordem de varredura dos
pixels (linha a linha) e usa sempre os bits menos significativos de cada
canal. Para WAV o fluxo percorre as amostras PCM na ordem do arquivo e usa os
bits menos significativos do byte menos significativo de cada amostra, o que
funciona para amostras de 8, 16, 24 ou 32 bits.

A senha não é criptografia forte: aplica um XOR com o resumo SHA-256 da senha
repetido ao longo da carga. Serve para impedir a leitura casual do conteúdo,
conforme a especificação da ferramenta.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ASSINATURA = b"WTBXSTEG"
VERSAO = 1
TAM_CABECALHO = len(ASSINATURA) + 1 + 1 + 1 + 32 + 8
BITS_CABECALHO = TAM_CABECALHO * 8
PROFUNDIDADE_MAXIMA = 4
FLAG_SENHA = 0x01
FLAG_TEXTO = 0x02

EXTENSOES_IMAGEM = (".png", ".bmp")
EXTENSOES_WAV = (".wav",)
EXTENSOES_SUPORTADAS = EXTENSOES_IMAGEM + EXTENSOES_WAV


class ErroEstegano(ValueError):
    """Falha de leitura, capacidade ou integridade da carga esteganográfica."""


# ---------------------------------------------------------------------------
# Utilidades de bytes
# ---------------------------------------------------------------------------
def fluxo_de_chave(senha: str, comprimento: int) -> bytes:
    """Gera o fluxo de XOR repetindo o resumo SHA-256 da senha."""
    if comprimento <= 0:
        return b""
    digest = hashlib.sha256(senha.encode("utf-8")).digest()
    repeticoes = comprimento // len(digest) + 1
    return (digest * repeticoes)[:comprimento]


def aplicar_xor(dados: bytes, senha: str) -> bytes:
    """Aplica (ou remove) o XOR de senha sobre ``dados``."""
    if not senha:
        return dados
    chave = fluxo_de_chave(senha, len(dados))
    return bytes(a ^ b for a, b in zip(dados, chave))


def calcular_sha256(dados: bytes) -> bytes:
    """Resumo SHA-256 em bytes."""
    return hashlib.sha256(dados).digest()


def montar_cabecalho(tamanho: int, resumo: bytes, profundidade: int, flags: int) -> bytes:
    """Monta o cabeçalho binário de 51 bytes."""
    if len(resumo) != 32:
        raise ErroEstegano("Resumo SHA-256 inválido ao montar o cabeçalho.")
    if not 1 <= profundidade <= PROFUNDIDADE_MAXIMA:
        raise ErroEstegano(
            f"Profundidade inválida: {profundidade}. Use de 1 a {PROFUNDIDADE_MAXIMA} bits por canal."
        )
    return (
        ASSINATURA
        + bytes((VERSAO, flags & 0xFF, profundidade))
        + resumo
        + int(tamanho).to_bytes(8, "big")
    )


def interpretar_cabecalho(dados: bytes) -> Dict[str, Any]:
    """Valida e decodifica o cabeçalho, devolvendo seus campos."""
    if len(dados) < TAM_CABECALHO:
        raise ErroEstegano("Arquivo pequeno demais para conter um cabeçalho WTBXSTEG.")
    if dados[: len(ASSINATURA)] != ASSINATURA:
        raise ErroEstegano(
            "Assinatura WTBXSTEG não encontrada. O arquivo não contém uma carga "
            "criada por esta ferramenta (ou os bits menos significativos foram alterados)."
        )
    versao = dados[len(ASSINATURA)]
    if versao != VERSAO:
        raise ErroEstegano(
            f"Versão de formato não suportada: {versao}. Esta ferramenta lê a versão {VERSAO}."
        )
    flags = dados[len(ASSINATURA) + 1]
    profundidade = dados[len(ASSINATURA) + 2]
    if not 1 <= profundidade <= PROFUNDIDADE_MAXIMA:
        raise ErroEstegano(
            f"Cabeçalho inconsistente: profundidade {profundidade} fora da faixa 1-{PROFUNDIDADE_MAXIMA}."
        )
    inicio_resumo = len(ASSINATURA) + 3
    resumo = dados[inicio_resumo : inicio_resumo + 32]
    tamanho = int.from_bytes(dados[inicio_resumo + 32 : inicio_resumo + 40], "big")
    return {
        "versao": versao,
        "flags": flags,
        "profundidade": profundidade,
        "resumo": resumo,
        "tamanho": tamanho,
        "protegido": bool(flags & FLAG_SENHA),
        "texto": bool(flags & FLAG_TEXTO),
    }


# ---------------------------------------------------------------------------
# Fluxo de bits sobre "slots" (bytes cujos bits menos significativos são usados)
# ---------------------------------------------------------------------------
def capacidade_bytes(total_slots: int, profundidade: int) -> int:
    """Quantidade de bytes de carga que cabem no contêiner informado."""
    if profundidade < 1:
        return 0
    disponiveis = int(total_slots) - BITS_CABECALHO
    if disponiveis <= 0:
        return 0
    return (disponiveis * profundidade) // 8


def _quantidade_slots(bits: int, profundidade: int) -> int:
    """Número de slots necessários para acomodar ``bits`` bits na profundidade dada."""
    return int(math.ceil(bits / float(profundidade))) if bits > 0 else 0


def _gravar_bits(base: Any, inicio_slot: int, bits: Any, profundidade: int, passo: int) -> None:
    """Grava ``bits`` nos bits baixos dos slots de ``base`` a partir do slot ``inicio_slot``."""
    import numpy as np

    inicio = int(inicio_slot) * passo
    total_slots = _quantidade_slots(int(bits.size), profundidade)
    if total_slots <= 0:
        return
    ultimo = inicio + (total_slots - 1) * passo
    if ultimo >= base.size:
        raise ErroEstegano("Capacidade insuficiente no contêiner para gravar a carga.")
    fim = inicio + total_slots * passo
    preenchido = np.zeros(total_slots * profundidade, dtype=np.uint8)
    preenchido[: bits.size] = bits
    blocos = preenchido.reshape(total_slots, profundidade).astype(np.uint16)
    pesos = (np.uint16(1) << np.arange(profundidade, dtype=np.uint16))
    valores = (blocos * pesos).sum(axis=1).astype(np.uint8)
    mascara = np.uint8(0xFF ^ ((1 << profundidade) - 1))
    atuais = base[inicio:fim:passo]
    if atuais.size != total_slots:
        raise ErroEstegano("Fluxo de bits inconsistente: slots insuficientes no contêiner.")
    base[inicio:fim:passo] = (atuais & mascara) | valores


def _ler_bits(base: Any, inicio_slot: int, quantidade: int, profundidade: int, passo: int) -> Any:
    """Lê ``quantidade`` bits dos slots de ``base`` a partir do slot ``inicio_slot``."""
    import numpy as np

    inicio = int(inicio_slot) * passo
    total_slots = _quantidade_slots(quantidade, profundidade)
    if total_slots <= 0:
        return np.zeros(0, dtype=np.uint8)
    ultimo = inicio + (total_slots - 1) * passo
    if ultimo >= base.size:
        raise ErroEstegano(
            "Arquivo menor do que o esperado: não há slots suficientes para ler a carga."
        )
    fim = inicio + total_slots * passo
    slots = base[inicio:fim:passo]
    if slots.size < total_slots:
        raise ErroEstegano(
            "Arquivo menor do que o esperado: não há slots suficientes para ler a carga."
        )
    valores = slots.astype(np.uint8)
    colunas = [((valores >> deslocamento) & 1).astype(np.uint8) for deslocamento in range(profundidade)]
    fluxo = np.stack(colunas, axis=1).reshape(-1)
    return fluxo[:quantidade]


def _bytes_para_bits(dados: bytes) -> Any:
    import numpy as np

    return np.unpackbits(np.frombuffer(dados, dtype=np.uint8))


def _bits_para_bytes(bits: Any) -> bytes:
    import numpy as np

    if bits.size % 8 != 0:
        faltam = 8 - (bits.size % 8)
        bits = np.concatenate([bits, np.zeros(faltam, dtype=np.uint8)])
    return np.packbits(bits.astype(np.uint8)).tobytes()


# ---------------------------------------------------------------------------
# Contêineres: imagem PNG/BMP e áudio WAV
# ---------------------------------------------------------------------------
def _tipo_contêiner(caminho: Path) -> str:
    suffix = Path(caminho).suffix.lower()
    if suffix in EXTENSOES_IMAGEM:
        return "imagem"
    if suffix in EXTENSOES_WAV:
        return "wav"
    raise ErroEstegano(
        f"Extensão não suportada: {suffix or '(sem extensão)'}. "
        "Use PNG, BMP ou WAV sem compressão."
    )


def _abrir_imagem(caminho: Path) -> Tuple[Any, str]:
    """Abre PNG/BMP e devolve matriz RGB uint8 e o formato de origem."""
    from PIL import Image
    import numpy as np

    with Image.open(caminho) as imagem:
        formato = (imagem.format or "").upper()
        if formato not in ("PNG", "BMP"):
            raise ErroEstegano(
                f"Formato de imagem não suportado: {formato or 'desconhecido'}. "
                "A esteganografia LSB desta ferramenta trabalha com PNG e BMP (sem perdas)."
            )
        matriz = np.array(imagem.convert("RGB"), dtype=np.uint8)
    if matriz.ndim != 3 or matriz.shape[2] != 3:
        raise ErroEstegano("Imagem inesperada: não foi possível converter para RGB.")
    return matriz, formato


def _salvar_imagem(matriz: Any, destino: Path, formato: str) -> None:
    from PIL import Image

    Image.fromarray(matriz, mode="RGB").save(destino, format=formato)


def _abrir_wav(caminho: Path) -> Tuple[bytes, int, int, int, int]:
    """Abre WAV PCM sem compressão e devolve (dados, canais, largura, taxa, quadros)."""
    import wave

    try:
        with wave.open(str(caminho), "rb") as wav:
            if wav.getcomptype() != "NONE":
                raise ErroEstegano(
                    "Este WAV usa compressão. Converta para PCM sem compressão antes de usar a ferramenta."
                )
            canais = wav.getnchannels()
            largura = wav.getsampwidth()
            taxa = wav.getframerate()
            quadros = wav.getnframes()
            dados = wav.readframes(quadros)
    except wave.Error as exc:
        raise ErroEstegano(f"Arquivo WAV inválido ou corrompido: {exc}") from exc
    if largura < 1:
        raise ErroEstegano("WAV com largura de amostra inválida.")
    return dados, canais, largura, taxa, quadros


def _salvar_wav(destino: Path, dados: bytes, canais: int, largura: int, taxa: int) -> None:
    import wave

    with wave.open(str(destino), "wb") as wav:
        wav.setnchannels(canais)
        wav.setsampwidth(largura)
        wav.setframerate(taxa)
        wav.writeframes(dados)


def _abrir_contêiner(caminho: Path) -> Dict[str, Any]:
    """Carrega o contêiner e devolve os dados necessários para leitura/escrita."""
    tipo = _tipo_contêiner(caminho)
    if tipo == "imagem":
        matriz, formato = _abrir_imagem(caminho)
        return {
            "tipo": tipo,
            "formato": formato,
            "matriz": matriz,
            "base": matriz.reshape(-1),
            "passo": 1,
            "total_slots": int(matriz.size),
        }
    dados, canais, largura, taxa, quadros = _abrir_wav(caminho)
    if not dados:
        raise ErroEstegano("O WAV não possui amostras de áudio.")
    import numpy as np

    base = np.frombuffer(dados, dtype=np.uint8).copy()
    total_slots = base.size // largura
    return {
        "tipo": tipo,
        "formato": "WAV",
        "base": base,
        "passo": largura,
        "total_slots": int(total_slots),
        "canais": canais,
        "largura": largura,
        "taxa": taxa,
        "quadros": quadros,
    }


def _gravar_contêiner(contêiner: Dict[str, Any], destino: Path) -> None:
    if contêiner["tipo"] == "imagem":
        _salvar_imagem(contêiner["matriz"], destino, contêiner["formato"])
        return
    _salvar_wav(
        destino,
        contêiner["base"].tobytes(),
        contêiner["canais"],
        contêiner["largura"],
        contêiner["taxa"],
    )


# ---------------------------------------------------------------------------
# API principal (pura, sem Qt)
# ---------------------------------------------------------------------------
def capacidade_do_arquivo(caminho: Path, profundidade: int = 1) -> Dict[str, Any]:
    """Descreve a capacidade de carga de um contêiner."""
    profundidade = max(1, min(PROFUNDIDADE_MAXIMA, int(profundidade)))
    contêiner = _abrir_contêiner(Path(caminho))
    total = contêiner["total_slots"]
    bytes_livres = capacidade_bytes(total, profundidade)
    return {
        "tipo": contêiner["tipo"],
        "formato": contêiner["formato"],
        "total_slots": total,
        "profundidade": profundidade,
        "capacidade_bytes": bytes_livres,
        "cabecalho_bytes": TAM_CABECALHO,
        "descricao": (
            f"{total} amostras/canais disponíveis; "
            f"cabem até {bytes_livres} bytes de carga com {profundidade} bit(s) por canal."
        ),
    }


def embutir_em_arquivo(
    caminho_origem: Path,
    caminho_destino: Path,
    carga: bytes,
    senha: str = "",
    profundidade: int = 1,
    texto: bool = False,
) -> Dict[str, Any]:
    """Embute ``carga`` no contêiner e grava ``caminho_destino``.

    Devolve um resumo com capacidade, tamanho usado, profundidade e resumo SHA-256.
    """
    if not isinstance(carga, (bytes, bytearray)) or not carga:
        raise ErroEstegano("A carga a ser escondida está vazia. Informe um texto ou um arquivo.")
    profundidade = int(profundidade)
    if not 1 <= profundidade <= PROFUNDIDADE_MAXIMA:
        raise ErroEstegano(
            f"Profundidade inválida: {profundidade}. Use de 1 a {PROFUNDIDADE_MAXIMA} bits por canal."
        )
    caminho_origem = Path(caminho_origem)
    caminho_destino = Path(caminho_destino)
    contêiner = _abrir_contêiner(caminho_origem)
    limite = capacidade_bytes(contêiner["total_slots"], profundidade)
    if len(carga) > limite:
        raise ErroEstegano(
            f"Carga grande demais para este contêiner: {len(carga)} bytes informados, "
            f"capacidade de {limite} bytes com {profundidade} bit(s) por canal. "
            "Reduza a carga, diminua a profundidade ou use um arquivo maior."
        )

    resumo = calcular_sha256(carga)
    flags = 0
    if senha:
        flags |= FLAG_SENHA
    if texto:
        flags |= FLAG_TEXTO
    cabecalho = montar_cabecalho(len(carga), resumo, profundidade, flags)
    protegida = aplicar_xor(bytes(carga), senha)

    base = contêiner["base"]
    passo = contêiner["passo"]
    _gravar_bits(base, 0, _bytes_para_bits(cabecalho), 1, passo)
    _gravar_bits(base, BITS_CABECALHO, _bytes_para_bits(protegida), profundidade, passo)
    _gravar_contêiner(contêiner, caminho_destino)

    return {
        "tipo": contêiner["tipo"],
        "formato": contêiner["formato"],
        "capacidade_bytes": limite,
        "tamanho_carga": len(carga),
        "profundidade": profundidade,
        "protegido": bool(senha),
        "texto": bool(texto),
        "sha256": resumo.hex(),
        "ocupacao": (len(carga) / limite * 100.0) if limite else 0.0,
    }


def extrair_de_arquivo(caminho: Path, senha: str = "") -> Dict[str, Any]:
    """Extrai a carga de um contêiner criado por esta ferramenta."""
    caminho = Path(caminho)
    contêiner = _abrir_contêiner(caminho)
    base = contêiner["base"]
    passo = contêiner["passo"]
    if contêiner["total_slots"] <= BITS_CABECALHO:
        raise ErroEstegano(
            "O arquivo é pequeno demais para conter o cabeçalho WTBXSTEG "
            f"(mínimo de {BITS_CABECALHO} amostras/canais)."
        )

    bits_cabecalho = _ler_bits(base, 0, BITS_CABECALHO, 1, passo)
    cabecalho = interpretar_cabecalho(_bits_para_bytes(bits_cabecalho)[:TAM_CABECALHO])
    profundidade = cabecalho["profundidade"]
    tamanho = cabecalho["tamanho"]
    limite = capacidade_bytes(contêiner["total_slots"], profundidade)
    if tamanho <= 0:
        raise ErroEstegano("Cabeçalho indica carga vazia; nada a extrair.")
    if tamanho > limite:
        raise ErroEstegano(
            "Cabeçalho inconsistente: a carga declarada "
            f"({tamanho} bytes) excede a capacidade do arquivo ({limite} bytes)."
        )
    if cabecalho["protegido"] and not senha:
        raise ErroEstegano(
            "A carga está protegida por senha. Informe a senha usada no momento de esconder."
        )

    bits_carga = _ler_bits(base, BITS_CABECALHO, tamanho * 8, profundidade, passo)
    protegida = _bits_para_bytes(bits_carga)[:tamanho]
    carga = aplicar_xor(protegida, senha if cabecalho["protegido"] else "")
    resumo = calcular_sha256(carga)
    if resumo != cabecalho["resumo"]:
        raise ErroEstegano(
            "Falha de integridade: o SHA-256 da carga não confere. "
            "Senha incorreta ou conteúdo alterado desde a criação."
        )

    texto: Optional[str] = None
    if cabecalho["texto"]:
        try:
            texto = carga.decode("utf-8")
        except UnicodeDecodeError:
            texto = carga.decode("utf-8", errors="replace")

    return {
        "tipo": contêiner["tipo"],
        "formato": contêiner["formato"],
        "carga": carga,
        "texto": texto,
        "tamanho": tamanho,
        "profundidade": profundidade,
        "protegido": cabecalho["protegido"],
        "declarada_texto": cabecalho["texto"],
        "sha256": resumo.hex(),
    }


def ler_cabecalho_de_arquivo(caminho: Path) -> Optional[Dict[str, Any]]:
    """Lê apenas o cabeçalho, sem extrair a carga. Devolve None quando não há assinatura."""
    try:
        contêiner = _abrir_contêiner(Path(caminho))
        base = contêiner["base"]
        passo = contêiner["passo"]
        if contêiner["total_slots"] <= BITS_CABECALHO:
            return None
        bits = _ler_bits(base, 0, BITS_CABECALHO, 1, passo)
        if _bits_para_bytes(bits)[: len(ASSINATURA)] != ASSINATURA:
            return None
        cabecalho = interpretar_cabecalho(_bits_para_bytes(bits)[:TAM_CABECALHO])
    except (ErroEstegano, OSError):
        return None

    limite = capacidade_bytes(contêiner["total_slots"], cabecalho["profundidade"])
    return {
        "tipo": contêiner["tipo"],
        "formato": contêiner["formato"],
        "tamanho": cabecalho["tamanho"],
        "profundidade": cabecalho["profundidade"],
        "protegido": cabecalho["protegido"],
        "texto": cabecalho["texto"],
        "sha256": cabecalho["resumo"].hex(),
        "capacidade_bytes": limite,
        "coerente": 0 < cabecalho["tamanho"] <= limite,
    }


def descrever_carga(carga: bytes, senha_usada: bool = False) -> str:
    """Resumo textual curto para mensagens de interface."""
    partes = [f"{len(carga)} bytes", f"SHA-256 {calcular_sha256(carga).hex()[:16]}..."]
    if senha_usada:
        partes.append("protegida por senha")
    return "; ".join(partes)


__all__ = [
    "ASSINATURA",
    "BITS_CABECALHO",
    "ErroEstegano",
    "EXTENSOES_SUPORTADAS",
    "FLAG_SENHA",
    "FLAG_TEXTO",
    "PROFUNDIDADE_MAXIMA",
    "TAM_CABECALHO",
    "aplicar_xor",
    "calcular_sha256",
    "capacidade_bytes",
    "capacidade_do_arquivo",
    "descrever_carga",
    "embutir_em_arquivo",
    "extrair_de_arquivo",
    "fluxo_de_chave",
    "interpretar_cabecalho",
    "ler_cabecalho_de_arquivo",
    "montar_cabecalho",
]

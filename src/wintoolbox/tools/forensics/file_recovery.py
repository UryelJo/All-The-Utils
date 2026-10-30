"""Recuperação forense de arquivos com acesso estritamente somente leitura.

A ferramenta trabalha em duas camadas:

1. Quando ``pytsk3`` está instalado, tenta recuperar entradas não alocadas de
   sistemas de arquivos suportados (NTFS, FAT, ext) abrindo a imagem ou o
   dispositivo apenas para leitura.
2. O carving nativo por assinaturas percorre a origem em blocos e extrai
   arquivos reconhecíveis (JPEG, PNG, PDF, ZIP, GIF, SQLite e PE) para uma pasta
   de destino escolhida pelo usuário.

A origem nunca é aberta para escrita. Unidades físicas são abertas com
``GENERIC_READ`` e a ferramenta recusa gravar o resultado no mesmo dispositivo
de origem quando essa verificação é possível.
"""
from __future__ import annotations

import ctypes
import os
import re
import struct
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
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
    DependenciaAusente,
    dependencia_disponivel,
    formatar_bytes,
    formatar_numero,
    garantir_admin,
)
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    botao_copiar,
    criar_aviso,
    criar_saida_texto,
    criar_tabela,
    executar_assincrono,
    mostrar_erro,
    preencher_tabela,
)

_log = get_logger("forensics.file_recovery")

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C
IOCTL_STORAGE_GET_DEVICE_NUMBER = 0x002D1080

_BLOCO_LEITURA = 4 * 1024 * 1024
# O registro EOCD de um ZIP pode estar até 65.557 bytes antes do fim por causa
# do comentário opcional; a cauda precisa cobrir esse intervalo entre blocos.
_CAUDA_ASSINATURA = 70 * 1024


class _GET_LENGTH_INFORMATION(ctypes.Structure):
    """Saída de IOCTL_DISK_GET_LENGTH_INFO."""

    _fields_ = [("Length", ctypes.c_longlong)]


class _STORAGE_DEVICE_NUMBER(ctypes.Structure):
    """Identificação do dispositivo físico de uma unidade."""

    _fields_ = [
        ("DeviceType", wintypes.DWORD),
        ("DeviceNumber", wintypes.DWORD),
        ("PartitionNumber", wintypes.DWORD),
    ]


def _carregar_kernel32() -> Optional[ctypes.WinDLL]:
    """Carrega e tipa as funções de leitura de dispositivos do Windows."""
    if os.name != "nt":
        return None
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    except OSError:
        return None

    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.SetFilePointerEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_longlong,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.SetFilePointerEx.restype = wintypes.BOOL
    kernel.GetFileSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
    kernel.GetFileSizeEx.restype = wintypes.BOOL
    kernel.DeviceIoControl.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    return kernel


_KERNEL32 = _carregar_kernel32()


def _eh_dispositivo(caminho: str) -> bool:
    """Reconhece caminhos de dispositivo do Windows (\\\\.\\...)."""
    return str(caminho).startswith("\\\\.\\")


@dataclass(frozen=True)
class Assinatura:
    """Assinatura de um formato recuperável por carving."""

    tipo: str
    extensao: str
    inicio: bytes
    tamanho_minimo: int = 16
    tamanho_maximo_padrao: int = 100 * 1024 * 1024
    marcador_fim: Optional[bytes] = None
    usa_eocd_zip: bool = False


ASSINATURAS: Tuple[Assinatura, ...] = (
    Assinatura("JPEG", "jpg", b"\xff\xd8\xff", 128, 80 * 1024 * 1024, b"\xff\xd9"),
    Assinatura(
        "PNG",
        "png",
        b"\x89PNG\r\n\x1a\n",
        80,
        80 * 1024 * 1024,
        b"IEND\xaeB`\x82",
    ),
    Assinatura("PDF", "pdf", b"%PDF-", 32, 200 * 1024 * 1024, b"%%EOF"),
    Assinatura("ZIP", "zip", b"PK\x03\x04", 64, 200 * 1024 * 1024, usa_eocd_zip=True),
    Assinatura("GIF", "gif", b"GIF87a", 32, 80 * 1024 * 1024, b";"),
    Assinatura("GIF", "gif", b"GIF89a", 32, 80 * 1024 * 1024, b";"),
    Assinatura("SQLite", "sqlite", b"SQLite format 3\x00", 256, 200 * 1024 * 1024),
    Assinatura("PE", "exe", b"MZ", 256, 200 * 1024 * 1024),
)


@dataclass
class ArquivoRecuperado:
    """Arquivo extraído durante a recuperação."""

    tipo: str
    offset: int
    tamanho: int
    caminho: str
    metodo: str


@dataclass
class ResultadoRecuperacao:
    """Resultado consolidado da recuperação."""

    origem: str
    destino: str
    tipo_fonte: str
    sistema_arquivos: str = ""
    arquivos: List[ArquivoRecuperado] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    bytes_escaneados: int = 0
    cancelado: bool = False


class FonteLeitura:
    """Abre arquivo ou dispositivo apenas para leitura e oferece acesso posicional."""

    def __init__(self, caminho: str | Path) -> None:
        self.caminho = str(caminho)
        self.dispositivo = _eh_dispositivo(self.caminho)
        self._arquivo = None
        self._handle: Optional[int] = None
        self.tamanho = 0
        self._abrir()

    def _abrir(self) -> None:
        if self.dispositivo:
            if _KERNEL32 is None:
                raise OSError("A leitura de dispositivos está disponível apenas no Windows.")
            handle = _KERNEL32.CreateFileW(
                self.caminho,
                GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                FILE_FLAG_SEQUENTIAL_SCAN,
                None,
            )
            if not handle or int(handle) == INVALID_HANDLE_VALUE:
                erro = ctypes.get_last_error()
                raise OSError(
                    erro,
                    "Não foi possível abrir o dispositivo somente para leitura. "
                    "Execute como Administrador e confira o caminho "
                    "(por exemplo, \\\\.\\PhysicalDrive0).",
                )
            self._handle = int(handle)
            self.tamanho = self._tamanho_dispositivo()
        else:
            caminho = Path(self.caminho).expanduser().resolve()
            if not caminho.exists():
                raise FileNotFoundError(f"Origem não encontrada: {caminho}")
            if not caminho.is_file():
                raise ValueError(f"A origem deve ser um arquivo ou dispositivo: {caminho}")
            self.caminho = str(caminho)
            self._arquivo = open(caminho, "rb")
            self.tamanho = caminho.stat().st_size

    def _tamanho_dispositivo(self) -> int:
        """Obtém o tamanho de um dispositivo, quando o driver informar."""
        if _KERNEL32 is None or self._handle is None:
            return 0
        tamanho = ctypes.c_longlong(0)
        if _KERNEL32.GetFileSizeEx(self._handle, ctypes.byref(tamanho)) and tamanho.value > 0:
            return int(tamanho.value)
        info = _GET_LENGTH_INFORMATION()
        retornados = wintypes.DWORD(0)
        ok = _KERNEL32.DeviceIoControl(
            self._handle,
            IOCTL_DISK_GET_LENGTH_INFO,
            None,
            0,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(retornados),
            None,
        )
        if ok and info.Length > 0:
            return int(info.Length)
        return 0

    def ler_em(self, offset: int, quantidade: int) -> bytes:
        """Lê até ``quantidade`` bytes a partir de ``offset`` sem alterar a origem."""
        if offset < 0 or quantidade <= 0:
            return b""
        if self.tamanho and offset >= self.tamanho:
            return b""
        quantidade = min(quantidade, _BLOCO_LEITURA) if self.dispositivo else quantidade

        if self.dispositivo:
            if _KERNEL32 is None or self._handle is None:
                return b""
            if not _KERNEL32.SetFilePointerEx(self._handle, offset, None, 0):
                return b""
            buffer = ctypes.create_string_buffer(quantidade)
            lidos = wintypes.DWORD(0)
            ok = _KERNEL32.ReadFile(
                self._handle,
                buffer,
                quantidade,
                ctypes.byref(lidos),
                None,
            )
            if not ok:
                return b""
            return buffer.raw[: lidos.value]

        if self._arquivo is None:
            return b""
        self._arquivo.seek(offset)
        return self._arquivo.read(quantidade)

    def fechar(self) -> None:
        """Libera o descritor ou handle da origem."""
        if self._arquivo is not None:
            try:
                self._arquivo.close()
            except OSError:
                pass
            self._arquivo = None
        if self._handle is not None and _KERNEL32 is not None:
            try:
                _KERNEL32.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None

    def __enter__(self) -> "FonteLeitura":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.fechar()


def _numero_dispositivo(caminho: str) -> Optional[int]:
    """Consulta o número do dispositivo físico de uma unidade, quando possível."""
    if _KERNEL32 is None or os.name != "nt":
        return None
    handle = _KERNEL32.CreateFileW(
        caminho,
        0,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if not handle or int(handle) == INVALID_HANDLE_VALUE:
        return None
    try:
        numero = _STORAGE_DEVICE_NUMBER()
        retornados = wintypes.DWORD(0)
        ok = _KERNEL32.DeviceIoControl(
            int(handle),
            IOCTL_STORAGE_GET_DEVICE_NUMBER,
            None,
            0,
            ctypes.byref(numero),
            ctypes.sizeof(numero),
            ctypes.byref(retornados),
            None,
        )
        if not ok:
            return None
        return int(numero.DeviceNumber)
    finally:
        _KERNEL32.CloseHandle(int(handle))


def _validar_destino(origem: str, destino: Path) -> List[str]:
    """Recusa gravar o resultado na mesma origem e devolve avisos de segurança."""
    avisos: List[str] = []
    origem_path = Path(origem).expanduser()
    try:
        if not _eh_dispositivo(origem) and destino.resolve() == origem_path.resolve():
            raise ValueError("O destino não pode ser o próprio arquivo de origem.")
    except OSError:
        pass

    if _eh_dispositivo(origem):
        letra = re.match(r"^\\\\.\\([A-Za-z]):", origem)
        if letra and destino.drive.upper() == f"{letra.group(1).upper()}:":
            raise ValueError(
                "O destino está na mesma unidade de origem. Escolha outra unidade para "
                "não sobrescrever evidências."
            )
        numero_origem = _numero_dispositivo(origem)
        numero_destino = None
        if destino.drive:
            numero_destino = _numero_dispositivo(f"\\\\.\\{destino.drive.rstrip(':')}:")
        if numero_origem is not None and numero_destino is not None:
            if numero_origem == numero_destino:
                raise ValueError(
                    "O destino pertence ao mesmo dispositivo físico da origem. "
                    "Escolha outro disco para preservar a evidência."
                )
        elif numero_origem is not None and numero_destino is None:
            avisos.append(
                "Não foi possível confirmar o dispositivo físico do destino. "
                "Verifique manualmente se ele é diferente da origem."
            )
    return avisos


def _fim_zip(dados: bytes) -> Optional[int]:
    """Localiza o fim de um arquivo ZIP pelo registro EOCD."""
    indice = dados.rfind(b"PK\x05\x06")
    if indice < 0 or len(dados) < indice + 22:
        return None
    try:
        comentario = struct.unpack_from("<H", dados, indice + 20)[0]
    except struct.error:
        return None
    fim = indice + 22 + comentario
    return fim if fim <= len(dados) else None


def _fim_artefato(
    tipo: str,
    cauda: bytes,
    bloco: bytes,
    assinatura: Assinatura,
    total_escrito: int,
) -> Optional[int]:
    """Devolve quantos bytes do bloco atual pertencem ao artefato, se o fim chegou."""
    combinado = cauda + bloco
    if assinatura.usa_eocd_zip:
        fim = _fim_zip(combinado)
        if fim is None:
            return None
        return fim - len(cauda)

    if assinatura.marcador_fim:
        indice = combinado.find(assinatura.marcador_fim, max(0, len(cauda) - 64))
        if indice < 0:
            return None
        fim = indice + len(assinatura.marcador_fim)
        return max(0, fim - len(cauda))

    if total_escrito >= assinatura.tamanho_maximo_padrao:
        return len(bloco)
    return None


def _extrair_artefato(
    fonte: FonteLeitura,
    assinatura: Assinatura,
    offset: int,
    destino: Path,
    tamanho_maximo: int,
) -> Optional[ArquivoRecuperado]:
    """Copia um artefato da origem para o destino, sem tocar na origem."""
    limite = min(tamanho_maximo, assinatura.tamanho_maximo_padrao)
    if limite <= 0:
        return None

    # "MZ" aparece em muitos falsos positivos; confirma o cabeçalho PE antes de
    # criar qualquer arquivo de saída.
    if assinatura.tipo == "PE":
        cabecalho = fonte.ler_em(offset, 0x100)
        if len(cabecalho) < 0x40:
            return None
        try:
            deslocamento_pe = struct.unpack_from("<I", cabecalho, 0x3C)[0]
        except struct.error:
            return None
        if deslocamento_pe < 0 or deslocamento_pe + 4 > len(cabecalho):
            return None
        if cabecalho[deslocamento_pe : deslocamento_pe + 4] != b"PE\x00\x00":
            return None

    caminho_saida = destino / f"{assinatura.tipo.lower()}_{offset:08x}.{assinatura.extensao}"
    contador = 1
    while caminho_saida.exists():
        caminho_saida = destino / (
            f"{assinatura.tipo.lower()}_{offset:08x}_{contador}.{assinatura.extensao}"
        )
        contador += 1

    escrito = 0
    cauda = b""
    try:
        with open(caminho_saida, "wb") as saida:
            while escrito < limite:
                bloco = fonte.ler_em(offset + escrito, min(1024 * 1024, limite - escrito))
                if not bloco:
                    break
                fim_local = _fim_artefato(
                    assinatura.tipo, cauda, bloco, assinatura, escrito
                )
                if fim_local is not None:
                    if fim_local > 0:
                        saida.write(bloco[:fim_local])
                        escrito += fim_local
                    break
                saida.write(bloco)
                escrito += len(bloco)
                cauda = (cauda + bloco)[-_CAUDA_ASSINATURA:]

        if escrito < assinatura.tamanho_minimo:
            caminho_saida.unlink(missing_ok=True)
            return None

        return ArquivoRecuperado(
            tipo=assinatura.tipo,
            offset=offset,
            tamanho=escrito,
            caminho=str(caminho_saida),
            metodo="carving de assinatura",
        )
    except OSError:
        caminho_saida.unlink(missing_ok=True)
        raise


def _escanear_assinaturas(
    fonte: FonteLeitura,
    tipos: Iterable[str],
    limite_bytes: int,
    limite_artefatos: int,
    ctx: Optional[TaskContext] = None,
) -> List[Tuple[Assinatura, int]]:
    """Percorre a origem em blocos e coleta inícios de artefatos reconhecidos."""
    selecionadas = [a for a in ASSINATURAS if a.tipo in set(tipos)]
    if not selecionadas:
        return []

    encontrados: List[Tuple[Assinatura, int]] = []
    vistos: set[int] = set()
    offset = 0
    cauda = b""
    total = fonte.tamanho
    lidos = 0

    while limite_artefatos <= 0 or len(encontrados) < limite_artefatos:
        if ctx is not None and ctx.cancelled():
            break
        if limite_bytes and lidos >= limite_bytes:
            break
        if total and offset >= total:
            break

        bloco = fonte.ler_em(offset, _BLOCO_LEITURA)
        if not bloco:
            break
        base = offset - len(cauda)
        combinado = cauda + bloco
        lidos += len(bloco)

        for assinatura in selecionadas:
            inicio = 0
            while limite_artefatos <= 0 or len(encontrados) < limite_artefatos:
                pos = combinado.find(assinatura.inicio, inicio)
                if pos < 0:
                    break
                absoluto = base + pos
                if absoluto not in vistos and absoluto >= 0:
                    vistos.add(absoluto)
                    encontrados.append((assinatura, absoluto))
                inicio = pos + 1

        if ctx is not None and total:
            ctx.progress(
                min(offset + len(bloco), total),
                total,
                f"Varredura: {formatar_bytes(offset + len(bloco))} de {formatar_bytes(total)}",
            )
        offset += len(bloco)
        cauda = combinado[-_CAUDA_ASSINATURA:]

    return encontrados


def analisar_com_tsk(origem: str | Path) -> Dict[str, Any]:
    """Abre a origem com pytsk3 e devolve metadados do sistema de arquivos.

    Levanta ``DependenciaAusente`` quando a biblioteca opcional não está
    instalada. Nenhuma escrita é feita na origem.
    """
    try:
        import pytsk3  # importação tardia
    except ImportError as exc:
        raise DependenciaAusente(
            "recuperação NTFS via pytsk3", "pytsk3", "pytsk3"
        ) from exc

    imagem = pytsk3.Img_Info(str(origem))
    sistema = pytsk3.FS_Info(imagem)
    info = sistema.info
    return {
        "tipo": str(getattr(info, "ftype", "desconhecido")),
        "tamanho_bloco": int(getattr(info, "block_size", 0) or 0),
        "quantidade_blocos": int(getattr(info, "block_count", 0) or 0),
        "raiz": str(getattr(info, "root_inum", "")),
    }


def _nome_entrada_tsk(entrada: Any) -> str:
    """Extrai o nome de uma entrada pytsk3 de forma tolerante."""
    try:
        nome = entrada.info.name.name
        if isinstance(nome, bytes):
            return nome.decode("utf-8", errors="replace")
        return str(nome)
    except Exception:
        return ""


def _recuperar_com_tsk(
    origem: str,
    destino: Path,
    limite: int,
    tamanho_maximo: int,
    ctx: Optional[TaskContext] = None,
) -> List[ArquivoRecuperado]:
    """Tenta recuperar entradas não alocadas usando pytsk3."""
    try:
        import pytsk3  # importação tardia
    except ImportError as exc:
        raise DependenciaAusente(
            "recuperação NTFS via pytsk3", "pytsk3", "pytsk3"
        ) from exc

    recuperados: List[ArquivoRecuperado] = []
    imagem = pytsk3.Img_Info(origem)
    sistema = pytsk3.FS_Info(imagem)
    flag_nao_alocado = int(getattr(pytsk3, "TSK_FS_META_FLAG_UNALLOC", 0x0002))
    fila = [""]
    visitados = 0

    while fila and len(recuperados) < limite:
        if ctx is not None and ctx.cancelled():
            break
        caminho_dir = fila.pop(0)
        try:
            diretorio = sistema.open_dir(path=caminho_dir)
        except Exception:
            continue

        for entrada in diretorio:
            if len(recuperados) >= limite:
                break
            if ctx is not None and ctx.cancelled():
                break
            visitados += 1
            nome = _nome_entrada_tsk(entrada)
            if nome in ("", ".", ".."):
                continue
            meta = getattr(entrada.info, "meta", None)
            if meta is None:
                continue
            try:
                if getattr(meta, "type", None) == getattr(pytsk3, "TSK_FS_META_TYPE_DIR", 2):
                    fila.append(f"{caminho_dir}/{nome}" if caminho_dir else nome)
                    continue
            except Exception:
                pass

            try:
                flags = int(getattr(meta, "flags", 0) or 0)
            except Exception:
                flags = 0
            if not flags & flag_nao_alocado:
                continue

            tamanho_meta = int(getattr(meta, "size", 0) or 0)
            if tamanho_meta <= 0 or tamanho_meta > tamanho_maximo:
                continue
            try:
                arquivo = sistema.open_meta(inode=int(meta.addr))
                conteudo = b""
                deslocamento = 0
                while deslocamento < tamanho_meta:
                    pedaco = arquivo.read_random(deslocamento, min(1024 * 1024, tamanho_meta - deslocamento))
                    if not pedaco:
                        break
                    conteudo += pedaco
                    deslocamento += len(pedaco)
            except Exception:
                continue

            if len(conteudo) < 16:
                continue
            nome_seguro = re.sub(r"[^A-Za-z0-9._-]+", "_", nome).strip("._") or "recuperado"
            caminho_saida = destino / f"tsk_{len(recuperados):04d}_{nome_seguro}"
            try:
                caminho_saida.write_bytes(conteudo)
            except OSError:
                continue
            recuperados.append(
                ArquivoRecuperado(
                    tipo="TSK",
                    offset=int(getattr(meta, "addr", 0) or 0),
                    tamanho=len(conteudo),
                    caminho=str(caminho_saida),
                    metodo="pytsk3",
                )
            )
            if ctx is not None:
                ctx.log("INFO", f"Recuperado via pytsk3: {nome_seguro} ({formatar_bytes(len(conteudo))})")

    return recuperados


def recuperar_arquivos(
    origem: str | Path,
    destino: str | Path,
    tipos: Optional[Iterable[str]] = None,
    tamanho_maximo: int = 100 * 1024 * 1024,
    limite_bytes: int = 0,
    limite_artefatos: int = 200,
    usar_tsk: bool = True,
    usar_carving: bool = True,
    ctx: Optional[TaskContext] = None,
) -> ResultadoRecuperacao:
    """Recupera arquivos de uma imagem ou dispositivo sem alterar a origem.

    ``tipos`` aceita os nomes de ``ASSINATURAS`` (JPEG, PNG, PDF, ZIP, GIF,
    SQLite, PE). ``limite_bytes`` restringe a varredura (0 = sem limite).
    """
    destino_path = Path(destino).expanduser().resolve()
    destino_path.mkdir(parents=True, exist_ok=True)
    if destino_path.is_file():
        raise ValueError("O destino deve ser uma pasta.")

    tipos_lista = list(tipos) if tipos is not None else [a.tipo for a in ASSINATURAS]
    resultado = ResultadoRecuperacao(
        origem=str(origem),
        destino=str(destino_path),
        tipo_fonte="dispositivo" if _eh_dispositivo(str(origem)) else "imagem ou arquivo",
    )

    with FonteLeitura(origem) as fonte:
        resultado.avisos.extend(_validar_destino(str(origem), destino_path))
        if fonte.tamanho <= 0:
            resultado.avisos.append(
                "O tamanho da origem não foi informado pelo driver. A varredura seguirá até o fim do fluxo."
            )

        # pytsk3 é opcional: quando ausente, o carving nativo continua funcionando.
        sistema_arquivos = ""
        if usar_tsk:
            if dependencia_disponivel("pytsk3"):
                try:
                    metadados = analisar_com_tsk(origem)
                    sistema_arquivos = metadados.get("tipo", "")
                    resultado.sistema_arquivos = sistema_arquivos
                    if ctx is not None:
                        ctx.log(
                            "INFO",
                            f"pytsk3 disponível: {sistema_arquivos}, bloco de "
                            f"{metadados.get('tamanho_bloco', 0)} bytes.",
                        )
                    recuperados_tsk = _recuperar_com_tsk(
                        str(origem),
                        destino_path,
                        limite=max(1, int(limite_artefatos)),
                        tamanho_maximo=max(1024, int(tamanho_maximo)),
                        ctx=ctx,
                    )
                    resultado.arquivos.extend(recuperados_tsk)
                    if not recuperados_tsk:
                        resultado.avisos.append(
                            "pytsk3 não encontrou entradas não alocadas recuperáveis; "
                            "o carving de assinaturas será usado como complemento."
                        )
                except Exception as exc:
                    resultado.avisos.append(
                        f"pytsk3 não conseguiu analisar a origem ({exc}). "
                        "O carving de assinaturas será usado."
                    )
            else:
                resultado.avisos.append(
                    "pytsk3 não está instalado. O carving nativo de assinaturas será "
                    "usado. Para recuperação NTFS por metadados, instale com: "
                    "pip install pytsk3"
                )

        if usar_carving:
            encontrados = _escanear_assinaturas(
                fonte,
                tipos=tipos_lista,
                limite_bytes=max(0, int(limite_bytes)),
                limite_artefatos=max(0, int(limite_artefatos)),
                ctx=ctx,
            )
            if ctx is not None:
                ctx.log("INFO", f"{len(encontrados)} possível(is) artefato(s) encontrado(s) no carving.")
            for indice, (assinatura, offset) in enumerate(encontrados):
                if ctx is not None and ctx.cancelled():
                    resultado.cancelado = True
                    break
                if len(resultado.arquivos) >= limite_artefatos > 0:
                    break
                try:
                    recuperado = _extrair_artefato(
                        fonte,
                        assinatura,
                        offset,
                        destino_path,
                        max(1024, int(tamanho_maximo)),
                    )
                except Exception as exc:
                    resultado.avisos.append(
                        f"Falha ao extrair {assinatura.tipo} no deslocamento 0x{offset:X}: {exc}"
                    )
                    continue
                if recuperado is not None:
                    resultado.arquivos.append(recuperado)
                if ctx is not None:
                    ctx.progress(
                        indice + 1,
                        max(1, len(encontrados)),
                        f"Extraindo {assinatura.tipo} {indice + 1}/{len(encontrados)}",
                    )

        resultado.bytes_escaneados = min(fonte.tamanho, limite_bytes) if limite_bytes else fonte.tamanho

    resultado.avisos.append(
        "A origem foi aberta somente para leitura. Nenhum byte foi gravado nela."
    )
    return resultado


def formatar_resultado_recuperacao(resultado: ResultadoRecuperacao) -> str:
    """Resumo textual da recuperação para a interface."""
    linhas = [
        "Recuperação concluída.",
        "",
        f"Origem: {resultado.origem}",
        f"Tipo de fonte: {resultado.tipo_fonte}",
        f"Sistema de arquivos: {resultado.sistema_arquivos or 'não identificado'}",
        f"Destino: {resultado.destino}",
        f"Arquivos recuperados: {formatar_numero(len(resultado.arquivos))}",
        f"Cancelado: {'sim' if resultado.cancelado else 'não'}",
        "",
        "Avisos:",
    ]
    linhas.extend(f"- {aviso}" for aviso in resultado.avisos)
    if resultado.arquivos:
        linhas.extend(["", "Arquivos:"])
        for item in resultado.arquivos[:30]:
            linhas.append(
                f"- {item.tipo} | offset 0x{item.offset:X} | "
                f"{formatar_bytes(item.tamanho)} | {item.caminho}"
            )
        if len(resultado.arquivos) > 30:
            linhas.append(f"... e mais {len(resultado.arquivos) - 30} arquivo(s).")
    return "\n".join(linhas)


@register
class FileRecoveryTool(Tool):
    """Ferramenta de recuperação de arquivos por pytsk3 e carving."""

    id = "forensics.file_recovery"
    name = "Recuperação de Arquivos"
    category = "Forense"
    description = (
        "Recupera arquivos de imagens de disco e unidades usando pytsk3 (quando "
        "disponível) ou carving read-only por assinaturas, sem gravar na origem"
    )
    keywords = [
        "recuperação",
        "recuperacao",
        "arquivos",
        "apagados",
        "carving",
        "pytsk3",
        "ntfs",
        "disco",
        "forense",
        "imagem",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return FileRecoveryView(self, parent)


class FileRecoveryView(PainelFerramenta):
    """Interface de configuração e acompanhamento da recuperação."""

    def __init__(self, tool: FileRecoveryTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._montar()

    def _montar(self) -> None:
        self.adicionar_aviso(
            "A origem é aberta apenas para leitura. Escolha um destino em outro "
            "disco ou pasta e nunca grave resultados na unidade que está sendo "
            "analisada. Para unidades físicas, execute como Administrador.",
            destaque=True,
        )

        cartao, layout = self.adicionar_card("Origem e destino")
        linha_origem = QHBoxLayout()
        linha_origem.addWidget(QLabel("Origem:"))
        self.txt_origem = QLineEdit()
        self.txt_origem.setPlaceholderText(
            "Imagem de disco, arquivo ou \\\\.\\PhysicalDrive0"
        )
        linha_origem.addWidget(self.txt_origem, stretch=1)
        self.btn_origem = QPushButton("Arquivo...")
        self.btn_origem.clicked.connect(self._escolher_origem)
        linha_origem.addWidget(self.btn_origem)
        layout.addLayout(linha_origem)

        linha_destino = QHBoxLayout()
        linha_destino.addWidget(QLabel("Destino:"))
        self.txt_destino = QLineEdit()
        self.txt_destino.setPlaceholderText("Pasta onde os arquivos recuperados serão gravados")
        linha_destino.addWidget(self.txt_destino, stretch=1)
        self.btn_destino = QPushButton("Pasta...")
        self.btn_destino.clicked.connect(self._escolher_destino)
        linha_destino.addWidget(self.btn_destino)
        layout.addLayout(linha_destino)

        cartao_tipos, layout_tipos = self.adicionar_card("Assinaturas procuradas no carving")
        grade = QGridLayout()
        self._checks: Dict[str, QCheckBox] = {}
        for indice, assinatura in enumerate(ASSINATURAS):
            if assinatura.tipo in self._checks:
                continue
            check = QCheckBox(f"{assinatura.tipo} (.{assinatura.extensao})")
            check.setChecked(True)
            self._checks[assinatura.tipo] = check
            grade.addWidget(check, indice // 4, indice % 4)
        layout_tipos.addLayout(grade)

        linha_opcoes = QHBoxLayout()
        linha_opcoes.addWidget(QLabel("Tamanho máximo por arquivo (MB):"))
        self.spin_tamanho = QSpinBox()
        self.spin_tamanho.setRange(1, 4096)
        self.spin_tamanho.setValue(100)
        linha_opcoes.addWidget(self.spin_tamanho)

        linha_opcoes.addWidget(QLabel("Limite de varredura (MB, 0 = tudo):"))
        self.spin_limite = QSpinBox()
        self.spin_limite.setRange(0, 262144)
        self.spin_limite.setValue(2048)
        self.spin_limite.setSpecialValueText("Sem limite")
        linha_opcoes.addWidget(self.spin_limite)

        linha_opcoes.addWidget(QLabel("Máximo de arquivos:"))
        self.spin_artefatos = QSpinBox()
        self.spin_artefatos.setRange(1, 10000)
        self.spin_artefatos.setValue(200)
        linha_opcoes.addWidget(self.spin_artefatos)

        self.chk_tsk = QCheckBox("Tentar pytsk3")
        self.chk_tsk.setChecked(True)
        linha_opcoes.addWidget(self.chk_tsk)
        self.chk_carving = QCheckBox("Usar carving")
        self.chk_carving.setChecked(True)
        linha_opcoes.addWidget(self.chk_carving)
        layout_tipos.addLayout(linha_opcoes)

        linha_execucao = QHBoxLayout()
        self.lbl_status = QLabel(
            "Informe a origem e o destino. O carving funciona sem dependências opcionais."
        )
        self.lbl_status.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        linha_execucao.addWidget(self.lbl_status, stretch=1)
        self.btn_recuperar = QPushButton("Iniciar Recuperação")
        self.btn_recuperar.clicked.connect(self._recuperar)
        linha_execucao.addWidget(self.btn_recuperar)
        layout_tipos.addLayout(linha_execucao)

        cartao_resultado, layout_resultado = self.adicionar_card("Arquivos recuperados")
        self.tabela = criar_tabela(
            ["Tipo", "Offset", "Tamanho", "Método", "Arquivo"], self
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.tabela.setMinimumHeight(180)
        layout_resultado.addWidget(self.tabela)

        self.txt_saida = criar_saida_texto(200, self)
        layout_resultado.addWidget(self.txt_saida)
        linha_botoes = QHBoxLayout()
        linha_botoes.addWidget(
            botao_copiar(lambda: self.txt_saida.toPlainText(), self, "Copiar Resultado")
        )
        linha_botoes.addStretch()
        layout_resultado.addLayout(linha_botoes)

        self.log = adicionar_log_painel(self, "Log da Recuperação")
        self.adicionar_espaco()

    def _escolher_origem(self) -> None:
        """Seleciona uma imagem ou arquivo de origem."""
        origem, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar imagem ou arquivo de disco",
            str(Path.home()),
            "Imagens de disco (*.img *.dd *.raw *.vhd *.vhdx *.iso *.bin);;Todos os arquivos (*.*)",
        )
        if origem:
            self.txt_origem.setText(origem)

    def _escolher_destino(self) -> None:
        """Seleciona a pasta de destino dos arquivos recuperados."""
        destino = QFileDialog.getExistingDirectory(
            self, "Selecionar pasta de destino", str(Path.home())
        )
        if destino:
            self.txt_destino.setText(destino)

    def _tipos_selecionados(self) -> List[str]:
        """Lista os tipos marcados na interface."""
        return [tipo for tipo, check in self._checks.items() if check.isChecked()]

    def _recuperar(self) -> None:
        """Valida os campos e executa a recuperação em segundo plano."""
        origem = self.txt_origem.text().strip()
        destino = self.txt_destino.text().strip()
        if not origem:
            QMessageBox.information(self, "Informe a origem", "Escolha uma imagem ou dispositivo.")
            return
        if not destino:
            QMessageBox.information(self, "Informe o destino", "Escolha uma pasta de destino.")
            return
        tipos = self._tipos_selecionados()
        if not tipos and self.chk_carving.isChecked():
            QMessageBox.information(
                self, "Selecione um tipo", "Marque ao menos uma assinatura para o carving."
            )
            return

        if _eh_dispositivo(origem):
            if not garantir_admin(self, self.tool.name, permitir_continuar=True):
                return

        self.btn_recuperar.setEnabled(False)
        self.lbl_status.setText("Recuperando arquivos...")
        self.tabela.setRowCount(0)
        limite_bytes = int(self.spin_limite.value()) * 1024 * 1024
        tamanho_maximo = int(self.spin_tamanho.value()) * 1024 * 1024

        def tarefa(ctx: TaskContext) -> ResultadoRecuperacao:
            return recuperar_arquivos(
                origem=origem,
                destino=destino,
                tipos=tipos,
                tamanho_maximo=tamanho_maximo,
                limite_bytes=limite_bytes,
                limite_artefatos=int(self.spin_artefatos.value()),
                usar_tsk=self.chk_tsk.isChecked(),
                usar_carving=self.chk_carving.isChecked(),
                ctx=ctx,
            )

        def concluiu(resultado: ResultadoRecuperacao) -> None:
            self.btn_recuperar.setEnabled(True)
            self.lbl_status.setText(
                f"Recuperação concluída: {formatar_numero(len(resultado.arquivos))} arquivo(s)."
            )
            preencher_tabela(
                self.tabela,
                [
                    [
                        item.tipo,
                        f"0x{item.offset:X}",
                        formatar_bytes(item.tamanho),
                        item.metodo,
                        item.caminho,
                    ]
                    for item in resultado.arquivos
                ],
            )
            self.txt_saida.setPlainText(formatar_resultado_recuperacao(resultado))

        def falhou(erro: Exception) -> None:
            self.btn_recuperar.setEnabled(True)
            self.lbl_status.setText("Falha na recuperação.")
            mensagem = str(erro)
            if isinstance(erro, DependenciaAusente):
                mensagem += "\n\nO carving nativo continua disponível sem pytsk3."
            self.txt_saida.setPlainText(
                "A recuperação não foi concluída.\n\n"
                f"{mensagem}\n\n"
                "Confira se a origem é legível, se o destino é gravável e, para "
                "unidades físicas, se o aplicativo está elevado."
            )
            mostrar_erro(self, "Falha na recuperação de arquivos", erro)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_progredir=lambda atual, total, msg: self.lbl_status.setText(msg),
            ao_logar=lambda nivel, msg: self.log.append_log(nivel, msg),
        )

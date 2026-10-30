"""Extração forense de artefatos de navegadores, sempre sobre cópias temporárias.

Bancos SQLite de Chrome/Edge/Brave/Vivaldi/Opera e Firefox são copiados para uma
pasta temporária antes de qualquer consulta. Cookies e senhas do Chromium são
descriptografados com DPAPI (``win32crypt``) e AES-GCM (``cryptography``) quando
disponíveis. No Firefox, ``logins.json`` é lido apenas como metadado: a
descriptografia NSS de ``key4.db`` não é simulada nem inventada.

Nenhum arquivo do navegador é aberto para escrita. A ferramenta foi desenhada
para uso autorizado em resposta a incidentes e auditoria do próprio perfil.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
    confirmar_termo_etico,
    dependencia_disponivel,
    formatar_numero,
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

_log = get_logger("forensics.browser_extract")

_CATEGORIAS = ("Historico", "Downloads", "Cookies", "Senhas")
_CHAVES_CACHE: Dict[str, bytes] = {}


@dataclass
class NavegadorInfo:
    """Navegador detectado e seus perfis utilizáveis."""

    nome: str
    tipo: str
    raiz: str
    perfis: List[str] = field(default_factory=list)


@dataclass
class ItemNavegador:
    """Um artefato extraído de um perfil de navegador."""

    categoria: str
    navegador: str
    perfil: str
    titulo: str = ""
    url: str = ""
    usuario: str = ""
    valor: str = ""
    data: str = ""
    observacao: str = ""


@dataclass
class ResultadoNavegador:
    """Resultado consolidado da extração."""

    navegador: str
    itens: List[ItemNavegador] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    def contagem(self) -> Dict[str, int]:
        """Contagem de itens por categoria."""
        resumo: Dict[str, int] = {}
        for item in self.itens:
            resumo[item.categoria] = resumo.get(item.categoria, 0) + 1
        return resumo


def _local_appdata() -> Path:
    """Pasta LocalAppData do usuário atual."""
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))


def _appdata() -> Path:
    """Pasta Roaming do usuário atual."""
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))


def _perfis_chromium(base: Path) -> List[Path]:
    """Descobre perfis Chromium que contenham bancos reconhecíveis."""
    if not base.exists():
        return []
    nomes = ("History", "Cookies", "Login Data", "Network")
    perfis: List[Path] = []

    def tem_banco(caminho: Path) -> bool:
        try:
            if (caminho / "History").exists() or (caminho / "Login Data").exists():
                return True
            if (caminho / "Cookies").exists() or (caminho / "Network" / "Cookies").exists():
                return True
        except OSError:
            pass
        return False

    if tem_banco(base):
        perfis.append(base)
    try:
        for filho in sorted(base.iterdir()):
            if filho.is_dir() and tem_banco(filho):
                perfis.append(filho)
    except OSError:
        pass
    return perfis


def _perfis_firefox(base: Path) -> List[Path]:
    """Descobre perfis Firefox que contenham places.sqlite ou logins.json."""
    candidatos: List[Path] = []
    if (base / "places.sqlite").exists() or (base / "logins.json").exists():
        candidatos.append(base)
    pasta = base / "Profiles"
    if pasta.exists():
        try:
            for filho in sorted(pasta.iterdir()):
                if filho.is_dir() and (
                    (filho / "places.sqlite").exists() or (filho / "logins.json").exists()
                ):
                    candidatos.append(filho)
        except OSError:
            pass
    return candidatos


def detectar_navegadores() -> List[NavegadorInfo]:
    """Detecta navegadores e perfis instalados no perfil do usuário atual."""
    encontrados: List[NavegadorInfo] = []
    bases_chromium = [
        ("Google Chrome", _local_appdata() / "Google" / "Chrome" / "User Data"),
        ("Microsoft Edge", _local_appdata() / "Microsoft" / "Edge" / "User Data"),
        ("Brave", _local_appdata() / "BraveSoftware" / "Brave-Browser" / "User Data"),
        ("Vivaldi", _local_appdata() / "Vivaldi" / "User Data"),
        ("Opera", _appdata() / "Opera Software" / "Opera Stable"),
    ]
    for nome, base in bases_chromium:
        perfis = _perfis_chromium(base)
        if perfis:
            encontrados.append(
                NavegadorInfo(nome=nome, tipo="chromium", raiz=str(base), perfis=[str(p) for p in perfis])
            )

    base_firefox = _appdata() / "Mozilla" / "Firefox"
    perfis_firefox = _perfis_firefox(base_firefox)
    if perfis_firefox:
        encontrados.append(
            NavegadorInfo(
                nome="Mozilla Firefox",
                tipo="firefox",
                raiz=str(base_firefox),
                perfis=[str(p) for p in perfis_firefox],
            )
        )
    return encontrados


def _copiar_banco(origem: Path, tempdir: Path, nome: str) -> Optional[Path]:
    """Copia um banco SQLite para a pasta temporária e devolve o destino."""
    if not origem.exists():
        return None
    destino = tempdir / nome
    try:
        shutil.copy2(origem, destino)
    except OSError:
        return None
    # Arquivos WAL/SHM ajudam a ver o estado mais recente sem tocar no original.
    for sufixo in ("-wal", "-shm"):
        lateral = Path(str(origem) + sufixo)
        if lateral.exists():
            try:
                shutil.copy2(lateral, Path(str(destino) + sufixo))
            except OSError:
                pass
    return destino


def _consultar(caminho: Path, sql: str, parametros: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
    """Executa uma consulta somente leitura em uma cópia temporária."""
    uri = f"{caminho.resolve().as_uri()}?mode=ro"
    conexao = sqlite3.connect(uri, uri=True)
    conexao.row_factory = sqlite3.Row
    try:
        return list(conexao.execute(sql, parametros))
    finally:
        conexao.close()


def _chrome_para_iso(valor: Any) -> str:
    """Converte microssegundos desde 1601 do Chromium em data ISO local."""
    try:
        numero = int(valor or 0)
    except (TypeError, ValueError):
        return ""
    if numero <= 0:
        return ""
    try:
        segundos = numero / 1_000_000 - 11_644_473_600
        return datetime.fromtimestamp(segundos, tz=timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _firefox_para_iso(valor: Any) -> str:
    """Converte microssegundos desde 1970 do Firefox em data ISO local."""
    try:
        numero = int(valor or 0)
    except (TypeError, ValueError):
        return ""
    if numero <= 0:
        return ""
    try:
        return datetime.fromtimestamp(numero / 1_000_000, tz=timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _ms_para_iso(valor: Any) -> str:
    """Converte milissegundos desde 1970 em data ISO local."""
    try:
        numero = int(valor or 0)
    except (TypeError, ValueError):
        return ""
    if numero <= 0:
        return ""
    try:
        return datetime.fromtimestamp(numero / 1000, tz=timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _local_state(perfil: Path) -> Optional[Path]:
    """Localiza o arquivo Local State acima do perfil Chromium."""
    atual = perfil
    for _ in range(4):
        candidato = atual / "Local State"
        if candidato.exists():
            return candidato
        if atual.parent == atual:
            break
        atual = atual.parent
    return None


def obter_chave_chromium(perfil: Path | str) -> bytes:
    """Obtém a chave AES do Chromium protegida por DPAPI.

    Requer ``win32crypt`` (pywin32) e o mesmo contexto de usuário que criou o
    perfil. Quando a chave não pode ser recuperada, levanta ``DependenciaAusente``
    com instrução de instalação.
    """
    chave_cache = str(Path(perfil).resolve())
    if chave_cache in _CHAVES_CACHE:
        return _CHAVES_CACHE[chave_cache]

    if not dependencia_disponivel("win32crypt"):
        raise DependenciaAusente(
            "descriptografia DPAPI do Chromium", "win32crypt", "pywin32"
        )

    import win32crypt  # importação tardia

    estado = _local_state(Path(perfil))
    if estado is None:
        raise RuntimeError(
            "Arquivo 'Local State' não encontrado. Sem ele não é possível obter a "
            "chave DPAPI do Chromium."
        )
    try:
        dados = json.loads(estado.read_text(encoding="utf-8"))
        chave_cifrada = base64.b64decode(dados["os_crypt"]["encrypted_key"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Falha ao ler a chave do Chromium: {exc}") from exc

    if chave_cifrada.startswith(b"DPAPI"):
        chave_cifrada = chave_cifrada[5:]
    try:
        _descricao, chave = win32crypt.CryptUnprotectData(
            chave_cifrada, None, None, None, 0
        )
    except Exception as exc:
        raise RuntimeError(
            "O Windows não permitiu descriptografar a chave DPAPI. "
            "Execute no mesmo usuário que criou o perfil, com o perfil carregado."
        ) from exc

    chave = bytes(chave)
    _CHAVES_CACHE[chave_cache] = chave
    return chave


def _descriptografar_chromium(blob: bytes, chave: Optional[bytes]) -> Tuple[str, str]:
    """Descriptografa um blob v10/v11 do Chromium; devolve (texto, observação)."""
    if not blob:
        return "", ""
    if blob.startswith(b"v20"):
        return "", (
            "Valor v20 (App-Bound Encryption) não descriptografado. "
            "Essa proteção exige elevação e contexto do aplicativo; nenhum dado foi inventado."
        )
    if blob[:3] in (b"v10", b"v11"):
        if not chave:
            return "", "Chave DPAPI indisponível; valor permanece cifrado."
        if not dependencia_disponivel("cryptography"):
            raise DependenciaAusente(
                "descriptografia AES-GCM dos cookies", "cryptography", "cryptography"
            )
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # importação tardia

        nonce = blob[3:15]
        ciphertext = blob[15:]
        try:
            texto = AESGCM(chave).decrypt(nonce, ciphertext, None)
            return texto.decode("utf-8", errors="replace"), ""
        except Exception as exc:
            return "", f"Falha ao descriptografar AES-GCM: {exc}"

    # Formato legado (pré-Chrome 80) protegido diretamente por DPAPI.
    if not dependencia_disponivel("win32crypt"):
        return "", "win32crypt indisponível; valor legado permanece cifrado."
    import win32crypt  # importação tardia

    try:
        _descricao, texto = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        return bytes(texto).decode("utf-8", errors="replace"), "Formato DPAPI legado."
    except Exception as exc:
        return "", f"Falha no DPAPI legado: {exc}"


def extrair_historico(
    perfil: Path | str,
    navegador: str,
    tipo: str,
    limite: int = 500,
) -> Tuple[List[ItemNavegador], List[str]]:
    """Extrai histórico e downloads de um perfil, usando cópia temporária."""
    perfil_path = Path(perfil)
    itens: List[ItemNavegador] = []
    avisos: List[str] = []

    with tempfile.TemporaryDirectory(prefix="wintoolbox_nav_") as temp:
        tempdir = Path(temp)
        if tipo == "chromium":
            banco = _copiar_banco(perfil_path / "History", tempdir, "History")
            if banco is None:
                return itens, ["Banco History não encontrado neste perfil."]
            try:
                for linha in _consultar(
                    banco,
                    "SELECT url, title, visit_count, last_visit_time FROM urls "
                    "ORDER BY last_visit_time DESC LIMIT ?",
                    (max(1, int(limite)),),
                ):
                    itens.append(
                        ItemNavegador(
                            categoria="Histórico",
                            navegador=navegador,
                            perfil=str(perfil_path),
                            titulo=str(linha["title"] or ""),
                            url=str(linha["url"] or ""),
                            valor=f"{int(linha['visit_count'] or 0)} visita(s)",
                            data=_chrome_para_iso(linha["last_visit_time"]),
                        )
                    )
            except sqlite3.Error as exc:
                avisos.append(f"Falha ao consultar History: {exc}")

            try:
                for linha in _consultar(
                    banco,
                    "SELECT target_path, tab_url, total_bytes, start_time FROM downloads "
                    "ORDER BY start_time DESC LIMIT ?",
                    (max(1, int(limite)),),
                ):
                    itens.append(
                        ItemNavegador(
                            categoria="Downloads",
                            navegador=navegador,
                            perfil=str(perfil_path),
                            titulo=str(linha["target_path"] or ""),
                            url=str(linha["tab_url"] or ""),
                            valor=f"{int(linha['total_bytes'] or 0)} byte(s)",
                            data=_chrome_para_iso(linha["start_time"]),
                        )
                    )
            except sqlite3.Error:
                # Versões antigas podem não ter a tabela downloads; não é erro fatal.
                pass
        else:
            banco = _copiar_banco(perfil_path / "places.sqlite", tempdir, "places.sqlite")
            if banco is None:
                return itens, ["Banco places.sqlite não encontrado neste perfil."]
            try:
                for linha in _consultar(
                    banco,
                    "SELECT p.url AS url, p.title AS title, p.visit_count AS visit_count, "
                    "MAX(h.visit_date) AS visit_date "
                    "FROM moz_places p LEFT JOIN moz_historyvisits h ON h.place_id = p.id "
                    "GROUP BY p.id ORDER BY visit_date DESC LIMIT ?",
                    (max(1, int(limite)),),
                ):
                    itens.append(
                        ItemNavegador(
                            categoria="Histórico",
                            navegador=navegador,
                            perfil=str(perfil_path),
                            titulo=str(linha["title"] or ""),
                            url=str(linha["url"] or ""),
                            valor=f"{int(linha['visit_count'] or 0)} visita(s)",
                            data=_firefox_para_iso(linha["visit_date"]),
                        )
                    )
            except sqlite3.Error as exc:
                avisos.append(f"Falha ao consultar places.sqlite: {exc}")
    return itens, avisos


def extrair_cookies(
    perfil: Path | str,
    navegador: str,
    tipo: str,
    limite: int = 500,
) -> Tuple[List[ItemNavegador], List[str]]:
    """Extrai cookies de um perfil, descriptografando somente quando possível."""
    perfil_path = Path(perfil)
    itens: List[ItemNavegador] = []
    avisos: List[str] = []
    chave: Optional[bytes] = None
    if tipo == "chromium":
        try:
            chave = obter_chave_chromium(perfil_path)
        except (DependenciaAusente, RuntimeError) as exc:
            avisos.append(str(exc))

    with tempfile.TemporaryDirectory(prefix="wintoolbox_cookies_") as temp:
        tempdir = Path(temp)
        if tipo == "chromium":
            origem = perfil_path / "Network" / "Cookies"
            if not origem.exists():
                origem = perfil_path / "Cookies"
            banco = _copiar_banco(origem, tempdir, "Cookies")
            if banco is None:
                return itens, ["Banco Cookies não encontrado neste perfil."]
            try:
                for linha in _consultar(
                    banco,
                    "SELECT host_key, name, value, encrypted_value, path, expires_utc, "
                    "is_secure, is_httponly FROM cookies ORDER BY expires_utc DESC LIMIT ?",
                    (max(1, int(limite)),),
                ):
                    valor = str(linha["value"] or "")
                    observacao = ""
                    if not valor and linha["encrypted_value"]:
                        valor, observacao = _descriptografar_chromium(
                            bytes(linha["encrypted_value"]), chave
                        )
                    itens.append(
                        ItemNavegador(
                            categoria="Cookie",
                            navegador=navegador,
                            perfil=str(perfil_path),
                            titulo=str(linha["host_key"] or ""),
                            url=f"{linha['host_key'] or ''}{linha['path'] or ''}",
                            valor=valor,
                            data=_chrome_para_iso(linha["expires_utc"]),
                            observacao=(
                                f"{observacao + ' ' if observacao else ''}"
                                f"seguro={int(linha['is_secure'] or 0)} "
                                f"httponly={int(linha['is_httponly'] or 0)}"
                            ).strip(),
                        )
                    )
            except sqlite3.Error as exc:
                avisos.append(f"Falha ao consultar Cookies: {exc}")
        else:
            banco = _copiar_banco(perfil_path / "cookies.sqlite", tempdir, "cookies.sqlite")
            if banco is None:
                return itens, ["Banco cookies.sqlite não encontrado neste perfil."]
            try:
                for linha in _consultar(
                    banco,
                    "SELECT host, name, value, path, expiry, isSecure, isHttpOnly "
                    "FROM moz_cookies ORDER BY expiry DESC LIMIT ?",
                    (max(1, int(limite)),),
                ):
                    itens.append(
                        ItemNavegador(
                            categoria="Cookie",
                            navegador=navegador,
                            perfil=str(perfil_path),
                            titulo=str(linha["host"] or ""),
                            url=f"{linha['host'] or ''}{linha['path'] or ''}",
                            valor=str(linha["value"] or ""),
                            data=_ms_para_iso(int(linha["expiry"] or 0) * 1000),
                            observacao=(
                                f"seguro={int(linha['isSecure'] or 0)} "
                                f"httponly={int(linha['isHttpOnly'] or 0)}"
                            ),
                        )
                    )
            except sqlite3.Error as exc:
                avisos.append(f"Falha ao consultar cookies.sqlite: {exc}")
    return itens, avisos


def extrair_senhas(
    perfil: Path | str,
    navegador: str,
    tipo: str,
    limite: int = 500,
) -> Tuple[List[ItemNavegador], List[str]]:
    """Extrai credenciais salvas quando a descriptografia é viável.

    No Chromium, tenta DPAPI/AES-GCM. No Firefox, lê apenas os metadados de
    ``logins.json`` e deixa claro que os campos cifrados exigem NSS/key4.db.
    """
    perfil_path = Path(perfil)
    itens: List[ItemNavegador] = []
    avisos: List[str] = []

    if tipo == "chromium":
        chave: Optional[bytes] = None
        try:
            chave = obter_chave_chromium(perfil_path)
        except (DependenciaAusente, RuntimeError) as exc:
            avisos.append(str(exc))
        with tempfile.TemporaryDirectory(prefix="wintoolbox_logins_") as temp:
            banco = _copiar_banco(perfil_path / "Login Data", Path(temp), "Login Data")
            if banco is None:
                return itens, ["Banco 'Login Data' não encontrado neste perfil."]
            try:
                for linha in _consultar(
                    banco,
                    "SELECT origin_url, username_value, password_value, date_created, "
                    "date_last_used, times_used FROM logins ORDER BY date_last_used DESC LIMIT ?",
                    (max(1, int(limite)),),
                ):
                    senha = ""
                    observacao = ""
                    if linha["password_value"]:
                        senha, observacao = _descriptografar_chromium(
                            bytes(linha["password_value"]), chave
                        )
                    itens.append(
                        ItemNavegador(
                            categoria="Senha",
                            navegador=navegador,
                            perfil=str(perfil_path),
                            titulo=str(linha["origin_url"] or ""),
                            url=str(linha["origin_url"] or ""),
                            usuario=str(linha["username_value"] or ""),
                            valor=senha,
                            data=_chrome_para_iso(linha["date_last_used"]),
                            observacao=observacao or (
                                f"criada em {_chrome_para_iso(linha['date_created'])}; "
                                f"{int(linha['times_used'] or 0)} uso(s)"
                            ),
                        )
                    )
            except sqlite3.Error as exc:
                avisos.append(f"Falha ao consultar 'Login Data': {exc}")
    else:
        arquivo = perfil_path / "logins.json"
        if not arquivo.exists():
            return itens, ["Arquivo logins.json não encontrado neste perfil."]
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return itens, [f"Falha ao ler logins.json: {exc}"]

        for entrada in list(dados.get("logins", []))[: max(1, int(limite))]:
            itens.append(
                ItemNavegador(
                    categoria="Senha (metadados)",
                    navegador=navegador,
                    perfil=str(perfil_path),
                    titulo=str(entrada.get("hostname") or ""),
                    url=str(entrada.get("hostname") or ""),
                    usuario=str(entrada.get("usernameField") or ""),
                    valor="(campo cifrado)",
                    data=_ms_para_iso(entrada.get("timeLastUsed")),
                    observacao=(
                        "Usuário e senha estão cifrados pelo NSS (key4.db). "
                        "A descriptografia exige a chave mestra do Firefox e não é "
                        "realizada por esta ferramenta."
                    ),
                )
            )
        if dados.get("logins"):
            avisos.append(
                f"{len(dados['logins'])} credencial(is) do Firefox listada(s) apenas como "
                "metadados; nenhuma senha foi inventada ou descriptografada sem chave."
            )
    return itens, avisos


def extrair_navegador(
    nome: str,
    categorias: Optional[Iterable[str]] = None,
    limite: int = 500,
    ctx: Optional[TaskContext] = None,
) -> ResultadoNavegador:
    """Extrai as categorias escolhidas de todos os perfis de um navegador."""
    disponiveis = {info.nome: info for info in detectar_navegadores()}
    info = disponiveis.get(nome)
    if info is None:
        raise ValueError(f"Navegador não encontrado no perfil atual: {nome}")

    desejadas = set(categorias or _CATEGORIAS)
    resultado = ResultadoNavegador(navegador=nome)
    for indice, perfil in enumerate(info.perfis):
        if ctx is not None:
            ctx.progress(indice, len(info.perfis), f"Perfil {indice + 1}/{len(info.perfis)}")
            ctx.log("INFO", f"Analisando perfil: {perfil}")

        # Histórico e Downloads vêm do mesmo banco; consulta uma única vez por perfil.
        if "Historico" in desejadas or "Downloads" in desejadas:
            try:
                itens, avisos = extrair_historico(perfil, nome, info.tipo, limite)
                if "Historico" not in desejadas:
                    itens = [item for item in itens if item.categoria != "Histórico"]
                if "Downloads" not in desejadas:
                    itens = [item for item in itens if item.categoria != "Downloads"]
                resultado.itens.extend(itens)
                resultado.avisos.extend(aviso for aviso in avisos if aviso not in resultado.avisos)
            except Exception as exc:
                resultado.avisos.append(f"Falha em histórico/downloads no perfil {perfil}: {exc}")

        for categoria in ("Cookies", "Senhas"):
            if categoria not in desejadas:
                continue
            try:
                if categoria == "Cookies":
                    itens, avisos = extrair_cookies(perfil, nome, info.tipo, limite)
                else:
                    itens, avisos = extrair_senhas(perfil, nome, info.tipo, limite)
                resultado.itens.extend(itens)
                resultado.avisos.extend(aviso for aviso in avisos if aviso not in resultado.avisos)
            except Exception as exc:
                resultado.avisos.append(f"Falha em {categoria} no perfil {perfil}: {exc}")

    if ctx is not None:
        ctx.log("INFO", f"Extração concluída: {len(resultado.itens)} item(ns).")
    return resultado


def formatar_resultado_navegador(resultado: ResultadoNavegador) -> str:
    """Resumo textual da extração para a interface."""
    linhas = [
        "Extração de navegador concluída.",
        "",
        f"Navegador: {resultado.navegador}",
        f"Itens extraídos: {formatar_numero(len(resultado.itens))}",
        "",
        "Contagem por categoria:",
    ]
    for categoria, quantidade in sorted(resultado.contagem().items()):
        linhas.append(f"- {categoria}: {formatar_numero(quantidade)}")
    if not resultado.itens:
        linhas.append("- Nenhum item foi extraído.")
    linhas.extend(["", "Avisos:"])
    linhas.extend(f"- {aviso}" for aviso in resultado.avisos) if resultado.avisos else linhas.append(
        "- Nenhum aviso."
    )
    linhas.extend(
        [
            "",
            "Observação: os bancos foram copiados para uma pasta temporária e "
            "abertos em modo somente leitura. Nenhum arquivo do navegador foi alterado.",
        ]
    )
    return "\n".join(linhas)


@register
class BrowserExtractTool(Tool):
    """Ferramenta de extração de artefatos de navegadores."""

    id = "forensics.browser_extract"
    name = "Extração de Artefatos de Navegadores"
    category = "Forense"
    description = (
        "Extrai histórico, downloads, cookies e credenciais salvas de Chrome, Edge, "
        "Brave, Vivaldi, Opera e Firefox por meio de cópias temporárias somente leitura"
    )
    keywords = [
        "navegador",
        "browser",
        "histórico",
        "historico",
        "cookies",
        "senhas",
        "chrome",
        "edge",
        "firefox",
        "forense",
        "lgpd",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return BrowserExtractView(self, parent)


class BrowserExtractView(PainelFerramenta):
    """Interface de escolha de navegador, perfil e categorias."""

    def __init__(self, tool: BrowserExtractTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._navegadores: List[NavegadorInfo] = []
        self._montar()

    def _montar(self) -> None:
        self.adicionar_aviso(
            "Aviso ético e legal: os dados de navegação podem conter informações "
            "pessoais e credenciais. Use apenas em perfis próprios ou com autorização "
            "expressa e por escrito, respeitando a LGPD (Lei 13.709/2018). "
            "A ferramenta não altera os bancos: ela trabalha sobre cópias temporárias.",
            destaque=True,
        )

        cartao, layout = self.adicionar_card("Navegador e perfil")
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Navegador:"))
        self.cmb_navegador = QComboBox()
        self.cmb_navegador.currentIndexChanged.connect(self._atualizar_perfis)
        linha.addWidget(self.cmb_navegador, stretch=1)
        self.btn_detectar = QPushButton("Detectar Novamente")
        self.btn_detectar.clicked.connect(self._detectar)
        linha.addWidget(self.btn_detectar)
        layout.addLayout(linha)

        linha_perfil = QHBoxLayout()
        linha_perfil.addWidget(QLabel("Perfil:"))
        self.cmb_perfil = QComboBox()
        linha_perfil.addWidget(self.cmb_perfil, stretch=1)
        layout.addLayout(linha_perfil)

        linha_categorias = QHBoxLayout()
        self.chk_historico = QCheckBox("Histórico")
        self.chk_historico.setChecked(True)
        linha_categorias.addWidget(self.chk_historico)
        self.chk_downloads = QCheckBox("Downloads")
        self.chk_downloads.setChecked(True)
        linha_categorias.addWidget(self.chk_downloads)
        self.chk_cookies = QCheckBox("Cookies")
        self.chk_cookies.setChecked(True)
        linha_categorias.addWidget(self.chk_cookies)
        self.chk_senhas = QCheckBox("Senhas (DPAPI/NSS)")
        self.chk_senhas.setChecked(True)
        linha_categorias.addWidget(self.chk_senhas)

        linha_categorias.addWidget(QLabel("Limite por categoria:"))
        self.spin_limite = QSpinBox()
        self.spin_limite.setRange(10, 10000)
        self.spin_limite.setValue(500)
        linha_categorias.addWidget(self.spin_limite)

        self.btn_extrair = QPushButton("Extrair Artefatos")
        self.btn_extrair.clicked.connect(self._extrair)
        linha_categorias.addWidget(self.btn_extrair)
        layout.addLayout(linha_categorias)

        self.lbl_status = QLabel(
            "Selecione o navegador e o perfil. A extração usa cópias temporárias e não "
            "modifica os arquivos originais."
        )
        self.lbl_status.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        layout.addWidget(self.lbl_status)

        cartao_resultado, layout_resultado = self.adicionar_card("Artefatos extraídos")
        self.tabela = criar_tabela(
            [
                "Categoria",
                "Navegador",
                "Perfil",
                "Título / URL",
                "Usuário",
                "Valor",
                "Data",
                "Observação",
            ],
            self,
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Stretch
        )
        self.tabela.setMinimumHeight(220)
        layout_resultado.addWidget(self.tabela)

        self.txt_saida = criar_saida_texto(170, self)
        layout_resultado.addWidget(self.txt_saida)
        linha_botoes = QHBoxLayout()
        linha_botoes.addWidget(
            botao_copiar(lambda: self.txt_saida.toPlainText(), self, "Copiar Resultado")
        )
        linha_botoes.addStretch()
        layout_resultado.addLayout(linha_botoes)

        self.log = adicionar_log_painel(self, "Log da Extração de Navegador")
        self.adicionar_espaco()
        self._detectar()

    def _detectar(self) -> None:
        """Executa a detecção de navegadores em segundo plano."""
        self.btn_detectar.setEnabled(False)
        self.lbl_status.setText("Detectando navegadores e perfis...")

        def tarefa(ctx: TaskContext) -> List[NavegadorInfo]:
            ctx.log("INFO", "Procurando perfis de navegadores no usuário atual.")
            return detectar_navegadores()

        def concluiu(infos: Any) -> None:
            self.btn_detectar.setEnabled(True)
            self._navegadores = list(infos or [])
            self.cmb_navegador.blockSignals(True)
            self.cmb_navegador.clear()
            self.cmb_navegador.addItems([info.nome for info in self._navegadores])
            self.cmb_navegador.blockSignals(False)
            self._atualizar_perfis()
            if self._navegadores:
                self.lbl_status.setText(
                    f"{len(self._navegadores)} navegador(es) detectado(s)."
                )
            else:
                self.lbl_status.setText(
                    "Nenhum navegador compatível encontrado no perfil do usuário."
                )
                self.txt_saida.setPlainText(
                    "Nenhum perfil de Chrome, Edge, Brave, Vivaldi, Opera ou Firefox "
                    "foi encontrado neste usuário."
                )

        def falhou(erro: Exception) -> None:
            self.btn_detectar.setEnabled(True)
            self.lbl_status.setText("Falha ao detectar navegadores.")
            mostrar_erro(self, "Falha na detecção de navegadores", erro)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_logar=lambda nivel, msg: self.log.append_log(nivel, msg),
        )

    def _atualizar_perfis(self) -> None:
        """Atualiza a lista de perfis do navegador selecionado."""
        indice = self.cmb_navegador.currentIndex()
        self.cmb_perfil.clear()
        if indice < 0 or indice >= len(self._navegadores):
            return
        self.cmb_perfil.addItems(self._navegadores[indice].perfis)

    def _categorias_selecionadas(self) -> List[str]:
        """Lista as categorias marcadas."""
        categorias: List[str] = []
        if self.chk_historico.isChecked():
            categorias.append("Historico")
        if self.chk_downloads.isChecked():
            categorias.append("Downloads")
        if self.chk_cookies.isChecked():
            categorias.append("Cookies")
        if self.chk_senhas.isChecked():
            categorias.append("Senhas")
        return categorias

    def _extrair(self) -> None:
        """Valida o termo ético e dispara a extração."""
        if not self._navegadores:
            QMessageBox.information(
                self,
                "Nenhum navegador detectado",
                "Nenhum perfil compatível foi encontrado. Feche o navegador e clique em "
                "'Detectar Novamente'.",
            )
            return
        nome = self.cmb_navegador.currentText()
        categorias = self._categorias_selecionadas()
        if not categorias:
            QMessageBox.information(
                self, "Selecione uma categoria", "Marque ao menos um tipo de artefato."
            )
            return
        if not confirmar_termo_etico(self, "forensics.browser_extract"):
            return

        self.btn_extrair.setEnabled(False)
        self.lbl_status.setText("Extraindo artefatos de navegador...")
        limite = int(self.spin_limite.value())

        def tarefa(ctx: TaskContext) -> ResultadoNavegador:
            return extrair_navegador(nome, categorias=categorias, limite=limite, ctx=ctx)

        def concluiu(resultado: ResultadoNavegador) -> None:
            self.btn_extrair.setEnabled(True)
            self.lbl_status.setText(
                f"Extração concluída: {formatar_numero(len(resultado.itens))} item(ns)."
            )
            preencher_tabela(
                self.tabela,
                [
                    [
                        item.categoria,
                        item.navegador,
                        item.perfil,
                        item.titulo,
                        item.usuario,
                        item.valor,
                        item.data,
                        item.observacao,
                    ]
                    for item in resultado.itens
                ],
            )
            self.txt_saida.setPlainText(formatar_resultado_navegador(resultado))

        def falhou(erro: Exception) -> None:
            self.btn_extrair.setEnabled(True)
            self.lbl_status.setText("Falha na extração de navegador.")
            mensagem = str(erro)
            if isinstance(erro, DependenciaAusente):
                mensagem += f"\n\nInstale a dependência com: pip install {erro.pacote}"
            self.txt_saida.setPlainText(
                "A extração não foi concluída.\n\n"
                f"{mensagem}\n\n"
                "Feche o navegador antes de tentar novamente. Os bancos são copiados "
                "para uma pasta temporária; se o arquivo estiver bloqueado, a cópia "
                "pode falhar."
            )
            mostrar_erro(self, "Falha na extração de navegador", erro)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_progredir=lambda atual, total, msg: self.lbl_status.setText(msg),
            ao_logar=lambda nivel, msg: self.log.append_log(nivel, msg),
        )

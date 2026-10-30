"""Enumeração de nome de usuário em mais de cem sites públicos.

A verificação é feita por requisições HTTP paralelas (`concurrent.futures`) com a
biblioteca `requests`, opcionalmente acelerada por `aiohttp` quando disponível.
Cada site declara marcadores de ausência no corpo da resposta para reduzir falsos
positivos de páginas que respondem 200 mesmo quando o perfil não existe.

A base de sites é apenas uma lista de URLs públicas: nenhuma credencial é usada e
nenhum dado é enviado além do próprio nome consultado.
"""
from __future__ import annotations

import csv
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import confirmar_termo_etico, dependencia_disponivel, truncar
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    botao_copiar,
    criar_card,
    criar_saida_texto,
    criar_tabela,
    executar_assincrono,
    mostrar_erro,
    preencher_tabela,
)

_log = get_logger("osint.username_enum")

UA_PADRAO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 WinToolbox-OSINT"
)

# (nome, categoria, url com {usuario}, marcador de ausência no HTML)
_SITES_BRUTOS: List[Tuple[str, str, str, str]] = [
    # Desenvolvimento e código
    ("GitHub", "Desenvolvimento", "https://github.com/{usuario}", ""),
    ("GitLab", "Desenvolvimento", "https://gitlab.com/{usuario}", ""),
    ("Bitbucket", "Desenvolvimento", "https://bitbucket.org/{usuario}/", ""),
    ("Codeberg", "Desenvolvimento", "https://codeberg.org/{usuario}", "Not Found"),
    ("Sourcehut", "Desenvolvimento", "https://git.sr.ht/~{usuario}", "not found"),
    ("SourceForge", "Desenvolvimento", "https://sourceforge.net/u/{usuario}/profile", ""),
    ("Launchpad", "Desenvolvimento", "https://launchpad.net/~{usuario}", "not found"),
    ("Keybase", "Desenvolvimento", "https://keybase.io/{usuario}", "We couldn't find"),
    ("Keyoxide", "Desenvolvimento", "https://keyoxide.org/{usuario}", ""),
    ("npm", "Desenvolvimento", "https://www.npmjs.com/~{usuario}", ""),
    ("PyPI", "Desenvolvimento", "https://pypi.org/user/{usuario}/", ""),
    ("Docker Hub", "Desenvolvimento", "https://hub.docker.com/u/{usuario}", ""),
    ("Hugging Face", "Desenvolvimento", "https://huggingface.co/{usuario}", ""),
    ("Kaggle", "Desenvolvimento", "https://www.kaggle.com/{usuario}", "404"),
    ("Packagist", "Desenvolvimento", "https://packagist.org/users/{usuario}/", "not found"),
    ("RubyGems", "Desenvolvimento", "https://rubygems.org/profiles/{usuario}", ""),
    ("Hacker News", "Desenvolvimento", "https://news.ycombinator.com/user?id={usuario}", "No such user."),
    ("Lobsters", "Desenvolvimento", "https://lobste.rs/~{usuario}", "not found"),
    ("Slashdot", "Desenvolvimento", "https://slashdot.org/~{usuario}/", ""),
    ("Dev.to", "Desenvolvimento", "https://dev.to/{usuario}", ""),
    ("Hashnode", "Desenvolvimento", "https://hashnode.com/@{usuario}", ""),
    ("Medium", "Desenvolvimento", "https://medium.com/@{usuario}", "404"),
    ("Substack", "Desenvolvimento", "https://{usuario}.substack.com", ""),
    ("WordPress.com", "Desenvolvimento", "https://{usuario}.wordpress.com", ""),
    ("Blogger", "Desenvolvimento", "https://{usuario}.blogspot.com", ""),
    ("Wix", "Desenvolvimento", "https://{usuario}.wixsite.com", ""),
    ("Weebly", "Desenvolvimento", "https://{usuario}.weebly.com", ""),
    ("LiveJournal", "Desenvolvimento", "https://{usuario}.livejournal.com", ""),
    ("Tumblr", "Desenvolvimento", "https://{usuario}.tumblr.com", ""),
    ("GitBook", "Desenvolvimento", "https://{usuario}.gitbook.io", ""),
    ("SmugMug", "Desenvolvimento", "https://{usuario}.smugmug.com", ""),
    ("Replit", "Desenvolvimento", "https://replit.com/@{usuario}", ""),
    ("Glitch", "Desenvolvimento", "https://glitch.com/@{usuario}", ""),
    ("CodePen", "Desenvolvimento", "https://codepen.io/{usuario}", ""),
    ("JSFiddle", "Desenvolvimento", "https://jsfiddle.net/user/{usuario}/", ""),
    ("StackBlitz", "Desenvolvimento", "https://stackblitz.com/@{usuario}", ""),
    ("GitHub Gist", "Desenvolvimento", "https://gist.github.com/{usuario}", ""),
    ("Figma", "Desenvolvimento", "https://www.figma.com/@{usuario}", ""),
    ("Behance", "Desenvolvimento", "https://www.behance.net/{usuario}", ""),
    ("Dribbble", "Desenvolvimento", "https://dribbble.com/{usuario}", ""),
    ("Product Hunt", "Desenvolvimento", "https://www.producthunt.com/@{usuario}", ""),
    ("Wellfound", "Desenvolvimento", "https://wellfound.com/u/{usuario}", ""),
    ("Crunchbase", "Desenvolvimento", "https://www.crunchbase.com/person/{usuario}", ""),
    ("F6S", "Desenvolvimento", "https://www.f6s.com/{usuario}", ""),
    ("StackShare", "Desenvolvimento", "https://stackshare.io/{usuario}", ""),
    # Plataformas de programação competitiva e segurança
    ("HackerRank", "Desafios", "https://www.hackerrank.com/profile/{usuario}", ""),
    ("LeetCode", "Desafios", "https://leetcode.com/u/{usuario}/", ""),
    ("Codeforces", "Desafios", "https://codeforces.com/profile/{usuario}", ""),
    ("CodeChef", "Desafios", "https://www.codechef.com/users/{usuario}", ""),
    ("Exercism", "Desafios", "https://exercism.org/profiles/{usuario}", ""),
    ("Codewars", "Desafios", "https://www.codewars.com/users/{usuario}", ""),
    ("TopCoder", "Desafios", "https://www.topcoder.com/members/{usuario}", ""),
    ("HackerEarth", "Desafios", "https://www.hackerearth.com/@{usuario}", ""),
    ("GeeksforGeeks", "Desafios", "https://auth.geeksforgeeks.org/user/{usuario}/", ""),
    ("SPOJ", "Desafios", "https://www.spoj.com/users/{usuario}/", ""),
    ("Kattis", "Desafios", "https://open.kattis.com/users/{usuario}", ""),
    ("DMOJ", "Desafios", "https://dmoj.ca/user/{usuario}", ""),
    ("AtCoder", "Desafios", "https://atcoder.jp/users/{usuario}", ""),
    ("CodeSignal", "Desafios", "https://app.codesignal.com/profile/{usuario}", ""),
    ("HackerOne", "Segurança", "https://hackerone.com/{usuario}", ""),
    ("Bugcrowd", "Segurança", "https://bugcrowd.com/{usuario}", ""),
    ("TryHackMe", "Segurança", "https://tryhackme.com/p/{usuario}", ""),
    ("Hack The Box", "Segurança", "https://app.hackthebox.com/users/{usuario}", ""),
    # Redes sociais
    ("Reddit", "Redes sociais", "https://www.reddit.com/user/{usuario}/", "Sorry, nobody on Reddit goes by that name"),
    ("X (Twitter)", "Redes sociais", "https://x.com/{usuario}", "This account doesn"),
    ("Instagram", "Redes sociais", "https://www.instagram.com/{usuario}/", "Sorry, this page isn"),
    ("Facebook", "Redes sociais", "https://www.facebook.com/{usuario}", ""),
    ("TikTok", "Redes sociais", "https://www.tiktok.com/@{usuario}", "Couldn't find this account"),
    ("YouTube", "Redes sociais", "https://www.youtube.com/@{usuario}", "This page isn"),
    ("Pinterest", "Redes sociais", "https://www.pinterest.com/{usuario}/", "Sorry! We couldn"),
    ("Flickr", "Redes sociais", "https://www.flickr.com/people/{usuario}/", ""),
    ("Vimeo", "Redes sociais", "https://vimeo.com/{usuario}", ""),
    ("Dailymotion", "Redes sociais", "https://www.dailymotion.com/{usuario}", ""),
    ("Twitch", "Redes sociais", "https://www.twitch.tv/{usuario}", ""),
    ("Kick", "Redes sociais", "https://kick.com/{usuario}", ""),
    ("Trovo", "Redes sociais", "https://trovo.live/s/{usuario}", ""),
    ("DLive", "Redes sociais", "https://dlive.tv/{usuario}", ""),
    ("Rumble", "Redes sociais", "https://rumble.com/user/{usuario}", ""),
    ("Odysee", "Redes sociais", "https://odysee.com/@{usuario}", ""),
    ("BitChute", "Redes sociais", "https://www.bitchute.com/channel/{usuario}/", ""),
    ("Telegram", "Redes sociais", "https://t.me/{usuario}", ""),
    ("Mastodon", "Redes sociais", "https://mastodon.social/@{usuario}", ""),
    ("Bluesky", "Redes sociais", "https://bsky.app/profile/{usuario}.bsky.social", ""),
    ("Threads", "Redes sociais", "https://www.threads.net/@{usuario}", ""),
    ("VK", "Redes sociais", "https://vk.com/{usuario}", ""),
    ("OK.ru", "Redes sociais", "https://ok.ru/{usuario}", ""),
    ("Gab", "Redes sociais", "https://gab.com/{usuario}", ""),
    ("Snapchat", "Redes sociais", "https://www.snapchat.com/add/{usuario}", ""),
    ("Clubhouse", "Redes sociais", "https://www.clubhouse.com/@{usuario}", ""),
    ("Quora", "Redes sociais", "https://www.quora.com/profile/{usuario}", ""),
    ("9GAG", "Redes sociais", "https://9gag.com/u/{usuario}", ""),
    ("Imgur", "Redes sociais", "https://imgur.com/user/{usuario}", ""),
    ("Giphy", "Redes sociais", "https://giphy.com/{usuario}", ""),
    ("Tenor", "Redes sociais", "https://tenor.com/users/{usuario}", ""),
    ("VSCO", "Redes sociais", "https://vsco.co/{usuario}/gallery", ""),
    ("Coub", "Redes sociais", "https://coub.com/{usuario}", ""),
    ("LinkedIn", "Redes sociais", "https://www.linkedin.com/in/{usuario}", "Page not found"),
    ("Xing", "Redes sociais", "https://www.xing.com/profile/{usuario}", ""),
    ("About.me", "Redes sociais", "https://about.me/{usuario}", ""),
    ("Gravatar", "Redes sociais", "https://gravatar.com/{usuario}", ""),
    ("Fandom", "Redes sociais", "https://www.fandom.com/u/{usuario}", ""),
    ("Archive.org", "Redes sociais", "https://archive.org/details/@{usuario}", ""),
    # Jogos
    ("Steam", "Jogos", "https://steamcommunity.com/id/{usuario}", "The specified profile could not be found"),
    ("Roblox", "Jogos", "https://www.roblox.com/users/profile?username={usuario}", ""),
    ("itch.io", "Jogos", "https://{usuario}.itch.io/", ""),
    ("Kongregate", "Jogos", "https://www.kongregate.com/accounts/{usuario}", ""),
    ("Chess.com", "Jogos", "https://www.chess.com/member/{usuario}", ""),
    ("Lichess", "Jogos", "https://lichess.org/@{usuario}", ""),
    ("Scratch", "Jogos", "https://scratch.mit.edu/users/{usuario}/", "Sorry, we couldn"),
    ("Speedrun.com", "Jogos", "https://www.speedrun.com/user/{usuario}", ""),
    ("Backloggd", "Jogos", "https://backloggd.com/u/{usuario}/", ""),
    ("Xbox Gamertag", "Jogos", "https://xboxgamertag.com/search/{usuario}", ""),
    ("PSN Profiles", "Jogos", "https://psnprofiles.com/{usuario}", ""),
    # Criativo e mídia
    ("SoundCloud", "Criativo", "https://soundcloud.com/{usuario}", ""),
    ("Bandcamp", "Criativo", "https://bandcamp.com/{usuario}", ""),
    ("Mixcloud", "Criativo", "https://www.mixcloud.com/{usuario}/", ""),
    ("Spotify", "Criativo", "https://open.spotify.com/user/{usuario}", ""),
    ("Deezer", "Criativo", "https://www.deezer.com/profile/{usuario}", ""),
    ("Last.fm", "Criativo", "https://www.last.fm/user/{usuario}", ""),
    ("DeviantArt", "Criativo", "https://www.deviantart.com/{usuario}", ""),
    ("ArtStation", "Criativo", "https://www.artstation.com/{usuario}", ""),
    ("Unsplash", "Criativo", "https://unsplash.com/@{usuario}", ""),
    ("500px", "Criativo", "https://500px.com/p/{usuario}", ""),
    ("Patreon", "Criativo", "https://www.patreon.com/{usuario}", ""),
    ("Ko-fi", "Criativo", "https://ko-fi.com/{usuario}", ""),
    ("Buy Me a Coffee", "Criativo", "https://www.buymeacoffee.com/{usuario}", ""),
    ("Wattpad", "Criativo", "https://www.wattpad.com/user/{usuario}", ""),
    ("Archive of Our Own", "Criativo", "https://archiveofourown.org/users/{usuario}/profile", ""),
    ("LibraryThing", "Criativo", "https://www.librarything.com/profile/{usuario}", ""),
    ("Goodreads", "Criativo", "https://www.goodreads.com/{usuario}", ""),
    ("Letterboxd", "Criativo", "https://letterboxd.com/{usuario}/", ""),
    ("MyAnimeList", "Criativo", "https://myanimelist.net/profile/{usuario}", ""),
    ("AniList", "Criativo", "https://anilist.co/user/{usuario}/", ""),
    ("Trakt", "Criativo", "https://trakt.tv/users/{usuario}", ""),
    ("SlideShare", "Criativo", "https://www.slideshare.net/{usuario}", ""),
    ("Scribd", "Criativo", "https://www.scribd.com/{usuario}", ""),
    ("Issuu", "Criativo", "https://issuu.com/{usuario}", ""),
    # Comércio e serviços
    ("Etsy", "Comércio", "https://www.etsy.com/shop/{usuario}", ""),
    ("eBay", "Comércio", "https://www.ebay.com/usr/{usuario}", ""),
    ("Mercado Livre", "Comércio", "https://www.mercadolivre.com.br/perfil/{usuario}", ""),
    ("Fiverr", "Comércio", "https://www.fiverr.com/{usuario}", ""),
    ("Upwork", "Comércio", "https://www.upwork.com/freelancers/{usuario}", ""),
    ("Freelancer", "Comércio", "https://www.freelancer.com/u/{usuario}", ""),
    ("PeoplePerHour", "Comércio", "https://www.peopleperhour.com/freelancer/{usuario}", ""),
    ("Kickstarter", "Comércio", "https://www.kickstarter.com/profile/{usuario}", ""),
    ("Indiegogo", "Comércio", "https://www.indiegogo.com/individuals/{usuario}", ""),
    # Educação e outros
    ("Duolingo", "Educação", "https://www.duolingo.com/profile/{usuario}", ""),
    ("Khan Academy", "Educação", "https://www.khanacademy.org/profile/{usuario}", ""),
    ("Udemy", "Educação", "https://www.udemy.com/user/{usuario}/", ""),
    ("Skillshare", "Educação", "https://www.skillshare.com/user/{usuario}", ""),
    ("ResearchGate", "Educação", "https://www.researchgate.net/profile/{usuario}", ""),
    ("Academia.edu", "Educação", "https://independent.academia.edu/{usuario}", ""),
    ("MyFitnessPal", "Educação", "https://www.myfitnesspal.com/profile/{usuario}", ""),
    ("AllTrails", "Educação", "https://www.alltrails.com/members/{usuario}", ""),
    ("Geocaching", "Educação", "https://www.geocaching.com/profile/?u={usuario}", ""),
    ("Trello", "Educação", "https://trello.com/{usuario}", ""),
    ("Habr", "Educação", "https://habr.com/ru/users/{usuario}/", ""),
]

SITES: List[Dict[str, Any]] = [
    {
        "nome": nome,
        "categoria": categoria,
        "url": url,
        "ausente": [marcador] if marcador else [],
    }
    for nome, categoria, url, marcador in _SITES_BRUTOS
]

SITES_POPULARES = {
    "GitHub", "GitLab", "Reddit", "Instagram", "X (Twitter)", "TikTok", "YouTube",
    "Twitch", "Steam", "SoundCloud", "Medium", "Dev.to", "Pinterest", "Facebook",
    "Telegram", "Mastodon", "Bluesky", "Hacker News", "Behance", "Dribbble",
    "Patreon", "npm", "PyPI", "Hugging Face", "LinkedIn", "LeetCode", "Codeforces",
    "Kaggle", "Last.fm", "Letterboxd", "Flickr", "Vimeo", "Quora", "9GAG", "Imgur",
    "About.me", "Gravatar", "TryHackMe", "HackerOne", "Replit", "CodePen",
}

TEXTO_ETICO = (
    "A enumeração de nome de usuário cruza dados públicos de terceiros e pode "
    "revelar a presença de uma pessoa em serviços que ela não divulgou.\n\n"
    "Use somente com finalidade legítima: investigação autorizada, verificação da "
    "própria presença digital, due diligence contratada ou resposta a incidente. "
    "A Lei 13.709/2018 (LGPD) exige base legal e finalidade específica para "
    "tratar dados pessoais; a coleta em massa sem autorização pode configurar uso "
    "indevido de dados e violar os termos de serviço dos sites consultados.\n\n"
    "O WinToolbox apenas faz requisições HTTP públicas, sem contornar autenticação "
    "e sem burlar bloqueios. Os resultados podem conter falsos positivos.\n\n"
    "Você confirma que assume integral responsabilidade pelo uso?"
)

_ESTADO = threading.local()


def _sessao_http():
    """Devolve uma sessão `requests` por thread para reaproveitar conexões."""
    import requests

    sessao = getattr(_ESTADO, "sessao", None)
    if sessao is None:
        sessao = requests.Session()
        sessao.headers.update({"User-Agent": UA_PADRAO, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})
        _ESTADO.sessao = sessao
    return sessao


def aiohttp_disponivel() -> bool:
    """Indica se o motor assíncrono opcional (`aiohttp`) pode ser usado."""
    return dependencia_disponivel("aiohttp")


def normalizar_usuario(usuario: str) -> str:
    """Remove espaços, arrobas e barras do nome informado."""
    limpo = str(usuario or "").strip().lstrip("@").strip().strip("/")
    if not limpo:
        raise ValueError("Informe um nome de usuário.")
    if len(limpo) > 64:
        raise ValueError("O nome de usuário deve ter no máximo 64 caracteres.")
    if not re.fullmatch(r"[A-Za-z0-9._\-]+", limpo):
        raise ValueError(
            "Use apenas letras, números, ponto, hífen e sublinhado no nome de usuário."
        )
    return limpo


def selecionar_sites(populares: bool = False) -> List[Dict[str, Any]]:
    """Seleciona a lista completa ou apenas os sites mais populares."""
    if populares:
        return [s for s in SITES if s["nome"] in SITES_POPULARES]
    return list(SITES)


def montar_url(site: Dict[str, Any], usuario: str) -> str:
    """Monta a URL do perfil para o site indicado."""
    return site["url"].format(usuario=usuario)


def _avaliar_resposta(site: Dict[str, Any], status: int, corpo: str) -> Optional[bool]:
    """Decide se o perfil existe com base no status HTTP e nos marcadores do site."""
    if status in (404, 410):
        return False
    texto = corpo.lower()
    for marcador in site.get("ausente", []):
        if marcador.lower() in texto:
            return False
    if status in (200, 226):
        return True
    if 300 <= status < 400:
        return True
    return None


def verificar_site(site: Dict[str, Any], usuario: str, timeout: float = 8.0) -> Dict[str, Any]:
    """Consulta um site e devolve o resultado padronizado da enumeração."""
    import requests

    url = montar_url(site, usuario)
    inicio = time.perf_counter()
    resultado: Dict[str, Any] = {
        "site": site["nome"],
        "categoria": site["categoria"],
        "url": url,
        "situacao": "Indeterminado",
        "http": "-",
        "evidencia": "",
        "tempo_ms": 0,
    }
    try:
        resposta = _sessao_http().get(url, timeout=timeout, allow_redirects=True, stream=True)
        try:
            pedaco = resposta.raw.read(200_000) if resposta.raw is not None else b""
        except Exception:
            pedaco = b""
        corpo = pedaco.decode("utf-8", errors="ignore") if pedaco else ""
        achado = _avaliar_resposta(site, resposta.status_code, corpo)
        resultado["http"] = str(resposta.status_code)
        if achado is True:
            resultado["situacao"] = "Encontrado"
            resultado["evidencia"] = "Perfil respondeu com sucesso"
        elif achado is False:
            resultado["situacao"] = "Não encontrado"
            resultado["evidencia"] = (
                "Marcador de ausência na página" if resposta.status_code == 200 else "Status HTTP de ausência"
            )
        else:
            resultado["evidencia"] = f"Status HTTP {resposta.status_code} sem confirmação"
    except requests.exceptions.Timeout:
        resultado["situacao"] = "Erro"
        resultado["evidencia"] = "Tempo limite excedido"
    except requests.exceptions.SSLError:
        resultado["situacao"] = "Erro"
        resultado["evidencia"] = "Falha de TLS/SSL"
    except requests.exceptions.ConnectionError:
        resultado["situacao"] = "Erro"
        resultado["evidencia"] = "Falha de conexão"
    except Exception as exc:  # noqa: BLE001 - a lista de sites é heterogênea
        resultado["situacao"] = "Erro"
        resultado["evidencia"] = truncar(str(exc), 120)
    finally:
        resultado["tempo_ms"] = int((time.perf_counter() - inicio) * 1000)
    return resultado


def _executar_aiohttp(
    sites: Sequence[Dict[str, Any]],
    usuario: str,
    timeout: float,
    ao_progresso: Optional[Callable[[int, int, str], None]],
    deve_cancelar: Optional[Callable[[], bool]],
) -> List[Dict[str, Any]]:
    """Motor assíncrono opcional; levanta RuntimeError se `aiohttp` não existir."""
    import asyncio

    import aiohttp

    async def _consultar(sessao, site):
        url = montar_url(site, usuario)
        inicio = time.perf_counter()
        try:
            async with sessao.get(url, allow_redirects=True) as resposta:
                corpo = ""
                try:
                    corpo = (await resposta.content.read(200_000)).decode("utf-8", errors="ignore")
                except Exception:
                    corpo = ""
                achado = _avaliar_resposta(site, resposta.status, corpo)
                situacao = "Indeterminado"
                evidencia = f"Status HTTP {resposta.status} sem confirmação"
                if achado is True:
                    situacao, evidencia = "Encontrado", "Perfil respondeu com sucesso"
                elif achado is False:
                    situacao = "Não encontrado"
                    evidencia = (
                        "Marcador de ausência na página" if resposta.status == 200 else "Status HTTP de ausência"
                    )
                return {
                    "site": site["nome"],
                    "categoria": site["categoria"],
                    "url": url,
                    "situacao": situacao,
                    "http": str(resposta.status),
                    "evidencia": evidencia,
                    "tempo_ms": int((time.perf_counter() - inicio) * 1000),
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "site": site["nome"],
                "categoria": site["categoria"],
                "url": url,
                "situacao": "Erro",
                "http": "-",
                "evidencia": truncar(str(exc), 120),
                "tempo_ms": int((time.perf_counter() - inicio) * 1000),
            }

    async def _principal():
        limite = asyncio.Semaphore(25)
        total = len(sites)
        feitos = 0
        resultados: List[Dict[str, Any]] = []

        async with aiohttp.ClientSession(headers={"User-Agent": UA_PADRAO}) as sessao:
            async def _envolver(site):
                nonlocal feitos
                if deve_cancelar is not None and deve_cancelar():
                    return None
                async with limite:
                    item = await _consultar(sessao, site)
                feitos += 1
                if ao_progresso is not None:
                    ao_progresso(feitos, total, site["nome"])
                return item

            tarefas = [_envolver(site) for site in sites]
            for tarefa in asyncio.as_completed(tarefas):
                item = await tarefa
                if item is not None:
                    resultados.append(item)
        return resultados

    return asyncio.run(_principal())


def verificar_usuario(
    usuario: str,
    populares: bool = False,
    timeout: float = 8.0,
    max_workers: int = 20,
    motor: str = "threads",
    ao_progresso: Optional[Callable[[int, int, str], None]] = None,
    ao_log: Optional[Callable[[str, str], None]] = None,
    deve_cancelar: Optional[Callable[[], bool]] = None,
) -> List[Dict[str, Any]]:
    """Executa a enumeração e devolve uma lista de resultados por site.

    ``motor`` aceita ``"threads"`` (padrão, sempre disponível) ou ``"aiohttp"``.
    Quando o motor assíncrono não está instalado, cai automaticamente para threads.
    """
    nome = normalizar_usuario(usuario)
    sites = selecionar_sites(populares)
    total = len(sites)

    if ao_log is not None:
        ao_log("INFO", f"Consultando {total} site(s) para o nome '{nome}'.")

    if motor == "aiohttp":
        if aiohttp_disponivel():
            try:
                resultados = _executar_aiohttp(sites, nome, timeout, ao_progresso, deve_cancelar)
                resultados.sort(key=lambda item: (item["situacao"] != "Encontrado", item["site"].lower()))
                return resultados
            except Exception as exc:  # noqa: BLE001
                if ao_log is not None:
                    ao_log("WARN", f"Falha no motor aiohttp ({exc}); usando threads.")
        elif ao_log is not None:
            ao_log("WARN", "aiohttp não instalado; usando o motor de threads com requests.")

    resultados: List[Dict[str, Any]] = []
    feitos = 0
    with ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), 64))) as executor:
        futuros = {executor.submit(verificar_site, site, nome, timeout): site for site in sites}
        for futuro in as_completed(futuros):
            if deve_cancelar is not None and deve_cancelar():
                for pendente in futuros:
                    pendente.cancel()
                if ao_log is not None:
                    ao_log("WARN", "Consulta cancelada pelo usuário.")
                break
            site = futuros[futuro]
            try:
                resultados.append(futuro.result())
            except Exception as exc:  # noqa: BLE001
                resultados.append(
                    {
                        "site": site["nome"],
                        "categoria": site["categoria"],
                        "url": montar_url(site, nome),
                        "situacao": "Erro",
                        "http": "-",
                        "evidencia": truncar(str(exc), 120),
                        "tempo_ms": 0,
                    }
                )
            feitos += 1
            if ao_progresso is not None:
                ao_progresso(feitos, total, site["nome"])

    resultados.sort(key=lambda item: (item["situacao"] != "Encontrado", item["site"].lower()))
    return resultados


def resumir_resultados(resultados: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    """Conta resultados por situação."""
    resumo = {"Encontrado": 0, "Não encontrado": 0, "Indeterminado": 0, "Erro": 0}
    for item in resultados:
        chave = item.get("situacao", "Indeterminado")
        resumo[chave] = resumo.get(chave, 0) + 1
    return resumo


def exportar_resultados(resultados: Sequence[Dict[str, Any]], destino: Path, formato: str) -> Path:
    """Grava os resultados em JSON ou CSV e devolve o caminho final."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if formato == "csv":
        with open(destino, "w", encoding="utf-8-sig", newline="") as fp:
            escritor = csv.writer(fp, delimiter=";")
            escritor.writerow(["Site", "Categoria", "Situacao", "HTTP", "URL", "Evidencia", "TempoMs"])
            for item in resultados:
                escritor.writerow(
                    [
                        item.get("site", ""),
                        item.get("categoria", ""),
                        item.get("situacao", ""),
                        item.get("http", ""),
                        item.get("url", ""),
                        item.get("evidencia", ""),
                        item.get("tempo_ms", 0),
                    ]
                )
    else:
        destino.write_text(
            json.dumps(list(resultados), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return destino


@register
class UsernameEnumTool(Tool):
    """Ferramenta de enumeração de nome de usuário em sites públicos."""

    id = "osint.username_enum"
    name = "Enumeração de Nome de Usuário"
    category = "OSINT"
    description = (
        "Verifica, em paralelo e sem autenticação, em quais de mais de cem sites públicos "
        "o nome de usuário informado possui perfil, com marcadores para reduzir falsos positivos"
    )
    keywords = [
        "osint", "username", "nome de usuario", "enumeração", "perfil", "pegada digital",
        "reconhecimento", "sherlock", "whatsmyname", "lgpd",
    ]
    optional_deps = ["aiohttp"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return UsernameEnumView(self, parent)


class UsernameEnumView(PainelFerramenta):
    """Painel interativo da enumeração de nome de usuário."""

    def __init__(self, tool: UsernameEnumTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultados: List[Dict[str, Any]] = []
        self._executando = False

        self.adicionar_aviso(TEXTO_ETICO, destaque=True)
        self.adicionar_aviso(
            f"Base local com {len(SITES)} sites distribuídos em {len({s['categoria'] for s in SITES})} categorias. "
            "Os resultados refletem apenas o que cada site respondeu no momento da consulta.",
            destaque=False,
        )

        card_entrada, layout_entrada = self.adicionar_card("Alvo da enumeração")
        linha_alvo = QHBoxLayout()
        linha_alvo.addWidget(QLabel("Nome de usuário:"))
        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Ex.: johndoe (sem arroba)")
        self.txt_usuario.returnPressed.connect(self._executar)
        linha_alvo.addWidget(self.txt_usuario, stretch=1)
        layout_entrada.addLayout(linha_alvo)

        linha_opcoes = QHBoxLayout()
        linha_opcoes.addWidget(QLabel("Abrangência:"))
        self.cmb_abrangencia = QComboBox()
        self.cmb_abrangencia.addItem(f"Todos os {len(SITES)} sites", False)
        self.cmb_abrangencia.addItem(f"Somente populares ({len(SITES_POPULARES)})", True)
        linha_opcoes.addWidget(self.cmb_abrangencia)

        linha_opcoes.addWidget(QLabel("Motor:"))
        self.cmb_motor = QComboBox()
        self.cmb_motor.addItem("Threads (requests)", "threads")
        rotulo_aiohttp = "Assíncrono (aiohttp)" if aiohttp_disponivel() else "Assíncrono (aiohttp não instalado)"
        self.cmb_motor.addItem(rotulo_aiohttp, "aiohttp")
        self.cmb_motor.setEnabled(aiohttp_disponivel())
        linha_opcoes.addWidget(self.cmb_motor)

        linha_opcoes.addWidget(QLabel("Concorrência:"))
        self.spn_threads = QSpinBox()
        self.spn_threads.setRange(1, 64)
        self.spn_threads.setValue(20)
        linha_opcoes.addWidget(self.spn_threads)

        linha_opcoes.addWidget(QLabel("Tempo limite (s):"))
        self.spn_timeout = QSpinBox()
        self.spn_timeout.setRange(3, 60)
        self.spn_timeout.setValue(8)
        linha_opcoes.addWidget(self.spn_timeout)
        linha_opcoes.addStretch()
        layout_entrada.addLayout(linha_opcoes)

        linha_acoes = QHBoxLayout()
        self.btn_executar = QPushButton("Iniciar Enumeração")
        self.btn_executar.setProperty("class", "primary")
        self.btn_executar.clicked.connect(self._executar)
        linha_acoes.addWidget(self.btn_executar)

        self.btn_exportar_json = QPushButton("Exportar JSON...")
        self.btn_exportar_json.clicked.connect(lambda: self._exportar("json"))
        linha_acoes.addWidget(self.btn_exportar_json)

        self.btn_exportar_csv = QPushButton("Exportar CSV...")
        self.btn_exportar_csv.clicked.connect(lambda: self._exportar("csv"))
        linha_acoes.addWidget(self.btn_exportar_csv)

        self.btn_copiar = botao_copiar(self._texto_resumo, self, "Copiar resumo")
        linha_acoes.addWidget(self.btn_copiar)
        linha_acoes.addStretch()
        layout_entrada.addLayout(linha_acoes)

        self.lbl_resumo = QLabel("Nenhuma consulta executada.")
        self.lbl_resumo.setWordWrap(True)
        layout_entrada.addWidget(self.lbl_resumo)

        card_resultados, layout_resultados = self.adicionar_card("Perfis encontrados")
        self.tabela = criar_tabela(
            ["Site", "Categoria", "Situação", "HTTP", "URL", "Evidência"], self
        )
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        layout_resultados.addWidget(self.tabela)

        card_saida, layout_saida = self.adicionar_card("Resumo da execução")
        self.saida = criar_saida_texto(160, self)
        layout_saida.addWidget(self.saida)

        self.log = adicionar_log_painel(self, "Log da enumeração")
        self.adicionar_espaco()

    # ------------------------------------------------------------------ ações
    def _texto_resumo(self) -> str:
        if not self._resultados:
            return ""
        resumo = resumir_resultados(self._resultados)
        linhas = [
            f"Consulta: {self.txt_usuario.text().strip()}",
            f"Sites consultados: {len(self._resultados)}",
            f"Encontrados: {resumo.get('Encontrado', 0)}",
            f"Não encontrados: {resumo.get('Não encontrado', 0)}",
            f"Indeterminados: {resumo.get('Indeterminado', 0)}",
            f"Erros: {resumo.get('Erro', 0)}",
            "",
        ]
        for item in self._resultados:
            if item.get("situacao") == "Encontrado":
                linhas.append(f"[{item['categoria']}] {item['site']}: {item['url']}")
        return "\n".join(linhas)

    def _definir_execucao(self, ativa: bool) -> None:
        self._executando = ativa
        for botao in (self.btn_executar, self.btn_exportar_json, self.btn_exportar_csv):
            botao.setEnabled(not ativa)

    def _executar(self) -> None:
        if self._executando:
            return
        try:
            usuario = normalizar_usuario(self.txt_usuario.text())
        except ValueError as exc:
            mostrar_erro(self, "Nome de usuário inválido", exc)
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return

        populares = bool(self.cmb_abrangencia.currentData())
        motor = self.cmb_motor.currentData() or "threads"
        threads = self.spn_threads.value()
        timeout = float(self.spn_timeout.value())

        self._definir_execucao(True)
        self.lbl_resumo.setText(f"Consultando sites para '{usuario}'...")
        self.tabela.setRowCount(0)
        self.saida.clear()
        self.log.append_log("INFO", f"Iniciando enumeração de '{usuario}'.")

        def tarefa(ctx):
            return verificar_usuario(
                usuario,
                populares=populares,
                timeout=timeout,
                max_workers=threads,
                motor=motor,
                ao_progresso=lambda feitos, total, site: ctx.progress(feitos, total, f"Consultando {site}"),
                ao_log=ctx.log,
                deve_cancelar=ctx.cancelled,
            )

        def concluiu(resultados) -> None:
            self._definir_execucao(False)
            self._resultados = list(resultados or [])
            self._preencher()
            encontrados = sum(1 for item in self._resultados if item.get("situacao") == "Encontrado")
            self.lbl_resumo.setText(
                f"{len(self._resultados)} site(s) consultado(s); {encontrados} perfil(is) encontrado(s)."
            )
            self.log.append_log("INFO", f"Enumeração concluída: {encontrados} encontrado(s).")

        def falhou(erro: Exception) -> None:
            self._definir_execucao(False)
            self.lbl_resumo.setText("Falha na execução da enumeração.")
            self.log.append_log("ERROR", str(erro))
            mostrar_erro(self, "Falha na enumeração", erro)

        executar_assincrono(self, tarefa, concluiu, falhou)

    def _preencher(self) -> None:
        linhas: List[List[Any]] = []
        for item in self._resultados:
            linhas.append(
                [
                    item.get("site", ""),
                    item.get("categoria", ""),
                    item.get("situacao", ""),
                    item.get("http", ""),
                    item.get("url", ""),
                    item.get("evidencia", ""),
                ]
            )
        preencher_tabela(self.tabela, linhas)
        self.saida.setPlainText(self._texto_resumo())

    def _exportar(self, formato: str) -> None:
        if not self._resultados:
            mostrar_erro(self, "Nada para exportar", "Execute uma enumeração antes de exportar.")
            return
        sufixo = "json" if formato == "json" else "csv"
        filtro = "JSON (*.json)" if formato == "json" else "CSV (*.csv)"
        sugestao = f"username_{self.txt_usuario.text().strip() or 'resultado'}.{sufixo}"
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar resultados", sugestao, filtro)
        if not destino:
            return
        try:
            final = exportar_resultados(self._resultados, Path(destino), sufixo)
            self.log.append_log("INFO", f"Resultados gravados em {final}.")
            self.lbl_resumo.setText(f"Resultados exportados para {final}.")
        except OSError as exc:
            mostrar_erro(self, "Falha ao exportar", exc)

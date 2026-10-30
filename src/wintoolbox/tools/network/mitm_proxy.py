"""Ferramenta: Proxy de interceptação HTTP/HTTPS (MITM) para diagnóstico.

Dois modos de operação:

* ``mitmproxy``: sobe o DumpMaster em 127.0.0.1 na porta escolhida (8080 por
  padrão), intercepta HTTP/HTTPS com o certificado do mitmproxy e permite
  reescrita de URL e exportação em HAR. Depende de ``pip install mitmproxy``.
* ``Proxy HTTP nativo``: proxy de diagnóstico sem dependências externas, que
  encaminha apenas requisições HTTP simples e recusa túneis HTTPS. Serve para
  validar configuração de cliente, regras de reescrita e conectividade quando o
  mitmproxy não está instalado.

A interface nunca importa mitmproxy no carregamento do módulo: a ausência da
dependência é tratada na hora de iniciar, com oferta explícita do modo nativo.
"""
from __future__ import annotations

import asyncio
import json
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlsplit

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import (
    DependenciaAusente,
    aviso_dependencia,
    confirmar_termo_etico,
    dependencia_disponivel,
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

TEXTO_ETICO = (
    "Um proxy de interceptação recebe e pode alterar todo o tráfego HTTP/HTTPS "
    "dos clientes configurados para usá-lo, incluindo cookies, tokens e dados "
    "pessoais. Para HTTPS, o cliente precisa confiar no certificado gerado pelo "
    "mitmproxy.\n\n"
    "Configure apenas dispositivos que você administra e para os quais possui "
    "autorização expressa e por escrito do responsável, delimitando o período e "
    "os usuários afetados. Remova o certificado e o proxy ao terminar.\n\n"
    "A interceptação não autorizada de comunicações é crime previsto na Lei "
    "12.737/2012 (art. 154-A do Código Penal) e pode violar a Lei 13.709/2018 "
    "(LGPD).\n\n"
    "Você declara possuir autorização por escrito e assume integral "
    "responsabilidade pela interceptação?"
)

MAX_FLUXOS = 2000
MAX_EXIBICAO = 500
MAX_CORPO_NATIVO = 8 * 1024 * 1024
TEMPO_LIMITE_NATIVO = 15


class _SinaisProxy(QObject):
    """Sinais emitidos pelas threads do mitmproxy ou do proxy nativo."""

    fluxo = Signal(object)


def _compilar_regras(regras: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Valida expressões regulares e devolve a lista pronta para uso."""
    compiladas: List[Tuple[str, str]] = []
    for padrao, substituto in regras:
        texto = str(padrao or "").strip()
        if not texto:
            continue
        try:
            re.compile(texto)
        except re.error as exc:
            raise ValueError(f"Expressão regular inválida '{texto}': {exc}") from exc
        compiladas.append((texto, str(substituto or "")))
    return compiladas


def _aplicar_regras(url: str, regras: Tuple[Tuple[str, str], ...] | List[Tuple[str, str]]) -> str:
    """Aplica as regras de reescrita sobre a URL, ignorando padrões inválidos."""
    resultado = str(url or "")
    for padrao, substituto in regras:
        try:
            resultado = re.sub(padrao, substituto, resultado)
        except re.error:
            continue
    return resultado


class _AddonMitm:
    """Addon do mitmproxy por duck typing, sem importar mitmproxy no topo."""

    def __init__(
        self, sinais: _SinaisProxy, regras: List[Tuple[str, str]]
    ) -> None:
        self._sinais = sinais
        self._regras = tuple(regras)
        self._inicios: Dict[int, float] = {}

    def request(self, flow: Any) -> None:
        try:
            self._inicios[id(flow)] = time.perf_counter()
            self._reescrever(flow)
        except Exception:
            pass

    def response(self, flow: Any) -> None:
        try:
            self._registrar(flow)
        except Exception:
            pass

    def error(self, flow: Any) -> None:
        try:
            self._registrar(flow, erro="Falha de conexão")
        except Exception:
            pass

    def _reescrever(self, flow: Any) -> None:
        """Reescreve esquema, host, porta e caminho da requisição."""
        original = str(flow.request.pretty_url)
        nova = _aplicar_regras(original, self._regras)
        if nova == original:
            return
        partes = urlsplit(nova)
        if partes.scheme in ("http", "https"):
            flow.request.scheme = partes.scheme
        if partes.hostname:
            flow.request.host = partes.hostname
        if partes.port:
            flow.request.port = partes.port
        caminho = partes.path or "/"
        if partes.query:
            caminho = f"{caminho}?{partes.query}"
        flow.request.path = caminho

    def _registrar(self, flow: Any, erro: Optional[str] = None) -> None:
        requisicao = flow.request
        resposta = getattr(flow, "response", None)
        url = str(requisicao.pretty_url)
        partes = urlsplit(url)
        inicio = float(getattr(requisicao, "timestamp_start", 0.0) or time.time())
        relogio = self._inicios.pop(id(flow), None)
        duracao = (time.perf_counter() - relogio) * 1000.0 if relogio else 0.0

        cabecalhos_requisicao = [[str(chave), str(valor)] for chave, valor in requisicao.headers.items()]
        cabecalhos_resposta: List[List[str]] = []
        status = 0
        tipo = ""
        corpo = b""
        if resposta is not None:
            try:
                status = int(resposta.status_code)
            except (TypeError, ValueError):
                status = 0
            try:
                cabecalhos_resposta = [
                    [str(chave), str(valor)] for chave, valor in resposta.headers.items()
                ]
                tipo = str(resposta.headers.get("content-type", ""))
            except Exception:
                cabecalhos_resposta = []
            try:
                corpo = bytes(resposta.content or b"")
            except Exception:
                corpo = b""

        detalhe = [
            f"{requisicao.method} {url}",
            f"Status: {status}" if status else "Status: sem resposta",
            "",
            "Cabeçalhos da requisição:",
        ]
        detalhe.extend(f"  {chave}: {valor}" for chave, valor in cabecalhos_requisicao)
        if cabecalhos_resposta:
            detalhe.append("")
            detalhe.append("Cabeçalhos da resposta:")
            detalhe.extend(f"  {chave}: {valor}" for chave, valor in cabecalhos_resposta)
        if corpo:
            detalhe.append("")
            detalhe.append("Prévia do corpo:")
            detalhe.append(corpo[:600].decode("utf-8", errors="replace"))
        if erro:
            detalhe.append("")
            detalhe.append(erro)

        self._sinais.fluxo.emit(
            {
                "hora": time.strftime("%H:%M:%S"),
                "inicio": inicio,
                "metodo": str(requisicao.method),
                "host": str(partes.hostname or ""),
                "caminho": (partes.path or "/")
                + (f"?{partes.query}" if partes.query else ""),
                "url": url,
                "status": status,
                "tipo": tipo,
                "tamanho": len(corpo),
                "duracao": duracao,
                "detalhe": "\n".join(detalhe),
                "previa": corpo[:600].decode("utf-8", errors="replace"),
                "cabecalhos_requisicao": cabecalhos_requisicao,
                "cabecalhos_resposta": cabecalhos_resposta,
                "origem": "mitmproxy",
            }
        )


class _ProxyHttpNativo(BaseHTTPRequestHandler):
    """Proxy HTTP de diagnóstico: encaminha requisições e recusa túneis HTTPS."""

    protocol_version = "HTTP/1.1"
    sinais: Any = None
    regras: Tuple[Tuple[str, str], ...] = ()
    tempo_limite = TEMPO_LIMITE_NATIVO

    def log_message(self, formato: str, *args: Any) -> None:
        """Silencia o log padrão: os fluxos aparecem na tabela da interface."""
        return

    # ------------------------------------------------------------- métodos
    def do_GET(self) -> None:  # noqa: N802 (assinatura http.server)
        self._encaminhar()

    def do_POST(self) -> None:  # noqa: N802
        self._encaminhar()

    def do_PUT(self) -> None:  # noqa: N802
        self._encaminhar()

    def do_PATCH(self) -> None:  # noqa: N802
        self._encaminhar()

    def do_DELETE(self) -> None:  # noqa: N802
        self._encaminhar()

    def do_HEAD(self) -> None:  # noqa: N802
        self._encaminhar()

    def do_CONNECT(self) -> None:  # noqa: N802
        corpo = (
            "Este modo de diagnóstico não intercepta HTTPS.\n"
            "Use o modo mitmproxy para inspecionar tráfego TLS com um "
            "certificado próprio.\n"
        ).encode("utf-8")
        try:
            self.send_response(501, "HTTPS não interceptado")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self._registrar(
            "CONNECT",
            self.path,
            501,
            "text/plain; charset=utf-8",
            len(corpo),
            "Túnel HTTPS recusado pelo modo nativo.",
        )

    # ------------------------------------------------------------ encaminhar
    def _encaminhar(self) -> None:
        url = str(self.path or "")
        if url.lower().startswith("https://"):
            self._recusar_https(url)
            return
        if not url.lower().startswith("http://"):
            self.send_error(400, "Use este proxy com uma URL absoluta http://...")
            return

        url = _aplicar_regras(url, self.regras)
        corpo_entrada = b""
        if self.command in ("POST", "PUT", "PATCH"):
            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                tamanho = 0
            if tamanho > 0:
                corpo_entrada = self.rfile.read(min(tamanho, MAX_CORPO_NATIVO))

        cabecalhos: Dict[str, str] = {}
        for chave, valor in self.headers.items():
            if chave.lower() in (
                "proxy-connection",
                "proxy-authorization",
                "connection",
                "host",
                "content-length",
                "accept-encoding",
            ):
                continue
            cabecalhos[chave] = valor

        requisicao = urllib.request.Request(
            url, data=corpo_entrada or None, headers=cabecalhos, method=self.command
        )
        inicio = time.perf_counter()
        try:
            with urllib.request.urlopen(requisicao, timeout=self.tempo_limite) as resposta:
                status = int(resposta.status)
                motivo = resposta.reason
                cabecalhos_resposta = list(resposta.headers.items())
                dados = resposta.read(MAX_CORPO_NATIVO)
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            motivo = exc.reason
            cabecalhos_resposta = list(exc.headers.items()) if exc.headers else []
            dados = exc.read(MAX_CORPO_NATIVO)
        except Exception as exc:
            corpo_erro = f"Falha ao encaminhar a requisição: {exc}".encode(
                "utf-8", errors="replace"
            )
            try:
                self.send_response(502, "Falha no proxy")
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo_erro)))
                self.end_headers()
                self.wfile.write(corpo_erro)
            except (BrokenPipeError, ConnectionResetError):
                pass
            self._registrar(
                self.command,
                url,
                502,
                "text/plain; charset=utf-8",
                len(corpo_erro),
                f"Erro ao encaminhar: {exc}",
                (time.perf_counter() - inicio) * 1000.0,
            )
            return

        tipo = next(
            (valor for chave, valor in cabecalhos_resposta if chave.lower() == "content-type"),
            "",
        )
        try:
            self.send_response(status, motivo)
            for chave, valor in cabecalhos_resposta:
                if chave.lower() in ("connection", "transfer-encoding", "content-length"):
                    continue
                self.send_header(chave, valor)
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(dados)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

        self._registrar(
            self.command,
            url,
            status,
            tipo,
            len(dados),
            self._montar_detalhe(url, status, cabecalhos_resposta, dados),
            (time.perf_counter() - inicio) * 1000.0,
            dados[:600].decode("utf-8", errors="replace"),
        )

    def _recusar_https(self, url: str) -> None:
        corpo = (
            "O modo nativo de diagnóstico não intercepta HTTPS. "
            "Configure o cliente com o modo mitmproxy.\n"
        ).encode("utf-8")
        try:
            self.send_response(501, "HTTPS não interceptado")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self._registrar(
            self.command, url, 501, "text/plain; charset=utf-8", len(corpo),
            "URL HTTPS recusada pelo modo nativo.",
        )

    def _montar_detalhe(
        self,
        url: str,
        status: int,
        cabecalhos_resposta: List[Tuple[str, str]],
        dados: bytes,
    ) -> str:
        linhas = [
            f"{self.command} {url}",
            f"Status: {status}",
            "",
            "Cabeçalhos da requisição:",
        ]
        linhas.extend(f"  {chave}: {valor}" for chave, valor in self.headers.items())
        if cabecalhos_resposta:
            linhas.append("")
            linhas.append("Cabeçalhos da resposta:")
            linhas.extend(f"  {chave}: {valor}" for chave, valor in cabecalhos_resposta)
        if dados:
            linhas.append("")
            linhas.append("Prévia do corpo:")
            linhas.append(dados[:600].decode("utf-8", errors="replace"))
        return "\n".join(linhas)

    def _registrar(
        self,
        metodo: str,
        url: str,
        status: int,
        tipo: str,
        tamanho: int,
        detalhe: str,
        duracao: float = 0.0,
        previa: str = "",
    ) -> None:
        sinais = self.sinais
        if sinais is None:
            return
        partes = urlsplit(url if url.lower().startswith("http") else f"http://{url}")
        sinais.fluxo.emit(
            {
                "hora": time.strftime("%H:%M:%S"),
                "inicio": time.time(),
                "metodo": str(metodo),
                "host": str(partes.hostname or ""),
                "caminho": (partes.path or "/")
                + (f"?{partes.query}" if partes.query else ""),
                "url": str(url),
                "status": status,
                "tipo": tipo,
                "tamanho": tamanho,
                "duracao": duracao,
                "detalhe": detalhe,
                "previa": previa,
                "cabecalhos_requisicao": [[str(k), str(v)] for k, v in self.headers.items()],
                "cabecalhos_resposta": [],
                "origem": "nativo",
            }
        )


def _criar_handler(sinais: _SinaisProxy, regras: List[Tuple[str, str]]) -> type:
    """Cria a classe do handler já ligada aos sinais e às regras da sessão."""
    return type(
        "HandlerProxyNativo",
        (_ProxyHttpNativo,),
        {"sinais": sinais, "regras": tuple(regras)},
    )


class _ServidorProxyNativo(ThreadingHTTPServer):
    """Servidor do modo nativo que não polui o console com desconexões de cliente."""

    def handle_error(self, request: Any, client_address: Any) -> None:
        import sys

        tipo = sys.exc_info()[0]
        if tipo in (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return
        super().handle_error(request, client_address)


def _tarefa_proxy_nativo(
    porta: int,
    regras: List[Tuple[str, str]],
    sinais: _SinaisProxy,
    parar: threading.Event,
    ctx: Any,
) -> Dict[str, Any]:
    """Sobe o proxy HTTP nativo e atende conexões até a parada solicitada."""
    servidor = _ServidorProxyNativo(
        ("127.0.0.1", porta), _criar_handler(sinais, regras)
    )
    servidor.daemon_threads = True
    servidor.timeout = 0.25
    ctx.log("INFO", f"Proxy HTTP nativo escutando em 127.0.0.1:{porta}.")
    try:
        while not parar.is_set() and not ctx.cancelled():
            servidor.handle_request()
    finally:
        servidor.server_close()
    return {"modo": "nativo", "porta": porta}


def _tarefa_mitm(
    porta: int,
    regras: List[Tuple[str, str]],
    sinais: _SinaisProxy,
    parar: threading.Event,
    ctx: Any,
) -> Dict[str, Any]:
    """Executa o DumpMaster do mitmproxy em um laço asyncio próprio."""
    try:
        from mitmproxy import options
        from mitmproxy.tools.dump import DumpMaster
    except ImportError as exc:
        raise DependenciaAusente("mitmproxy", "mitmproxy", "mitmproxy") from exc

    addon = _AddonMitm(sinais, regras)

    async def principal() -> None:
        opcoes = options.Options(listen_host="127.0.0.1", listen_port=porta)
        try:
            mestre = DumpMaster(opcoes, with_termlog=False, with_dumper=False)
        except TypeError:
            mestre = DumpMaster(opcoes)
        mestre.addons.add(addon)
        ctx.log("INFO", f"mitmproxy escutando em 127.0.0.1:{porta}.")

        async def vigiar() -> None:
            while not parar.is_set() and not ctx.cancelled():
                await asyncio.sleep(0.2)
            mestre.shutdown()

        vigia = asyncio.create_task(vigiar())
        try:
            await mestre.run()
        finally:
            vigia.cancel()

    laco = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(laco)
        laco.run_until_complete(principal())
    finally:
        try:
            laco.run_until_complete(laco.shutdown_asyncgens())
        except Exception:
            pass
        laco.close()
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass
    return {"modo": "mitmproxy", "porta": porta}


def _montar_har(fluxos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Converte os fluxos capturados no formato HAR 1.2."""
    entradas: List[Dict[str, Any]] = []
    for fluxo in fluxos:
        inicio = float(fluxo.get("inicio") or time.time())
        duracao = float(fluxo.get("duracao") or 0.0)
        url = str(fluxo.get("url") or "")
        consulta = parse_qsl(urlsplit(url).query, keep_blank_values=True)
        entradas.append(
            {
                "startedDateTime": datetime.fromtimestamp(
                    inicio, tz=timezone.utc
                ).isoformat().replace("+00:00", "Z"),
                "time": round(duracao, 3),
                "request": {
                    "method": str(fluxo.get("metodo") or "GET"),
                    "url": url,
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": str(chave), "value": str(valor)}
                        for chave, valor in fluxo.get("cabecalhos_requisicao", [])
                    ],
                    "queryString": [
                        {"name": str(nome), "value": str(valor)}
                        for nome, valor in consulta
                    ],
                    "cookies": [],
                    "headersSize": -1,
                    "bodySize": -1,
                },
                "response": {
                    "status": int(fluxo.get("status") or 0),
                    "statusText": "",
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": str(chave), "value": str(valor)}
                        for chave, valor in fluxo.get("cabecalhos_resposta", [])
                    ],
                    "cookies": [],
                    "content": {
                        "size": int(fluxo.get("tamanho") or 0),
                        "mimeType": str(fluxo.get("tipo") or ""),
                        "text": str(fluxo.get("previa") or ""),
                    },
                    "redirectURL": "",
                    "headersSize": -1,
                    "bodySize": int(fluxo.get("tamanho") or 0),
                },
                "cache": {},
                "timings": {
                    "send": 0,
                    "wait": round(duracao, 3),
                    "receive": 0,
                },
            }
        )
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "WinToolbox", "version": "1.0"},
            "pages": [],
            "entries": entradas,
        }
    }


@register
class MitmProxyTool(Tool):
    """Ferramenta de proxy de interceptação HTTP/HTTPS."""

    id = "network.mitm_proxy"
    name = "Proxy de Interceptação MITM"
    category = "Rede e Internet"
    description = (
        "mitmproxy em 127.0.0.1:8080 com tabela de fluxos, filtro, reescrita de "
        "URL e exportação HAR; inclui proxy HTTP nativo de diagnóstico quando o "
        "mitmproxy não está instalado"
    )
    keywords = [
        "mitm",
        "proxy",
        "interceptação",
        "https",
        "har",
        "mitmproxy",
        "reescrita",
        "diagnóstico",
    ]
    requires_admin = False
    optional_deps = ["mitmproxy"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return MitmProxyView(self, parent)


class MitmProxyView(PainelFerramenta):
    """Página interativa do proxy de interceptação."""

    def __init__(self, tool: MitmProxyTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self.sinais = _SinaisProxy(self)
        self._parar = threading.Event()
        self._executando = False
        self._fluxos: List[Dict[str, Any]] = []
        self._visiveis: List[Dict[str, Any]] = []
        self._montar_interface()
        self.sinais.fluxo.connect(self._ao_fluxo)

    # ------------------------------------------------------------------ UI
    def _montar_interface(self) -> None:
        tem_mitmproxy = dependencia_disponivel("mitmproxy")
        if tem_mitmproxy:
            self.adicionar(
                criar_aviso(
                    "O modo mitmproxy intercepta HTTP e HTTPS. Para inspecionar TLS, "
                    "o cliente precisa confiar no certificado do mitmproxy "
                    "(http://mitm.it). Instale-o apenas em dispositivos sob sua "
                    "responsabilidade e remova-o ao final do teste.",
                    self,
                    destaque=True,
                )
            )
        else:
            self.adicionar(
                criar_aviso(
                    "mitmproxy não está instalado. O modo 'mitmproxy' exige "
                    "'pip install mitmproxy' e é o único que intercepta HTTPS. O "
                    "modo 'Proxy HTTP nativo' funciona sem dependências, registra e "
                    "encaminha somente requisições HTTP e recusa túneis HTTPS: ideal "
                    "para diagnóstico de configuração, sem interceptar tráfego "
                    "criptografado.",
                    self,
                    destaque=True,
                )
            )

        cartao_servidor, layout_servidor = criar_card("Servidor", self)
        self.adicionar(cartao_servidor)
        linha_modo = QHBoxLayout()
        linha_modo.addWidget(QLabel("Modo:"))
        self.cmb_modo = QComboBox()
        self.cmb_modo.addItem("mitmproxy (intercepta HTTP e HTTPS)", "mitmproxy")
        self.cmb_modo.addItem("Proxy HTTP nativo (diagnóstico, sem HTTPS)", "nativo")
        if not tem_mitmproxy:
            self.cmb_modo.setCurrentIndex(1)
        linha_modo.addWidget(self.cmb_modo, stretch=1)
        layout_servidor.addLayout(linha_modo)

        linha_endereco = QHBoxLayout()
        linha_endereco.addWidget(QLabel("Endereço de escuta:"))
        lbl_endereco = QLabel("127.0.0.1")
        lbl_endereco.setStyleSheet("font-weight: 600;")
        linha_endereco.addWidget(lbl_endereco)
        linha_endereco.addSpacing(16)
        linha_endereco.addWidget(QLabel("Porta:"))
        self.spin_porta = QSpinBox()
        self.spin_porta.setRange(1024, 65535)
        self.spin_porta.setValue(8080)
        linha_endereco.addWidget(self.spin_porta)
        linha_endereco.addStretch()
        layout_servidor.addLayout(linha_endereco)

        linha_controle = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar proxy")
        self.btn_iniciar.setProperty("class", "primary")
        self.btn_iniciar.clicked.connect(self._iniciar)
        linha_controle.addWidget(self.btn_iniciar)

        self.btn_parar = QPushButton("Parar proxy")
        self.btn_parar.setEnabled(False)
        self.btn_parar.clicked.connect(self._parar_proxy)
        linha_controle.addWidget(self.btn_parar)
        linha_controle.addStretch()
        layout_servidor.addLayout(linha_controle)

        self.lbl_status = QLabel(
            "Configure o cliente para usar 127.0.0.1 na porta escolhida e inicie o proxy."
        )
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout_servidor.addWidget(self.lbl_status)

        cartao_regras, layout_regras = self.adicionar_card("Regras de reescrita de URL")
        self.tabela_regras = criar_tabela(["Padrão (regex)", "Substituição"], self)
        self.tabela_regras.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        cabecalho_regras = self.tabela_regras.horizontalHeader()
        cabecalho_regras.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cabecalho_regras.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabela_regras.setMinimumHeight(110)
        layout_regras.addWidget(self.tabela_regras)

        linha_regras = QHBoxLayout()
        self.btn_adicionar_regra = QPushButton("Adicionar regra")
        self.btn_adicionar_regra.clicked.connect(self._adicionar_regra)
        linha_regras.addWidget(self.btn_adicionar_regra)
        self.btn_remover_regra = QPushButton("Remover selecionada")
        self.btn_remover_regra.clicked.connect(self._remover_regra)
        linha_regras.addWidget(self.btn_remover_regra)
        linha_regras.addStretch()
        layout_regras.addLayout(linha_regras)
        dica = QLabel(
            "As regras são aplicadas sobre a URL completa antes do encaminhamento, "
            "nos dois modos. Exemplo: https://antigo\\.local/ -> https://novo.local/"
        )
        dica.setProperty("class", "secondary")
        dica.setWordWrap(True)
        layout_regras.addWidget(dica)

        cartao_fluxos, layout_fluxos = self.adicionar_card("Fluxos observados")
        linha_filtro = QHBoxLayout()
        linha_filtro.addWidget(QLabel("Filtro:"))
        self.txt_filtro = QLineEdit()
        self.txt_filtro.setPlaceholderText("Filtra por método, host ou caminho")
        self.txt_filtro.textChanged.connect(self._reconstruir_tabela)
        linha_filtro.addWidget(self.txt_filtro, stretch=1)
        layout_fluxos.addLayout(linha_filtro)

        self.tabela = criar_tabela(
            ["Hora", "Método", "Host", "Caminho", "Status", "Tipo", "Tamanho"], self
        )
        cabecalho = self.tabela.horizontalHeader()
        for coluna in (0, 1, 4, 6):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        cabecalho.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.setMinimumHeight(240)
        self.tabela.cellClicked.connect(self._mostrar_fluxo)
        layout_fluxos.addWidget(self.tabela)

        linha_fluxos = QHBoxLayout()
        self.btn_exportar = QPushButton("Exportar HAR")
        self.btn_exportar.clicked.connect(self._exportar_har)
        linha_fluxos.addWidget(self.btn_exportar)
        self.btn_limpar = QPushButton("Limpar fluxos")
        self.btn_limpar.clicked.connect(self._limpar_fluxos)
        linha_fluxos.addWidget(self.btn_limpar)
        linha_fluxos.addStretch()
        self.lbl_contagem = QLabel("0 fluxo(s)")
        self.lbl_contagem.setProperty("class", "secondary")
        linha_fluxos.addWidget(self.lbl_contagem)
        layout_fluxos.addLayout(linha_fluxos)

        cartao_detalhes, layout_detalhes = self.adicionar_card("Detalhes do fluxo")
        self.txt_detalhes = criar_saida_texto(170, self)
        layout_detalhes.addWidget(self.txt_detalhes)
        linha_detalhes = QHBoxLayout()
        linha_detalhes.addWidget(
            botao_copiar(lambda: self.txt_detalhes.toPlainText(), self, "Copiar detalhes")
        )
        linha_detalhes.addStretch()
        layout_detalhes.addLayout(linha_detalhes)

        self.log_panel = adicionar_log_painel(self, "Log do proxy")
        self._definir_ocupado(False)

    def _adicionar_regra(self) -> None:
        linha = self.tabela_regras.rowCount()
        self.tabela_regras.insertRow(linha)
        self.tabela_regras.setItem(linha, 0, QTableWidgetItem(""))
        self.tabela_regras.setItem(linha, 1, QTableWidgetItem(""))

    def _remover_regra(self) -> None:
        linha = self.tabela_regras.currentRow()
        if linha < 0:
            self.lbl_status.setText("Selecione uma regra de reescrita para remover.")
            return
        self.tabela_regras.removeRow(linha)

    def _coletar_regras(self) -> List[Tuple[str, str]]:
        """Lê e valida as regras na thread principal."""
        regras: List[Tuple[str, str]] = []
        for linha in range(self.tabela_regras.rowCount()):
            item_padrao = self.tabela_regras.item(linha, 0)
            item_substituto = self.tabela_regras.item(linha, 1)
            padrao = (item_padrao.text() if item_padrao else "").strip()
            substituto = (item_substituto.text() if item_substituto else "").strip()
            if not padrao:
                continue
            regras.append((padrao, substituto))
        return _compilar_regras(regras)

    def _definir_ocupado(self, ocupado: bool) -> None:
        self._executando = ocupado
        self.btn_iniciar.setEnabled(not ocupado)
        self.btn_parar.setEnabled(ocupado)
        self.cmb_modo.setEnabled(not ocupado)
        self.spin_porta.setEnabled(not ocupado)
        self.tabela_regras.setEnabled(not ocupado)
        self.btn_adicionar_regra.setEnabled(not ocupado)
        self.btn_remover_regra.setEnabled(not ocupado)
        self.btn_exportar.setEnabled(not ocupado)

    # -------------------------------------------------------------- servidor
    def _iniciar(self) -> None:
        if self._executando:
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return
        try:
            regras = self._coletar_regras()
        except ValueError as exc:
            mostrar_erro(self, "Regras inválidas", exc)
            return

        modo = str(self.cmb_modo.currentData() or "mitmproxy")
        if modo == "mitmproxy" and not dependencia_disponivel("mitmproxy"):
            aviso_dependencia(
                self, DependenciaAusente("mitmproxy", "mitmproxy", "mitmproxy")
            )
            resposta = QMessageBox.question(
                self,
                "Modo alternativo",
                "O mitmproxy não está instalado. Deseja iniciar o proxy HTTP nativo "
                "de diagnóstico?\n\nEle registra e encaminha somente requisições "
                "HTTP e não intercepta HTTPS.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if resposta != QMessageBox.StandardButton.Yes:
                self.log_panel.append_log(
                    "AVISO", "Início cancelado: mitmproxy não está instalado."
                )
                return
            self.cmb_modo.setCurrentIndex(1)
            modo = "nativo"

        porta = int(self.spin_porta.value())
        self._parar.clear()
        self._definir_ocupado(True)
        rotulo = "mitmproxy" if modo == "mitmproxy" else "proxy HTTP nativo"
        self.lbl_status.setText(f"Iniciando {rotulo} em 127.0.0.1:{porta}...")
        self.log_panel.append_log(
            "INFO",
            f"Iniciando {rotulo} em 127.0.0.1:{porta} com {len(regras)} regra(s) "
            "de reescrita.",
        )

        def tarefa(ctx) -> Dict[str, Any]:
            if modo == "mitmproxy":
                return _tarefa_mitm(porta, regras, self.sinais, self._parar, ctx)
            return _tarefa_proxy_nativo(porta, regras, self.sinais, self._parar, ctx)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._proxy_encerrado,
            ao_falhar=self._falhou,
            ao_logar=self.log_panel.append_log,
        )

    def _parar_proxy(self) -> None:
        if not self._executando:
            return
        self._parar.set()
        self.runner.cancel_current()
        self.btn_parar.setEnabled(False)
        self.lbl_status.setText("Encerrando o proxy e fechando a porta de escuta...")

    def _proxy_encerrado(self, resultado: Dict[str, Any]) -> None:
        self._definir_ocupado(False)
        modo = "mitmproxy" if resultado.get("modo") == "mitmproxy" else "proxy HTTP nativo"
        self.lbl_status.setText(f"{modo.capitalize()} encerrado.")
        self.log_panel.append_log("INFO", f"{modo.capitalize()} encerrado.")

    def _falhou(self, erro: Exception) -> None:
        self._definir_ocupado(False)
        self.lbl_status.setText("O proxy não foi iniciado.")
        texto = str(erro)
        self.log_panel.append_log("ERRO", texto)
        if "Esta ferramenta requer" in texto:
            aviso_dependencia(self, erro)
        else:
            mostrar_erro(self, "Falha no proxy", texto)

    # ---------------------------------------------------------------- fluxos
    def _ao_fluxo(self, dados: Dict[str, Any]) -> None:
        self._fluxos.append(dados)
        if len(self._fluxos) > MAX_FLUXOS:
            self._fluxos.pop(0)
        self._reconstruir_tabela()
        if not self._executando:
            self.lbl_status.setText(
                f"Fluxo recebido: {dados.get('metodo')} {dados.get('host')}"
            )

    def _reconstruir_tabela(self) -> None:
        filtro = self.txt_filtro.text().strip().lower()
        if filtro:
            visiveis = [
                fluxo
                for fluxo in self._fluxos
                if filtro
                in (
                    f"{fluxo.get('metodo', '')} {fluxo.get('host', '')} "
                    f"{fluxo.get('caminho', '')} {fluxo.get('url', '')}"
                ).lower()
            ]
        else:
            visiveis = list(self._fluxos)
        if len(visiveis) > MAX_EXIBICAO:
            visiveis = visiveis[-MAX_EXIBICAO:]
        self._visiveis = visiveis
        preencher_tabela(
            self.tabela,
            [
                [
                    fluxo.get("hora", ""),
                    fluxo.get("metodo", ""),
                    fluxo.get("host", ""),
                    fluxo.get("caminho", ""),
                    fluxo.get("status", ""),
                    fluxo.get("tipo", ""),
                    fluxo.get("tamanho", 0),
                ]
                for fluxo in visiveis
            ],
        )
        self.lbl_contagem.setText(
            f"{len(visiveis)} exibido(s) de {len(self._fluxos)} fluxo(s)"
        )

    def _mostrar_fluxo(self, linha: int, _coluna: int) -> None:
        if 0 <= linha < len(self._visiveis):
            self.txt_detalhes.setPlainText(str(self._visiveis[linha].get("detalhe", "")))

    def _limpar_fluxos(self) -> None:
        self._fluxos.clear()
        self._visiveis.clear()
        preencher_tabela(self.tabela, [])
        self.txt_detalhes.clear()
        self.lbl_contagem.setText("0 fluxo(s)")
        self.lbl_status.setText("Fluxos limpos.")

    def _exportar_har(self) -> None:
        if not self._fluxos:
            mostrar_erro(
                self,
                "Nada para exportar",
                "Nenhum fluxo foi capturado até o momento.",
            )
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar fluxos em HAR",
            "fluxos.har",
            "Arquivos HAR (*.har);;Arquivos JSON (*.json);;Todos os arquivos (*.*)",
        )
        if not destino:
            return
        fluxos = list(self._fluxos)

        def tarefa(ctx) -> str:
            har = _montar_har(fluxos)
            Path(destino).write_text(
                json.dumps(har, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return destino

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=lambda caminho: self.log_panel.append_log(
                "INFO", f"HAR exportado em {caminho} ({len(fluxos)} fluxo(s))."
            ),
            ao_falhar=self._falhou,
        )

    def hideEvent(self, evento) -> None:  # noqa: N802 (assinatura Qt)
        """Sair da página encerra o proxy para não deixar a porta aberta."""
        if self._executando:
            self._parar_proxy()
        super().hideEvent(evento)

"""Ferramenta de varredura não destrutiva de vulnerabilidades web.

Analisa formulários e parâmetros de consulta de uma página, executa testes
controlados de SQL Injection (error-based), XSS refletido, LFI, redirecionamento
aberto e cabeçalhos HTTP ausentes. Todas as cargas são benignas, o número de
requisições é limitado e nenhum dado é alterado de forma intencional. A extração
de HTML usa ``html.parser`` nativo e aproveita ``bs4`` quando instalado.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html import escape
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urljoin, urlsplit

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import (
    confirmar_termo_etico,
    normalizar_espacos,
    truncar,
    validar_url,
)
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    criar_aviso,
    criar_card,
    criar_saida_texto,
    criar_tabela,
    executar_assincrono,
    mostrar_erro,
    preencher_tabela,
)

LIMITE_REQUISICOES_PADRAO = 60
LIMITE_REQUISICOES_MAXIMO = 300
MAXIMO_PONTOS_INJECAO = 8
MAXIMO_PARAMETROS_POR_PONTO = 4
TAMANHO_MAXIMO_CORPO = 300_000
AGENTE_PADRAO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 WinToolbox/1.0"
)

TEXTO_AVISO = (
    "Aviso de uso responsável: esta ferramenta envia cargas de teste benignas para a "
    "aplicação informada, com limite de requisições e sem finalidade destrutiva. "
    "Utilize apenas em sistemas dos quais você é proprietário ou para os quais possui "
    "autorização expressa e por escrito. As cargas não tentam obter acesso, extrair "
    "dados ou apagar conteúdo, mas formulários POST podem executar ações reais na "
    "aplicação; execute-os somente em ambiente autorizado. Nenhuma requisição é "
    "enviada sem a sua confirmação."
)

# Cabeçalhos de segurança avaliados e a recomendação correspondente.
CABECALHOS_SEGURANCA: Tuple[Tuple[str, str, str, str], ...] = (
    (
        "strict-transport-security",
        "Strict-Transport-Security",
        "Alta",
        "Ative HSTS com max-age de pelo menos um ano para impedir downgrades para HTTP.",
    ),
    (
        "content-security-policy",
        "Content-Security-Policy",
        "Alta",
        "Defina uma CSP restritiva para reduzir o impacto de injeção de scripts.",
    ),
    (
        "x-frame-options",
        "X-Frame-Options",
        "Média",
        "Envie X-Frame-Options: DENY ou SAMEORIGIN (ou frame-ancestors na CSP) contra clickjacking.",
    ),
    (
        "x-content-type-options",
        "X-Content-Type-Options",
        "Baixa",
        "Envie X-Content-Type-Options: nosniff para bloquear a interpretação incorreta de tipos.",
    ),
    (
        "referrer-policy",
        "Referrer-Policy",
        "Baixa",
        "Envie Referrer-Policy: strict-origin-when-cross-origin ou mais restritiva.",
    ),
    (
        "permissions-policy",
        "Permissions-Policy",
        "Baixa",
        "Envie Permissions-Policy desabilitando recursos de navegador não utilizados.",
    ),
)

PADROES_ERRO_SQL: Tuple[str, ...] = (
    "you have an error in your sql syntax",
    "warning: mysql",
    "unclosed quotation mark after the character string",
    "quoted string not properly terminated",
    "sqlstate[",
    "ora-01756",
    "ora-00933",
    "pg_query",
    "pg::syntaxerror",
    "syntax error at or near",
    "microsoft ole db provider",
    "odbc sql server driver",
    "microsoft sql native client",
    "supplied argument is not a valid mysql",
    "mysql_fetch_array",
    "mysqli_sql_exception",
    "postgresql query failed",
    "sqlite3.operationalerror",
    "sqlite error",
    "unterminated quoted string",
    "invalid query",
    "divisão por zero",
)

CARGAS_SQLI: Tuple[str, ...] = (
    "'",
    '"',
    "1' OR '1'='1",
)

PADROES_LFI: Tuple[str, ...] = (
    "root:x:0:0:",
    "root:*:0:0:",
    "daemon:x:",
    "[extensions]",
    "[fonts]",
    "for 16-bit app support",
    "[mci extensions]",
)

CARGAS_LFI: Tuple[str, ...] = (
    "../../../../../../etc/passwd",
    "....//....//....//....//etc/passwd",
    "..\\..\\..\\..\\..\\windows\\win.ini",
    "/etc/passwd",
)

MARCADOR_REDIRECIONAMENTO = "exemplo-invalido.wintoolbox.test"

CARGAS_REDIRECIONAMENTO: Tuple[str, ...] = (
    f"//{MARCADOR_REDIRECIONAMENTO}",
    f"https://{MARCADOR_REDIRECIONAMENTO}/",
    f"\\\\{MARCADOR_REDIRECIONAMENTO}",
)

TIPOS_IGNORADOS = {"submit", "button", "image", "reset", "file"}

_AVISOS_TLS_SILENCIADOS = False


def _obter_requests() -> Any:
    """Importa ``requests`` sob demanda com mensagem amigável em caso de ausência."""
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - ambiente sem requests
        raise RuntimeError(
            "A biblioteca 'requests' é necessária para esta ferramenta. "
            "Instale com: pip install requests"
        ) from exc
    return requests


def _silenciar_avisos_tls() -> None:
    """Desativa o aviso repetitivo de certificado inválido durante a varredura."""
    global _AVISOS_TLS_SILENCIADOS
    if _AVISOS_TLS_SILENCIADOS:
        return
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    _AVISOS_TLS_SILENCIADOS = True


@dataclass
class CampoFormulario:
    """Campo de um formulário HTML."""

    nome: str
    tipo: str = "text"
    valor: str = ""


@dataclass
class Formulario:
    """Formulário HTML com ação absoluta, método e campos preenchíveis."""

    acao: str
    metodo: str
    campos: List[CampoFormulario] = field(default_factory=list)
    origem: str = ""

    def valores_iniciais(self) -> Dict[str, str]:
        """Mapeia nome do campo para o valor inicial (vazio vira texto de teste)."""
        valores: Dict[str, str] = {}
        for campo in self.campos:
            if campo.nome:
                valores[campo.nome] = campo.valor or "teste"
        return valores


@dataclass
class Achado:
    """Uma constatação da varredura."""

    categoria: str
    severidade: str
    confianca: str
    url: str
    metodo: str = "GET"
    parametro: str = ""
    payload: str = ""
    evidencia: str = ""
    descricao: str = ""

    def para_linha(self) -> List[str]:
        """Converte o achado para a linha exibida na tabela."""
        return [
            self.severidade,
            self.categoria,
            self.url,
            self.parametro or "-",
            self.confianca,
            self.evidencia or "-",
        ]


@dataclass
class ResultadoVarredura:
    """Resultado consolidado da varredura de vulnerabilidades."""

    alvo: str
    url_final: str
    status_inicial: int
    iniciado_em: str
    total_requisicoes: int
    limite_requisicoes: int
    limite_atingido: bool
    formularios: List[Formulario] = field(default_factory=list)
    achados: List[Achado] = field(default_factory=list)
    cabecalhos_ausentes: List[str] = field(default_factory=list)
    notas: List[str] = field(default_factory=list)
    erros: int = 0
    cancelado: bool = False
    duracao_s: float = 0.0

    def contagem_por_severidade(self) -> Dict[str, int]:
        """Conta os achados por severidade em ordem decrescente de risco."""
        contagem: Dict[str, int] = {}
        for achado in self.achados:
            contagem[achado.severidade] = contagem.get(achado.severidade, 0) + 1
        ordem = {"Alta": 0, "Média": 1, "Baixa": 2, "Informativa": 3}
        return dict(sorted(contagem.items(), key=lambda par: ordem.get(par[0], 9)))

    def resumo(self) -> str:
        """Texto de resumo em português para o painel de saída."""
        linhas = [
            f"Alvo: {self.alvo}",
            f"URL final: {self.url_final}",
            f"Status inicial: {self.status_inicial}",
            f"Início: {self.iniciado_em}",
            f"Duração: {self.duracao_s:.1f} s",
            (
                f"Requisições: {self.total_requisicoes} de {self.limite_requisicoes}"
                f" (limite atingido: {'sim' if self.limite_atingido else 'nao'})"
            ),
            f"Formulários analisados: {len(self.formularios)}",
            f"Erros de rede: {self.erros}",
            f"Cancelado: {'sim' if self.cancelado else 'nao'}",
            "",
            f"Achados: {len(self.achados)}",
        ]
        for severidade, quantidade in self.contagem_por_severidade().items():
            linhas.append(f"  {severidade}: {quantidade}")
        if self.cabecalhos_ausentes:
            linhas.append("")
            linhas.append("Cabeçalhos ausentes: " + ", ".join(self.cabecalhos_ausentes))
        if self.notas:
            linhas.append("")
            linhas.extend(f"Obs.: {nota}" for nota in self.notas)
        return "\n".join(linhas)


@dataclass
class RespostaHTTP:
    """Resposta HTTP resumida usada pelos testes."""

    url: str
    status: int
    texto: str
    tamanho: int
    cabecalhos: Dict[str, str]
    tempo_ms: float


@dataclass
class _PontoInjecao:
    """Parâmetros de uma URL ou formulário aptos a receber cargas de teste."""

    url: str
    metodo: str
    valores: Dict[str, str]
    origem: str


class _ColetorHTML(HTMLParser):
    """Extrai formulários, campos e links usando apenas a biblioteca padrão."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.formularios: List[Formulario] = []
        self.links: List[str] = []
        self._formulario: Optional[Formulario] = None
        self._textarea: Optional[CampoFormulario] = None
        self._select: Optional[CampoFormulario] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        dados = {chave.lower(): (valor or "") for chave, valor in attrs}

        if tag == "form":
            metodo = (dados.get("method") or "GET").upper()
            if metodo not in ("GET", "POST"):
                metodo = "GET"
            self._formulario = Formulario(
                acao=urljoin(self.base_url, dados.get("action") or self.base_url),
                metodo=metodo,
                campos=[],
                origem=self.base_url,
            )
            return

        if tag == "a" and dados.get("href"):
            self.links.append(urljoin(self.base_url, dados["href"]))
            return

        if self._formulario is None:
            return

        if tag == "input":
            tipo = (dados.get("type") or "text").lower()
            nome = (dados.get("name") or "").strip()
            if not nome or tipo in TIPOS_IGNORADOS:
                return
            self._formulario.campos.append(
                CampoFormulario(nome=nome, tipo=tipo, valor=dados.get("value") or "")
            )
        elif tag == "textarea":
            nome = (dados.get("name") or "").strip()
            if nome:
                self._textarea = CampoFormulario(nome=nome, tipo="textarea", valor="")
        elif tag == "select":
            nome = (dados.get("name") or "").strip()
            if nome:
                self._select = CampoFormulario(nome=nome, tipo="select", valor="")
        elif tag == "option" and self._select is not None:
            valor = (dados.get("value") or "").strip()
            if valor:
                self._select.valor = valor

    def handle_data(self, data: str) -> None:
        if self._textarea is not None and data:
            self._textarea.valor += data
        elif self._select is not None and data and not self._select.valor:
            self._select.valor = data.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "textarea" and self._textarea is not None:
            self._textarea.valor = self._textarea.valor.strip()
            if self._formulario is not None:
                self._formulario.campos.append(self._textarea)
            self._textarea = None
        elif tag == "select" and self._select is not None:
            if self._formulario is not None:
                self._formulario.campos.append(self._select)
            self._select = None
        elif tag == "form" and self._formulario is not None:
            self.formularios.append(self._formulario)
            self._formulario = None


def _extrair_com_bs4(texto: str, base_url: str) -> Optional[Tuple[List[Formulario], List[str]]]:
    """Tenta extrair formulários e links com BeautifulSoup; ``None`` se indisponível."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    try:
        sopa = BeautifulSoup(texto, "html.parser")
    except Exception:
        return None

    formularios: List[Formulario] = []
    for elemento in sopa.find_all("form"):
        metodo = (elemento.get("method") or "GET").upper()
        if metodo not in ("GET", "POST"):
            metodo = "GET"
        formulario = Formulario(
            acao=urljoin(base_url, elemento.get("action") or base_url),
            metodo=metodo,
            campos=[],
            origem=base_url,
        )
        for campo in elemento.find_all(["input", "textarea", "select"]):
            nome = (campo.get("name") or "").strip()
            if not nome:
                continue
            tipo = (campo.get("type") or campo.name or "text").lower()
            if tipo in TIPOS_IGNORADOS:
                continue
            if campo.name == "select":
                opcao = campo.find("option")
                valor = ""
                if opcao is not None:
                    valor = (opcao.get("value") or opcao.get_text(strip=True) or "")
                formulario.campos.append(
                    CampoFormulario(nome=nome, tipo="select", valor=valor)
                )
            elif campo.name == "textarea":
                formulario.campos.append(
                    CampoFormulario(
                        nome=nome, tipo="textarea", valor=campo.get_text(strip=True)
                    )
                )
            else:
                formulario.campos.append(
                    CampoFormulario(nome=nome, tipo=tipo, valor=campo.get("value") or "")
                )
        formularios.append(formulario)

    links = [
        urljoin(base_url, elemento["href"])
        for elemento in sopa.find_all("a", href=True)
        if elemento.get("href")
    ]
    return formularios, links


def analisar_html(texto: str, base_url: str) -> Tuple[List[Formulario], List[str]]:
    """Extrai formulários e links do HTML, usando bs4 quando disponível."""
    resultado = _extrair_com_bs4(texto, base_url)
    if resultado is not None:
        return resultado
    coletor = _ColetorHTML(base_url)
    try:
        coletor.feed(texto or "")
        coletor.close()
    except Exception:
        return [], []
    return coletor.formularios, coletor.links


def extrair_formularios(html_texto: str, base_url: str) -> List[Formulario]:
    """Devolve apenas os formulários encontrados no HTML."""
    formularios, _ = analisar_html(html_texto, base_url)
    return formularios


def extrair_links_com_parametros(html_texto: str, base_url: str) -> List[str]:
    """Devolve links únicos que possuem parâmetros de consulta."""
    _, links = analisar_html(html_texto, base_url)
    vistos = set()
    saida: List[str] = []
    for link in links:
        if "?" not in link:
            continue
        partes = urlsplit(link)
        if not partes.query:
            continue
        if link in vistos:
            continue
        vistos.add(link)
        saida.append(link)
    return saida


class _ClienteHTTP:
    """Cliente HTTP com contador de requisições, limite rígido e cancelamento."""

    def __init__(
        self,
        *,
        timeout: float,
        agente: str,
        limite: int,
        ignorar_tls: bool,
        is_cancelled: Optional[Callable[[], bool]] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        if ignorar_tls:
            _silenciar_avisos_tls()
        self._requests = _obter_requests()
        self._timeout = max(1.0, float(timeout))
        self._agente = agente
        self._limite = max(1, int(limite))
        self._ignorar_tls = bool(ignorar_tls)
        self._is_cancelled = is_cancelled
        self._on_log = on_log
        self._sessao = self._requests.Session()
        self._sessao.headers.update(
            {
                "User-Agent": agente,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Connection": "close",
            }
        )
        self.total = 0
        self.erros = 0
        self.limite_atingido = False

    def cancelado(self) -> bool:
        """Consulta o sinal de cancelamento de forma defensiva."""
        try:
            return bool(self._is_cancelled()) if callable(self._is_cancelled) else False
        except Exception:
            return False

    def logar(self, nivel: str, mensagem: str) -> None:
        """Encaminha uma mensagem para o log, quando houver callback."""
        if callable(self._on_log):
            self._on_log(nivel, mensagem)

    def fechar(self) -> None:
        """Encerra a sessão HTTP."""
        try:
            self._sessao.close()
        except Exception:
            pass

    def requisitar(
        self,
        metodo: str,
        url: str,
        *,
        params: Optional[Dict[str, str]] = None,
        dados: Optional[Dict[str, str]] = None,
        permitir_redirecionar: bool = True,
    ) -> Optional[RespostaHTTP]:
        """Executa uma requisição respeitando o limite e devolvendo ``None`` quando bloqueada."""
        if self.cancelado():
            return None
        if self.total >= self._limite:
            if not self.limite_atingido:
                self.limite_atingido = True
                self.logar(
                    "AVISO",
                    f"Limite de {self._limite} requisições atingido; testes restantes ignorados.",
                )
            return None

        self.total += 1
        inicio = time.perf_counter()
        try:
            resposta = self._sessao.request(
                metodo.upper(),
                url,
                params=params,
                data=dados,
                timeout=self._timeout,
                allow_redirects=permitir_redirecionar,
                verify=not self._ignorar_tls,
            )
        except Exception as exc:
            self.erros += 1
            self.logar("AVISO", f"Falha ao requisitar {url}: {exc}")
            return None

        duracao = (time.perf_counter() - inicio) * 1000.0
        try:
            texto = resposta.text or ""
        except Exception:
            texto = ""
        texto = texto[:TAMANHO_MAXIMO_CORPO]
        cabecalhos = {str(chave).lower(): str(valor) for chave, valor in resposta.headers.items()}
        return RespostaHTTP(
            url=str(resposta.url),
            status=int(resposta.status_code),
            texto=texto,
            tamanho=len(texto),
            cabecalhos=cabecalhos,
            tempo_ms=duracao,
        )


def verificar_cabecalhos(
    cabecalhos: Dict[str, str],
    url: str,
    *,
    is_https: bool = True,
) -> List[Achado]:
    """Compara os cabeçalhos de resposta com a lista mínima de segurança recomendada."""
    achados: List[Achado] = []
    presentes = {chave.lower() for chave in cabecalhos}
    for chave, rotulo, severidade, recomendacao in CABECALHOS_SEGURANCA:
        if chave in presentes:
            continue
        severidade_ajustada = severidade
        if chave == "strict-transport-security" and not is_https:
            severidade_ajustada = "Informativa"
        achados.append(
            Achado(
                categoria="Cabeçalho HTTP ausente",
                severidade=severidade_ajustada,
                confianca="Alta",
                url=url,
                metodo="GET",
                parametro=rotulo,
                evidencia=f"O cabeçalho {rotulo} não foi retornado na resposta inicial.",
                descricao=recomendacao,
            )
        )
    return achados


def _requisitar_ponto(
    cliente: _ClienteHTTP,
    ponto: _PontoInjecao,
    valores: Dict[str, str],
    *,
    permitir_redirecionar: bool = True,
) -> Optional[RespostaHTTP]:
    """Envia os valores informados para o ponto de injeção respeitando o método."""
    if ponto.metodo == "POST":
        return cliente.requisitar(
            "POST", ponto.url, dados=valores, permitir_redirecionar=permitir_redirecionar
        )
    return cliente.requisitar(
        "GET", ponto.url, params=valores, permitir_redirecionar=permitir_redirecionar
    )


def _trecho_evidencia(texto: str, limite: int = 160) -> str:
    """Normaliza e encurta um trecho de resposta para uso como evidência."""
    return truncar(normalizar_espacos(texto), limite)


def testar_sqli(
    cliente: _ClienteHTTP,
    ponto: _PontoInjecao,
    *,
    cargas: Sequence[str] = CARGAS_SQLI,
) -> List[Achado]:
    """Procura mensagens de erro de banco de dados disparadas por aspas simples ou duplas."""
    achados: List[Achado] = []
    parametros = list(ponto.valores)[:MAXIMO_PARAMETROS_POR_PONTO]
    for parametro in parametros:
        for carga in cargas:
            valores = dict(ponto.valores)
            valores[parametro] = carga
            resposta = _requisitar_ponto(cliente, ponto, valores)
            if resposta is None:
                return achados
            texto = resposta.texto.lower()
            for padrao in PADROES_ERRO_SQL:
                if padrao in texto:
                    indice = texto.find(padrao)
                    trecho = resposta.texto[max(0, indice - 60) : indice + 100]
                    achados.append(
                        Achado(
                            categoria="SQL Injection (error-based)",
                            severidade="Alta",
                            confianca="Média",
                            url=resposta.url,
                            metodo=ponto.metodo,
                            parametro=parametro,
                            payload=carga,
                            evidencia=_trecho_evidencia(trecho),
                            descricao=(
                                "A aplicação retornou uma mensagem de erro de banco de dados "
                                "após a injeção de aspas. Valide com parametrização de consultas."
                            ),
                        )
                    )
                    break
            if achados and achados[-1].parametro == parametro:
                break
    return achados


def testar_xss(
    cliente: _ClienteHTTP,
    ponto: _PontoInjecao,
) -> List[Achado]:
    """Verifica se cargas de script são refletidas sem codificação na resposta."""
    achados: List[Achado] = []
    parametros = list(ponto.valores)[:MAXIMO_PARAMETROS_POR_PONTO]
    cargas = (
        '"><script>alert(1)</script>',
        "'><svg/onload=alert(1)>",
    )
    for parametro in parametros:
        for carga in cargas:
            valores = dict(ponto.valores)
            valores[parametro] = carga
            resposta = _requisitar_ponto(cliente, ponto, valores)
            if resposta is None:
                return achados
            literal_script = "<script>alert(1)</script>" in resposta.texto
            literal_svg = "<svg/onload=alert(1)>" in resposta.texto
            refletiu = literal_script or literal_svg
            if refletiu:
                achados.append(
                    Achado(
                        categoria="XSS refletido",
                        severidade="Alta",
                        confianca="Média",
                        url=resposta.url,
                        metodo=ponto.metodo,
                        parametro=parametro,
                        payload=carga,
                        evidencia="A carga de script foi refletida sem codificação HTML.",
                        descricao=(
                            "A entrada do usuário é devolvida sem escape. Aplique codificação "
                            "de saída contextual e uma Content-Security-Policy restritiva."
                        ),
                    )
                )
                break
            if carga in resposta.texto:
                achados.append(
                    Achado(
                        categoria="Reflexão de entrada (possível XSS)",
                        severidade="Baixa",
                        confianca="Baixa",
                        url=resposta.url,
                        metodo=ponto.metodo,
                        parametro=parametro,
                        payload=carga,
                        evidencia="A carga apareceu na resposta, mas sem execução confirmada.",
                        descricao=(
                            "A entrada é refletida na página. Confirme manualmente o contexto "
                            "de saída antes de classificar como XSS explorável."
                        ),
                    )
                )
                break
    return achados


def testar_lfi(
    cliente: _ClienteHTTP,
    ponto: _PontoInjecao,
) -> List[Achado]:
    """Tenta travessia de diretórios com cargas benignas e assinaturas de arquivos do sistema."""
    achados: List[Achado] = []
    parametros = list(ponto.valores)[:MAXIMO_PARAMETROS_POR_PONTO]
    for parametro in parametros:
        for carga in CARGAS_LFI:
            valores = dict(ponto.valores)
            valores[parametro] = carga
            resposta = _requisitar_ponto(cliente, ponto, valores)
            if resposta is None:
                return achados
            texto = resposta.texto
            for padrao in PADROES_LFI:
                if padrao in texto:
                    indice = texto.find(padrao)
                    trecho = texto[max(0, indice - 40) : indice + 120]
                    achados.append(
                        Achado(
                            categoria="Inclusão local de arquivo (LFI)",
                            severidade="Alta",
                            confianca="Alta",
                            url=resposta.url,
                            metodo=ponto.metodo,
                            parametro=parametro,
                            payload=carga,
                            evidencia=_trecho_evidencia(trecho),
                            descricao=(
                                "O parâmetro parece incluir arquivos locais. Restrinja caminhos "
                                "a uma lista permitida e evite concatenar entrada do usuário."
                            ),
                        )
                    )
                    break
            if achados and achados[-1].parametro == parametro:
                break
    return achados


def testar_open_redirect(
    cliente: _ClienteHTTP,
    ponto: _PontoInjecao,
) -> List[Achado]:
    """Verifica se o parâmetro controla o cabeçalho Location sem validação de destino."""
    achados: List[Achado] = []
    parametros = list(ponto.valores)[:MAXIMO_PARAMETROS_POR_PONTO]
    for parametro in parametros:
        for carga in CARGAS_REDIRECIONAMENTO:
            valores = dict(ponto.valores)
            valores[parametro] = carga
            resposta = _requisitar_ponto(cliente, ponto, valores, permitir_redirecionar=False)
            if resposta is None:
                return achados
            destino = resposta.cabecalhos.get("location", "")
            if resposta.status in (301, 302, 303, 307, 308) and MARCADOR_REDIRECIONAMENTO in destino:
                achados.append(
                    Achado(
                        categoria="Redirecionamento aberto",
                        severidade="Média",
                        confianca="Alta",
                        url=resposta.url,
                        metodo=ponto.metodo,
                        parametro=parametro,
                        payload=carga,
                        evidencia=_trecho_evidencia(f"Location: {destino}"),
                        descricao=(
                            "O destino do redirecionamento é controlado pelo usuário. Aceite "
                            "apenas caminhos relativos ou destinos em lista permitida."
                        ),
                    )
                )
                break
    return achados


def _mesmo_host(url: str, host: str) -> bool:
    """Confirma se a URL pertence ao mesmo host do alvo, evitando terceiros."""
    try:
        return (urlsplit(url).hostname or "").lower() == host.lower()
    except Exception:
        return False


def _montar_pontos_injecao(
    alvo: str,
    formularios: Sequence[Formulario],
    links: Sequence[str],
    *,
    on_log: Optional[Callable[[str, str], None]] = None,
) -> List[_PontoInjecao]:
    """Monta a lista de pontos de injeção do próprio alvo, sem repetições."""
    host = (urlsplit(alvo).hostname or "").lower()
    pontos: List[_PontoInjecao] = []
    vistos = set()

    def adicionar(url: str, metodo: str, valores: Dict[str, str], origem: str) -> None:
        if not valores:
            return
        chave = (metodo.upper(), url, tuple(sorted(valores)))
        if chave in vistos:
            return
        vistos.add(chave)
        pontos.append(
            _PontoInjecao(url=url, metodo=metodo.upper(), valores=valores, origem=origem)
        )

    for formulario in formularios:
        if not _mesmo_host(formulario.acao, host):
            if callable(on_log):
                on_log(
                    "AVISO",
                    f"Formulário para outro domínio ignorado: {formulario.acao}",
                )
            continue
        adicionar(
            formulario.acao,
            formulario.metodo,
            formulario.valores_iniciais(),
            "formulário",
        )

    for link in links:
        if not _mesmo_host(link, host) or "?" not in link:
            continue
        partes = urlsplit(link)
        try:
            consulta = parse_qs(partes.query, keep_blank_values=True)
        except Exception:
            continue
        valores = {chave: (lista[0] if lista else "") or "teste" for chave, lista in consulta.items()}
        base = f"{partes.scheme}://{partes.netloc}{partes.path}"
        adicionar(base, "GET", valores, "link")

    return pontos[:MAXIMO_PONTOS_INJECAO]


def executar_varredura(
    alvo: str,
    *,
    limite_requisicoes: int = LIMITE_REQUISICOES_PADRAO,
    timeout: float = 8.0,
    testar_sqli_habilitado: bool = True,
    testar_xss_habilitado: bool = True,
    testar_lfi_habilitado: bool = True,
    testar_redirect_habilitado: bool = True,
    ignorar_tls: bool = True,
    agente: str = AGENTE_PADRAO,
    is_cancelled: Optional[Callable[[], bool]] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    on_log: Optional[Callable[[str, str], None]] = None,
) -> ResultadoVarredura:
    """Executa a varredura não destrutiva, respeitando o limite de requisições."""
    url_alvo = validar_url(alvo, permitir_local=True)
    limite = max(1, min(int(limite_requisicoes), LIMITE_REQUISICOES_MAXIMO))

    def logar(nivel: str, mensagem: str) -> None:
        if callable(on_log):
            on_log(nivel, mensagem)

    def progresso(atual: int, total: int, mensagem: str = "") -> None:
        if callable(on_progress):
            on_progress(atual, max(1, total), mensagem)

    iniciado_em = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    iniciou = time.perf_counter()
    cliente = _ClienteHTTP(
        timeout=timeout,
        agente=agente,
        limite=limite,
        ignorar_tls=ignorar_tls,
        is_cancelled=is_cancelled,
        on_log=on_log,
    )

    logar("INFO", f"Iniciando varredura não destrutiva em {url_alvo} com limite de {limite} requisições.")

    formularios: List[Formulario] = []
    achados: List[Achado] = []
    cabecalhos_ausentes: List[str] = []
    notas: List[str] = []
    cancelado = False
    url_final = url_alvo
    status_inicial = 0
    duracao = 0.0
    try:
        resposta_inicial = cliente.requisitar("GET", url_alvo)
        if resposta_inicial is None:
            if cliente.cancelado():
                raise RuntimeError("Varredura cancelada antes da primeira requisição.")
            raise RuntimeError(
                "Não foi possível acessar o alvo. Verifique a URL, a conectividade e o TLS."
            )

        url_final = resposta_inicial.url
        status_inicial = resposta_inicial.status
        is_https = url_final.lower().startswith("https://")
        logar("INFO", f"Resposta inicial: HTTP {status_inicial} em {url_final}")

        progresso(1, limite, "Analisando cabeçalhos de segurança")
        achados_cabecalhos = verificar_cabecalhos(
            resposta_inicial.cabecalhos, url_final, is_https=is_https
        )
        achados.extend(achados_cabecalhos)
        cabecalhos_ausentes = [achado.parametro for achado in achados_cabecalhos]
        if cabecalhos_ausentes:
            logar(
                "AVISO",
                f"{len(cabecalhos_ausentes)} cabeçalho(s) de segurança ausente(s).",
            )

        if cliente.cancelado():
            cancelado = True
            notas.append("Execução cancelada durante a análise inicial.")
        else:
            progresso(2, limite, "Extraindo formulários e parâmetros")
            formularios, links = analisar_html(resposta_inicial.texto, url_final)
            pontos = _montar_pontos_injecao(
                url_final, formularios, links, on_log=on_log
            )
            logar(
                "INFO",
                f"{len(formularios)} formulário(s) e {len(pontos)} ponto(s) de injeção identificado(s).",
            )
            if not pontos:
                notas.append(
                    "Nenhum formulário ou parâmetro de consulta foi encontrado na página inicial."
                )

            for indice, ponto in enumerate(pontos, start=1):
                if cliente.cancelado() or cliente.limite_atingido:
                    break
                progresso(
                    cliente.total,
                    limite,
                    f"Testando ponto {indice} de {len(pontos)}: {ponto.url}",
                )
                testes = []
                if testar_sqli_habilitado:
                    testes.append(("SQLi", testar_sqli))
                if testar_xss_habilitado:
                    testes.append(("XSS", testar_xss))
                if testar_lfi_habilitado:
                    testes.append(("LFI", testar_lfi))
                if testar_redirect_habilitado:
                    testes.append(("Redirecionamento", testar_open_redirect))

                for rotulo, funcao in testes:
                    if cliente.cancelado() or cliente.limite_atingido:
                        break
                    try:
                        novos = funcao(cliente, ponto)
                    except Exception as exc:
                        notas.append(f"Falha no teste de {rotulo} em {ponto.url}: {exc}")
                        logar("ERRO", f"Falha no teste de {rotulo}: {exc}")
                        continue
                    if novos:
                        achados.extend(novos)
                        logar(
                            "SUCESSO",
                            f"{len(novos)} achado(s) de {rotulo} em {ponto.url}",
                        )

        if cliente.limite_atingido:
            notas.append(
                f"O limite de {limite} requisições foi atingido; parte dos testes não foi executada."
            )
        if cliente.cancelado():
            cancelado = True
            notas.append("Execução cancelada pelo usuário.")
    finally:
        cliente.fechar()
        duracao = time.perf_counter() - iniciou

    # Reordena por severidade para facilitar a leitura do relatório.
    ordem = {"Alta": 0, "Média": 1, "Baixa": 2, "Informativa": 3}
    achados.sort(key=lambda item: (ordem.get(item.severidade, 9), item.categoria, item.url))

    resultado = ResultadoVarredura(
        alvo=url_alvo,
        url_final=url_final,
        status_inicial=status_inicial,
        iniciado_em=iniciado_em,
        total_requisicoes=cliente.total,
        limite_requisicoes=limite,
        limite_atingido=cliente.limite_atingido,
        formularios=formularios,
        achados=achados,
        cabecalhos_ausentes=cabecalhos_ausentes,
        notas=notas,
        erros=cliente.erros,
        cancelado=cancelado,
        duracao_s=duracao,
    )
    logar(
        "INFO",
        f"Varredura finalizada: {len(achados)} achado(s) em "
        f"{cliente.total} requisição(ões) ({duracao:.1f} s).",
    )
    return resultado


def _tabela_markdown_achados(achados: Sequence[Achado]) -> str:
    """Monta a tabela resumida de achados para o relatório Markdown."""
    if not achados:
        return "Nenhum achado registrado.\n"
    linhas = [
        "| Severidade | Categoria | URL | Parâmetro | Confiança |",
        "| :--- | :--- | :--- | :--- | :---: |",
    ]
    for achado in achados:
        url = escape(achado.url).replace("|", "/")
        parametro = escape(achado.parametro or "-").replace("|", "/")
        categoria = escape(achado.categoria).replace("|", "/")
        linhas.append(
            f"| {achado.severidade} | {categoria} | {url} | {parametro} | {achado.confianca} |"
        )
    return "\n".join(linhas) + "\n"


def gerar_relatorio_markdown(resultado: ResultadoVarredura) -> str:
    """Gera o relatório completo em Markdown."""
    linhas = [
        "# Relatório de Varredura Não Destrutiva de Vulnerabilidades Web",
        "",
        f"- **Alvo informado:** {resultado.alvo}",
        f"- **URL final:** {resultado.url_final}",
        f"- **Status HTTP inicial:** {resultado.status_inicial}",
        f"- **Início da execução:** {resultado.iniciado_em}",
        f"- **Duração:** {resultado.duracao_s:.1f} s",
        (
            f"- **Requisições realizadas:** {resultado.total_requisicoes} de "
            f"{resultado.limite_requisicoes}"
        ),
        f"- **Limite de requisições atingido:** {'sim' if resultado.limite_atingido else 'não'}",
        f"- **Formulários analisados:** {len(resultado.formularios)}",
        f"- **Execução cancelada:** {'sim' if resultado.cancelado else 'não'}",
        "",
        "## Resumo por severidade",
        "",
    ]
    contagem = resultado.contagem_por_severidade()
    if contagem:
        linhas.extend(f"- **{severidade}:** {quantidade}" for severidade, quantidade in contagem.items())
    else:
        linhas.append("- Nenhum achado registrado.")

    linhas.extend(
        [
            "",
            "## Tabela de achados",
            "",
            _tabela_markdown_achados(resultado.achados).rstrip(),
            "",
            "## Detalhamento dos achados",
            "",
        ]
    )

    if not resultado.achados:
        linhas.append("Nenhum achado para detalhar.")
    else:
        for indice, achado in enumerate(resultado.achados, start=1):
            linhas.extend(
                [
                    f"### {indice}. {achado.categoria}",
                    "",
                    f"- **Severidade:** {achado.severidade}",
                    f"- **Confiança:** {achado.confianca}",
                    f"- **URL:** {achado.url}",
                    f"- **Método:** {achado.metodo}",
                    f"- **Parâmetro:** {achado.parametro or '-'}",
                    f"- **Carga utilizada:** `{achado.payload or '-'}`",
                    f"- **Evidência:** {achado.evidencia or '-'}",
                    f"- **Descrição e recomendação:** {achado.descricao or '-'}",
                    "",
                ]
            )

    linhas.extend(["## Cabeçalhos de segurança ausentes", ""])
    if resultado.cabecalhos_ausentes:
        linhas.extend(f"- {nome}" for nome in resultado.cabecalhos_ausentes)
    else:
        linhas.append("Nenhum cabeçalho da lista mínima está ausente.")

    linhas.extend(["", "## Observações e limitações", ""])
    if resultado.notas:
        linhas.extend(f"- {nota}" for nota in resultado.notas)
    else:
        linhas.append("- Nenhuma observação adicional.")
    linhas.extend(
        [
            "- Os testes são não destrutivos e utilizam cargas benignas de verificação.",
            "- Um resultado negativo não garante ausência da vulnerabilidade; a análise manual complementar é recomendada.",
            "",
            "---",
            "*Relatório gerado pelo WinToolbox. Use somente em sistemas autorizados.*",
        ]
    )
    return "\n".join(linhas)


def gerar_relatorio_json(resultado: ResultadoVarredura) -> str:
    """Gera o relatório completo em JSON."""
    dados = {
        "alvo": resultado.alvo,
        "url_final": resultado.url_final,
        "status_inicial": resultado.status_inicial,
        "iniciado_em": resultado.iniciado_em,
        "duracao_segundos": round(resultado.duracao_s, 2),
        "total_requisicoes": resultado.total_requisicoes,
        "limite_requisicoes": resultado.limite_requisicoes,
        "limite_atingido": resultado.limite_atingido,
        "cancelado": resultado.cancelado,
        "erros": resultado.erros,
        "formularios": [
            {
                "acao": formulario.acao,
                "metodo": formulario.metodo,
                "campos": [asdict(campo) for campo in formulario.campos],
            }
            for formulario in resultado.formularios
        ],
        "cabecalhos_ausentes": resultado.cabecalhos_ausentes,
        "achados": [asdict(achado) for achado in resultado.achados],
        "contagem_por_severidade": resultado.contagem_por_severidade(),
        "notas": resultado.notas,
    }
    return json.dumps(dados, ensure_ascii=False, indent=2)


def cor_severidade(severidade: str) -> Optional[str]:
    """Define a cor de destaque da severidade na tabela de achados."""
    return {
        "Alta": "#ef4444",
        "Média": "#f59e0b",
        "Baixa": "#3b82f6",
        "Informativa": "#9ca3af",
    }.get(severidade)


@register
class VulnScannerTool(Tool):
    """Ferramenta de varredura não destrutiva de vulnerabilidades web."""

    id = "web.vuln_scanner"
    name = "Varredura de Vulnerabilidades Web"
    category = "Web"
    description = (
        "Testes não destrutivos de SQL Injection, XSS refletido, LFI, redirecionamento "
        "aberto e cabeçalhos ausentes, com limite de requisições e relatório em Markdown ou JSON"
    )
    keywords = [
        "vulnerabilidades",
        "scanner",
        "sqli",
        "xss",
        "lfi",
        "open redirect",
        "cabeçalhos",
        "headers",
        "owasp",
        "web",
        "pentest",
        "segurança",
        "seguranca",
    ]
    optional_deps = ["requests", "bs4"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return VulnScannerView(self, parent)


class VulnScannerView(PainelFerramenta):
    """Interface de configuração, execução e exportação da varredura de vulnerabilidades."""

    def __init__(self, tool: VulnScannerTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[ResultadoVarredura] = None
        self._construir_interface()

    def _construir_interface(self) -> None:
        """Monta todos os cartões e controles da página."""
        self.adicionar(criar_aviso(TEXTO_AVISO, self, destaque=True))

        cartao_alvo, layout_alvo = criar_card("Alvo e escopo dos testes", self)
        self.adicionar(cartao_alvo)

        linha_alvo = QHBoxLayout()
        linha_alvo.setSpacing(8)
        linha_alvo.addWidget(QLabel("URL alvo:"))
        self.txt_alvo = QLineEdit("https://exemplo.com")
        self.txt_alvo.setPlaceholderText("https://seusite.com.br/pagina")
        self.txt_alvo.returnPressed.connect(self._iniciar)
        linha_alvo.addWidget(self.txt_alvo, stretch=1)
        self.btn_iniciar = QPushButton("Iniciar varredura")
        self.btn_iniciar.setProperty("class", "primary")
        self.btn_iniciar.clicked.connect(self._iniciar)
        linha_alvo.addWidget(self.btn_iniciar)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self._cancelar)
        linha_alvo.addWidget(self.btn_cancelar)
        layout_alvo.addLayout(linha_alvo)

        linha_opcoes = QHBoxLayout()
        linha_opcoes.setSpacing(10)
        linha_opcoes.addWidget(QLabel("Limite de requisições:"))
        self.spin_limite = QSpinBox()
        self.spin_limite.setRange(10, LIMITE_REQUISICOES_MAXIMO)
        self.spin_limite.setValue(LIMITE_REQUISICOES_PADRAO)
        self.spin_limite.setSingleStep(10)
        linha_opcoes.addWidget(self.spin_limite)

        linha_opcoes.addWidget(QLabel("Timeout:"))
        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setRange(1.0, 60.0)
        self.spin_timeout.setDecimals(1)
        self.spin_timeout.setSuffix(" s")
        self.spin_timeout.setValue(8.0)
        linha_opcoes.addWidget(self.spin_timeout)
        linha_opcoes.addStretch(1)
        layout_alvo.addLayout(linha_opcoes)

        linha_testes = QHBoxLayout()
        linha_testes.setSpacing(12)
        self.chk_sqli = QCheckBox("SQL Injection (error-based)")
        self.chk_sqli.setChecked(True)
        linha_testes.addWidget(self.chk_sqli)
        self.chk_xss = QCheckBox("XSS refletido")
        self.chk_xss.setChecked(True)
        linha_testes.addWidget(self.chk_xss)
        self.chk_lfi = QCheckBox("LFI")
        self.chk_lfi.setChecked(True)
        linha_testes.addWidget(self.chk_lfi)
        self.chk_redirect = QCheckBox("Redirecionamento aberto")
        self.chk_redirect.setChecked(True)
        linha_testes.addWidget(self.chk_redirect)
        linha_testes.addStretch(1)
        layout_alvo.addLayout(linha_testes)

        self.lbl_escopo = QLabel(
            "Os testes cobrem apenas a página informada e os formulários/links do mesmo "
            "domínio. Cabeçalhos são sempre verificados. Nenhuma carga altera dados."
        )
        self.lbl_escopo.setProperty("class", "secondary")
        self.lbl_escopo.setWordWrap(True)
        layout_alvo.addWidget(self.lbl_escopo)

        self.progresso = QProgressBar()
        self.progresso.setRange(0, LIMITE_REQUISICOES_PADRAO)
        self.progresso.setValue(0)
        self.progresso.setFormat("%v de %m requisições")
        layout_alvo.addWidget(self.progresso)

        self.lbl_status = QLabel(
            "Pronto para iniciar. O termo de responsabilidade será solicitado na execução."
        )
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout_alvo.addWidget(self.lbl_status)

        _, layout_tabela = self.adicionar_card("Achados")
        self.tabela: QTableWidget = criar_tabela(
            ["Severidade", "Categoria", "URL", "Parâmetro", "Confiança", "Evidência"]
        )
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.Stretch)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(5, QHeaderView.Stretch)
        self.tabela.setMinimumHeight(250)
        layout_tabela.addWidget(self.tabela)

        _, layout_resumo = self.adicionar_card("Resumo da varredura")
        self.saida = criar_saida_texto(150)
        self.saida.setPlainText("O resumo da varredura será exibido aqui após a execução.")
        layout_resumo.addWidget(self.saida)

        linha_botoes = QHBoxLayout()
        self.btn_markdown = QPushButton("Exportar relatório Markdown...")
        self.btn_markdown.setEnabled(False)
        self.btn_markdown.clicked.connect(self._exportar_markdown)
        linha_botoes.addWidget(self.btn_markdown)
        self.btn_json = QPushButton("Exportar relatório JSON...")
        self.btn_json.setEnabled(False)
        self.btn_json.clicked.connect(self._exportar_json)
        linha_botoes.addWidget(self.btn_json)
        linha_botoes.addStretch(1)
        layout_resumo.addLayout(linha_botoes)

        self._log = adicionar_log_painel(self, "Log da varredura")
        self.adicionar_espaco()

    def _iniciar(self) -> None:
        """Confirma o termo ético e dispara a varredura assíncrona."""
        if not confirmar_termo_etico(self, self.tool.id):
            self._log.append_log("AVISO", "Execução recusada: termo de responsabilidade não aceito.")
            return

        try:
            alvo = validar_url(self.txt_alvo.text(), permitir_local=True)
        except ValueError as exc:
            mostrar_erro(self, "URL inválida", exc)
            return

        limite = self.spin_limite.value()
        timeout = self.spin_timeout.value()
        testar_sqli = self.chk_sqli.isChecked()
        testar_xss = self.chk_xss.isChecked()
        testar_lfi = self.chk_lfi.isChecked()
        testar_redirect = self.chk_redirect.isChecked()

        if not any((testar_sqli, testar_xss, testar_lfi, testar_redirect)):
            self._log.append_log(
                "AVISO",
                "Nenhum teste de injeção habilitado; apenas cabeçalhos serão verificados.",
            )

        self._resultado = None
        self._log.clear()
        self.tabela.setRowCount(0)
        self.saida.setPlainText("Varredura em andamento...")
        self.progresso.setRange(0, limite)
        self.progresso.setValue(0)
        self.btn_iniciar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.btn_markdown.setEnabled(False)
        self.btn_json.setEnabled(False)
        self.lbl_status.setText(f"Varrendo {alvo}...")

        def tarefa(ctx):
            return executar_varredura(
                alvo,
                limite_requisicoes=limite,
                timeout=timeout,
                testar_sqli_habilitado=testar_sqli,
                testar_xss_habilitado=testar_xss,
                testar_lfi_habilitado=testar_lfi,
                testar_redirect_habilitado=testar_redirect,
                is_cancelled=ctx.is_cancelled,
                on_progress=ctx.progress,
                on_log=ctx.log,
            )

        def concluiu(resultado: ResultadoVarredura) -> None:
            self._resultado = resultado
            self.btn_iniciar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.progresso.setValue(min(resultado.total_requisicoes, self.progresso.maximum()))
            self._preencher(resultado)

        def falhou(erro: Exception) -> None:
            self.btn_iniciar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.lbl_status.setText("A varredura falhou. Consulte o log de execução.")
            self.saida.setPlainText(f"Falha na varredura: {erro}")
            mostrar_erro(self, "Falha na varredura", erro)

        def progrediu(atual: int, total: int, mensagem: str) -> None:
            total = max(1, int(total))
            self.progresso.setMaximum(total)
            self.progresso.setValue(min(int(atual), total))
            if mensagem:
                self.lbl_status.setText(mensagem)

        def logou(nivel: str, mensagem: str) -> None:
            self._log.append_log(nivel, mensagem)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_progredir=progrediu,
            ao_logar=logou,
        )

    def _cancelar(self) -> None:
        """Solicita o cancelamento cooperativo da varredura."""
        if hasattr(self.runner, "cancel_current"):
            self.runner.cancel_current()
        self.btn_cancelar.setEnabled(False)
        self.lbl_status.setText("Cancelamento solicitado. Aguardando a requisição em curso...")
        self._log.append_log("AVISO", "Cancelamento solicitado pelo usuário.")

    def _preencher(self, resultado: ResultadoVarredura) -> None:
        """Atualiza tabela, resumo e botões de exportação."""
        linhas = [achado.para_linha() for achado in resultado.achados]
        preencher_tabela(self.tabela, linhas)
        for indice, achado in enumerate(resultado.achados):
            item = self.tabela.item(indice, 0)
            if item is None:
                continue
            cor = cor_severidade(achado.severidade)
            if cor:
                item.setForeground(QBrush(QColor(cor)))
        self.saida.setPlainText(resultado.resumo())
        self.btn_markdown.setEnabled(True)
        self.btn_json.setEnabled(True)
        if resultado.cancelado:
            self.lbl_status.setText(
                f"Varredura cancelada após {resultado.total_requisicoes} requisição(ões)."
            )
        elif resultado.limite_atingido:
            self.lbl_status.setText(
                f"Limite de {resultado.limite_requisicoes} requisições atingido. "
                f"{len(resultado.achados)} achado(s) registrado(s)."
            )
        else:
            self.lbl_status.setText(
                f"Varredura concluída em {resultado.duracao_s:.1f} s. "
                f"{len(resultado.achados)} achado(s) registrado(s)."
            )

    def _exportar_markdown(self) -> None:
        """Solicita o destino e grava o relatório Markdown."""
        if not self._resultado:
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar relatório de varredura",
            "relatorio_vulnerabilidades.md",
            "Arquivo Markdown (*.md);;Texto simples (*.txt);;Todos os arquivos (*.*)",
        )
        if not destino:
            return
        self._salvar(destino, gerar_relatorio_markdown(self._resultado))

    def _exportar_json(self) -> None:
        """Solicita o destino e grava o relatório JSON."""
        if not self._resultado:
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar relatório de varredura",
            "relatorio_vulnerabilidades.json",
            "Arquivo JSON (*.json);;Todos os arquivos (*.*)",
        )
        if not destino:
            return
        self._salvar(destino, gerar_relatorio_json(self._resultado))

    def _salvar(self, destino: str, conteudo: str) -> None:
        """Grava o relatório em disco com tratamento de erro amigável."""
        try:
            with open(destino, "w", encoding="utf-8", newline="") as arquivo:
                arquivo.write(conteudo)
        except OSError as exc:
            mostrar_erro(self, "Falha ao salvar", exc)
            return
        self._log.append_log("SUCESSO", f"Relatório exportado para {destino}.")
        self.lbl_status.setText(f"Relatório exportado para {destino}.")

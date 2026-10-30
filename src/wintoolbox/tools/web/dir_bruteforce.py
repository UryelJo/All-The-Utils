"""Ferramenta de força bruta de diretórios e arquivos web.

Realiza requisições HTTP sequenciais e concorrentes contra uma lista interna de
caminhos conhecidos, reportando os que retornam códigos de interesse. A execução
é limitada por um número máximo de threads, atraso configurável entre requisições
e filtro de tamanho de resposta. Toda a lógica de rede é independente da interface
gráfica e pode ser cancelada por meio de um ``TaskContext``.
"""
from __future__ import annotations

import csv
import io
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
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
from wintoolbox.tools._helpers import confirmar_termo_etico, formatar_bytes, validar_url
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

CODIGOS_PADRAO: Tuple[int, ...] = (200, 204, 301, 302, 307, 401, 403)
LIMITE_MAXIMO_THREADS = 64
LIMITE_MAXIMO_ATRASO = 10.0
AGENTE_PADRAO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 WinToolbox/1.0"
)

TEXTO_AVISO = (
    "Aviso de uso responsável: esta varredura envia requisições HTTP em volume para o "
    "alvo informado. Utilize apenas em sistemas dos quais você é proprietário ou para "
    "os quais possui autorização expressa e por escrito. A varredura não explora falhas, "
    "mas o volume de requisições pode ser interpretado como atividade maliciosa por "
    "serviços de proteção. Nenhuma requisição é enviada sem a sua confirmação."
)

# Lista interna com caminhos reais frequentemente encontrados em aplicações web.
# Mantida no próprio módulo para que a ferramenta funcione sem arquivos externos.
WORDLIST_DIRETORIOS: Tuple[str, ...] = (
    # Painéis administrativos e autenticação
    "admin",
    "admin/",
    "admin/login",
    "admin/index.php",
    "admin.php",
    "admin.html",
    "administrator",
    "administrator/index.php",
    "administracao",
    "administrativo",
    "painel",
    "painel.php",
    "painel-admin",
    "paineladm",
    "admin-panel",
    "gestao",
    "gerenciador",
    "manager",
    "management",
    "login",
    "login.php",
    "login.html",
    "login.aspx",
    "signin",
    "signin.php",
    "entrar",
    "logout",
    "logout.php",
    "register",
    "register.php",
    "signup",
    "cadastro",
    "cadastro.php",
    "criar-conta",
    "recuperar-senha",
    "forgot-password",
    "reset-password",
    "password",
    "senha",
    "auth",
    "oauth",
    "oauth2",
    "sso",
    "saml",
    "token",
    "tokens",
    "perfil",
    "profile",
    "perfil.php",
    "conta",
    "conta/login",
    "usuario",
    "usuarios",
    "users",
    # Painéis de hospedagem e controle
    "cpanel",
    "whm",
    "webdisk",
    "plesk",
    "directadmin",
    "webmin",
    "portal",
    "intranet",
    "extranet",
    "dashboard",
    "dashboard-admin",
    "app",
    "app/login",
    "app/dashboard",
    "sistema",
    "services",
    "servicos",
    # Aplicações populares
    "wp-admin",
    "wp-login.php",
    "wp-content",
    "wp-includes",
    "wp-json",
    "xmlrpc.php",
    "wp-config.php",
    "wp-config.php.bak",
    "wp-config.php.old",
    "wp-cron.php",
    "wordpress",
    "joomla",
    "administrator/components",
    "typo3",
    "drupal",
    "magento",
    "loja",
    "shop",
    "store",
    "ecommerce",
    "checkout",
    "carrinho",
    "cart",
    "produtos",
    "products",
    "pedidos",
    "orders",
    "pagamento",
    "payment",
    "boleto",
    "pix",
    "assinatura",
    "subscription",
    "planos",
    "pricing",
    "precos",
    "orcamento",
    # Conteúdo e comunicação
    "blog",
    "noticias",
    "news",
    "forum",
    "comunidade",
    "wiki",
    "docs",
    "doc",
    "documentation",
    "documentation.html",
    "help",
    "suporte",
    "support",
    "faq",
    "manual",
    "contato",
    "contact",
    "contato.php",
    "newsletter",
    "subscribe",
    "eventos",
    "cursos",
    "academy",
    "treinamento",
    # Arquivos sensíveis e configuração
    ".git",
    ".git/config",
    ".git/HEAD",
    ".gitignore",
    ".svn",
    ".hg",
    ".env",
    ".env.local",
    ".env.bak",
    ".env.example",
    ".htaccess",
    ".htpasswd",
    ".DS_Store",
    ".npmrc",
    ".babelrc",
    "config",
    "config.php",
    "config.php.bak",
    "config.json",
    "config.yaml",
    "config.yml",
    "config.xml",
    "configuration.php",
    "settings.py",
    "settings.php",
    "database.yml",
    "composer.json",
    "composer.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "gulpfile.js",
    "webpack.config.js",
    "robots.txt",
    "sitemap.xml",
    "sitemap_index.xml",
    "security.txt",
    ".well-known",
    ".well-known/security.txt",
    "crossdomain.xml",
    "manifest.json",
    "service-worker.js",
    "favicon.ico",
    "apple-touch-icon.png",
    # Backups e dumps
    "backup",
    "backups",
    "backup.zip",
    "backup.tar.gz",
    "backup.sql",
    "backup.rar",
    "db.sql",
    "dump.sql",
    "database.sql",
    "site.sql",
    "www.zip",
    "wwwroot.zip",
    "public_html.zip",
    "old",
    "old-site",
    "antigo",
    "novo",
    "legacy",
    # Ambientes e ramificações
    "dev",
    "desenvolvimento",
    "staging",
    "homolog",
    "homologacao",
    "teste",
    "test",
    "tests",
    "qa",
    "sandbox",
    "demo",
    "sample",
    "exemplo",
    "beta",
    "alpha",
    "preview",
    "v2",
    # APIs e documentação técnica
    "api",
    "api/v1",
    "api/v2",
    "api/docs",
    "api/swagger",
    "api-docs",
    "swagger",
    "swagger-ui",
    "swagger-ui.html",
    "swagger.json",
    "openapi.json",
    "graphql",
    "graphiql",
    "rest",
    "soap",
    "wsdl",
    # Estrutura de aplicação
    "assets",
    "static",
    "public",
    "private",
    "includes",
    "inc",
    "lib",
    "libs",
    "vendor",
    "node_modules",
    "build",
    "dist",
    "src",
    "application",
    "core",
    "modules",
    "plugins",
    "themes",
    "templates",
    "cache",
    "logs",
    "log",
    "log.txt",
    "error.log",
    "access.log",
    "debug.log",
    "errors",
    "monitoring",
    "health",
    "healthz",
    "status",
    "ping",
    "version",
    "metrics",
    # Upload, mídia e documentos
    "uploads",
    "upload",
    "arquivos",
    "arquivo",
    "files",
    "download",
    "downloads",
    "media",
    "imagens",
    "images",
    "img",
    "js",
    "css",
    "fonts",
    "videos",
    "audio",
    "pdf",
    "documentos",
    "relatorios",
    "reports",
    # Ferramentas de banco e administração conhecidas
    "adminer.php",
    "adminer",
    "phpmyadmin",
    "pma",
    "mysql",
    "mysqladmin",
    "db",
    "database",
    "sql",
    "dbadmin",
    "shell.php",
    "cmd.php",
    "upload.php",
    "filemanager",
    "filemanager.html",
    "elfinder",
    "editor",
    "ckeditor",
    "tinymce",
    "fckeditor",
    "console",
    "terminal",
    "shell",
    "cmd",
    "exec",
    "system",
    "cgi-bin",
    "cgi-bin/test.cgi",
    "cgi",
    "bin",
    "scripts",
    # Diagnóstico e informações expostas
    "phpinfo.php",
    "info.php",
    "test.php",
    "server-status",
    "server-info",
    "debug",
    "trace",
    "actuator",
    "actuator/health",
    "actuator/env",
    "env",
    "console/login",
    # Institucional e negócio
    "financeiro",
    "rh",
    "clientes",
    "fornecedores",
    "parceiros",
    "vendas",
    "sales",
    "marketing",
    "leads",
    "crm",
    "erp",
    "bi",
    "analytics",
    "intranet/login",
    "webmail",
    "mail",
    "email",
    "smtp",
    "ftp",
    "ssh",
    "vpn",
    "remote",
    # Raiz e páginas padrão
    "index",
    "index.html",
    "index.htm",
    "index.php",
    "index.asp",
    "index.aspx",
    "index.jsp",
    "default.html",
    "default.aspx",
    "main.php",
    "app.php",
    "home",
    "landing",
    "coming-soon",
    "em-breve",
    "maintenance",
    "manutencao",
    "404",
    "403",
    "500",
    "erro",
    "error",
    "README",
    "README.md",
    "README.txt",
    "CHANGELOG.md",
    "LICENSE",
)

_LOCAL = threading.local()


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
    """Desativa o aviso repetitivo de certificado inválido quando o usuário opta por ignorá-lo."""
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass


def _sessao_da_thread(requests_mod: Any, agente: str) -> Any:
    """Devolve uma sessão HTTP reutilizável por thread, recriada se o agente mudar."""
    sessao = getattr(_LOCAL, "sessao", None)
    if sessao is not None and getattr(_LOCAL, "agente", None) == agente:
        return sessao
    sessao = requests_mod.Session()
    sessao.headers.update(
        {
            "User-Agent": agente,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Connection": "close",
        }
    )
    _LOCAL.sessao = sessao
    _LOCAL.agente = agente
    return sessao


@dataclass
class EntradaDiretorio:
    """Um caminho que respondeu com um dos códigos de interesse."""

    caminho: str
    url: str
    status: int
    tamanho: int
    redireciona_para: str = ""
    tempo_ms: float = 0.0

    def para_linha(self) -> List[str]:
        """Converte a entrada para a representação exibida na tabela da interface."""
        tamanho = formatar_bytes(self.tamanho) if self.tamanho >= 0 else "desconhecido"
        return [
            self.caminho,
            self.url,
            str(self.status),
            tamanho,
            self.redireciona_para or "-",
            f"{self.tempo_ms:.0f}",
        ]


@dataclass
class ResultadoDirBruteforce:
    """Resultado consolidado de uma execução de força bruta de diretórios."""

    base_url: str
    total_caminhos: int
    total_testados: int
    encontrados: List[EntradaDiretorio] = field(default_factory=list)
    erros: int = 0
    cancelado: bool = False
    duracao_s: float = 0.0

    def contagem_por_status(self) -> Dict[int, int]:
        """Conta os achados agrupados por código HTTP."""
        contagem: Dict[int, int] = {}
        for entrada in self.encontrados:
            contagem[entrada.status] = contagem.get(entrada.status, 0) + 1
        return dict(sorted(contagem.items()))

    def resumo(self) -> str:
        """Texto de resumo em português para o painel de saída."""
        linhas = [
            f"Alvo: {self.base_url}",
            f"Caminhos na wordlist: {self.total_caminhos}",
            f"Caminhos testados: {self.total_testados}",
            f"Tempo total: {self.duracao_s:.1f} s",
            f"Erros de conexão: {self.erros}",
            f"Cancelado pelo usuário: {'sim' if self.cancelado else 'nao'}",
            "",
            f"Encontrados: {len(self.encontrados)}",
        ]
        for status, quantidade in self.contagem_por_status().items():
            linhas.append(f"  HTTP {status}: {quantidade}")
        if not self.encontrados:
            linhas.append("  Nenhum caminho respondeu com os códigos configurados.")
        return "\n".join(linhas)


@dataclass
class _RespostaCaminho:
    """Resultado interno de uma requisição isolada (não faz parte da API pública)."""

    entrada: Optional[EntradaDiretorio] = None
    erro: bool = False
    cancelado: bool = False


def normalizar_base_url(alvo: str) -> str:
    """Valida a URL base, aceita endereços locais e remove consulta e fragmento."""
    url = validar_url(alvo, permitir_local=True)
    partes = urlsplit(url)
    caminho = partes.path.rstrip("/")
    return urlunsplit((partes.scheme, partes.netloc, caminho, "", ""))


def parsear_codigos(texto: str) -> Tuple[int, ...]:
    """Converte a lista textual de códigos HTTP em uma tupla ordenada e validada."""
    codigos = set()
    for parte in re.split(r"[,;\s]+", str(texto or "")):
        if not parte:
            continue
        try:
            valor = int(parte)
        except ValueError as exc:
            raise ValueError(f"Código HTTP inválido: {parte!r}. Use apenas números.") from exc
        if not 100 <= valor <= 599:
            raise ValueError(f"Código HTTP fora da faixa permitida (100 a 599): {valor}.")
        codigos.add(valor)
    if not codigos:
        raise ValueError("Informe pelo menos um código HTTP de interesse.")
    return tuple(sorted(codigos))


def normalizar_caminhos(caminhos: Optional[Sequence[str]] = None) -> List[str]:
    """Limpa a lista de caminhos, remove duplicatas e comentários preservando a ordem."""
    origem = caminhos if caminhos is not None else WORDLIST_DIRETORIOS
    vistos = set()
    saida: List[str] = []
    for bruto in origem:
        caminho = str(bruto or "").strip().lstrip("/")
        if not caminho or caminho.startswith("#"):
            continue
        chave = caminho.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(caminho)
    return saida


def executar_bruteforce(
    alvo: str,
    *,
    caminhos: Optional[Sequence[str]] = None,
    codigos_interesse: Sequence[int] = CODIGOS_PADRAO,
    threads: int = 10,
    atraso: float = 0.0,
    timeout: float = 8.0,
    tamanho_minimo: int = 0,
    tamanho_maximo: int = 0,
    seguir_redirecionamento: bool = False,
    ignorar_tls: bool = True,
    agente: str = AGENTE_PADRAO,
    is_cancelled: Optional[Callable[[], bool]] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    on_log: Optional[Callable[[str, str], None]] = None,
) -> ResultadoDirBruteforce:
    """Executa a força bruta de diretórios de forma concorrente e cancelável.

    A função não toca em widgets: pode rodar em qualquer thread de trabalho. O
    cancelamento é cooperativo e verificado antes de cada requisição e ao final
    de cada resposta concluída.
    """
    requests_mod = _obter_requests()
    if ignorar_tls:
        _silenciar_avisos_tls()

    base = normalizar_base_url(alvo)
    lista = normalizar_caminhos(caminhos)
    if not lista:
        raise ValueError("A wordlist está vazia. Informe pelo menos um caminho.")

    codigos = tuple(int(c) for c in codigos_interesse) or CODIGOS_PADRAO

    def cancelado() -> bool:
        try:
            return bool(is_cancelled()) if callable(is_cancelled) else False
        except Exception:
            return False

    def logar(nivel: str, mensagem: str) -> None:
        if callable(on_log):
            on_log(nivel, mensagem)

    def progresso(atual: int, total: int, mensagem: str = "") -> None:
        if callable(on_progress):
            on_progress(atual, total, mensagem)

    trabalhadores = max(1, min(int(threads), LIMITE_MAXIMO_THREADS))
    pausa = max(0.0, min(float(atraso), LIMITE_MAXIMO_ATRASO))
    limite_min = max(0, int(tamanho_minimo or 0))
    limite_max = max(0, int(tamanho_maximo or 0))

    logar(
        "INFO",
        f"Iniciando varredura em {base} com {len(lista)} caminhos, "
        f"{trabalhadores} thread(s) e atraso de {pausa:.2f} s.",
    )

    iniciou = time.perf_counter()
    total = len(lista)
    encontrados: List[EntradaDiretorio] = []
    erros = 0
    cancelado_em = False

    def testar(caminho: str) -> _RespostaCaminho:
        if cancelado():
            return _RespostaCaminho(cancelado=True)
        if pausa > 0:
            time.sleep(pausa)
            if cancelado():
                return _RespostaCaminho(cancelado=True)

        url = f"{base}/{caminho}"
        sessao = _sessao_da_thread(requests_mod, agente)
        inicio = time.perf_counter()
        try:
            resposta = sessao.get(
                url,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
                verify=not ignorar_tls,
            )
            duracao_ms = (time.perf_counter() - inicio) * 1000.0
            try:
                tamanho = int(resposta.headers.get("Content-Length", "-1"))
            except (TypeError, ValueError):
                tamanho = -1
            local = resposta.headers.get("Location", "") or ""
            status = int(resposta.status_code)
            resposta.close()
        except Exception as exc:  # erro de rede isolado não interrompe o lote
            logar("AVISO", f"Falha ao acessar {url}: {exc}")
            return _RespostaCaminho(erro=True)

        if status not in codigos:
            return _RespostaCaminho()
        if tamanho >= 0:
            if limite_min and tamanho < limite_min:
                return _RespostaCaminho()
            if limite_max and tamanho > limite_max:
                return _RespostaCaminho()
        entrada = EntradaDiretorio(
            caminho=caminho,
            url=url,
            status=status,
            tamanho=tamanho,
            redireciona_para=local,
            tempo_ms=duracao_ms,
        )
        return _RespostaCaminho(entrada=entrada)

    executor = ThreadPoolExecutor(max_workers=trabalhadores, thread_name_prefix="wtb-dir")
    futuros = {executor.submit(testar, caminho): caminho for caminho in lista}
    testados = 0
    try:
        for futuro in as_completed(futuros):
            if cancelado():
                cancelado_em = True
                break
            testados += 1
            caminho = futuros[futuro]
            try:
                resultado = futuro.result()
            except Exception as exc:  # falha inesperada em uma thread
                erros += 1
                logar("ERRO", f"Falha inesperada em {caminho}: {exc}")
                continue
            if resultado.cancelado:
                cancelado_em = True
                break
            if resultado.erro:
                erros += 1
            if resultado.entrada is not None:
                encontrados.append(resultado.entrada)
                logar(
                    "SUCESSO",
                    f"Encontrado: {resultado.entrada.caminho} "
                    f"(HTTP {resultado.entrada.status})",
                )
            progresso(testados, total, f"{testados} de {total} caminhos testados")
    finally:
        cancelado_em = cancelado_em or cancelado()
        executor.shutdown(wait=not cancelado_em, cancel_futures=True)

    encontrados.sort(key=lambda item: (item.status, item.caminho))
    duracao = time.perf_counter() - iniciou
    logar(
        "INFO",
        f"Varredura finalizada em {duracao:.1f} s: {len(encontrados)} achado(s), "
        f"{erros} erro(s).",
    )
    if cancelado_em:
        logar("AVISO", "Execução cancelada pelo usuário.")

    return ResultadoDirBruteforce(
        base_url=base,
        total_caminhos=len(lista),
        total_testados=testados,
        encontrados=encontrados,
        erros=erros,
        cancelado=cancelado_em,
        duracao_s=duracao,
    )


def gerar_csv(resultado: ResultadoDirBruteforce) -> str:
    """Gera o conteúdo CSV (separador ponto e vírgula) dos achados."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", lineterminator="\n")
    escritor.writerow(
        ["Caminho", "URL", "Status HTTP", "Tamanho (bytes)", "Redireciona para", "Tempo (ms)"]
    )
    for entrada in resultado.encontrados:
        escritor.writerow(
            [
                entrada.caminho,
                entrada.url,
                entrada.status,
                entrada.tamanho,
                entrada.redireciona_para,
                f"{entrada.tempo_ms:.0f}",
            ]
        )
    return buffer.getvalue()


def gerar_json(resultado: ResultadoDirBruteforce) -> str:
    """Gera o conteúdo JSON completo do resultado."""
    dados = {
        "alvo": resultado.base_url,
        "total_caminhos": resultado.total_caminhos,
        "total_testados": resultado.total_testados,
        "duracao_segundos": round(resultado.duracao_s, 2),
        "erros": resultado.erros,
        "cancelado": resultado.cancelado,
        "encontrados": [asdict(entrada) for entrada in resultado.encontrados],
        "contagem_por_status": resultado.contagem_por_status(),
    }
    return json.dumps(dados, ensure_ascii=False, indent=2)


def cor_status(status: int) -> Optional[str]:
    """Define a cor de destaque do código HTTP na tabela de resultados."""
    if 200 <= status < 300:
        return "#10b981"
    if 300 <= status < 400:
        return "#3b82f6"
    if status in (401, 403):
        return "#f59e0b"
    if status >= 500:
        return "#ef4444"
    return None


@register
class DirBruteforceTool(Tool):
    """Ferramenta de força bruta de diretórios web com wordlist interna."""

    id = "web.dir_bruteforce"
    name = "Força Bruta de Diretórios Web"
    category = "Web"
    description = (
        "Descoberta de diretórios e arquivos expostos por meio de uma wordlist interna "
        "de caminhos reais, com controle de threads, atraso, códigos HTTP e filtro de tamanho"
    )
    keywords = [
        "diretórios",
        "diretorios",
        "força bruta",
        "forca bruta",
        "bruteforce",
        "web",
        "wordlist",
        "enumeração",
        "enumeracao",
        "http",
        "pentest",
        "reconhecimento",
    ]
    optional_deps = ["requests"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return DirBruteforceView(self, parent)


class DirBruteforceView(PainelFerramenta):
    """Interface de configuração, execução e exportação da varredura de diretórios."""

    def __init__(self, tool: DirBruteforceTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[ResultadoDirBruteforce] = None
        self._construir_interface()

    def _construir_interface(self) -> None:
        """Monta todos os cartões e controles da página."""
        self.adicionar(criar_aviso(TEXTO_AVISO, self, destaque=True))

        cartao_alvo, layout_alvo = criar_card("Alvo e parâmetros da varredura", self)
        self.adicionar(cartao_alvo)
        linha_alvo = QHBoxLayout()
        linha_alvo.setSpacing(8)
        linha_alvo.addWidget(QLabel("URL base:"))
        self.txt_alvo = QLineEdit("https://exemplo.com")
        self.txt_alvo.setPlaceholderText("https://seusite.com.br")
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

        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(8)

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, LIMITE_MAXIMO_THREADS)
        self.spin_threads.setValue(10)
        self.spin_threads.setToolTip(f"Máximo de {LIMITE_MAXIMO_THREADS} threads simultâneas.")
        grade.addWidget(QLabel("Threads:"), 0, 0)
        grade.addWidget(self.spin_threads, 0, 1)

        self.spin_atraso = QDoubleSpinBox()
        self.spin_atraso.setRange(0.0, LIMITE_MAXIMO_ATRASO)
        self.spin_atraso.setDecimals(2)
        self.spin_atraso.setSingleStep(0.1)
        self.spin_atraso.setSuffix(" s")
        self.spin_atraso.setValue(0.0)
        grade.addWidget(QLabel("Atraso por requisição:"), 0, 2)
        grade.addWidget(self.spin_atraso, 0, 3)

        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setRange(1.0, 60.0)
        self.spin_timeout.setDecimals(1)
        self.spin_timeout.setSuffix(" s")
        self.spin_timeout.setValue(8.0)
        grade.addWidget(QLabel("Timeout:"), 0, 4)
        grade.addWidget(self.spin_timeout, 0, 5)

        self.txt_codigos = QLineEdit(",".join(str(c) for c in CODIGOS_PADRAO))
        self.txt_codigos.setToolTip("Códigos HTTP considerados interessantes, separados por vírgula.")
        grade.addWidget(QLabel("Códigos de interesse:"), 1, 0)
        grade.addWidget(self.txt_codigos, 1, 1, 1, 3)

        self.spin_minimo = QSpinBox()
        self.spin_minimo.setRange(0, 100_000_000)
        self.spin_minimo.setSingleStep(100)
        self.spin_minimo.setSpecialValueText("sem mínimo")
        grade.addWidget(QLabel("Tamanho mínimo (bytes):"), 1, 4)
        grade.addWidget(self.spin_minimo, 1, 5)

        self.spin_maximo = QSpinBox()
        self.spin_maximo.setRange(0, 100_000_000)
        self.spin_maximo.setSingleStep(100)
        self.spin_maximo.setSpecialValueText("sem máximo")
        grade.addWidget(QLabel("Tamanho máximo (bytes):"), 2, 0)
        grade.addWidget(self.spin_maximo, 2, 1)

        self.chk_redirecionar = QCheckBox("Seguir redirecionamentos")
        grade.addWidget(self.chk_redirecionar, 2, 2, 1, 2)

        self.chk_tls = QCheckBox("Aceitar certificados inválidos")
        self.chk_tls.setChecked(True)
        grade.addWidget(self.chk_tls, 2, 4, 1, 2)

        layout_alvo.addLayout(grade)

        self.lbl_wordlist = QLabel(
            f"Wordlist interna com {len(WORDLIST_DIRETORIOS)} caminhos reais. "
            "Nenhum arquivo externo é necessário."
        )
        self.lbl_wordlist.setProperty("class", "secondary")
        self.lbl_wordlist.setWordWrap(True)
        layout_alvo.addWidget(self.lbl_wordlist)

        self.progresso = QProgressBar()
        self.progresso.setRange(0, 100)
        self.progresso.setValue(0)
        self.progresso.setFormat("%v de %m")
        layout_alvo.addWidget(self.progresso)

        self.lbl_status = QLabel("Pronto para iniciar. Confirme o termo de responsabilidade ao executar.")
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout_alvo.addWidget(self.lbl_status)

        _, layout_tabela = self.adicionar_card("Caminhos encontrados")
        self.tabela: QTableWidget = criar_tabela(
            ["Caminho", "URL", "Status", "Tamanho", "Redireciona para", "Tempo (ms)"]
        )
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(1, QHeaderView.Stretch)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.tabela.setMinimumHeight(240)
        layout_tabela.addWidget(self.tabela)

        _, layout_resumo = self.adicionar_card("Resumo da execução")
        self.saida = criar_saida_texto(130)
        self.saida.setPlainText(
            "O resumo da varredura será exibido aqui após a execução."
        )
        layout_resumo.addWidget(self.saida)

        linha_botoes = QHBoxLayout()
        self.btn_csv = QPushButton("Exportar CSV...")
        self.btn_csv.setEnabled(False)
        self.btn_csv.clicked.connect(lambda: self._exportar("csv"))
        linha_botoes.addWidget(self.btn_csv)
        self.btn_json = QPushButton("Exportar JSON...")
        self.btn_json.setEnabled(False)
        self.btn_json.clicked.connect(lambda: self._exportar("json"))
        linha_botoes.addWidget(self.btn_json)
        linha_botoes.addStretch(1)
        layout_resumo.addLayout(linha_botoes)

        self._log = adicionar_log_painel(self, "Log da varredura")
        self.adicionar_espaco()

    def _iniciar(self) -> None:
        """Valida as opções, confirma o termo ético e dispara a varredura assíncrona."""
        if not confirmar_termo_etico(self, self.tool.id):
            self._log.append_log("AVISO", "Execução recusada: termo de responsabilidade não aceito.")
            return

        try:
            alvo = normalizar_base_url(self.txt_alvo.text())
            codigos = parsear_codigos(self.txt_codigos.text())
        except ValueError as exc:
            mostrar_erro(self, "Parâmetros inválidos", exc)
            return

        threads = self.spin_threads.value()
        atraso = self.spin_atraso.value()
        timeout = self.spin_timeout.value()
        minimo = self.spin_minimo.value()
        maximo = self.spin_maximo.value()
        redirecionar = self.chk_redirecionar.isChecked()
        ignorar_tls = self.chk_tls.isChecked()

        if maximo and minimo and maximo < minimo:
            mostrar_erro(
                self,
                "Parâmetros inválidos",
                "O tamanho máximo não pode ser menor que o tamanho mínimo.",
            )
            return

        self._resultado = None
        self._log.clear()
        self.tabela.setRowCount(0)
        self.saida.setPlainText("Varredura em andamento...")
        self.progresso.setRange(0, 100)
        self.progresso.setValue(0)
        self.btn_iniciar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.btn_csv.setEnabled(False)
        self.btn_json.setEnabled(False)
        self.lbl_status.setText(f"Varrendo {alvo}...")

        def tarefa(ctx):
            return executar_bruteforce(
                alvo,
                codigos_interesse=codigos,
                threads=threads,
                atraso=atraso,
                timeout=timeout,
                tamanho_minimo=minimo,
                tamanho_maximo=maximo,
                seguir_redirecionamento=redirecionar,
                ignorar_tls=ignorar_tls,
                is_cancelled=ctx.is_cancelled,
                on_progress=ctx.progress,
                on_log=ctx.log,
            )

        def concluiu(resultado: ResultadoDirBruteforce) -> None:
            self._resultado = resultado
            self.btn_iniciar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.progresso.setValue(self.progresso.maximum())
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
        """Solicita o cancelamento cooperativo da tarefa em execução."""
        if hasattr(self.runner, "cancel_current"):
            self.runner.cancel_current()
        self.btn_cancelar.setEnabled(False)
        self.lbl_status.setText("Cancelamento solicitado. Aguardando as requisições em curso...")
        self._log.append_log("AVISO", "Cancelamento solicitado pelo usuário.")

    def _preencher(self, resultado: ResultadoDirBruteforce) -> None:
        """Atualiza tabela, resumo e botões de exportação com o resultado recebido."""
        linhas = [entrada.para_linha() for entrada in resultado.encontrados]
        preencher_tabela(self.tabela, linhas)
        for indice, entrada in enumerate(resultado.encontrados):
            item = self.tabela.item(indice, 2)
            if item is None:
                continue
            cor = cor_status(entrada.status)
            if cor:
                item.setForeground(QBrush(QColor(cor)))
        self.saida.setPlainText(resultado.resumo())
        self.btn_csv.setEnabled(bool(resultado.encontrados))
        self.btn_json.setEnabled(True)
        if resultado.cancelado:
            self.lbl_status.setText(
                f"Varredura cancelada após {resultado.total_testados} caminho(s). "
                f"{len(resultado.encontrados)} achado(s) registrado(s)."
            )
        else:
            self.lbl_status.setText(
                f"Varredura concluída em {resultado.duracao_s:.1f} s. "
                f"{len(resultado.encontrados)} caminho(s) de interesse encontrado(s)."
            )

    def _exportar(self, formato: str) -> None:
        """Solicita o destino e grava o resultado em CSV ou JSON."""
        if not self._resultado:
            return
        if formato == "csv":
            conteudo = gerar_csv(self._resultado)
            filtro = "Arquivo CSV (*.csv);;Todos os arquivos (*.*)"
            sugestao = "varredura_diretorios.csv"
        else:
            conteudo = gerar_json(self._resultado)
            filtro = "Arquivo JSON (*.json);;Todos os arquivos (*.*)"
            sugestao = "varredura_diretorios.json"

        destino, _ = QFileDialog.getSaveFileName(
            self, "Exportar resultado da varredura", sugestao, filtro
        )
        if not destino:
            return
        try:
            with open(destino, "w", encoding="utf-8", newline="") as arquivo:
                arquivo.write(conteudo)
        except OSError as exc:
            mostrar_erro(self, "Falha ao salvar", exc)
            return
        self._log.append_log("SUCESSO", f"Resultado exportado para {destino}.")
        self.lbl_status.setText(f"Resultado exportado para {destino}.")

"""Ferramenta de enumeração de subdomínios por wordlist.

Resolve nomes de uma lista interna com concorrência controlada, detecta
encaminhamento curinga (wildcard) para evitar falsos positivos e, opcionalmente,
verifica a resposta HTTP de cada subdomínio encontrado. A resolução DNS usa
``dnspython`` quando instalado e recorre ao ``socket.getaddrinfo`` nativo caso
contrário. Nenhuma biblioteca opcional é importada no topo do módulo.
"""
from __future__ import annotations

import csv
import io
import json
import secrets
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

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
from wintoolbox.tools._helpers import (
    confirmar_termo_etico,
    dependencia_disponivel,
    formatar_bytes,
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

LIMITE_MAXIMO_THREADS = 50
LIMITE_MAXIMO_ATRASO = 10.0
AGENTE_PADRAO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 WinToolbox/1.0"
)

_AVISOS_TLS_SILENCIADOS = False

TEXTO_AVISO = (
    "Aviso de uso responsável: a enumeração de subdomínios consulta serviços de DNS "
    "e, quando habilitada, envia requisições HTTP aos nomes encontrados. Utilize apenas "
    "em domínios que você controla ou para os quais possui autorização expressa e por "
    "escrito. A ferramenta não explora falhas e não realiza força bruta de credenciais, "
    "mas o volume de consultas pode ser registrado pelo provedor de DNS. Nenhuma "
    "consulta é feita sem a sua confirmação."
)

# Lista interna de nomes de subdomínio comuns. Cobre serviços web, e-mail, DNS,
# bancos de dados, ambientes e infraestrutura de desenvolvimento.
WORDLIST_SUBDOMINIOS: Tuple[str, ...] = (
    # Web e aplicações
    "www",
    "www1",
    "www2",
    "www3",
    "w3",
    "web",
    "web1",
    "web2",
    "web3",
    "m",
    "mobile",
    "app",
    "apps",
    "app1",
    "app2",
    "portal",
    "site",
    "home",
    "landing",
    "blog",
    "noticias",
    "news",
    "forum",
    "comunidade",
    "wiki",
    "loja",
    "shop",
    "store",
    "ecommerce",
    "checkout",
    "pagamento",
    "carrinho",
    "produtos",
    "pedidos",
    "crm",
    "erp",
    "bi",
    "analytics",
    "relatorios",
    "reports",
    "financeiro",
    "rh",
    "vendas",
    "sales",
    "marketing",
    "newsletter",
    "clientes",
    "fornecedores",
    "parceiros",
    "sac",
    "atendimento",
    "helpdesk",
    "chamados",
    "tickets",
    "servicedesk",
    # APIs e integração
    "api",
    "api1",
    "api2",
    "apis",
    "api-v1",
    "api-v2",
    "api-dev",
    "api-staging",
    "api-hml",
    "api-homolog",
    "api-prod",
    "rest",
    "graphql",
    "gateway",
    "gw",
    "proxy",
    "proxy1",
    "firewall",
    # Acesso remoto e redes
    "vpn",
    "vpn1",
    "vpn2",
    "remote",
    "acesso",
    "ssh",
    "sftp",
    "ftp",
    "ftps",
    "noc",
    "ops",
    "infra",
    "devops",
    "cloud",
    "aws",
    "azure",
    "gcp",
    "storage",
    "s3",
    "nas",
    "nfs",
    "smb",
    "ldap",
    "ad",
    "dc",
    "dc1",
    "dc2",
    # Arquivos e conteúdo estático
    "files",
    "file",
    "download",
    "downloads",
    "upload",
    "uploads",
    "static",
    "assets",
    "cdn",
    "img",
    "images",
    "media",
    "videos",
    "docs",
    "doc",
    "documentation",
    "help",
    "suporte",
    "support",
    "faq",
    "manual",
    "biblioteca",
    "academy",
    "escola",
    "cursos",
    "aluno",
    "alunos",
    "professor",
    "treinamento",
    "eventos",
    # Observabilidade e operação
    "status",
    "monitor",
    "monitoring",
    "metrics",
    "grafana",
    "prometheus",
    "kibana",
    "elastic",
    "elasticsearch",
    "log",
    "logs",
    "syslog",
    "backup",
    "backups",
    # Dados
    "db",
    "db1",
    "db2",
    "database",
    "mysql",
    "postgres",
    "postgresql",
    "mssql",
    "oracle",
    "mongo",
    "mongodb",
    "redis",
    "cache",
    "queue",
    "rabbitmq",
    "kafka",
    "zookeeper",
    "hadoop",
    "spark",
    # Desenvolvimento e entrega
    "jenkins",
    "ci",
    "cd",
    "build",
    "deploy",
    "release",
    "git",
    "gitlab",
    "github",
    "bitbucket",
    "svn",
    "nexus",
    "artifactory",
    "registry",
    "docker",
    "kubernetes",
    "k8s",
    "rancher",
    "openshift",
    "cluster",
    "node1",
    "node2",
    "node3",
    "dev",
    "dev1",
    "dev2",
    "desenvolvimento",
    "staging",
    "staging1",
    "staging2",
    "homolog",
    "homologacao",
    "hml",
    "teste",
    "test",
    "qa",
    "sandbox",
    "demo",
    "lab",
    "labs",
    "beta",
    "alpha",
    "preview",
    "v2",
    "novo",
    "antigo",
    "old",
    "legacy",
    "prod",
    "producao",
    "production",
    "prd",
    # Autenticação e identidade
    "sso",
    "auth",
    "login",
    "oauth",
    "id",
    "identity",
    "accounts",
    "conta",
    "cadastro",
    "seguranca",
    "secure",
    "interno",
    "internal",
    "externo",
    "intranet",
    "extranet",
    # Correio e comunicação
    "mail",
    "mail1",
    "mail2",
    "email",
    "webmail",
    "smtp",
    "smtp1",
    "pop",
    "pop3",
    "imap",
    "mx",
    "mx1",
    "mx2",
    "exchange",
    "owa",
    "autodiscover",
    "lync",
    "lyncdiscover",
    "teams",
    "sip",
    "voip",
    "pbx",
    "asterisk",
    # DNS
    "ns1",
    "ns2",
    "ns3",
    "ns4",
    "dns",
    "dns1",
    "dns2",
    "dns3",
    # Painéis de hospedagem
    "cpanel",
    "whm",
    "plesk",
    "webdisk",
    "admin",
    "administrador",
    "painel",
    "gestao",
)


def _obter_requests() -> Any:
    """Importa ``requests`` sob demanda com mensagem amigável em caso de ausência."""
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - ambiente sem requests
        raise RuntimeError(
            "A biblioteca 'requests' é necessária para a checagem HTTP. "
            "Instale com: pip install requests"
        ) from exc
    return requests


def _silenciar_avisos_tls() -> None:
    """Evita a repetição do aviso de certificado inválido durante a checagem HTTP."""
    global _AVISOS_TLS_SILENCIADOS
    if _AVISOS_TLS_SILENCIADOS:
        return
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    _AVISOS_TLS_SILENCIADOS = True


def _resolver_com_dnspython(nome: str, timeout: float) -> Optional[List[str]]:
    """Resolve A e AAAA via dnspython; devolve ``None`` quando a biblioteca não existe."""
    try:
        import dns.resolver
    except ImportError:
        return None

    enderecos: List[str] = []
    try:
        resolvedor = dns.resolver.Resolver(configure=True)
        resolvedor.lifetime = max(0.5, float(timeout))
        resolvedor.timeout = max(0.5, float(timeout))
    except Exception:
        return None

    for tipo in ("A", "AAAA"):
        try:
            resposta = resolvedor.resolve(nome, tipo, lifetime=max(0.5, float(timeout)))
        except Exception:
            continue
        for registro in resposta:
            valor = str(registro).strip()
            if valor and valor not in enderecos:
                enderecos.append(valor)
    return enderecos


def _resolver_com_socket(nome: str) -> List[str]:
    """Resolve A e AAAA com a biblioteca nativa, sem depender de pacotes externos."""
    try:
        informacoes = socket.getaddrinfo(nome, None, proto=socket.IPPROTO_TCP)
    except OSError:
        return []
    enderecos: List[str] = []
    for informacao in informacoes:
        try:
            valor = informacao[4][0]
        except (IndexError, TypeError):
            continue
        if valor and valor not in enderecos:
            enderecos.append(valor)
    return sorted(enderecos)


def provedor_dns() -> str:
    """Informa qual mecanismo de resolução está disponível no ambiente."""
    return "dnspython" if dependencia_disponivel("dns") else "socket"


def resolver_enderecos(nome: str, timeout: float = 4.0) -> List[str]:
    """Resolve um nome para endereços A/AAAA usando dnspython ou o socket nativo."""
    nome = str(nome or "").strip().rstrip(".")
    if not nome:
        return []
    enderecos = _resolver_com_dnspython(nome, timeout)
    if enderecos is not None:
        return enderecos
    return _resolver_com_socket(nome)


def detectar_wildcard(dominio: str, timeout: float = 4.0) -> Tuple[bool, List[str]]:
    """Consulta um rótulo aleatório para identificar encaminhamento curinga do DNS."""
    rotulo = f"wtb-{secrets.token_hex(6)}"
    enderecos = resolver_enderecos(f"{rotulo}.{dominio}", timeout)
    return bool(enderecos), enderecos


def normalizar_dominio(texto: str) -> str:
    """Aceita domínio puro ou URL e devolve apenas o host normalizado."""
    bruto = str(texto or "").strip()
    if not bruto:
        raise ValueError("Informe o domínio alvo.")
    if "://" not in bruto:
        bruto = "http://" + bruto
    partes = urlsplit(bruto)
    host = (partes.hostname or "").strip().rstrip(".").lower()
    if not host:
        raise ValueError("Domínio inválido.")
    if " " in host or "/" in host:
        raise ValueError("Domínio inválido: remova espaços, caminhos e barras.")
    if "." not in host:
        raise ValueError("Informe um domínio completo, por exemplo: exemplo.com.br")
    return host


def normalizar_nomes(nomes: Optional[Sequence[str]] = None) -> List[str]:
    """Limpa a lista de nomes, ignorando vazios, comentários e duplicatas."""
    origem = nomes if nomes is not None else WORDLIST_SUBDOMINIOS
    vistos = set()
    saida: List[str] = []
    for bruto in origem:
        nome = str(bruto or "").strip().strip(".").lower()
        if not nome or nome.startswith("#"):
            continue
        if nome in vistos:
            continue
        vistos.add(nome)
        saida.append(nome)
    return saida


def verificar_http(
    fqdn: str,
    *,
    timeout: float = 8.0,
    agente: str = AGENTE_PADRAO,
) -> Tuple[Optional[int], int, str]:
    """Tenta HTTPS e, em caso de falha, HTTP; devolve (status, tamanho, URL final)."""
    requests_mod = _obter_requests()
    _silenciar_avisos_tls()
    for esquema in ("https", "http"):
        try:
            resposta = requests_mod.get(
                f"{esquema}://{fqdn}",
                timeout=timeout,
                allow_redirects=True,
                verify=False,
                headers={"User-Agent": agente, "Connection": "close"},
            )
            return int(resposta.status_code), len(resposta.content), str(resposta.url)
        except Exception:
            continue
    return None, -1, ""


@dataclass
class EntradaSubdominio:
    """Um subdomínio resolvido (ou descartado por suspeita de wildcard)."""

    nome: str
    fqdn: str
    ips: List[str] = field(default_factory=list)
    status_http: Optional[int] = None
    tamanho: int = -1
    url_final: str = ""
    falso_positivo: bool = False

    def texto_status(self) -> str:
        """Representação textual do status HTTP para a tabela."""
        if self.falso_positivo:
            return "wildcard"
        return str(self.status_http) if self.status_http is not None else "sem resposta"

    def para_linha(self) -> List[str]:
        """Converte a entrada para a linha correspondente na tabela da interface."""
        tamanho = formatar_bytes(self.tamanho) if self.tamanho >= 0 else "-"
        return [
            self.fqdn,
            ", ".join(self.ips),
            self.texto_status(),
            tamanho,
            self.url_final or "-",
        ]


@dataclass
class ResultadoSubdominio:
    """Resultado consolidado da enumeração de subdomínios."""

    dominio: str
    provedor: str
    wildcard: bool
    ips_wildcard: List[str]
    total_nomes: int
    total_consultados: int
    encontrados: List[EntradaSubdominio] = field(default_factory=list)
    descartados: List[EntradaSubdominio] = field(default_factory=list)
    erros: int = 0
    cancelado: bool = False
    duracao_s: float = 0.0

    def resumo(self) -> str:
        """Texto de resumo em português para o painel de saída."""
        linhas = [
            f"Domínio: {self.dominio}",
            f"Provedor de resolução DNS: {self.provedor}",
            f"Nomes na wordlist: {self.total_nomes}",
            f"Nomes consultados: {self.total_consultados}",
            f"Tempo total: {self.duracao_s:.1f} s",
            f"Erros de resolução: {self.erros}",
            f"Cancelado pelo usuário: {'sim' if self.cancelado else 'nao'}",
            "",
            f"Subdomínios encontrados: {len(self.encontrados)}",
        ]
        if self.wildcard:
            linhas.append(
                "Wildcard detectado: "
                + (", ".join(self.ips_wildcard) if self.ips_wildcard else "sem endereço")
            )
            linhas.append(
                f"Possíveis falsos positivos descartados: {len(self.descartados)}"
            )
        else:
            linhas.append("Wildcard: não detectado")
        return "\n".join(linhas)


@dataclass
class _RespostaNome:
    """Resultado interno de uma consulta isolada (não faz parte da API pública)."""

    entrada: Optional[EntradaSubdominio] = None
    descartado: Optional[EntradaSubdominio] = None
    erro: bool = False
    cancelado: bool = False


def executar_enumeracao(
    alvo: str,
    *,
    nomes: Optional[Sequence[str]] = None,
    threads: int = 12,
    atraso: float = 0.0,
    timeout_dns: float = 4.0,
    verificar_http_habilitado: bool = True,
    timeout_http: float = 8.0,
    incluir_wildcard: bool = False,
    agente: str = AGENTE_PADRAO,
    is_cancelled: Optional[Callable[[], bool]] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    on_log: Optional[Callable[[str, str], None]] = None,
) -> ResultadoSubdominio:
    """Enumera subdomínios de forma concorrente, cancelável e sem tocar na interface."""
    dominio = normalizar_dominio(alvo)
    lista = normalizar_nomes(nomes)
    if not lista:
        raise ValueError("A wordlist de subdomínios está vazia.")

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
    provedor = provedor_dns()

    logar(
        "INFO",
        f"Iniciando enumeração de {dominio} com {len(lista)} nomes, "
        f"{trabalhadores} thread(s) e resolução via {provedor}.",
    )

    if cancelado():
        return ResultadoSubdominio(
            dominio=dominio,
            provedor=provedor,
            wildcard=False,
            ips_wildcard=[],
            total_nomes=len(lista),
            total_consultados=0,
            cancelado=True,
        )

    wildcard, ips_wildcard = detectar_wildcard(dominio, timeout_dns)
    if wildcard:
        logar(
            "AVISO",
            "Wildcard detectado para "
            f"*.{dominio} ({', '.join(ips_wildcard)}). "
            "Respostas idênticas ao curinga serão tratadas como falsos positivos.",
        )
    else:
        logar("INFO", "Nenhum encaminhamento curinga detectado.")

    conjunto_wildcard = set(ips_wildcard)
    iniciou = time.perf_counter()
    total = len(lista)
    encontrados: List[EntradaSubdominio] = []
    descartados: List[EntradaSubdominio] = []
    erros = 0
    cancelado_em = False

    def consultar(nome: str) -> _RespostaNome:
        if cancelado():
            return _RespostaNome(cancelado=True)
        if pausa > 0:
            time.sleep(pausa)
            if cancelado():
                return _RespostaNome(cancelado=True)

        fqdn = f"{nome}.{dominio}"
        try:
            ips = resolver_enderecos(fqdn, timeout_dns)
        except Exception as exc:
            logar("AVISO", f"Falha ao resolver {fqdn}: {exc}")
            return _RespostaNome(erro=True)
        if not ips:
            return _RespostaNome()

        entrada = EntradaSubdominio(nome=nome, fqdn=fqdn, ips=list(ips))
        if conjunto_wildcard and set(ips).issubset(conjunto_wildcard):
            entrada.falso_positivo = True
            return _RespostaNome(descartado=entrada)

        if verificar_http_habilitado and not cancelado():
            status, tamanho, url_final = verificar_http(
                fqdn, timeout=timeout_http, agente=agente
            )
            entrada.status_http = status
            entrada.tamanho = tamanho
            entrada.url_final = url_final
        return _RespostaNome(entrada=entrada)

    executor = ThreadPoolExecutor(max_workers=trabalhadores, thread_name_prefix="wtb-sub")
    futuros = {executor.submit(consultar, nome): nome for nome in lista}
    consultados = 0
    try:
        for futuro in as_completed(futuros):
            if cancelado():
                cancelado_em = True
                break
            consultados += 1
            nome = futuros[futuro]
            try:
                resposta = futuro.result()
            except Exception as exc:
                erros += 1
                logar("ERRO", f"Falha inesperada em {nome}: {exc}")
                continue
            if resposta.cancelado:
                cancelado_em = True
                break
            if resposta.erro:
                erros += 1
            if resposta.descartado is not None:
                descartados.append(resposta.descartado)
                logar(
                    "AVISO",
                    f"{resposta.descartado.fqdn} ignorado por corresponder ao wildcard.",
                )
            if resposta.entrada is not None:
                encontrados.append(resposta.entrada)
                status = resposta.entrada.texto_status()
                logar("SUCESSO", f"Encontrado: {resposta.entrada.fqdn} ({status})")
            progresso(consultados, total, f"{consultados} de {total} nomes consultados")
    finally:
        cancelado_em = cancelado_em or cancelado()
        executor.shutdown(wait=not cancelado_em, cancel_futures=True)

    encontrados.sort(key=lambda item: item.fqdn)
    descartados.sort(key=lambda item: item.fqdn)
    duracao = time.perf_counter() - iniciou
    logar(
        "INFO",
        f"Enumeração finalizada em {duracao:.1f} s: {len(encontrados)} subdomínio(s), "
        f"{len(descartados)} descartado(s) por wildcard.",
    )
    if cancelado_em:
        logar("AVISO", "Execução cancelada pelo usuário.")

    if incluir_wildcard:
        encontrados = encontrados + descartados
        encontrados.sort(key=lambda item: item.fqdn)

    return ResultadoSubdominio(
        dominio=dominio,
        provedor=provedor,
        wildcard=wildcard,
        ips_wildcard=list(ips_wildcard),
        total_nomes=len(lista),
        total_consultados=consultados,
        encontrados=encontrados,
        descartados=descartados,
        erros=erros,
        cancelado=cancelado_em,
        duracao_s=duracao,
    )


def gerar_csv(resultado: ResultadoSubdominio) -> str:
    """Gera o conteúdo CSV (separador ponto e vírgula) dos subdomínios."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", lineterminator="\n")
    escritor.writerow(
        [
            "Subdomínio",
            "Endereços IP",
            "Status HTTP",
            "Tamanho (bytes)",
            "URL final",
            "Falso positivo (wildcard)",
        ]
    )
    for entrada in resultado.encontrados:
        escritor.writerow(
            [
                entrada.fqdn,
                ", ".join(entrada.ips),
                entrada.texto_status(),
                entrada.tamanho,
                entrada.url_final,
                "sim" if entrada.falso_positivo else "nao",
            ]
        )
    return buffer.getvalue()


def gerar_json(resultado: ResultadoSubdominio) -> str:
    """Gera o conteúdo JSON completo do resultado."""
    dados = {
        "dominio": resultado.dominio,
        "provedor_dns": resultado.provedor,
        "wildcard": resultado.wildcard,
        "ips_wildcard": resultado.ips_wildcard,
        "total_nomes": resultado.total_nomes,
        "total_consultados": resultado.total_consultados,
        "duracao_segundos": round(resultado.duracao_s, 2),
        "erros": resultado.erros,
        "cancelado": resultado.cancelado,
        "encontrados": [asdict(entrada) for entrada in resultado.encontrados],
        "descartados": [asdict(entrada) for entrada in resultado.descartados],
    }
    return json.dumps(dados, ensure_ascii=False, indent=2)


def cor_status_http(status: Optional[int], falso_positivo: bool = False) -> Optional[str]:
    """Define a cor de destaque do status HTTP na tabela de resultados."""
    if falso_positivo:
        return "#9ca3af"
    if status is None:
        return "#9ca3af"
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
class SubdomainEnumTool(Tool):
    """Ferramenta de enumeração de subdomínios com detecção de wildcard."""

    id = "web.subdomain_enum"
    name = "Enumeração de Subdomínios"
    category = "Web"
    description = (
        "Descoberta de subdomínios por wordlist interna, com concorrência controlada, "
        "detecção de wildcard, checagem HTTP opcional e exportação CSV"
    )
    keywords = [
        "subdomínios",
        "subdominios",
        "dns",
        "enumeração",
        "enumeracao",
        "wildcard",
        "reconhecimento",
        "web",
        "wordlist",
        "osint",
    ]
    optional_deps = ["requests", "dnspython"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return SubdomainEnumView(self, parent)


class SubdomainEnumView(PainelFerramenta):
    """Interface de configuração, execução e exportação da enumeração de subdomínios."""

    def __init__(self, tool: SubdomainEnumTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[ResultadoSubdominio] = None
        self._construir_interface()

    def _construir_interface(self) -> None:
        """Monta todos os cartões e controles da página."""
        self.adicionar(criar_aviso(TEXTO_AVISO, self, destaque=True))

        cartao_alvo, layout_alvo = criar_card("Domínio e parâmetros", self)
        self.adicionar(cartao_alvo)

        linha_alvo = QHBoxLayout()
        linha_alvo.setSpacing(8)
        linha_alvo.addWidget(QLabel("Domínio alvo:"))
        self.txt_alvo = QLineEdit("exemplo.com")
        self.txt_alvo.setPlaceholderText("exemplo.com ou https://exemplo.com")
        self.txt_alvo.returnPressed.connect(self._iniciar)
        linha_alvo.addWidget(self.txt_alvo, stretch=1)
        self.btn_iniciar = QPushButton("Iniciar enumeração")
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
        self.spin_threads.setValue(12)
        grade.addWidget(QLabel("Threads:"), 0, 0)
        grade.addWidget(self.spin_threads, 0, 1)

        self.spin_atraso = QDoubleSpinBox()
        self.spin_atraso.setRange(0.0, LIMITE_MAXIMO_ATRASO)
        self.spin_atraso.setDecimals(2)
        self.spin_atraso.setSingleStep(0.1)
        self.spin_atraso.setSuffix(" s")
        grade.addWidget(QLabel("Atraso por consulta:"), 0, 2)
        grade.addWidget(self.spin_atraso, 0, 3)

        self.spin_timeout_dns = QDoubleSpinBox()
        self.spin_timeout_dns.setRange(0.5, 30.0)
        self.spin_timeout_dns.setDecimals(1)
        self.spin_timeout_dns.setSuffix(" s")
        self.spin_timeout_dns.setValue(4.0)
        grade.addWidget(QLabel("Timeout DNS:"), 0, 4)
        grade.addWidget(self.spin_timeout_dns, 0, 5)

        self.spin_timeout_http = QDoubleSpinBox()
        self.spin_timeout_http.setRange(1.0, 60.0)
        self.spin_timeout_http.setDecimals(1)
        self.spin_timeout_http.setSuffix(" s")
        self.spin_timeout_http.setValue(8.0)
        grade.addWidget(QLabel("Timeout HTTP:"), 1, 0)
        grade.addWidget(self.spin_timeout_http, 1, 1)

        self.chk_http = QCheckBox("Verificar resposta HTTP (mais lento)")
        self.chk_http.setChecked(True)
        grade.addWidget(self.chk_http, 1, 2, 1, 2)

        self.chk_wildcard = QCheckBox("Exibir falsos positivos de wildcard")
        grade.addWidget(self.chk_wildcard, 1, 4, 1, 2)

        layout_alvo.addLayout(grade)

        self.lbl_wordlist = QLabel(
            f"Wordlist interna com {len(WORDLIST_SUBDOMINIOS)} nomes. "
            f"Mecanismo de resolução disponível: {provedor_dns()}."
        )
        self.lbl_wordlist.setProperty("class", "secondary")
        self.lbl_wordlist.setWordWrap(True)
        layout_alvo.addWidget(self.lbl_wordlist)

        self.progresso = QProgressBar()
        self.progresso.setRange(0, 100)
        self.progresso.setValue(0)
        self.progresso.setFormat("%v de %m")
        layout_alvo.addWidget(self.progresso)

        self.lbl_status = QLabel(
            "Pronto para iniciar. A detecção de wildcard ocorre antes da enumeração."
        )
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout_alvo.addWidget(self.lbl_status)

        _, layout_tabela = self.adicionar_card("Subdomínios encontrados")
        self.tabela: QTableWidget = criar_tabela(
            ["Subdomínio", "Endereços IP", "Status HTTP", "Tamanho", "URL final"]
        )
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(4, QHeaderView.Stretch)
        self.tabela.setMinimumHeight(230)
        layout_tabela.addWidget(self.tabela)

        _, layout_resumo = self.adicionar_card("Resumo da enumeração")
        self.saida = criar_saida_texto(120)
        self.saida.setPlainText("O resumo da enumeração será exibido aqui após a execução.")
        layout_resumo.addWidget(self.saida)

        linha_botoes = QHBoxLayout()
        self.btn_csv = QPushButton("Exportar CSV...")
        self.btn_csv.setEnabled(False)
        self.btn_csv.clicked.connect(self._exportar_csv)
        linha_botoes.addWidget(self.btn_csv)
        self.btn_json = QPushButton("Exportar JSON...")
        self.btn_json.setEnabled(False)
        self.btn_json.clicked.connect(self._exportar_json)
        linha_botoes.addWidget(self.btn_json)
        linha_botoes.addStretch(1)
        layout_resumo.addLayout(linha_botoes)

        self._log = adicionar_log_painel(self, "Log da enumeração")
        self.adicionar_espaco()

    def _iniciar(self) -> None:
        """Confirma o termo ético e dispara a enumeração assíncrona."""
        if not confirmar_termo_etico(self, self.tool.id):
            self._log.append_log("AVISO", "Execução recusada: termo de responsabilidade não aceito.")
            return

        try:
            dominio = normalizar_dominio(self.txt_alvo.text())
        except ValueError as exc:
            mostrar_erro(self, "Domínio inválido", exc)
            return

        threads = self.spin_threads.value()
        atraso = self.spin_atraso.value()
        timeout_dns = self.spin_timeout_dns.value()
        timeout_http = self.spin_timeout_http.value()
        verificar = self.chk_http.isChecked()
        incluir_wildcard = self.chk_wildcard.isChecked()

        self._resultado = None
        self._log.clear()
        self.tabela.setRowCount(0)
        self.saida.setPlainText("Enumeração em andamento...")
        self.progresso.setRange(0, 100)
        self.progresso.setValue(0)
        self.btn_iniciar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.btn_csv.setEnabled(False)
        self.btn_json.setEnabled(False)
        self.lbl_status.setText(f"Consultando subdomínios de {dominio}...")

        def tarefa(ctx):
            return executar_enumeracao(
                dominio,
                threads=threads,
                atraso=atraso,
                timeout_dns=timeout_dns,
                verificar_http_habilitado=verificar,
                timeout_http=timeout_http,
                incluir_wildcard=incluir_wildcard,
                is_cancelled=ctx.is_cancelled,
                on_progress=ctx.progress,
                on_log=ctx.log,
            )

        def concluiu(resultado: ResultadoSubdominio) -> None:
            self._resultado = resultado
            self.btn_iniciar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.progresso.setValue(self.progresso.maximum())
            self._preencher(resultado)

        def falhou(erro: Exception) -> None:
            self.btn_iniciar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.lbl_status.setText("A enumeração falhou. Consulte o log de execução.")
            self.saida.setPlainText(f"Falha na enumeração: {erro}")
            mostrar_erro(self, "Falha na enumeração", erro)

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
        """Solicita o cancelamento cooperativo da enumeração em execução."""
        if hasattr(self.runner, "cancel_current"):
            self.runner.cancel_current()
        self.btn_cancelar.setEnabled(False)
        self.lbl_status.setText("Cancelamento solicitado. Aguardando as consultas em curso...")
        self._log.append_log("AVISO", "Cancelamento solicitado pelo usuário.")

    def _preencher(self, resultado: ResultadoSubdominio) -> None:
        """Atualiza tabela, resumo e botões de exportação."""
        linhas = [entrada.para_linha() for entrada in resultado.encontrados]
        preencher_tabela(self.tabela, linhas)
        for indice, entrada in enumerate(resultado.encontrados):
            item = self.tabela.item(indice, 2)
            if item is None:
                continue
            cor = cor_status_http(entrada.status_http, entrada.falso_positivo)
            if cor:
                item.setForeground(QBrush(QColor(cor)))
        self.saida.setPlainText(resultado.resumo())
        self.btn_csv.setEnabled(bool(resultado.encontrados))
        self.btn_json.setEnabled(True)
        if resultado.wildcard:
            self.lbl_status.setText(
                "Enumeração concluída com wildcard detectado: "
                f"{len(resultado.encontrados)} subdomínio(s) e "
                f"{len(resultado.descartados)} descarte(s) por falso positivo."
            )
        elif resultado.cancelado:
            self.lbl_status.setText(
                f"Enumeração cancelada após {resultado.total_consultados} consulta(s)."
            )
        else:
            self.lbl_status.setText(
                f"Enumeração concluída em {resultado.duracao_s:.1f} s. "
                f"{len(resultado.encontrados)} subdomínio(s) encontrado(s)."
            )

    def _exportar_csv(self) -> None:
        """Solicita o destino e grava o CSV dos subdomínios."""
        if not self._resultado:
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar subdomínios",
            "subdominios.csv",
            "Arquivo CSV (*.csv);;Todos os arquivos (*.*)",
        )
        if not destino:
            return
        self._salvar(destino, gerar_csv(self._resultado))

    def _exportar_json(self) -> None:
        """Solicita o destino e grava o JSON completo da enumeração."""
        if not self._resultado:
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar subdomínios",
            "subdominios.json",
            "Arquivo JSON (*.json);;Todos os arquivos (*.*)",
        )
        if not destino:
            return
        self._salvar(destino, gerar_json(self._resultado))

    def _salvar(self, destino: str, conteudo: str) -> None:
        """Grava o conteúdo em disco com tratamento de erro amigável."""
        try:
            with open(destino, "w", encoding="utf-8", newline="") as arquivo:
                arquivo.write(conteudo)
        except OSError as exc:
            mostrar_erro(self, "Falha ao salvar", exc)
            return
        self._log.append_log("SUCESSO", f"Resultado exportado para {destino}.")
        self.lbl_status.setText(f"Resultado exportado para {destino}.")

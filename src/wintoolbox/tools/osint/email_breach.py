"""Consulta de vazamentos de e-mail na API v3 do Have I Been Pwned.

A chave de API nunca é escrita no código: ela é lida de `get_api_token("hibp")`,
ou seja, do cofre local preenchido em Configurações. O módulo aceita lote de
endereços, classifica o risco a partir das classes de dados expostos e devolve o
detalhamento em JSON.
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.settings import get_api_token
from wintoolbox.tools._helpers import confirmar_termo_etico, truncar
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

_log = get_logger("osint.email_breach")

SERVICO_TOKEN = "hibp"
URL_API = "https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
UA_API = "WinToolbox-OSINT"

TEXTO_ETICO = (
    "Esta ferramenta consulta dados de terceiros em uma base pública de vazamentos "
    "e pode revelar informações pessoais sensíveis (senhas expostas, documentos, "
    "endereços e dados financeiros).\n\n"
    "A Lei 13.709/2018 (LGPD) exige base legal, finalidade específica e minimização "
    "para tratar dados pessoais de outras pessoas. Use apenas em contas próprias, "
    "em investigação autorizada por escrito ou em resposta a incidente do qual você "
    "é responsável.\n\n"
    "A consulta é enviada diretamente à API oficial do Have I Been Pwned com a chave "
    "que você configurou; nenhum dado é armazenado pelo WinToolbox.\n\n"
    "Você confirma que assume integral responsabilidade pelo uso?"
)

INSTRUCAO_TOKEN = (
    "Nenhuma chave da API do Have I Been Pwned foi encontrada.\n\n"
    "Como configurar:\n"
    "1. Abra Configurações > Chaves de API e Tokens.\n"
    "2. Clique em Adicionar chave personalizada e use o identificador hibp.\n"
    "3. Cole a chave obtida em haveibeenpwned.com/API/Key e salve.\n\n"
    "A API v3 de contas vazadas exige uma assinatura paga do HIBP. A chave fica "
    "guardada nas preferências locais e nunca é incluída no código-fonte."
)

CLASSES_CRITICAS = {
    "passwords": 40,
    "credit cards": 30,
    "bank accounts": 30,
    "government ids": 18,
    "password hints": 12,
    "security questions and answers": 14,
    "physical addresses": 6,
    "phone numbers": 8,
    "dates of birth": 6,
    "ip addresses": 5,
    "sexual orientations": 8,
    "health records": 20,
}

_PADRAO_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def normalizar_emails(texto: str) -> List[str]:
    """Extrai e valida endereços de e-mail de um texto multilinha."""
    vistos: List[str] = []
    invalidos: List[str] = []
    for pedaco in re.split(r"[\s,;]+", str(texto or "")):
        email = pedaco.strip().strip("<>").lower()
        if not email:
            continue
        if not _PADRAO_EMAIL.fullmatch(email):
            invalidos.append(email)
            continue
        if email not in vistos:
            vistos.append(email)
    if not vistos and not invalidos:
        raise ValueError("Informe ao menos um endereço de e-mail.")
    if not vistos and invalidos:
        raise ValueError(f"Nenhum e-mail válido encontrado. Verifique: {', '.join(invalidos[:3])}")
    return vistos


def _classe_risco(pontuacao: int) -> str:
    if pontuacao >= 60:
        return "Crítico"
    if pontuacao >= 35:
        return "Alto"
    if pontuacao >= 15:
        return "Médio"
    if pontuacao > 0:
        return "Baixo"
    return "Nenhum"


def classificar_risco(vazamentos: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcula pontuação, nível e justificativas a partir das classes de dados."""
    pontuacao = 0
    motivos: List[str] = []
    classes: Dict[str, int] = {}

    for vazamento in vazamentos:
        for classe in vazamento.get("DataClasses", []) or []:
            chave = str(classe).strip()
            classes[chave] = classes.get(chave, 0) + 1
            peso = CLASSES_CRITICAS.get(chave.lower(), 0)
            if peso:
                pontuacao += peso

    if vazamentos:
        pontuacao += min(20, len(vazamentos) * 2)
        if len(vazamentos) >= 5:
            motivos.append(f"{len(vazamentos)} vazamentos distintos")

    recente = None
    for vazamento in vazamentos:
        data = str(vazamento.get("BreachDate", ""))
        if len(data) == 10:
            try:
                quando = datetime.strptime(data, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if recente is None or quando > recente:
                recente = quando
    if recente is not None:
        dias = (datetime.now(timezone.utc) - recente).days
        if dias <= 365:
            pontuacao += 10
            motivos.append("vazamento nos últimos 12 meses")
        elif dias <= 730:
            pontuacao += 5
            motivos.append("vazamento nos últimos 24 meses")

    for chave, quantidade in sorted(classes.items(), key=lambda item: -item[1]):
        if chave.lower() in CLASSES_CRITICAS:
            motivos.append(f"{chave} exposto em {quantidade} vazamento(s)")

    pontuacao = min(100, pontuacao)
    return {
        "nivel": _classe_risco(pontuacao),
        "pontuacao": pontuacao,
        "motivos": motivos,
        "classes": classes,
    }


def _converter_vazamento(bruto: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um item da API para o formato usado pela interface."""
    return {
        "Nome": bruto.get("Name", ""),
        "Titulo": bruto.get("Title", ""),
        "Dominio": bruto.get("Domain", ""),
        "Data": bruto.get("BreachDate", ""),
        "Adicionado": bruto.get("AddedDate", ""),
        "Contas": bruto.get("PwnCount", 0),
        "Classes": list(bruto.get("DataClasses", []) or []),
        "Verificado": bool(bruto.get("IsVerified", False)),
        "Sensivel": bool(bruto.get("IsSensitive", False)),
        "Spam": bool(bruto.get("IsSpamList", False)),
        "Descricao": re.sub(r"<[^>]+>", " ", str(bruto.get("Description", "")))[:600],
    }


def consultar_email(email: str, token: str, timeout: float = 15.0) -> Dict[str, Any]:
    """Consulta um único e-mail na API v3 do HIBP."""
    import requests

    email = email.strip().lower()
    if not _PADRAO_EMAIL.fullmatch(email):
        raise ValueError(f"E-mail inválido: {email}")
    if not str(token or "").strip():
        raise ValueError("Chave da API do HIBP não configurada.")

    resposta_base: Dict[str, Any] = {
        "email": email,
        "ok": False,
        "status_http": None,
        "vazamentos": [],
        "total": 0,
        "risco": {"nivel": "Nenhum", "pontuacao": 0, "motivos": [], "classes": {}},
        "erro": "",
    }
    try:
        resposta = requests.get(
            URL_API.format(email=email),
            headers={
                "hibp-api-key": str(token).strip(),
                "User-Agent": UA_API,
                "Accept": "application/json",
            },
            timeout=timeout,
            params={"truncateResponse": "false"},
        )
    except Exception as exc:  # noqa: BLE001
        resposta_base["erro"] = f"Falha de rede: {exc}"
        return resposta_base

    resposta_base["status_http"] = resposta.status_code
    if resposta.status_code == 404:
        resposta_base["ok"] = True
        return resposta_base
    if resposta.status_code == 401:
        resposta_base["erro"] = "Chave da API inválida ou não informada (HTTP 401)."
        return resposta_base
    if resposta.status_code == 403:
        resposta_base["erro"] = (
            "A chave não possui acesso a este recurso (HTTP 403). A API de contas vazadas "
            "do HIBP exige assinatura ativa."
        )
        return resposta_base
    if resposta.status_code == 429:
        espera = resposta.headers.get("Retry-After", "")
        resposta_base["erro"] = (
            "Limite de requisições do HIBP atingido (HTTP 429)."
            + (f" Tente novamente em {espera} segundo(s)." if espera else " Aguarde e tente novamente.")
        )
        return resposta_base
    if resposta.status_code >= 400:
        resposta_base["erro"] = f"Resposta inesperada do HIBP: HTTP {resposta.status_code}."
        return resposta_base

    try:
        dados = resposta.json() or []
    except ValueError:
        resposta_base["erro"] = "A resposta do HIBP não está em JSON válido."
        return resposta_base

    vazamentos = [_converter_vazamento(item) for item in dados if isinstance(item, dict)]
    vazamentos.sort(key=lambda item: item.get("Data", ""), reverse=True)
    resposta_base["vazamentos"] = vazamentos
    resposta_base["total"] = len(vazamentos)
    resposta_base["risco"] = classificar_risco(vazamentos)
    resposta_base["ok"] = True
    return resposta_base


def consultar_lote(
    emails: Sequence[str],
    token: str,
    max_workers: int = 4,
    timeout: float = 15.0,
    ao_progresso: Optional[Callable[[int, int, str], None]] = None,
    ao_log: Optional[Callable[[str, str], None]] = None,
    deve_cancelar: Optional[Callable[[], bool]] = None,
) -> List[Dict[str, Any]]:
    """Consulta vários e-mails respeitando um limite modesto de concorrência."""
    total = len(emails)
    resultados: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), 10))) as executor:
        futuros = {executor.submit(consultar_email, email, token, timeout): email for email in emails}
        feitos = 0
        for futuro in as_completed(futuros):
            if deve_cancelar is not None and deve_cancelar():
                for pendente in futuros:
                    pendente.cancel()
                if ao_log is not None:
                    ao_log("WARN", "Consulta em lote cancelada pelo usuário.")
                break
            email = futuros[futuro]
            try:
                resultados.append(futuro.result())
            except Exception as exc:  # noqa: BLE001
                resultados.append(
                    {
                        "email": email,
                        "ok": False,
                        "status_http": None,
                        "vazamentos": [],
                        "total": 0,
                        "risco": {"nivel": "Nenhum", "pontuacao": 0, "motivos": [], "classes": {}},
                        "erro": str(exc),
                    }
                )
            feitos += 1
            if ao_progresso is not None:
                ao_progresso(feitos, total, email)
    ordem = {email: indice for indice, email in enumerate(emails)}
    resultados.sort(key=lambda item: ordem.get(item.get("email", ""), 9999))
    return resultados


def exportar_json(resultados: Sequence[Dict[str, Any]], destino: Path) -> Path:
    """Grava o relatório completo em JSON e devolve o caminho final."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ferramenta": "osint.email_breach",
        "fonte": "Have I Been Pwned API v3",
        "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "consultas": list(resultados),
    }
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def resumo_texto(resultados: Sequence[Dict[str, Any]]) -> str:
    """Resumo legível do lote consultado."""
    linhas = [f"Consultas: {len(resultados)}", ""]
    for item in resultados:
        risco = item.get("risco") or {}
        if item.get("erro"):
            linhas.append(f"{item['email']}: erro - {item['erro']}")
            continue
        if not item.get("total"):
            linhas.append(f"{item['email']}: nenhum vazamento conhecido")
            continue
        linhas.append(
            f"{item['email']}: {item['total']} vazamento(s), risco {risco.get('nivel', '-')} "
            f"({risco.get('pontuacao', 0)}/100)"
        )
        for vazamento in item.get("vazamentos", []):
            linhas.append(
                f"  - {vazamento.get('Titulo') or vazamento.get('Nome')} ({vazamento.get('Data', '-')}): "
                f"{', '.join(vazamento.get('Classes', []))}"
            )
        if risco.get("motivos"):
            linhas.append(f"  Motivos: {'; '.join(risco['motivos'])}")
    return "\n".join(linhas)


@register
class EmailBreachTool(Tool):
    """Ferramenta de verificação de e-mails vazados via HIBP."""

    id = "osint.email_breach"
    name = "Verificador de Vazamentos de E-mail"
    category = "OSINT"
    description = (
        "Consulta em lote a API v3 do Have I Been Pwned para saber quais vazamentos "
        "expuseram cada e-mail, classifica o risco pelas classes de dados e exporta o relatório em JSON"
    )
    keywords = [
        "osint", "email", "e-mail", "vazamento", "breach", "have i been pwned", "hibp",
        "credencial", "lgpd", "risco",
    ]
    optional_deps = []

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return EmailBreachView(self, parent)


class EmailBreachView(PainelFerramenta):
    """Painel interativo do verificador de vazamentos de e-mail."""

    def __init__(self, tool: EmailBreachTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultados: List[Dict[str, Any]] = []
        self._executando = False

        self.adicionar_aviso(TEXTO_ETICO, destaque=True)

        card_chave, layout_chave = self.adicionar_card("Chave da API")
        self.lbl_token = QLabel()
        self.lbl_token.setWordWrap(True)
        layout_chave.addWidget(self.lbl_token)
        self.aviso_token = self.adicionar_aviso(INSTRUCAO_TOKEN, destaque=True)
        self._atualizar_estado_token()

        card_entrada, layout_entrada = self.adicionar_card("Endereços a consultar")
        layout_entrada.addWidget(
            QLabel("Um e-mail por linha (ou separados por vírgula/ponto e vírgula):")
        )
        self.txt_emails = QPlainTextEdit()
        self.txt_emails.setPlaceholderText("usuario@exemplo.com\noutro@exemplo.com.br")
        self.txt_emails.setFixedHeight(110)
        layout_entrada.addWidget(self.txt_emails)

        linha_opcoes = QHBoxLayout()
        linha_opcoes.addWidget(QLabel("Consultas simultâneas:"))
        self.spn_threads = QSpinBox()
        self.spn_threads.setRange(1, 10)
        self.spn_threads.setValue(3)
        linha_opcoes.addWidget(self.spn_threads)
        linha_opcoes.addWidget(QLabel("Tempo limite (s):"))
        self.spn_timeout = QSpinBox()
        self.spn_timeout.setRange(5, 60)
        self.spn_timeout.setValue(15)
        linha_opcoes.addWidget(self.spn_timeout)
        linha_opcoes.addStretch()
        layout_entrada.addLayout(linha_opcoes)

        linha_acoes = QHBoxLayout()
        self.btn_executar = QPushButton("Consultar Vazamentos")
        self.btn_executar.setProperty("class", "primary")
        self.btn_executar.clicked.connect(self._executar)
        linha_acoes.addWidget(self.btn_executar)

        self.btn_exportar = QPushButton("Exportar JSON...")
        self.btn_exportar.clicked.connect(self._exportar)
        linha_acoes.addWidget(self.btn_exportar)

        self.btn_copiar = botao_copiar(self._texto_saida, self, "Copiar resultado")
        linha_acoes.addWidget(self.btn_copiar)

        self.lbl_status = QLabel("Nenhuma consulta executada.")
        self.lbl_status.setWordWrap(True)
        linha_acoes.addWidget(self.lbl_status, stretch=1)
        layout_entrada.addLayout(linha_acoes)

        card_resultados, layout_resultados = self.adicionar_card("Resultados por e-mail")
        self.tabela = criar_tabela(
            ["E-mail", "Vazamentos", "Risco", "Pontuação", "Dados expostos", "Vazamento mais recente"],
            self,
        )
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        layout_resultados.addWidget(self.tabela)

        card_saida, layout_saida = self.adicionar_card("Resumo e JSON")
        self.saida = criar_saida_texto(240, self)
        layout_saida.addWidget(self.saida)

        self.log = adicionar_log_painel(self, "Log das consultas")
        self.adicionar_espaco()

    # ------------------------------------------------------------------ estado
    def _token_configurado(self) -> str:
        try:
            return str(get_api_token(SERVICO_TOKEN, "") or "").strip()
        except Exception:  # noqa: BLE001 - preferências podem estar indisponíveis
            return ""

    def _atualizar_estado_token(self) -> None:
        token = self._token_configurado()
        if token:
            self.lbl_token.setText(
                "Chave configurada para o serviço hibp (a chave não é exibida na interface)."
            )
            self.aviso_token.setVisible(False)
        else:
            self.lbl_token.setText("Chave não configurada para o serviço hibp.")
            self.aviso_token.setVisible(True)

    def _texto_saida(self) -> str:
        return self.saida.toPlainText()

    def _definir_execucao(self, ativa: bool) -> None:
        self._executando = ativa
        for botao in (self.btn_executar, self.btn_exportar):
            botao.setEnabled(not ativa)

    def _executar(self) -> None:
        if self._executando:
            return
        self._atualizar_estado_token()
        token = self._token_configurado()
        if not token:
            self.aviso_token.setVisible(True)
            mostrar_erro(self, "Chave da API ausente", INSTRUCAO_TOKEN)
            return
        try:
            emails = normalizar_emails(self.txt_emails.toPlainText())
        except ValueError as exc:
            mostrar_erro(self, "E-mails inválidos", exc)
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return

        threads = self.spn_threads.value()
        timeout = float(self.spn_timeout.value())

        self._definir_execucao(True)
        self.lbl_status.setText(f"Consultando {len(emails)} e-mail(s) no HIBP...")
        self.tabela.setRowCount(0)
        self.saida.clear()
        self.log.append_log("INFO", f"Consultando {len(emails)} e-mail(s) na API v3 do HIBP.")

        def tarefa(ctx):
            return consultar_lote(
                emails,
                token,
                max_workers=threads,
                timeout=timeout,
                ao_progresso=lambda feitos, total, email: ctx.progress(feitos, total, email),
                ao_log=ctx.log,
                deve_cancelar=ctx.cancelled,
            )

        def concluiu(resultados) -> None:
            self._definir_execucao(False)
            self._resultados = list(resultados or [])
            self._preencher()
            criticos = sum(
                1
                for item in self._resultados
                if (item.get("risco") or {}).get("nivel") in {"Crítico", "Alto"}
            )
            self.lbl_status.setText(
                f"{len(self._resultados)} e-mail(s) consultado(s); "
                f"{criticos} com risco alto ou crítico."
            )
            self.log.append_log("INFO", "Consulta em lote concluída.")

        def falhou(erro: Exception) -> None:
            self._definir_execucao(False)
            self.lbl_status.setText("Falha na consulta.")
            self.log.append_log("ERROR", str(erro))
            mostrar_erro(self, "Falha na consulta de vazamentos", erro)

        executar_assincrono(self, tarefa, concluiu, falhou)

    def _preencher(self) -> None:
        linhas: List[List[Any]] = []
        for item in self._resultados:
            risco = item.get("risco") or {}
            classes: List[str] = []
            for vazamento in item.get("vazamentos", []):
                for classe in vazamento.get("Classes", []):
                    if classe not in classes:
                        classes.append(classe)
            datas = [v.get("Data") for v in item.get("vazamentos", []) if v.get("Data")]
            if item.get("erro"):
                situacao = "Erro"
                total = "-"
            else:
                total = item.get("total", 0)
                situacao = risco.get("nivel", "-")
            linhas.append(
                [
                    item.get("email", ""),
                    total,
                    situacao,
                    risco.get("pontuacao", 0) if not item.get("erro") else "-",
                    ", ".join(classes[:8]) if classes else "-",
                    max(datas) if datas else "-",
                ]
            )
        preencher_tabela(self.tabela, linhas)
        self.saida.setPlainText(
            resumo_texto(self._resultados)
            + "\n\n"
            + json.dumps(list(self._resultados), ensure_ascii=False, indent=2)
        )

    def _exportar(self) -> None:
        if not self._resultados:
            mostrar_erro(self, "Nada para exportar", "Execute uma consulta antes de exportar.")
            return
        destino, _ = QFileDialog.getSaveFileName(
            self, "Salvar relatório", "vazamentos_email.json", "JSON (*.json)"
        )
        if not destino:
            return
        try:
            final = exportar_json(self._resultados, Path(destino))
            self.lbl_status.setText(f"Relatório exportado para {final}.")
            self.log.append_log("INFO", f"Relatório gravado em {final}.")
        except OSError as exc:
            mostrar_erro(self, "Falha ao exportar", exc)

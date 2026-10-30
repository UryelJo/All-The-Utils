"""Ferramenta: Construção e envio de pacotes ICMP, TCP, UDP e DNS.

Os pacotes são montados com o Scapy dentro da tarefa assíncrona, portanto a
interface abre normalmente mesmo sem a dependência instalada. O envio pode
aguardar resposta (``sr1``) ou apenas disparar o quadro (``send``).

O histórico guarda latência e resultado de cada envio. O traceroute usa o campo
TTL do cabeçalho IP para descobrir os saltos até o destino.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.elevation import is_admin
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import (
    DependenciaAusente,
    aviso_dependencia,
    confirmar_termo_etico,
    dependencia_disponivel,
    garantir_admin,
    salvar_texto,
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
    "O envio de pacotes forjados permite testar firewalls, filtros e serviços, "
    "mas também pode simular origem falsa, causar indisponibilidade e induzir "
    "equipamentos a erro.\n\n"
    "Use esta ferramenta somente em equipamentos e redes que você administra ou "
    "para os quais possui autorização expressa e por escrito do responsável, "
    "registrando o escopo e a janela de testes.\n\n"
    "A prática sem autorização pode configurar crime previsto na Lei 12.737/2012 "
    "(art. 154-A do Código Penal), além de violar normas de telecomunicações e a "
    "Lei 13.709/2018 (LGPD).\n\n"
    "Você declara possuir autorização por escrito e assume integral "
    "responsabilidade pelos pacotes que enviar?"
)

TIPOS_DNS = (("A", 1), ("AAAA", 28), ("MX", 15), ("TXT", 16), ("NS", 2), ("CNAME", 5))
ORDEM_FLAGS = ("F", "S", "R", "P", "A", "U")
ROTULOS_FLAGS = {
    "F": "FIN",
    "S": "SYN",
    "R": "RST",
    "P": "PSH",
    "A": "ACK",
    "U": "URG",
}


def _verificar_scapy(parent: QWidget) -> bool:
    """Confere a presença do Scapy sem importá-lo no carregamento do módulo."""
    if dependencia_disponivel("scapy"):
        return True
    aviso_dependencia(parent, DependenciaAusente("Scapy", "scapy.all", "scapy"))
    return False


def _montar_pacote(params: Dict[str, Any]):
    """Monta o pacote Scapy conforme o formulário da aba selecionada."""
    from scapy.all import DNS, DNSQR, ICMP, IP, Raw, TCP, UDP, RandShort

    destino = params["destino"]
    payload = str(params.get("payload") or "")
    carga = Raw(load=payload.encode("utf-8", errors="ignore")) if payload else None

    if params["tipo"] == "ICMP":
        camada = ICMP(type=int(params["icmp_tipo"]), code=int(params["icmp_codigo"]))
        pacote = IP(dst=destino) / camada
    elif params["tipo"] == "TCP":
        camada = TCP(
            dport=int(params["porta"]),
            flags=str(params["flags"] or "S"),
            seq=int(params.get("sequencia") or 0),
        )
        pacote = IP(dst=destino) / camada
    elif params["tipo"] == "UDP":
        camada = UDP(dport=int(params["porta"]))
        pacote = IP(dst=destino) / camada
    elif params["tipo"] == "DNS":
        consulta = DNSQR(qname=str(params["qname"]), qtype=int(params["qtype"]))
        pacote = (
            IP(dst=destino)
            / UDP(sport=RandShort(), dport=53)
            / DNS(rd=1, qd=consulta)
        )
    else:
        raise ValueError("Tipo de pacote não suportado.")

    if carga is not None:
        pacote = pacote / carga
    return pacote


def _enviar_pacote(params: Dict[str, Any], aguardar: bool, timeout: int) -> Dict[str, Any]:
    """Envia o pacote montado e devolve o resultado com latência medida."""
    from scapy.all import send, sr1

    pacote = _montar_pacote(params)
    inicio = time.perf_counter()
    resposta = None
    if aguardar:
        resposta = sr1(pacote, timeout=timeout, verbose=0)
    else:
        send(pacote, verbose=0)
    latencia = (time.perf_counter() - inicio) * 1000.0

    if not aguardar:
        resumo = "Enviado (sem aguardar resposta)"
    elif resposta is None:
        resumo = f"Sem resposta em {timeout} s"
    else:
        resumo = f"Resposta: {resposta.summary()}"

    detalhe = [
        f"Pacote: {pacote.summary()}",
        f"Destino: {params['destino']}",
        f"Latência: {latencia:.2f} ms".replace(".", ","),
        f"Resultado: {resumo}",
    ]
    if resposta is not None:
        detalhe.append(f"Resposta completa: {resposta.summary()}")
        origem = getattr(resposta, "src", "")
        if origem:
            detalhe.append(f"Origem da resposta: {origem}")

    return {
        "tipo": params["tipo"],
        "destino": params["destino"],
        "resumo": resumo,
        "detalhe": "\n".join(detalhe),
        "latencia": latencia,
        "pacote": pacote,
    }


def _executar_traceroute(
    destino: str, ttl_maximo: int, timeout: int, ctx
) -> List[Dict[str, Any]]:
    """Percorre os saltos do caminho variando o TTL do cabeçalho IP."""
    from scapy.all import ICMP, IP, sr1

    saltos: List[Dict[str, Any]] = []
    for ttl in range(1, ttl_maximo + 1):
        if ctx.cancelled():
            break
        pacote = IP(dst=destino, ttl=ttl) / ICMP()
        inicio = time.perf_counter()
        resposta = sr1(pacote, timeout=timeout, verbose=0)
        latencia = (time.perf_counter() - inicio) * 1000.0
        if resposta is None:
            saltos.append(
                {
                    "ttl": ttl,
                    "hop": "*",
                    "status": "Sem resposta",
                    "latencia": latencia,
                    "destino": destino,
                }
            )
            continue
        origem = str(resposta.src)
        saltos.append(
            {
                "ttl": ttl,
                "hop": origem,
                "status": "OK",
                "latencia": latencia,
                "destino": destino,
            }
        )
        if origem == destino or int(getattr(resposta, "type", -1)) == 0:
            break
    return saltos


@register
class PacketCrafterTool(Tool):
    """Ferramenta de construção de pacotes com quatro abas e traceroute."""

    id = "network.packet_crafter"
    name = "Construtor e Envio de Pacotes"
    category = "Rede e Internet"
    description = (
        "Monta e envia pacotes ICMP, TCP, UDP e DNS com flags, payload e latência, "
        "executa traceroute por TTL e exporta o histórico em TXT ou PCAP"
    )
    keywords = [
        "pacote",
        "craft",
        "icmp",
        "tcp",
        "udp",
        "dns",
        "flags",
        "traceroute",
        "ttl",
        "scapy",
    ]
    requires_admin = True
    optional_deps = ["scapy"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PacketCrafterView(self, parent)


class PacketCrafterView(PainelFerramenta):
    """Página interativa de construção e envio de pacotes."""

    def __init__(self, tool: PacketCrafterTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._linhas: List[List[str]] = []
        self._pacotes_enviados: List[Any] = []
        self._ocupado = False
        self._montar_interface()

    # ------------------------------------------------------------------ UI
    def _montar_interface(self) -> None:
        self.adicionar(
            criar_aviso(
                "Pacotes forjados podem derrubar serviços e confundir equipamentos "
                "de rede. Use apenas em ambiente de teste autorizado e prefira "
                "destinos que você controla.",
                self,
                destaque=True,
            )
        )
        self._montar_cartao_admin()

        self.tabs = QTabWidget()
        self.tabs.addTab(self._aba_icmp(), "ICMP")
        self.tabs.addTab(self._aba_tcp(), "TCP")
        self.tabs.addTab(self._aba_udp(), "UDP")
        self.tabs.addTab(self._aba_dns(), "DNS")
        self.adicionar(self.tabs)

        cartao_envio, layout_envio = self.adicionar_card("Envio")
        linha_controle = QHBoxLayout()
        linha_controle.addWidget(QLabel("Tempo limite (s):"))
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 30)
        self.spin_timeout.setValue(3)
        linha_controle.addWidget(self.spin_timeout)

        self.btn_sr1 = QPushButton("Enviar e aguardar resposta (sr1)")
        self.btn_sr1.setProperty("class", "primary")
        self.btn_sr1.clicked.connect(lambda: self._enviar(aguardar=True))
        linha_controle.addWidget(self.btn_sr1)

        self.btn_send = QPushButton("Enviar sem aguardar (send)")
        self.btn_send.clicked.connect(lambda: self._enviar(aguardar=False))
        linha_controle.addWidget(self.btn_send)
        linha_controle.addStretch()
        layout_envio.addLayout(linha_controle)

        self.lbl_status = QLabel("Preencha a aba desejada e envie o pacote.")
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout_envio.addWidget(self.lbl_status)

        cartao_rota, layout_rota = self.adicionar_card("Traceroute por TTL")
        linha_rota = QHBoxLayout()
        linha_rota.addWidget(QLabel("Destino:"))
        self.txt_rota_destino = QLineEdit("8.8.8.8")
        self.txt_rota_destino.setMaximumWidth(200)
        linha_rota.addWidget(self.txt_rota_destino)
        linha_rota.addWidget(QLabel("TTL máximo:"))
        self.spin_ttl_max = QSpinBox()
        self.spin_ttl_max.setRange(1, 30)
        self.spin_ttl_max.setValue(15)
        linha_rota.addWidget(self.spin_ttl_max)
        self.btn_tracert = QPushButton("Executar traceroute")
        self.btn_tracert.clicked.connect(self._iniciar_traceroute)
        linha_rota.addWidget(self.btn_tracert)
        linha_rota.addStretch()
        layout_rota.addLayout(linha_rota)

        cartao_hist, layout_hist = self.adicionar_card("Histórico de envios")
        self.tabela = criar_tabela(
            ["Hora", "Tipo", "Destino", "Resultado", "Latência (ms)"], self
        )
        cabecalho = self.tabela.horizontalHeader()
        for coluna in range(4):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabela.setMinimumHeight(220)
        layout_hist.addWidget(self.tabela)

        linha_hist = QHBoxLayout()
        self.btn_limpar = QPushButton("Limpar histórico")
        self.btn_limpar.clicked.connect(self._limpar_historico)
        linha_hist.addWidget(self.btn_limpar)

        self.btn_exportar_txt = QPushButton("Exportar TXT")
        self.btn_exportar_txt.clicked.connect(self._exportar_txt)
        linha_hist.addWidget(self.btn_exportar_txt)

        self.btn_exportar_pcap = QPushButton("Exportar PCAP")
        self.btn_exportar_pcap.clicked.connect(self._exportar_pcap)
        linha_hist.addWidget(self.btn_exportar_pcap)
        linha_hist.addStretch()
        layout_hist.addLayout(linha_hist)

        cartao_saida, layout_saida = self.adicionar_card("Detalhes da última operação")
        self.txt_saida = criar_saida_texto(150, self)
        layout_saida.addWidget(self.txt_saida)
        linha_saida = QHBoxLayout()
        linha_saida.addWidget(
            botao_copiar(lambda: self.txt_saida.toPlainText(), self, "Copiar detalhes")
        )
        linha_saida.addStretch()
        layout_saida.addLayout(linha_saida)

        self.log_panel = adicionar_log_painel(self, "Log de envios")
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
                "Executando com privilégios de Administrador. O envio bruto de "
                "pacotes está disponível."
            )
            self.btn_admin.setEnabled(False)
            self.btn_admin.setToolTip("O aplicativo já está elevado.")
        else:
            self.lbl_admin.setText(
                "Executando como usuário padrão. O envio de pacotes exige "
                "Administrador e o Npcap instalado."
            )
            self.btn_admin.setEnabled(True)
            self.btn_admin.setToolTip("Solicita a elevação do aplicativo via UAC.")

    # ----------------------------------------------------------------- abas
    def _aba_icmp(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        linha_destino = QHBoxLayout()
        linha_destino.addWidget(QLabel("Destino (IP ou host):"))
        self.txt_icmp_destino = QLineEdit("8.8.8.8")
        linha_destino.addWidget(self.txt_icmp_destino, stretch=1)
        layout.addLayout(linha_destino)

        linha_tipo = QHBoxLayout()
        linha_tipo.addWidget(QLabel("Tipo ICMP:"))
        self.cmb_icmp_tipo = QComboBox()
        self.cmb_icmp_tipo.addItem("Echo request (8)", 8)
        self.cmb_icmp_tipo.addItem("Echo reply (0)", 0)
        self.cmb_icmp_tipo.addItem("Destino inalcançável (3)", 3)
        linha_tipo.addWidget(self.cmb_icmp_tipo)

        linha_tipo.addWidget(QLabel("Código:"))
        self.spin_icmp_codigo = QSpinBox()
        self.spin_icmp_codigo.setRange(0, 15)
        linha_tipo.addWidget(self.spin_icmp_codigo)
        linha_tipo.addStretch()
        layout.addLayout(linha_tipo)

        linha_payload = QHBoxLayout()
        linha_payload.addWidget(QLabel("Payload (texto):"))
        self.txt_icmp_payload = QLineEdit()
        self.txt_icmp_payload.setPlaceholderText("Opcional")
        linha_payload.addWidget(self.txt_icmp_payload, stretch=1)
        layout.addLayout(linha_payload)
        layout.addStretch()
        return aba

    def _aba_tcp(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        linha_destino = QHBoxLayout()
        linha_destino.addWidget(QLabel("Destino (IP ou host):"))
        self.txt_tcp_destino = QLineEdit("192.168.0.1")
        linha_destino.addWidget(self.txt_tcp_destino, stretch=1)
        linha_destino.addWidget(QLabel("Porta:"))
        self.spin_tcp_porta = QSpinBox()
        self.spin_tcp_porta.setRange(1, 65535)
        self.spin_tcp_porta.setValue(80)
        linha_destino.addWidget(self.spin_tcp_porta)
        layout.addLayout(linha_destino)

        linha_flags = QHBoxLayout()
        linha_flags.addWidget(QLabel("Flags TCP:"))
        self._chk_flags: Dict[str, QCheckBox] = {}
        for sigla in ORDEM_FLAGS:
            caixa = QCheckBox(ROTULOS_FLAGS[sigla])
            caixa.setChecked(sigla == "S")
            linha_flags.addWidget(caixa)
            self._chk_flags[sigla] = caixa
        linha_flags.addStretch()
        layout.addLayout(linha_flags)

        linha_seq = QHBoxLayout()
        linha_seq.addWidget(QLabel("Número de sequência:"))
        self.spin_tcp_seq = QSpinBox()
        self.spin_tcp_seq.setRange(0, 2_147_483_647)
        linha_seq.addWidget(self.spin_tcp_seq)
        linha_seq.addWidget(QLabel("Payload (texto):"))
        self.txt_tcp_payload = QLineEdit()
        self.txt_tcp_payload.setPlaceholderText("Opcional")
        linha_seq.addWidget(self.txt_tcp_payload, stretch=1)
        layout.addLayout(linha_seq)
        layout.addStretch()
        return aba

    def _aba_udp(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        linha_destino = QHBoxLayout()
        linha_destino.addWidget(QLabel("Destino (IP ou host):"))
        self.txt_udp_destino = QLineEdit("8.8.8.8")
        linha_destino.addWidget(self.txt_udp_destino, stretch=1)
        linha_destino.addWidget(QLabel("Porta:"))
        self.spin_udp_porta = QSpinBox()
        self.spin_udp_porta.setRange(1, 65535)
        self.spin_udp_porta.setValue(53)
        linha_destino.addWidget(self.spin_udp_porta)
        layout.addLayout(linha_destino)

        linha_payload = QHBoxLayout()
        linha_payload.addWidget(QLabel("Payload (texto):"))
        self.txt_udp_payload = QLineEdit()
        self.txt_udp_payload.setPlaceholderText("Opcional")
        linha_payload.addWidget(self.txt_udp_payload, stretch=1)
        layout.addLayout(linha_payload)
        layout.addStretch()
        return aba

    def _aba_dns(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        linha_servidor = QHBoxLayout()
        linha_servidor.addWidget(QLabel("Servidor DNS (IP ou host):"))
        self.txt_dns_servidor = QLineEdit("8.8.8.8")
        linha_servidor.addWidget(self.txt_dns_servidor, stretch=1)
        layout.addLayout(linha_servidor)

        linha_consulta = QHBoxLayout()
        linha_consulta.addWidget(QLabel("Nome consultado:"))
        self.txt_dns_nome = QLineEdit("example.com")
        linha_consulta.addWidget(self.txt_dns_nome, stretch=1)
        linha_consulta.addWidget(QLabel("Tipo:"))
        self.cmb_dns_tipo = QComboBox()
        for rotulo, valor in TIPOS_DNS:
            self.cmb_dns_tipo.addItem(rotulo, valor)
        linha_consulta.addWidget(self.cmb_dns_tipo)
        layout.addLayout(linha_consulta)
        layout.addStretch()
        return aba

    # --------------------------------------------------------------- envio
    def _coletar_parametros(self) -> Dict[str, Any]:
        """Lê os campos da aba atual na thread principal antes da tarefa."""
        indice = self.tabs.currentIndex()
        if indice == 0:
            destino = self.txt_icmp_destino.text().strip()
            if not destino:
                raise ValueError("Informe o IP ou host de destino do ICMP.")
            return {
                "tipo": "ICMP",
                "destino": destino,
                "icmp_tipo": int(self.cmb_icmp_tipo.currentData()),
                "icmp_codigo": int(self.spin_icmp_codigo.value()),
                "payload": self.txt_icmp_payload.text(),
            }
        if indice == 1:
            destino = self.txt_tcp_destino.text().strip()
            if not destino:
                raise ValueError("Informe o IP ou host de destino do TCP.")
            flags = "".join(sigla for sigla in ORDEM_FLAGS if self._chk_flags[sigla].isChecked())
            if not flags:
                raise ValueError("Selecione ao menos uma flag TCP.")
            return {
                "tipo": "TCP",
                "destino": destino,
                "porta": int(self.spin_tcp_porta.value()),
                "flags": flags,
                "sequencia": int(self.spin_tcp_seq.value()),
                "payload": self.txt_tcp_payload.text(),
            }
        if indice == 2:
            destino = self.txt_udp_destino.text().strip()
            if not destino:
                raise ValueError("Informe o IP ou host de destino do UDP.")
            return {
                "tipo": "UDP",
                "destino": destino,
                "porta": int(self.spin_udp_porta.value()),
                "payload": self.txt_udp_payload.text(),
            }
        destino = self.txt_dns_servidor.text().strip()
        nome = self.txt_dns_nome.text().strip()
        if not destino:
            raise ValueError("Informe o servidor DNS de destino.")
        if not nome:
            raise ValueError("Informe o nome de domínio a consultar.")
        return {
            "tipo": "DNS",
            "destino": destino,
            "qname": nome,
            "qtype": int(self.cmb_dns_tipo.currentData()),
            "payload": "",
        }

    def _definir_ocupado(self, ocupado: bool) -> None:
        self._ocupado = ocupado
        self.btn_sr1.setEnabled(not ocupado)
        self.btn_send.setEnabled(not ocupado)
        self.btn_tracert.setEnabled(not ocupado)
        self.btn_exportar_txt.setEnabled(not ocupado)
        self.btn_exportar_pcap.setEnabled(not ocupado)

    def _enviar(self, aguardar: bool) -> None:
        if self._ocupado:
            return
        try:
            params = self._coletar_parametros()
        except ValueError as exc:
            mostrar_erro(self, "Parâmetros inválidos", exc)
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return
        if not _verificar_scapy(self):
            return
        if not garantir_admin(self, self.tool.name, permitir_continuar=False):
            return
        self._atualizar_status_admin()

        timeout = int(self.spin_timeout.value())
        self._definir_ocupado(True)
        self.lbl_status.setText(f"Enviando pacote {params['tipo']} para {params['destino']}...")
        self.log_panel.append_log("INFO", f"Envio {params['tipo']} para {params['destino']}.")

        def tarefa(ctx) -> Dict[str, Any]:
            return _enviar_pacote(params, aguardar, timeout)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._envio_concluido,
            ao_falhar=self._falhou,
        )

    def _envio_concluido(self, resultado: Dict[str, Any]) -> None:
        self._definir_ocupado(False)
        latencia = float(resultado.get("latencia") or 0.0)
        self._adicionar_linha(
            [
                time.strftime("%H:%M:%S"),
                str(resultado.get("tipo", "")),
                str(resultado.get("destino", "")),
                str(resultado.get("resumo", "")),
                f"{latencia:.1f}".replace(".", ","),
            ]
        )
        pacote = resultado.get("pacote")
        if pacote is not None:
            self._pacotes_enviados.append(pacote)
        self.txt_saida.setPlainText(str(resultado.get("detalhe", "")))
        self.lbl_status.setText(
            f"{resultado.get('tipo')} para {resultado.get('destino')} concluído."
        )
        latencia_texto = f"{latencia:.1f}".replace(".", ",")
        self.log_panel.append_log(
            "INFO", f"{resultado.get('resumo')} ({latencia_texto} ms)"
        )

    def _iniciar_traceroute(self) -> None:
        if self._ocupado:
            return
        destino = self.txt_rota_destino.text().strip()
        if not destino:
            mostrar_erro(self, "Parâmetros inválidos", "Informe o destino do traceroute.")
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return
        if not _verificar_scapy(self):
            return
        if not garantir_admin(self, self.tool.name, permitir_continuar=False):
            return
        self._atualizar_status_admin()

        maximo = int(self.spin_ttl_max.value())
        timeout = int(self.spin_timeout.value())
        self._definir_ocupado(True)
        self.lbl_status.setText(f"Executando traceroute para {destino} (TTL 1 a {maximo})...")

        def tarefa(ctx) -> List[Dict[str, Any]]:
            return _executar_traceroute(destino, maximo, timeout, ctx)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._traceroute_concluido,
            ao_falhar=self._falhou,
        )

    def _traceroute_concluido(self, saltos: List[Dict[str, Any]]) -> None:
        self._definir_ocupado(False)
        hora = time.strftime("%H:%M:%S")
        for salto in saltos:
            self._adicionar_linha(
                [
                    hora,
                    f"TTL {salto.get('ttl')}",
                    str(salto.get("destino", "")),
                    f"{salto.get('hop')} ({salto.get('status')})",
                    f"{float(salto.get('latencia') or 0.0):.1f}".replace(".", ","),
                ]
            )
        if saltos:
            partes = []
            for item in saltos:
                latencia = f"{float(item.get('latencia') or 0.0):.2f}".replace(".", ",")
                partes.append(
                    f"TTL {int(item.get('ttl')):>2}: {item.get('hop')} "
                    f"[{item.get('status')}] {latencia} ms"
                )
            relatorio = "\n".join(partes)
        else:
            relatorio = "Traceroute interrompido antes do primeiro salto."
        self.txt_saida.setPlainText(relatorio)
        self.lbl_status.setText(f"Traceroute concluído com {len(saltos)} salto(s) medido(s).")
        self.log_panel.append_log("INFO", f"Traceroute concluído: {len(saltos)} salto(s).")

    def _falhou(self, erro: Exception) -> None:
        self._definir_ocupado(False)
        self.lbl_status.setText("A operação não foi concluída.")
        texto = str(erro)
        self.log_panel.append_log("ERRO", texto)
        if "Esta ferramenta requer" in texto:
            aviso_dependencia(self, erro)
        else:
            mostrar_erro(self, "Falha no envio de pacotes", texto)

    # ------------------------------------------------------------- histórico
    def _adicionar_linha(self, linha: List[str]) -> None:
        self._linhas.append(linha)
        preencher_tabela(self.tabela, self._linhas)

    def _limpar_historico(self) -> None:
        if self._ocupado:
            return
        self._linhas.clear()
        self._pacotes_enviados.clear()
        preencher_tabela(self.tabela, [])
        self.txt_saida.clear()
        self.lbl_status.setText("Histórico limpo.")
        self.log_panel.append_log("INFO", "Histórico de envios limpo.")

    def _texto_historico(self) -> str:
        linhas = ["Histórico de envios de pacotes", ""]
        for linha in self._linhas:
            linhas.append(" | ".join(str(valor) for valor in linha))
        if not self._linhas:
            linhas.append("Nenhum envio registrado.")
        return "\n".join(linhas)

    def _exportar_txt(self) -> None:
        if salvar_texto(
            self,
            self._texto_historico(),
            "historico_pacotes.txt",
            "Arquivos de texto (*.txt);;Todos os arquivos (*.*)",
        ):
            self.log_panel.append_log("INFO", "Histórico exportado em TXT.")

    def _exportar_pcap(self) -> None:
        if not self._pacotes_enviados:
            mostrar_erro(
                self,
                "Nada para exportar",
                "Nenhum pacote foi enviado nesta sessão.",
            )
            return
        if not _verificar_scapy(self):
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar pacotes enviados",
            "pacotes_enviados.pcap",
            "Capturas PCAP (*.pcap);;Todos os arquivos (*.*)",
        )
        if not destino:
            return
        pacotes = list(self._pacotes_enviados)

        def tarefa(ctx) -> str:
            from scapy.utils import wrpcap

            wrpcap(destino, pacotes)
            return destino

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=lambda caminho: self.log_panel.append_log(
                "INFO", f"Pacotes salvos em {caminho}."
            ),
            ao_falhar=self._falhou,
        )

"""Ferramenta: Captura e Análise de Pacotes de Rede em tempo real.

A captura usa o Scapy (``AsyncSniffer``) e, no Windows, depende do Npcap. Nenhuma
biblioteca opcional é importada na carga deste módulo: a interface abre mesmo sem
o Scapy e a dependência só é exigida quando a captura é iniciada.

A thread de captura nunca toca em widgets. Cada pacote dissecado é entregue à
interface por um sinal Qt (conexão enfileirada), mantendo a UI na thread principal.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QWidget,
)

from wintoolbox.core.elevation import is_admin
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import (
    DependenciaAusente,
    aviso_dependencia,
    confirmar_termo_etico,
    dependencia_disponivel,
    formatar_bytes,
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
    "A captura de pacotes registra todo o tráfego que passa pelo adaptador de rede, "
    "incluindo endereços, nomes de hosts, conteúdos de requisições e credenciais "
    "transmitidas sem criptografia.\n\n"
    "Execute esta ferramenta somente em redes das quais você é o responsável ou "
    "para as quais possui autorização expressa e por escrito do proprietário, com "
    "escopo e período de coleta delimitados.\n\n"
    "A interceptação não autorizada de comunicações é crime previsto na Lei "
    "12.737/2012 (art. 154-A do Código Penal) e pode violar a Lei 13.709/2018 "
    "(LGPD).\n\n"
    "Você declara possuir autorização por escrito e assume integral "
    "responsabilidade pelo uso desta captura?"
)

MAX_LINHAS_TABELA = 5000
MAX_PACOTES_MEMORIA = 20000
INTERVALO_LOOP = 0.2
CHAVES_ESTATISTICA = ("total", "tcp", "udp", "icmp", "dns", "http", "tls", "bytes")


class _SinaisCaptura(QObject):
    """Sinais emitidos pela thread de captura e entregues na thread da interface."""

    pacote = Signal(object)


def _listar_interfaces() -> List[tuple[str, str]]:
    """Lista as interfaces conhecidas pelo Scapy como pares (rótulo, nome).

    Retorna lista vazia quando o Scapy não está disponível ou falha ao enumerar,
    sem interromper a abertura da interface gráfica.
    """
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
            rotulo = f"{descricao} ({endereco})" if endereco else descricao
            pares.append((rotulo, nome))
        return pares
    except Exception:
        return []


def _parece_http(carga: bytes) -> bool:
    """Heurística simples para reconhecer o início de uma mensagem HTTP."""
    if not carga:
        return False
    prefixos = (
        b"GET ",
        b"POST ",
        b"HEAD ",
        b"PUT ",
        b"DELETE ",
        b"OPTIONS ",
        b"PATCH ",
        b"CONNECT ",
        b"HTTP/1.",
        b"HTTP/2",
    )
    return carga.startswith(prefixos)


def _linha_http(carga: bytes) -> str:
    """Extrai a primeira linha de uma mensagem HTTP para exibição compacta."""
    texto = carga[:400].decode("latin-1", errors="ignore")
    primeira = texto.splitlines()[0].strip() if texto else ""
    return primeira[:160]


def _extrair_sni(carga: bytes) -> str:
    """Extrai o SNI de um ClientHello TLS a partir dos bytes brutos.

    A leitura é feita manualmente para não depender de versões específicas das
    camadas TLS do Scapy. Qualquer dado malformado resulta em string vazia.
    """
    try:
        if len(carga) < 50 or carga[0] != 0x16 or carga[5] != 0x01:
            return ""
        posicao = 43  # cabeçalho de registro (5) + handshake (4) + versão (2) + random (32)
        tamanho_sessao = carga[posicao]
        posicao += 1 + tamanho_sessao
        if posicao + 2 > len(carga):
            return ""
        tamanho_cifras = int.from_bytes(carga[posicao : posicao + 2], "big")
        posicao += 2 + tamanho_cifras
        if posicao + 1 > len(carga):
            return ""
        tamanho_compressao = carga[posicao]
        posicao += 1 + tamanho_compressao
        if posicao + 2 > len(carga):
            return ""
        tamanho_extensoes = int.from_bytes(carga[posicao : posicao + 2], "big")
        posicao += 2
        limite = min(len(carga), posicao + tamanho_extensoes)
        while posicao + 4 <= limite:
            tipo = int.from_bytes(carga[posicao : posicao + 2], "big")
            comprimento = int.from_bytes(carga[posicao + 2 : posicao + 4], "big")
            posicao += 4
            if tipo == 0x0000 and comprimento >= 5:
                dados = carga[posicao : posicao + comprimento]
                if len(dados) >= 5:
                    tamanho_nome = int.from_bytes(dados[3:5], "big")
                    nome = dados[5 : 5 + tamanho_nome]
                    # O SNI trafega em ASCII (IDN já vem em punycode); o codec idna
                    # não aceita o tratador de erros e não deve ser usado aqui.
                    return nome.decode("ascii", errors="ignore")
            posicao += comprimento
    except (IndexError, ValueError, UnicodeError):
        return ""
    return ""


def _dissecar(pacote: Any) -> Dict[str, Any]:
    """Descreve um pacote Scapy em um dicionário pronto para a tabela.

    As importações do Scapy são locais: o módulo pode ser importado sem a
    dependência instalada.
    """
    from scapy.layers.dns import DNS
    from scapy.layers.inet import ICMP, IP, TCP, UDP
    from scapy.layers.l2 import ARP
    from scapy.packet import Raw

    origem = ""
    destino = ""
    protocolo = "Outro"
    informacao = ""
    tamanho = len(pacote) if pacote is not None else 0

    if pacote.haslayer(ARP):
        arp = pacote[ARP]
        origem, destino = str(arp.psrc), str(arp.pdst)
        protocolo = "ARP"
        informacao = f"ARP op={arp.op} {arp.psrc} -> {arp.pdst}"
    elif pacote.haslayer(IP):
        camada_ip = pacote[IP]
        origem, destino = camada_ip.src, camada_ip.dst
        tamanho = len(camada_ip)

        if pacote.haslayer(DNS):
            dns = pacote[DNS]
            protocolo = "DNS"
            if int(dns.qr) == 0 and dns.qd is not None:
                nome = str(dns.qd.qname).rstrip(".")
                informacao = f"Consulta tipo {int(dns.qd.qtype)} para {nome}"
            elif int(dns.qr) == 1 and dns.an is not None:
                nome = str(getattr(dns.an, "rrname", "")).rstrip(".")
                resposta = str(getattr(dns.an, "rdata", ""))
                informacao = f"Resposta {nome} -> {resposta}"
            else:
                informacao = "Mensagem DNS"
        elif pacote.haslayer(TCP):
            tcp = pacote[TCP]
            protocolo = "TCP"
            carga = bytes(tcp.payload) if pacote.haslayer(Raw) else b""
            informacao = f"{int(tcp.sport)} -> {int(tcp.dport)} flags={tcp.flags}"
            if _parece_http(carga):
                protocolo = "HTTP"
                informacao = _linha_http(carga)
            else:
                sni = _extrair_sni(carga)
                if sni:
                    protocolo = "TLS"
                    informacao = f"SNI: {sni}"
                elif carga[:1] == b"\x16" and (int(tcp.dport) in (443, 8443)):
                    protocolo = "TLS"
                    informacao = f"TLS versão {carga[1]}.{carga[2]}"
        elif pacote.haslayer(UDP):
            udp = pacote[UDP]
            protocolo = "UDP"
            carga = bytes(udp.payload) if pacote.haslayer(Raw) else b""
            informacao = f"{int(udp.sport)} -> {int(udp.dport)} ({len(carga)} bytes)"
        elif pacote.haslayer(ICMP):
            icmp = pacote[ICMP]
            protocolo = "ICMP"
            informacao = f"tipo {int(icmp.type)} código {int(icmp.code)}"
        else:
            informacao = pacote.summary()
    else:
        informacao = pacote.summary()

    return {
        "hora": time.strftime("%H:%M:%S"),
        "origem": origem,
        "destino": destino,
        "protocolo": protocolo,
        "info": informacao,
        "tamanho": tamanho,
    }


@register
class PacketSnifferTool(Tool):
    """Ferramenta de captura de pacotes com filtro BPF e exportação em PCAP."""

    id = "network.packet_sniffer"
    name = "Captura e Análise de Pacotes"
    category = "Rede e Internet"
    description = (
        "Captura ao vivo com filtro BPF, dissecação de TCP, UDP, ICMP, DNS, HTTP e "
        "TLS SNI, estatísticas em tempo real e exportação em PCAP"
    )
    keywords = [
        "sniffer",
        "captura",
        "pacotes",
        "pcap",
        "bpf",
        "tcp",
        "udp",
        "dns",
        "tls",
        "sni",
        "npcap",
    ]
    requires_admin = True
    optional_deps = ["scapy"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PacketSnifferView(self, parent)


class PacketSnifferView(PainelFerramenta):
    """Página interativa da captura de pacotes."""

    def __init__(self, tool: PacketSnifferTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self.sinais = _SinaisCaptura(self)
        self._parar = threading.Event()
        self._trava = threading.Lock()
        self._pacotes: List[Any] = []
        self._capturando = False
        self._stats: Dict[str, int] = {chave: 0 for chave in CHAVES_ESTATISTICA}

        self._montar_interface()
        self.sinais.pacote.connect(self._ao_pacote)

        if dependencia_disponivel("scapy"):
            QTimer.singleShot(0, self._atualizar_interfaces)

    # ------------------------------------------------------------------ UI
    def _montar_interface(self) -> None:
        self.adicionar(
            criar_aviso(
                "No Windows, a captura exige o Npcap instalado (https://npcap.com) "
                "com a opção de compatibilidade com WinPcap. Sem o driver, o Scapy "
                "não consegue abrir o adaptador de rede. A captura também precisa "
                "ser executada como Administrador.",
                self,
                destaque=True,
            )
        )
        self._montar_cartao_admin()

        cartao_captura, layout = self.adicionar_card("Captura")
        linha_interface = QHBoxLayout()
        linha_interface.addWidget(QLabel("Interface:"))
        self.cmb_interface = QComboBox()
        self.cmb_interface.addItem("Automático (padrão do sistema)", "")
        self.cmb_interface.setMinimumWidth(240)
        linha_interface.addWidget(self.cmb_interface, stretch=1)

        self.btn_atualizar = QPushButton("Atualizar interfaces")
        self.btn_atualizar.clicked.connect(self._atualizar_interfaces)
        linha_interface.addWidget(self.btn_atualizar)
        layout.addLayout(linha_interface)

        linha_filtro = QHBoxLayout()
        linha_filtro.addWidget(QLabel("Filtro BPF:"))
        self.txt_filtro = QLineEdit()
        self.txt_filtro.setPlaceholderText("Ex.: tcp port 80 or udp port 53 (vazio captura tudo)")
        linha_filtro.addWidget(self.txt_filtro, stretch=1)
        layout.addLayout(linha_filtro)

        linha_controle = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar captura")
        self.btn_iniciar.setProperty("class", "primary")
        self.btn_iniciar.clicked.connect(self._iniciar_captura)
        linha_controle.addWidget(self.btn_iniciar)

        self.btn_parar = QPushButton("Parar captura")
        self.btn_parar.setEnabled(False)
        self.btn_parar.clicked.connect(self._parar_captura)
        linha_controle.addWidget(self.btn_parar)

        self.btn_salvar = QPushButton("Salvar PCAP")
        self.btn_salvar.setEnabled(False)
        self.btn_salvar.clicked.connect(self._salvar_pcap)
        linha_controle.addWidget(self.btn_salvar)
        linha_controle.addStretch()
        layout.addLayout(linha_controle)

        self.lbl_status = QLabel("Pronto. Informe um filtro opcional e inicie a captura.")
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        grade = QGridLayout()
        grade.setHorizontalSpacing(22)
        grade.setVerticalSpacing(4)
        itens = (
            ("total", "Total"),
            ("tcp", "TCP"),
            ("udp", "UDP"),
            ("icmp", "ICMP"),
            ("dns", "DNS"),
            ("http", "HTTP"),
            ("tls", "TLS"),
            ("bytes", "Tráfego"),
        )
        self._lbl_stats: Dict[str, QLabel] = {}
        for indice, (chave, rotulo) in enumerate(itens):
            etiqueta = QLabel(f"{rotulo}: 0")
            etiqueta.setProperty("class", "secondary")
            grade.addWidget(etiqueta, indice // 4, indice % 4)
            self._lbl_stats[chave] = etiqueta
        layout.addLayout(grade)

        cartao_tabela, layout_tabela = self.adicionar_card("Pacotes capturados")
        self.tabela = criar_tabela(
            ["Hora", "Origem", "Destino", "Protocolo", "Informação", "Bytes"], self
        )
        cabecalho = self.tabela.horizontalHeader()
        for coluna in range(5):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tabela.setMinimumHeight(280)
        layout_tabela.addWidget(self.tabela)

        linha_tabela = QHBoxLayout()
        self.btn_limpar = QPushButton("Limpar tabela e estatísticas")
        self.btn_limpar.clicked.connect(self._limpar_captura)
        linha_tabela.addWidget(self.btn_limpar)
        linha_tabela.addStretch()
        self.lbl_total = QLabel("0 pacote(s) na tabela")
        self.lbl_total.setProperty("class", "secondary")
        linha_tabela.addWidget(self.lbl_total)
        layout_tabela.addLayout(linha_tabela)

        cartao_relatorio, layout_relatorio = self.adicionar_card("Relatório da captura")
        self.txt_relatorio = criar_saida_texto(150, self)
        layout_relatorio.addWidget(self.txt_relatorio)
        linha_relatorio = QHBoxLayout()
        linha_relatorio.addWidget(
            botao_copiar(lambda: self.txt_relatorio.toPlainText(), self, "Copiar relatório")
        )
        linha_relatorio.addStretch()
        layout_relatorio.addLayout(linha_relatorio)

        self.log_panel = adicionar_log_painel(self, "Log da captura")
        self._atualizar_botoes()

    def _montar_cartao_admin(self) -> None:
        """Cartão de status de privilégios com reinício elevado sob demanda."""
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
                "Executando com privilégios de Administrador. A captura pode acessar "
                "os adaptadores de rede."
            )
            self.btn_admin.setEnabled(False)
            self.btn_admin.setToolTip("O aplicativo já está elevado.")
        else:
            self.lbl_admin.setText(
                "Executando como usuário padrão. A captura exige Administrador e o "
                "Npcap instalado."
            )
            self.btn_admin.setEnabled(True)
            self.btn_admin.setToolTip("Solicita a elevação do aplicativo via UAC.")

    def _atualizar_interfaces(self) -> None:
        """Repopula a lista de interfaces sem depender de widgets na thread de captura."""
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
        if pares:
            self.log_panel.append_log("INFO", f"{len(pares)} interface(s) encontrada(s).")
        else:
            self.log_panel.append_log(
                "AVISO", "Não foi possível enumerar as interfaces com o Scapy."
            )

    def _atualizar_botoes(self) -> None:
        self.btn_iniciar.setEnabled(not self._capturando)
        self.btn_parar.setEnabled(self._capturando)
        self.btn_atualizar.setEnabled(not self._capturando)
        self.btn_limpar.setEnabled(not self._capturando)
        self.cmb_interface.setEnabled(not self._capturando)
        self.txt_filtro.setEnabled(not self._capturando)
        with self._trava:
            possui_pacotes = bool(self._pacotes)
        self.btn_salvar.setEnabled(not self._capturando and possui_pacotes)

    def _atualizar_estatisticas(self) -> None:
        self._lbl_stats["total"].setText(f"Total: {formatar_numero(self._stats['total'])}")
        for chave, rotulo in (
            ("tcp", "TCP"),
            ("udp", "UDP"),
            ("icmp", "ICMP"),
            ("dns", "DNS"),
            ("http", "HTTP"),
            ("tls", "TLS"),
        ):
            self._lbl_stats[chave].setText(f"{rotulo}: {formatar_numero(self._stats[chave])}")
        self._lbl_stats["bytes"].setText(f"Tráfego: {formatar_bytes(self._stats['bytes'])}")
        self.lbl_total.setText(f"{formatar_numero(self._stats['total'])} pacote(s) na tabela")

    # ------------------------------------------------------------- captura
    def _verificar_scapy(self) -> bool:
        if dependencia_disponivel("scapy"):
            return True
        aviso_dependencia(self, DependenciaAusente("Scapy", "scapy.all", "scapy"))
        return False

    def _iniciar_captura(self) -> None:
        if self._capturando:
            return
        if not confirmar_termo_etico(self, self.tool.id, TEXTO_ETICO):
            return
        if not self._verificar_scapy():
            return
        if not garantir_admin(self, self.tool.name, permitir_continuar=False):
            return
        self._atualizar_status_admin()

        interface = self.cmb_interface.currentData() or ""
        filtro = self.txt_filtro.text().strip()
        self._limpar_captura()
        self._parar.clear()
        self._capturando = True
        self._atualizar_botoes()
        self.lbl_status.setText("Capturando... aguardando pacotes na interface selecionada.")
        self.log_panel.append_log(
            "INFO",
            f"Captura iniciada na interface '{interface or 'automática'}' "
            f"com filtro '{filtro or 'nenhum'}'.",
        )

        sinais = self.sinais
        parar = self._parar
        trava = self._trava
        pacotes = self._pacotes

        def tarefa(ctx) -> Dict[str, Any]:
            from scapy.all import AsyncSniffer

            def processar(pacote) -> None:
                if parar.is_set():
                    return
                try:
                    dados = _dissecar(pacote)
                except Exception:
                    dados = {
                        "hora": time.strftime("%H:%M:%S"),
                        "origem": "",
                        "destino": "",
                        "protocolo": "Outro",
                        "info": "Pacote não reconhecido",
                        "tamanho": len(pacote) if pacote is not None else 0,
                    }
                with trava:
                    if len(pacotes) < MAX_PACOTES_MEMORIA:
                        pacotes.append(pacote)
                sinais.pacote.emit(dados)

            sniffer = AsyncSniffer(
                iface=interface or None,
                filter=filtro or None,
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
                raise RuntimeError(f"Não foi possível iniciar a captura: {falha}")
            try:
                while not parar.is_set() and not ctx.cancelled():
                    time.sleep(INTERVALO_LOOP)
            finally:
                try:
                    sniffer.stop()
                except Exception:
                    pass
            return {"capturados": len(pacotes)}

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=self._captura_encerrada,
            ao_falhar=self._falhou,
            ao_logar=self.log_panel.append_log,
        )

    def _parar_captura(self) -> None:
        if not self._capturando:
            return
        self._parar.set()
        self.runner.cancel_current()
        self.btn_parar.setEnabled(False)
        self.lbl_status.setText("Encerrando a captura e fechando o adaptador de rede...")

    def _captura_encerrada(self, resultado: Any) -> None:
        self._capturando = False
        self._atualizar_botoes()
        self.lbl_status.setText(
            "Captura encerrada. "
            f"{formatar_numero(self._stats['total'])} pacote(s) observado(s)."
        )
        self.txt_relatorio.setPlainText(self._gerar_relatorio())
        self.log_panel.append_log("INFO", "Captura encerrada.")

    def _falhou(self, erro: Exception) -> None:
        self._capturando = False
        self._atualizar_botoes()
        texto = str(erro)
        self.log_panel.append_log("ERRO", texto)
        if "Esta ferramenta requer" in texto:
            aviso_dependencia(self, erro)
        else:
            mostrar_erro(self, "Falha na captura de pacotes", texto)

    def _ao_pacote(self, dados: Dict[str, Any]) -> None:
        """Atualiza tabela e estatísticas na thread principal."""
        self._stats["total"] += 1
        self._stats["bytes"] += int(dados.get("tamanho") or 0)
        chave = {
            "TCP": "tcp",
            "UDP": "udp",
            "ICMP": "icmp",
            "DNS": "dns",
            "HTTP": "http",
            "TLS": "tls",
        }.get(str(dados.get("protocolo", "")))
        if chave:
            self._stats[chave] += 1
        self._atualizar_estatisticas()

        tabela = self.tabela
        if tabela.rowCount() >= MAX_LINHAS_TABELA:
            tabela.removeRow(0)
        linha = tabela.rowCount()
        tabela.insertRow(linha)
        valores = (
            dados.get("hora", ""),
            dados.get("origem", ""),
            dados.get("destino", ""),
            dados.get("protocolo", ""),
            dados.get("info", ""),
            dados.get("tamanho", 0),
        )
        for coluna, valor in enumerate(valores):
            tabela.setItem(
                linha, coluna, QTableWidgetItem("" if valor is None else str(valor))
            )

    def _limpar_captura(self) -> None:
        with self._trava:
            self._pacotes.clear()
        for chave in CHAVES_ESTATISTICA:
            self._stats[chave] = 0
        self._atualizar_estatisticas()
        preencher_tabela(self.tabela, [])
        self.txt_relatorio.clear()
        self._atualizar_botoes()

    def _gerar_relatorio(self) -> str:
        linhas = [
            "Relatório de captura de pacotes",
            f"Gerado em: {time.strftime('%d/%m/%Y %H:%M:%S')}",
            f"Interface: {self.cmb_interface.currentData() or 'automática'}",
            f"Filtro BPF: {self.txt_filtro.text().strip() or 'nenhum'}",
            "",
            f"Pacotes observados: {formatar_numero(self._stats['total'])}",
            f"TCP: {formatar_numero(self._stats['tcp'])}",
            f"UDP: {formatar_numero(self._stats['udp'])}",
            f"ICMP: {formatar_numero(self._stats['icmp'])}",
            f"DNS: {formatar_numero(self._stats['dns'])}",
            f"HTTP: {formatar_numero(self._stats['http'])}",
            f"TLS: {formatar_numero(self._stats['tls'])}",
            f"Tráfego aproximado: {formatar_bytes(self._stats['bytes'])}",
            f"Pacotes mantidos para exportação: {formatar_numero(len(self._pacotes))}",
        ]
        return "\n".join(linhas)

    def _salvar_pcap(self) -> None:
        with self._trava:
            pacotes = list(self._pacotes)
        if not pacotes:
            mostrar_erro(
                self,
                "Nada para exportar",
                "Nenhum pacote foi capturado até o momento. Inicie a captura antes de salvar.",
            )
            return
        if not self._verificar_scapy():
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar captura em PCAP",
            "captura.pcap",
            "Capturas PCAP (*.pcap);;Todos os arquivos (*.*)",
        )
        if not destino:
            return

        def tarefa(ctx) -> str:
            from scapy.utils import wrpcap

            wrpcap(destino, pacotes)
            return destino

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=lambda caminho: self.log_panel.append_log(
                "INFO", f"Captura salva em {caminho} ({formatar_numero(len(pacotes))} pacotes)."
            ),
            ao_falhar=self._falhou,
        )

    def hideEvent(self, evento) -> None:  # noqa: N802 (assinatura Qt)
        """Encerra a captura ao sair da página para não deixar o adaptador aberto."""
        if self._capturando:
            self._parar_captura()
        super().hideEvent(evento)

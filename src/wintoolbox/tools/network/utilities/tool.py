"""
Ferramenta: Utilitários de Rede (Wake-on-LAN, Expansor de Links e Download com Retomada).
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.network.utilities.logic import (
    download_file_resumable,
    expand_url_chain,
    send_wake_on_lan,
    shorten_url,
)


@register
class UtilitiesTool(Tool):
    id = "network.utilities"
    name = "Utilitários de Rede e Conexão"
    category = "Rede e Internet"
    description = "Wake-on-LAN (ligar PC pela rede), expansor de links encurtados e download com retomada"
    keywords = ["wake", "lan", "wol", "magic", "packet", "url", "encurtador", "link", "download", "retomada", "rede"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return UtilitiesView(self, parent)


class UtilitiesView(QWidget):
    def __init__(self, tool: UtilitiesTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        tabs = QTabWidget()

        # ABA 1: Wake-on-LAN
        tab_wol = QWidget()
        l_wol = QVBoxLayout(tab_wol)
        l_wol.setSpacing(10)

        card_wol = QFrame()
        card_wol.setProperty("class", "card")
        l_cwol = QVBoxLayout(card_wol)
        l_cwol.setSpacing(8)

        row_w1 = QHBoxLayout()
        row_w1.addWidget(QLabel("Endereço MAC do Computador:"))
        self.txt_wol_mac = QLineEdit("00:11:22:33:44:55")
        row_w1.addWidget(self.txt_wol_mac)

        row_w1.addWidget(QLabel("IP de Broadcast:"))
        self.txt_wol_ip = QLineEdit("255.255.255.255")
        self.txt_wol_ip.setFixedWidth(130)
        row_w1.addWidget(self.txt_wol_ip)
        l_cwol.addLayout(row_w1)

        row_w2 = QHBoxLayout()
        btn_send_wol = QPushButton("Enviar Magic Packet (Ligar PC)")
        btn_send_wol.setProperty("class", "primary")
        btn_send_wol.clicked.connect(self._send_wol)
        row_w2.addWidget(btn_send_wol)
        row_w2.addStretch()
        l_cwol.addLayout(row_w2)

        l_wol.addWidget(card_wol)

        lbl_wol_info = QLabel(
            "O computador de destino deve ter o recurso Wake-on-LAN (WoL) ativado na BIOS/UEFI\n"
            "e estar conectado à mesma sub-rede via cabo Ethernet."
        )
        lbl_wol_info.setProperty("class", "secondary")
        l_wol.addWidget(lbl_wol_info)
        l_wol.addStretch()
        tabs.addTab(tab_wol, "Wake-on-LAN (Ligar Computador)")

        # ABA 2: Encurtador e Expansor de Links
        tab_url = QWidget()
        l_url = QVBoxLayout(tab_url)
        l_url.setSpacing(12)

        # Card de Encurtamento
        card_shorten = QFrame()
        card_shorten.setProperty("class", "card")
        l_cshort = QVBoxLayout(card_shorten)
        l_cshort.setSpacing(8)

        lbl_sh_title = QLabel("Encurtador de Links")
        lbl_sh_title.setStyleSheet("font-weight: 600;")
        l_cshort.addWidget(lbl_sh_title)

        row_sh_in = QHBoxLayout()
        row_sh_in.addWidget(QLabel("URL Longa:"))
        self.txt_long_url = QLineEdit()
        self.txt_long_url.setPlaceholderText("https://exemplo.com/artigo-muito-longo-para-compartilhar...")
        row_sh_in.addWidget(self.txt_long_url, stretch=1)

        row_sh_in.addWidget(QLabel("Serviço:"))
        self.cmb_short_service = QComboBox()
        self.cmb_short_service.addItems(["TinyURL", "is.gd"])
        row_sh_in.addWidget(self.cmb_short_service)

        self.btn_shorten = QPushButton("Encurtar")
        self.btn_shorten.setProperty("class", "primary")
        self.btn_shorten.clicked.connect(self._shorten_url)
        row_sh_in.addWidget(self.btn_shorten)
        l_cshort.addLayout(row_sh_in)

        row_sh_out = QHBoxLayout()
        row_sh_out.addWidget(QLabel("Link Gerado:"))
        self.txt_short_res = QLineEdit()
        self.txt_short_res.setReadOnly(True)
        self.txt_short_res.setPlaceholderText("O link encurtado aparecerá aqui...")
        row_sh_out.addWidget(self.txt_short_res, stretch=1)

        self.btn_copy_short = QPushButton("Copiar")
        self.btn_copy_short.clicked.connect(self._copy_shortened)
        row_sh_out.addWidget(self.btn_copy_short)
        l_cshort.addLayout(row_sh_out)
        l_url.addWidget(card_shorten)

        # Card de Expansão
        card_expand = QFrame()
        card_expand.setProperty("class", "card")
        l_cexp = QVBoxLayout(card_expand)
        l_cexp.setSpacing(8)

        lbl_exp_title = QLabel("Expansor de Links (Anti-Phishing / Destino Real)")
        lbl_exp_title.setStyleSheet("font-weight: 600;")
        l_cexp.addWidget(lbl_exp_title)

        row_url_in = QHBoxLayout()
        row_url_in.addWidget(QLabel("Link Encurtado:"))
        self.txt_short_url = QLineEdit("https://bit.ly/")
        row_url_in.addWidget(self.txt_short_url, stretch=1)

        btn_expand = QPushButton("Rastrear Destino Final")
        btn_expand.setProperty("class", "primary")
        btn_expand.clicked.connect(self._expand_url)
        row_url_in.addWidget(btn_expand)
        l_cexp.addLayout(row_url_in)

        self.table_url = QTableWidget(0, 2)
        self.table_url.setHorizontalHeaderLabels(["Status HTTP", "URL na Cadeia de Redirecionamento"])
        self.table_url.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_url.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_url.verticalHeader().setVisible(False)
        self.table_url.setFixedHeight(180)
        l_cexp.addWidget(self.table_url)
        l_url.addWidget(card_expand)

        tabs.addTab(tab_url, "Encurtador e Expansor de Links")

        # ABA 3: Download com Suporte a Retomada
        tab_dl = QWidget()
        l_dl = QVBoxLayout(tab_dl)
        l_dl.setSpacing(10)

        row_dl = QHBoxLayout()
        row_dl.addWidget(QLabel("URL do Arquivo:"))
        self.txt_dl_url = QLineEdit("https://speed.hetzner.de/100MB.bin")
        row_dl.addWidget(self.txt_dl_url, stretch=1)

        self.btn_dl_start = QPushButton("Iniciar Download")
        self.btn_dl_start.setProperty("class", "primary")
        self.btn_dl_start.clicked.connect(self._start_download)
        row_dl.addWidget(self.btn_dl_start)
        l_dl.addLayout(row_dl)

        self.prog_dl = QProgressBar()
        self.prog_dl.setRange(0, 100)
        self.prog_dl.setValue(0)
        l_dl.addWidget(self.prog_dl)

        self.lbl_dl_status = QLabel("Pronto para download.")
        self.lbl_dl_status.setProperty("class", "secondary")
        l_dl.addWidget(self.lbl_dl_status)
        l_dl.addStretch()

        tabs.addTab(tab_dl, "Download com Retomada")

        layout.addWidget(tabs)
        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _send_wol(self):
        mac = self.txt_wol_mac.text().strip()
        b_ip = self.txt_wol_ip.text().strip() or "255.255.255.255"
        try:
            send_wake_on_lan(mac, b_ip)
            QMessageBox.information(
                self,
                "Wake-on-LAN",
                f"Magic Packet transmitido com sucesso para {mac} via {b_ip}:9!"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao enviar pacote WoL:\n{str(e)}")

    def _shorten_url(self):
        long_url = self.txt_long_url.text().strip()
        if not long_url:
            QMessageBox.warning(self, "Aviso", "Digite a URL longa a ser encurtada.")
            return

        service = self.cmb_short_service.currentText().lower()
        self.btn_shorten.setEnabled(False)
        self.txt_short_res.setText("Encurtando...")

        def worker(ctx):
            return shorten_url(long_url, service)

        def on_done(res):
            self.btn_shorten.setEnabled(True)
            self.txt_short_res.setText(res)

        def on_error(err):
            self.btn_shorten.setEnabled(True)
            self.txt_short_res.clear()
            QMessageBox.critical(self, "Erro", f"Falha ao encurtar URL:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def _copy_shortened(self):
        text = self.txt_short_res.text().strip()
        if text and not text.startswith("Encurtando"):
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copiado", "Link copiado para a área de transferência!")

    def _expand_url(self):
        url = self.txt_short_url.text().strip()

        def worker(ctx):
            return expand_url_chain(url)

        def on_done(chain):
            self.table_url.setRowCount(len(chain))
            for row, item in enumerate(chain):
                self.table_url.setItem(row, 0, QTableWidgetItem(item["status"]))
                self.table_url.setItem(row, 1, QTableWidgetItem(item["url"]))

        self.runner.start_task(worker, on_finished=on_done)

    def _start_download(self):
        url = self.txt_dl_url.text().strip()
        if not url:
            return

        filename = url.split("/")[-1].split("?")[0] or "download.bin"
        save_path, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo", str(Path.home() / "Downloads" / filename))
        if not save_path:
            return

        target_file = Path(save_path)
        self.btn_dl_start.setEnabled(False)
        self.lbl_dl_status.setText("Iniciando download...")

        def worker(ctx):
            try:
                return download_file_resumable(
                    url=url,
                    target_file=target_file,
                    progress_cb=ctx.on_progress,
                    is_cancelled_fn=ctx.is_cancelled,
                )
            except Exception as e:
                ctx.on_log("ERROR", str(e))
                return -1

        def on_prog(cur, tot, msg):
            pct = int((cur / tot) * 100) if tot and tot > 0 else 0
            self.prog_dl.setValue(pct)
            mb_cur = cur / (1024 * 1024)
            mb_tot = (tot / (1024 * 1024)) if tot else 0
            if mb_tot > 0:
                self.lbl_dl_status.setText(f"Baixando: {mb_cur:.1f} MB de {mb_tot:.1f} MB ({pct}%)")
            else:
                self.lbl_dl_status.setText(f"Baixando: {mb_cur:.1f} MB")

        def on_done(res):
            self.btn_dl_start.setEnabled(True)
            if res > 0:
                self.prog_dl.setValue(100)
                self.lbl_dl_status.setText(f"Download concluído com sucesso ({res/(1024*1024):.1f} MB)!")
                QMessageBox.information(self, "Download Concluído", f"Arquivo salvo com sucesso em:\n{target_file}")
            else:
                self.lbl_dl_status.setText("Falha no download.")

        self.runner.start_task(worker, on_progress=on_prog, on_finished=on_done)

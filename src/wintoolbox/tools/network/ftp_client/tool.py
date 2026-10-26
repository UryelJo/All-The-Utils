"""
Ferramenta: Cliente FTP/SFTP simples.
Permite conectar a servidores FTP ou SFTP (SSH), navegar em pastas, fazer upload e download de arquivos.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.network.ftp_client.logic import FtpOrSftpClient, RemoteItem
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

@register
class FtpClientTool(Tool):
    id = "network.ftp_client"
    name = "Cliente FTP / SFTP Simples"
    category = "Rede e Internet"
    description = "Conexão e gerenciamento de arquivos em servidores remotos FTP e SFTP (SSH)"
    keywords = ["ftp", "sftp", "ssh", "servidor", "upload", "download", "transferencia", "arquivos", "rede"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FtpClientView(self, parent)

class FtpClientView(QWidget):
    def __init__(self, tool: FtpClientTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.client: Optional[FtpOrSftpClient] = None
        self.cached_items: List[RemoteItem] = []
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

        # Card de Configuração de Conexão
        card_conn = QFrame()
        card_conn.setProperty("class", "card")
        l_conn = QVBoxLayout(card_conn)
        l_conn.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Protocolo:"))
        self.cmb_proto = QComboBox()
        self.cmb_proto.addItems(["FTP", "SFTP"])
        self.cmb_proto.currentTextChanged.connect(self._on_protocol_change)
        row1.addWidget(self.cmb_proto)

        row1.addWidget(QLabel("Servidor/Host:"))
        self.txt_host = QLineEdit()
        self.txt_host.setPlaceholderText("ex: ftp.dlptest.com ou 192.168.1.100")
        row1.addWidget(self.txt_host, stretch=2)

        row1.addWidget(QLabel("Porta:"))
        self.txt_port = QLineEdit("21")
        self.txt_port.setFixedWidth(65)
        row1.addWidget(self.txt_port)
        l_conn.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Usuário:"))
        self.txt_user = QLineEdit("anonymous")
        row2.addWidget(self.txt_user, stretch=1)

        row2.addWidget(QLabel("Senha:"))
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.Password)
        self.txt_pass.setPlaceholderText("Opcional para anônimo")
        row2.addWidget(self.txt_pass, stretch=1)

        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.setProperty("class", "primary")
        self.btn_connect.clicked.connect(self._toggle_connection)
        row2.addWidget(self.btn_connect)
        l_conn.addLayout(row2)

        layout.addWidget(card_conn)

        # Barra de Navegação e Ações Remotas
        bar_nav = QHBoxLayout()
        self.btn_up = QPushButton("Subir (..)")
        self.btn_up.setEnabled(False)
        self.btn_up.clicked.connect(self._go_up)
        bar_nav.addWidget(self.btn_up)

        bar_nav.addWidget(QLabel("Pasta Remota:"))
        self.txt_path = QLineEdit("/")
        self.txt_path.setReadOnly(True)
        bar_nav.addWidget(self.txt_path, stretch=1)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.clicked.connect(self._refresh_list)
        bar_nav.addWidget(self.btn_refresh)

        self.btn_upload = QPushButton("Enviar Arquivo...")
        self.btn_upload.setEnabled(False)
        self.btn_upload.clicked.connect(self._upload_file)
        bar_nav.addWidget(self.btn_upload)

        self.btn_download = QPushButton("Baixar Selecionado")
        self.btn_download.setEnabled(False)
        self.btn_download.clicked.connect(self._download_selected)
        bar_nav.addWidget(self.btn_download)

        self.btn_delete = QPushButton("Excluir")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_selected)
        bar_nav.addWidget(self.btn_delete)

        layout.addLayout(bar_nav)

        # Tabela de Arquivos Remotos
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nome", "Tipo", "Tamanho", "Data Modificação"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setFixedHeight(300)
        self.table.cellDoubleClicked.connect(self._on_table_double_click)
        enable_sorting_on_table(self.table)
        layout.addWidget(self.table)

        # Progresso e Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Desconectado. Informe o servidor para iniciar.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _on_protocol_change(self, proto: str):
        if proto == "SFTP" and self.txt_port.text() in ("21", ""):
            self.txt_port.setText("22")
            if self.txt_user.text() == "anonymous":
                self.txt_user.setText("root")
        elif proto == "FTP" and self.txt_port.text() in ("22", ""):
            self.txt_port.setText("21")
            if self.txt_user.text() == "root":
                self.txt_user.setText("anonymous")

    def _toggle_connection(self):
        if self.client:
            self._disconnect()
            return

        host = self.txt_host.text().strip()
        if not host:
            QMessageBox.warning(self, "Aviso", "Informe o endereço do servidor ou host.")
            return

        port_str = self.txt_port.text().strip()
        port = int(port_str) if port_str.isdigit() else (22 if self.cmb_proto.currentText() == "SFTP" else 21)
        user = self.txt_user.text().strip()
        password = self.txt_pass.text().strip()
        proto = self.cmb_proto.currentText()

        self.btn_connect.setEnabled(False)
        self.lbl_status.setText(f"Conectando a {host}:{port} via {proto}...")

        def worker(ctx):
            client = FtpOrSftpClient(host=host, port=port, user=user, password=password, protocol=proto)
            msg = client.connect()
            items = client.list_dir()
            return client, msg, items

        def on_done(result):
            self.client, msg, items = result
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText("Desconectar")
            self.btn_connect.setProperty("class", "danger")
            self.btn_connect.style().unpolish(self.btn_connect)
            self.btn_connect.style().polish(self.btn_connect)

            self.btn_up.setEnabled(True)
            self.btn_refresh.setEnabled(True)
            self.btn_upload.setEnabled(True)
            self.btn_download.setEnabled(True)
            self.btn_delete.setEnabled(True)

            self.txt_path.setText(self.client.current_remote_dir)
            self.lbl_status.setText(msg)
            self._populate_table(items)

        def on_error(err):
            self.btn_connect.setEnabled(True)
            self.lbl_status.setText("Falha na conexão.")
            QMessageBox.critical(self, "Erro de Conexão", f"Não foi possível conectar:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def _disconnect(self):
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.client = None

        self.btn_connect.setText("Conectar")
        self.btn_connect.setProperty("class", "primary")
        self.btn_connect.style().unpolish(self.btn_connect)
        self.btn_connect.style().polish(self.btn_connect)

        self.btn_up.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.btn_upload.setEnabled(False)
        self.btn_download.setEnabled(False)
        self.btn_delete.setEnabled(False)

        self.table.setRowCount(0)
        self.cached_items.clear()
        self.txt_path.setText("/")
        self.lbl_status.setText("Desconectado.")

    def _get_selected_item(self) -> Optional[RemoteItem]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item_widget = self.table.item(row, 0)
        if not item_widget:
            return None
        return item_widget.data(Qt.UserRole)

    def _populate_table(self, items: List[RemoteItem]):
        self.cached_items = items
        with batch_table_update(self.table):
            self.table.setRowCount(len(items))
            for row, item in enumerate(items):
                type_str = "Pasta" if item.is_dir else "Arquivo"
                size_str = "-" if item.is_dir else self._format_size(item.size)

                display_name = f"[DIR] {item.name}" if item.is_dir else item.name
                item_name = SmartTableWidgetItem(display_name, sort_value=item.name.lower(), user_data=item)
                if item.is_dir:
                    item_name.setStyleSheet("font-weight: 600;")

                item_type = SmartTableWidgetItem(type_str)
                item_size = SmartTableWidgetItem(size_str, sort_value=(-1 if item.is_dir else item.size))
                item_date = SmartTableWidgetItem(item.modified)

                self.table.setItem(row, 0, item_name)
                self.table.setItem(row, 1, item_type)
                self.table.setItem(row, 2, item_size)
                self.table.setItem(row, 3, item_date)

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{round(size_bytes / 1024, 1)} KB"
        return f"{round(size_bytes / (1024 * 1024), 2)} MB"

    def _on_table_double_click(self, row: int, col: int):
        item_widget = self.table.item(row, 0)
        if not item_widget:
            return
        item: Optional[RemoteItem] = item_widget.data(Qt.UserRole)
        if item and item.is_dir:
            self._change_dir(item.name)

    def _go_up(self):
        self._change_dir("..")

    def _change_dir(self, target_dir: str):
        if not self.client:
            return
        self.lbl_status.setText("Carregando pasta...")

        def worker(ctx):
            new_path = self.client.change_dir(target_dir)
            items = self.client.list_dir()
            return new_path, items

        def on_done(res):
            new_path, items = res
            self.txt_path.setText(new_path)
            self._populate_table(items)
            self.lbl_status.setText(f"Pasta: {new_path} ({len(items)} itens)")

        def on_error(err):
            QMessageBox.critical(self, "Erro", f"Falha ao mudar de diretório:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def _refresh_list(self):
        if not self.client:
            return

        def worker(ctx):
            return self.client.list_dir()

        def on_done(items):
            self._populate_table(items)
            self.lbl_status.setText(f"Lista atualizada ({len(items)} itens).")

        def on_error(err):
            QMessageBox.critical(self, "Erro", f"Falha ao listar itens:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def _download_selected(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo para baixar.")
            return

        if item.is_dir:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo, não uma pasta.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo", str(Path.home() / "Downloads" / item.name))
        if not save_path:
            return

        self.btn_download.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_status.setText(f"Baixando {item.name}...")

        def worker(ctx):
            def on_progress(p):
                ctx.send_progress(p, "")

            self.client.download_file(item.name, save_path, on_progress)

        def on_task_progress(percent: int, _total: int, _msg: str):
            self.progress_bar.setValue(percent)

        def on_done(_):
            self.btn_download.setEnabled(True)
            self.progress_bar.setValue(100)
            self.lbl_status.setText(f"Download de {item.name} concluído com sucesso!")
            QMessageBox.information(self, "Sucesso", f"Arquivo {item.name} baixado com sucesso!")

        def on_error(err):
            self.btn_download.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha ao baixar arquivo:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)

    def _upload_file(self):
        if not self.client:
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo para Envio")
        if not file_path:
            return

        local_file = Path(file_path)
        remote_name = local_file.name

        self.btn_upload.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_status.setText(f"Enviando {remote_name}...")

        def worker(ctx):
            def on_progress(p):
                ctx.send_progress(p, "")

            self.client.upload_file(str(local_file), remote_name, on_progress)
            return self.client.list_dir()

        def on_task_progress(percent: int, _total: int, _msg: str):
            self.progress_bar.setValue(percent)

        def on_done(items):
            self.btn_upload.setEnabled(True)
            self.progress_bar.setValue(100)
            self._populate_table(items)
            self.lbl_status.setText(f"Arquivo {remote_name} enviado com sucesso!")
            QMessageBox.information(self, "Sucesso", f"Arquivo {remote_name} enviado com sucesso!")

        def on_error(err):
            self.btn_upload.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha no envio:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)

    def _delete_selected(self):
        item = self._get_selected_item()
        if not item:
            return
        kind = "a pasta" if item.is_dir else "o arquivo"
        reply = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Deseja realmente excluir {kind} '{item.name}' do servidor remoto?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        def worker(ctx):
            self.client.delete_item(item.name, item.is_dir)
            return self.client.list_dir()

        def on_done(items):
            self._populate_table(items)
            self.lbl_status.setText(f"'{item.name}' excluído.")

        def on_error(err):
            QMessageBox.critical(self, "Erro", f"Falha ao excluir item:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

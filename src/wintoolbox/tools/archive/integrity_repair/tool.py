"""
Interface gráfica do Verificador de Integridade e Recuperação de Compactados (archive.integrity_repair).
Permite analisar a integridade membro a membro de arquivos ZIP e extrair os arquivos intactos
mesmo quando parte do arquivo está corrompida.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.archive.integrity_repair.logic import (
    verify_zip_integrity,
    salvage_archive_files,
)


@register
class IntegrityRepairTool(Tool):
    id = "archive.integrity_repair"
    name = "Verificador de Integridade e Recuperação"
    description = "Testa a integridade estrutural e CRC de arquivos compactados e recupera os arquivos intactos."
    category = "archive"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Barra de seleção de arquivo
        top_box = QHBoxLayout()
        top_box.setSpacing(8)

        lbl_file = QLabel("Arquivo Compactado:")
        top_box.addWidget(lbl_file)

        self._edit_file = QLineEdit()
        self._edit_file.setPlaceholderText("Selecione um arquivo .zip para verificar...")
        top_box.addWidget(self._edit_file)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_file)
        top_box.addWidget(btn_browse)

        self._btn_verify = QPushButton("Verificar Integridade")
        self._btn_verify.clicked.connect(self._on_verify_click)
        top_box.addWidget(self._btn_verify)

        layout.addLayout(top_box)

        # Linha de resumo / estatísticas
        stat_box = QHBoxLayout()
        self._lbl_status = QLabel("Status: Aguardando seleção de arquivo.")
        self._lbl_status.setStyleSheet("font-weight: bold;")
        stat_box.addWidget(self._lbl_status)
        stat_box.addStretch()

        self._btn_salvage = QPushButton("Recuperar Arquivos Intactos...")
        self._btn_salvage.setEnabled(False)
        self._btn_salvage.clicked.connect(self._on_salvage_click)
        stat_box.addWidget(self._btn_salvage)

        layout.addLayout(stat_box)

        # Tabela de membros
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Nome do Arquivo",
            "Tamanho Original",
            "Comprimido",
            "CRC Esperado",
            "CRC Obtido",
            "Status",
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        layout.addWidget(self._table)

        self._current_archive: Path | None = None
        return widget

    def _on_browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Arquivo Compactado",
            "",
            "Arquivos Compactados (*.zip *.tar *.gz *.7z *.rar);;Todos os Arquivos (*.*)",
        )
        if path:
            self._edit_file.setText(path)
            self._current_archive = Path(path)
            self._on_verify_click()

    def _on_verify_click(self) -> None:
        raw_path = self._edit_file.text().strip()
        if not raw_path:
            QMessageBox.warning(None, "Aviso", "Por favor, selecione um arquivo compactado.")
            return

        archive_path = Path(raw_path)
        if not archive_path.is_file():
            QMessageBox.critical(None, "Erro", f"Arquivo não encontrado: {archive_path}")
            return

        self._current_archive = archive_path
        self._lbl_status.setText("Verificando integridade e testando streams de dados...")
        self._btn_verify.setEnabled(False)

        def worker():
            return verify_zip_integrity(archive_path)

        def on_done(res: Dict[str, Any]):
            self._btn_verify.setEnabled(True)
            self._display_results(res)

        def on_error(err: str):
            self._btn_verify.setEnabled(True)
            self._lbl_status.setText(f"Erro na verificação: {err}")
            QMessageBox.critical(None, "Erro", f"Falha na verificação: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _display_results(self, res: Dict[str, Any]) -> None:
        status = res.get("status", "DESCONHECIDO")
        total = res.get("total_members", 0)
        intact = res.get("intact_members", 0)
        corrupt = res.get("corrupt_members", 0)

        if status == "INTACTO":
            self._lbl_status.setText(f"Status: INTACTO — Todos os {total} arquivos são 100% íntegros e válidos.")
            self._lbl_status.setStyleSheet("font-weight: bold; color: #28a745;")
        elif status == "PARCIALMENTE_CORROMPIDO":
            self._lbl_status.setText(
                f"Status: PARCIALMENTE CORROMPIDO — {intact} intactos, {corrupt} corrompidos de {total} itens."
            )
            self._lbl_status.setStyleSheet("font-weight: bold; color: #dc3545;")
        else:
            self._lbl_status.setText(f"Status: {status} — {res.get('error', '')}")
            self._lbl_status.setStyleSheet("font-weight: bold; color: #ffc107;")

        self._btn_salvage.setEnabled(intact > 0)

        members = res.get("members", [])
        self._table.setRowCount(len(members))

        for row, m in enumerate(members):
            self._table.setItem(row, 0, QTableWidgetItem(m.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(f"{m.get('size', 0):,} B"))
            self._table.setItem(row, 2, QTableWidgetItem(f"{m.get('compressed_size', 0):,} B"))
            self._table.setItem(row, 3, QTableWidgetItem(str(m.get("crc_expected", ""))))
            self._table.setItem(row, 4, QTableWidgetItem(str(m.get("crc_actual", ""))))

            item_status = QTableWidgetItem(m.get("status", ""))
            if m.get("status") == "OK":
                item_status.setForeground(Qt.darkGreen)
            else:
                item_status.setForeground(Qt.red)
            self._table.setItem(row, 5, item_status)

    def _on_salvage_click(self) -> None:
        if not self._current_archive or not self._current_archive.is_file():
            return

        out_dir = QFileDialog.getExistingDirectory(
            None,
            "Selecione a Pasta de Destino para Recuperar os Arquivos Intactos",
        )
        if not out_dir:
            return

        target_dir = Path(out_dir)
        self._lbl_status.setText("Recuperando e salvando arquivos intactos...")
        self._btn_salvage.setEnabled(False)

        def worker():
            return salvage_archive_files(self._current_archive, target_dir)

        def on_done(res: Dict[str, Any]):
            self._btn_salvage.setEnabled(True)
            salvaged = res.get("salvaged_count", 0)
            failed = res.get("failed_count", 0)
            self._lbl_status.setText(
                f"Recuperação finalizada: {salvaged} arquivos salvos com sucesso em {out_dir}."
            )
            QMessageBox.information(
                None,
                "Recuperação Concluída",
                f"{salvaged} arquivos foram recuperados com sucesso em:\n{out_dir}\n"
                f"Falhas registradas: {failed}",
            )

        def on_error(err: str):
            self._btn_salvage.setEnabled(True)
            self._lbl_status.setText(f"Erro na recuperação: {err}")
            QMessageBox.critical(None, "Erro", f"Falha na recuperação: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

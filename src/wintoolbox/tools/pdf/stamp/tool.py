"""
Interface gráfica da ferramenta Numeração, Carimbos e Marca d'Água em PDF.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QProgressBar, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.pdf.stamp.logic import apply_stamp_and_numbering
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("pdf.stamp.ui")


@register
class StampTool(Tool):
    id = "pdf.stamp"
    name = "Carimbos e Numeração em PDF"
    category = "PDF"
    description = "Aplique numeração automática de páginas, carimbos textuais e marcas d'água em arquivos PDF"
    keywords = ["pdf", "carimbo", "marca d'agua", "numeracao", "paginas", "watermark", "confidencial", "rascunho"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return StampView(self, parent)


class StampView(QWidget):
    def __init__(self, tool: StampTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._is_running = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(ToolHeader(self.tool.name, self.tool.description))

        # Seleção de Arquivo
        file_card = QFrame()
        file_card.setObjectName("Card")
        f_lay = QHBoxLayout(file_card)
        f_lay.setContentsMargins(14, 12, 14, 12)
        f_lay.setSpacing(10)

        f_lay.addWidget(QLabel("Arquivo PDF:"))
        self.txt_pdf = QLineEdit()
        self.txt_pdf.setPlaceholderText("Selecione o arquivo PDF...")
        f_lay.addWidget(self.txt_pdf, stretch=1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_file)
        f_lay.addWidget(btn_browse)

        layout.addWidget(file_card)

        # 1. Grupo Numeração de Páginas
        grp_num = QGroupBox("Numeração de Páginas")
        g_lay1 = QGridLayout(grp_num)
        g_lay1.setContentsMargins(14, 14, 14, 14)
        g_lay1.setSpacing(10)

        self.chk_enable_num = QCheckBox("Ativar Numeração de Páginas")
        self.chk_enable_num.setChecked(True)
        g_lay1.addWidget(self.chk_enable_num, 0, 0, 1, 2)

        g_lay1.addWidget(QLabel("Formato:"), 1, 0)
        self.cmb_format = QComboBox()
        self.cmb_format.addItems([
            "Página {page} de {total}",
            "{page} / {total}",
            "Pág. {page}",
            "{page}",
        ])
        g_lay1.addWidget(self.cmb_format, 1, 1)

        g_lay1.addWidget(QLabel("Posição:"), 2, 0)
        self.cmb_position = QComboBox()
        self.cmb_position.addItem("Rodapé Central", "bottom_center")
        self.cmb_position.addItem("Rodapé Direito", "bottom_right")
        self.cmb_position.addItem("Cabeçalho Direito", "top_right")
        self.cmb_position.addItem("Cabeçalho Central", "top_center")
        g_lay1.addWidget(self.cmb_position, 2, 1)

        layout.addWidget(grp_num)

        # 2. Grupo Carimbo / Marca d'Água
        grp_stamp = QGroupBox("Carimbo e Marca d'Água")
        g_lay2 = QGridLayout(grp_stamp)
        g_lay2.setContentsMargins(14, 14, 14, 14)
        g_lay2.setSpacing(10)

        self.chk_enable_wm = QCheckBox("Ativar Carimbo / Marca d'Água")
        self.chk_enable_wm.setChecked(False)
        g_lay2.addWidget(self.chk_enable_wm, 0, 0, 1, 2)

        g_lay2.addWidget(QLabel("Texto do Carimbo:"), 1, 0)
        self.txt_wm_text = QLineEdit("CONFIDENCIAL")
        g_lay2.addWidget(self.txt_wm_text, 1, 1)

        # Presets rápidos
        row_preset = QHBoxLayout()
        for preset in ["CONFIDENCIAL", "RASCUNHO", "CÓPIA", "APROVADO", "URGENTE"]:
            btn_p = QPushButton(preset)
            btn_p.setFixedHeight(22)
            btn_p.setStyleSheet("font-size: 11px;")
            btn_p.clicked.connect(lambda _, t=preset: self.txt_wm_text.setText(t))
            row_preset.addWidget(btn_p)
        row_preset.addStretch()
        g_lay2.addLayout(row_preset, 2, 1)

        g_lay2.addWidget(QLabel("Opacidade:"), 3, 0)
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(5, 80)
        self.slider_opacity.setValue(25)
        g_lay2.addWidget(self.slider_opacity, 3, 1)

        g_lay2.addWidget(QLabel("Rotação (graus):"), 4, 0)
        self.spin_rotation = QSpinBox()
        self.spin_rotation.setRange(-90, 90)
        self.spin_rotation.setValue(45)
        g_lay2.addWidget(self.spin_rotation, 4, 1)

        layout.addWidget(grp_stamp)

        # 3. Páginas Alvo
        row_pages = QHBoxLayout()
        row_pages.addWidget(QLabel("Intervalo de Páginas (em branco = todas):"))
        self.txt_page_range = QLineEdit()
        self.txt_page_range.setPlaceholderText("Ex: 1-5, 8, 10-12")
        row_pages.addWidget(self.txt_page_range, stretch=1)
        layout.addLayout(row_pages)

        # Barra de Ação
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.btn_apply = QPushButton("Aplicar e Salvar PDF...")
        self.btn_apply.setProperty("class", "accent")
        self.btn_apply.setStyleSheet("padding: 8px 18px; font-weight: 600;")
        self.btn_apply.clicked.connect(self._apply)
        btn_bar.addWidget(self.btn_apply)

        layout.addLayout(btn_bar)
        layout.addStretch()

    def _browse_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo PDF", "", "Arquivos PDF (*.pdf)")
        if p:
            self.txt_pdf.setText(p)

    def _apply(self) -> None:
        if self._is_running:
            return

        pdf_str = self.txt_pdf.text().strip()
        if not pdf_str or not Path(pdf_str).is_file():
            show_toast(self, "Selecione um arquivo PDF válido.", kind="error")
            return

        src_path = Path(pdf_str)
        suggested = src_path.parent / f"{src_path.stem}_carimbado.pdf"
        dst, _ = QFileDialog.getSaveFileName(self, "Salvar Novo PDF", str(suggested), "Arquivos PDF (*.pdf)")
        if not dst:
            return

        dst_path = Path(dst)
        enable_num = self.chk_enable_num.isChecked()
        num_fmt = self.cmb_format.currentText()
        num_pos = self.cmb_position.currentData()
        enable_wm = self.chk_enable_wm.isChecked()
        wm_text = self.txt_wm_text.text()
        wm_rot = self.spin_rotation.value()
        wm_op = self.slider_opacity.value() / 100.0
        p_range = self.txt_page_range.text()

        self._is_running = True
        self.btn_apply.setEnabled(False)

        def _worker():
            return apply_stamp_and_numbering(
                src_path=src_path,
                dst_path=dst_path,
                enable_numbering=enable_num,
                numbering_format=num_fmt,
                numbering_position=num_pos,
                enable_watermark=enable_wm,
                watermark_text=wm_text,
                watermark_rotation=wm_rot,
                watermark_opacity=wm_op,
                page_range_str=p_range,
            )

        def _on_done(saved):
            self._is_running = False
            self.btn_apply.setEnabled(True)
            show_toast(self, "PDF carimbado salvo com sucesso!", kind="success")
            QMessageBox.information(
                self,
                "Concluído",
                f"O arquivo PDF foi gerado com sucesso em:\n{saved}"
            )

        def _on_error(err):
            self._is_running = False
            self.btn_apply.setEnabled(True)
            show_toast(self, f"Erro: {err}", kind="error")

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

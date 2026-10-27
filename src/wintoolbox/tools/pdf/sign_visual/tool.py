"""
Interface gráfica da ferramenta Assinatura Visual em PDF (pdf.sign_visual).
Permite posicionar graficamente assinaturas digitalizadas e carimbos de data sobre páginas de PDF.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.pdf.sign_visual.logic import apply_visual_signature


@register
class SignVisualTool(Tool):
    id = "pdf.sign_visual"
    name = "Assinatura Visual em PDF"
    description = "Assinador visual de PDF: insere assinatura manuscrita digitalizada em imagem PNG transparente, rubrica e data sobre as páginas do documento."
    category = "PDF"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        form_files = QFormLayout()

        # Arquivo PDF
        self._edit_pdf = QLineEdit()
        self._edit_pdf.setPlaceholderText("Selecione o arquivo PDF a ser assinado...")
        btn_browse_pdf = QPushButton("Procurar...")
        btn_browse_pdf.clicked.connect(self._on_browse_pdf)
        box_pdf = QHBoxLayout()
        box_pdf.addWidget(self._edit_pdf)
        box_pdf.addWidget(btn_browse_pdf)
        form_files.addRow("Documento PDF:", box_pdf)

        # Imagem da Assinatura
        self._edit_sig = QLineEdit()
        self._edit_sig.setPlaceholderText("Selecione a imagem da assinatura (PNG transparente recomendada)...")
        btn_browse_sig = QPushButton("Procurar...")
        btn_browse_sig.clicked.connect(self._on_browse_sig)
        box_sig = QHBoxLayout()
        box_sig.addWidget(self._edit_sig)
        box_sig.addWidget(btn_browse_sig)
        form_files.addRow("Imagem da Assinatura:", box_sig)

        layout.addLayout(form_files)

        # Configurações de posicionamento
        grp_pos = QGroupBox("Posicionamento e Dimensões (em pontos / pt)")
        form_pos = QFormLayout(grp_pos)

        self._combo_page = QComboBox()
        self._combo_page.addItem("Primeira Página (1)", 1)
        self._combo_page.addItem("Última Página", -2)
        self._combo_page.addItem("Todas as Páginas", -1)
        self._combo_page.addItem("Página Específica...", 0)
        self._combo_page.currentIndexChanged.connect(self._on_page_mode_changed)
        form_pos.addRow("Página Alvo:", self._combo_page)

        self._spin_custom_page = QSpinBox()
        self._spin_custom_page.setRange(1, 9999)
        self._spin_custom_page.setValue(1)
        self._spin_custom_page.setEnabled(False)
        form_pos.addRow("Número da Página:", self._spin_custom_page)

        coord_box = QHBoxLayout()
        self._spin_x = QDoubleSpinBox()
        self._spin_x.setRange(0, 2000)
        self._spin_x.setValue(100.0)
        self._spin_x.setSuffix(" pt")
        coord_box.addWidget(QLabel("X (horizontal):"))
        coord_box.addWidget(self._spin_x)

        self._spin_y = QDoubleSpinBox()
        self._spin_y.setRange(0, 2000)
        self._spin_y.setValue(100.0)
        self._spin_y.setSuffix(" pt")
        coord_box.addWidget(QLabel("Y (vertical):"))
        coord_box.addWidget(self._spin_y)
        form_pos.addRow("Coordenadas:", coord_box)

        dim_box = QHBoxLayout()
        self._spin_w = QDoubleSpinBox()
        self._spin_w.setRange(10, 1000)
        self._spin_w.setValue(150.0)
        self._spin_w.setSuffix(" pt")
        dim_box.addWidget(QLabel("Largura:"))
        dim_box.addWidget(self._spin_w)

        self._spin_h = QDoubleSpinBox()
        self._spin_h.setRange(10, 1000)
        self._spin_h.setValue(50.0)
        self._spin_h.setSuffix(" pt")
        dim_box.addWidget(QLabel("Altura:"))
        dim_box.addWidget(self._spin_h)
        form_pos.addRow("Dimensões:", dim_box)

        layout.addWidget(grp_pos)

        # Carimbo de data / texto
        grp_date = QGroupBox("Carimbo de Data / Rubrica")
        date_layout = QVBoxLayout(grp_date)
        self._chk_add_date = QCheckBox("Adicionar texto de data abaixo da assinatura")
        self._chk_add_date.setChecked(True)
        date_layout.addWidget(self._chk_add_date)

        self._edit_date_text = QLineEdit()
        today_str = datetime.now().strftime("Assinado em %d/%m/%Y às %H:%M")
        self._edit_date_text.setText(today_str)
        date_layout.addWidget(self._edit_date_text)
        layout.addWidget(grp_date)

        # Botão de ação
        self._btn_apply = QPushButton("Aplicar Assinatura e Salvar PDF...")
        self._btn_apply.clicked.connect(self._on_apply_click)
        layout.addWidget(self._btn_apply)

        self._lbl_status = QLabel("Selecione o PDF e a imagem de assinatura para iniciar.")
        layout.addWidget(self._lbl_status)
        layout.addStretch()
        return widget

    def _on_browse_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Selecionar Documento PDF", "", "Arquivos PDF (*.pdf)")
        if path:
            self._edit_pdf.setText(path)

    def _on_browse_sig(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Imagem da Assinatura",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp);;Todos os Arquivos (*.*)",
        )
        if path:
            self._edit_sig.setText(path)

    def _on_page_mode_changed(self, idx: int) -> None:
        val = self._combo_page.currentData()
        self._spin_custom_page.setEnabled(val == 0)

    def _on_apply_click(self) -> None:
        pdf_str = self._edit_pdf.text().strip()
        sig_str = self._edit_sig.text().strip()

        if not pdf_str or not sig_str:
            QMessageBox.warning(None, "Aviso", "Selecione o PDF e o arquivo da imagem da assinatura.")
            return

        pdf_path = Path(pdf_str)
        sig_path = Path(sig_str)

        out_path_str, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar PDF Assinado Como",
            str(pdf_path.parent / f"{pdf_path.stem}_assinado.pdf"),
            "Arquivos PDF (*.pdf)",
        )
        if not out_path_str:
            return

        out_path = Path(out_path_str)

        # Calcula página
        mode = self._combo_page.currentData()
        if mode == -2:
            import pypdf
            reader = pypdf.PdfReader(pdf_path)
            target_page = len(reader.pages)
        elif mode == 0:
            target_page = self._spin_custom_page.value()
        else:
            target_page = mode

        x = self._spin_x.value()
        y = self._spin_y.value()
        w = self._spin_w.value()
        h = self._spin_h.value()
        add_d = self._chk_add_date.isChecked()
        d_text = self._edit_date_text.text().strip()

        self._lbl_status.setText("Aplicando assinatura sobre o PDF...")
        self._btn_apply.setEnabled(False)

        def worker():
            return apply_visual_signature(
                pdf_path=pdf_path,
                signature_img_path=sig_path,
                output_pdf_path=out_path,
                page_number=target_page,
                x_pt=x,
                y_pt=y,
                width_pt=w,
                height_pt=h,
                add_date=add_d,
                date_text=d_text,
            )

        def on_done(res_path: Path):
            self._btn_apply.setEnabled(True)
            self._lbl_status.setText(f"PDF assinado com sucesso: {res_path.name}")
            QMessageBox.information(
                None,
                "Assinatura Concluída",
                f"O documento assinado foi gerado com sucesso em:\n{res_path}",
            )

        def on_error(err: str):
            self._btn_apply.setEnabled(True)
            self._lbl_status.setText(f"Erro ao aplicar assinatura: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao assinar PDF: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

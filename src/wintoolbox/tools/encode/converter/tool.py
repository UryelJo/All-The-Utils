"""
Ferramenta: Conversor de Timestamps Unix e Bases Numéricas.
Permite converter Epoch ↔ Data/Hora legível e sincronizar números entre Binário, Octal, Decimal e Hexadecimal.
"""
import time
from datetime import datetime, timezone
from typing import Optional
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QApplication, QDateTimeEdit, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from .logic import (
    TimestampConversionResult,
    convert_datetime_to_epoch,
    convert_epoch_to_dates,
    convert_number_bases,
)

@register
class ConverterTool(Tool):
    id = "encode.converter"
    name = "Conversor de Timestamps e Bases"
    category = "Codificação e Hash"
    description = "Converte timestamps Unix Epoch em datas legíveis e alterna entre bases numéricas (Bin/Oct/Dec/Hex)"
    keywords = ["timestamp", "epoch", "data", "hora", "conversor", "bases", "hex", "binario", "decimal", "octal"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ConverterView(self, parent)

class ConverterView(QWidget):
    def __init__(self, tool: ConverterTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._updating_bases = False
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

        # ABA 1: Conversor de Timestamp Unix Epoch
        tab_ts = QWidget()
        l_ts = QVBoxLayout(tab_ts)
        l_ts.setSpacing(12)

        card_epoch = QFrame()
        card_epoch.setProperty("class", "card")
        l_ce = QVBoxLayout(card_epoch)
        l_ce.setSpacing(10)

        row_e1 = QHBoxLayout()
        row_e1.addWidget(QLabel("Timestamp Unix (Segundos ou Milissegundos):"))
        self.txt_epoch_in = QLineEdit(str(int(time.time())))
        self.txt_epoch_in.textChanged.connect(self._on_epoch_changed)
        row_e1.addWidget(self.txt_epoch_in, stretch=1)

        btn_now = QPushButton("Momento Atual (Agora)")
        btn_now.setProperty("class", "primary")
        btn_now.clicked.connect(self._set_epoch_now)
        row_e1.addWidget(btn_now)
        l_ce.addLayout(row_e1)

        grid_dates = QGridLayout()
        grid_dates.setSpacing(8)

        grid_dates.addWidget(QLabel("Horário Local:"), 0, 0)
        self.txt_dt_local = QLineEdit()
        self.txt_dt_local.setReadOnly(True)
        grid_dates.addWidget(self.txt_dt_local, 0, 1)

        grid_dates.addWidget(QLabel("Horário UTC:"), 1, 0)
        self.txt_dt_utc = QLineEdit()
        self.txt_dt_utc.setReadOnly(True)
        grid_dates.addWidget(self.txt_dt_utc, 1, 1)

        grid_dates.addWidget(QLabel("Formato ISO 8601:"), 2, 0)
        self.txt_dt_iso = QLineEdit()
        self.txt_dt_iso.setReadOnly(True)
        grid_dates.addWidget(self.txt_dt_iso, 2, 1)

        l_ce.addLayout(grid_dates)
        l_ts.addWidget(card_epoch)

        # Conversão Inversa (Data -> Epoch)
        card_inv = QFrame()
        card_inv.setProperty("class", "card")
        l_ci = QVBoxLayout(card_inv)
        l_ci.setSpacing(8)

        lbl_inv_title = QLabel("Conversão Inversa (Data / Hora → Epoch)")
        lbl_inv_title.setStyleSheet("font-weight: 600;")
        l_ci.addWidget(lbl_inv_title)

        row_inv = QHBoxLayout()
        row_inv.addWidget(QLabel("Selecionar Data e Hora:"))
        self.dt_picker = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_picker.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        self.dt_picker.setCalendarPopup(True)
        self.dt_picker.dateTimeChanged.connect(self._on_dt_picker_changed)
        row_inv.addWidget(self.dt_picker, stretch=1)

        row_inv.addWidget(QLabel("Epoch (s):"))
        self.txt_res_epoch = QLineEdit()
        self.txt_res_epoch.setReadOnly(True)
        row_inv.addWidget(self.txt_res_epoch)

        btn_cp_epoch = QPushButton("Copiar")
        btn_cp_epoch.clicked.connect(lambda: self._copy_text(self.txt_res_epoch.text()))
        row_inv.addWidget(btn_cp_epoch)
        l_ci.addLayout(row_inv)

        l_ts.addWidget(card_inv)
        l_ts.addStretch()
        tabs.addTab(tab_ts, "Timestamp Epoch")

        # ABA 2: Conversor de Bases Numéricas
        tab_bases = QWidget()
        l_bases = QVBoxLayout(tab_bases)
        l_bases.setSpacing(12)

        card_b = QFrame()
        card_b.setProperty("class", "card")
        l_cb = QVBoxLayout(card_b)
        l_cb.setSpacing(10)

        grid_b = QGridLayout()
        grid_b.setSpacing(10)

        grid_b.addWidget(QLabel("Decimal (Base 10):"), 0, 0)
        self.txt_dec = QLineEdit("255")
        self.txt_dec.textChanged.connect(lambda s: self._convert_base(s, 10))
        grid_b.addWidget(self.txt_dec, 0, 1)

        grid_b.addWidget(QLabel("Hexadecimal (Base 16):"), 1, 0)
        self.txt_hex = QLineEdit("FF")
        self.txt_hex.textChanged.connect(lambda s: self._convert_base(s, 16))
        grid_b.addWidget(self.txt_hex, 1, 1)

        grid_b.addWidget(QLabel("Binário (Base 2):"), 2, 0)
        self.txt_bin = QLineEdit("11111111")
        self.txt_bin.textChanged.connect(lambda s: self._convert_base(s, 2))
        grid_b.addWidget(self.txt_bin, 2, 1)

        grid_b.addWidget(QLabel("Octal (Base 8):"), 3, 0)
        self.txt_oct = QLineEdit("377")
        self.txt_oct.textChanged.connect(lambda s: self._convert_base(s, 8))
        grid_b.addWidget(self.txt_oct, 3, 1)

        l_cb.addLayout(grid_b)
        l_bases.addWidget(card_b)
        l_bases.addStretch()
        tabs.addTab(tab_bases, "Bases Numéricas (Bin/Oct/Dec/Hex)")

        layout.addWidget(tabs)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        self._on_epoch_changed(self.txt_epoch_in.text())
        self._on_dt_picker_changed(self.dt_picker.dateTime())

    def _set_epoch_now(self):
        self.txt_epoch_in.setText(str(int(time.time())))

    def _on_epoch_changed(self, text: str):
        res = convert_epoch_to_dates(text)
        self.txt_dt_local.setText(res.local_str)
        self.txt_dt_utc.setText(res.utc_str)
        self.txt_dt_iso.setText(res.iso_str)

    def _on_dt_picker_changed(self, qdt: QDateTime):
        epoch = convert_datetime_to_epoch(qdt.toPython())
        self.txt_res_epoch.setText(str(epoch))

    def _convert_base(self, value_str: str, base: int):
        if self._updating_bases:
            return

        res = convert_number_bases(value_str, base)
        if not res.is_valid:
            return

        self._updating_bases = True
        if base != 10:
            self.txt_dec.setText(res.decimal)
        if base != 16:
            self.txt_hex.setText(res.hexadecimal)
        if base != 2:
            self.txt_bin.setText(res.binary)
        if base != 8:
            self.txt_oct.setText(res.octal)
        self._updating_bases = False

    def _copy_text(self, text: str):
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copiado", f"'{text}' copiado para a área de transferência!")

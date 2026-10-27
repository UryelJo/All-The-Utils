"""
Interface de usuário para o Estimador de Tempo de Transferência e Downloads.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.transfer.logic import (
    calculate_transfer_time,
)

PRESET_FILES = [
    ("Personalizado", 0, "GB"),
    ("Jogo Moderno (ex: Call of Duty / GTA V)", 90.0, "GB"),
    ("Filme em 4K HDR (Blu-ray Rip)", 25.0, "GB"),
    ("Imagem ISO de Instalação do Windows 11", 6.5, "GB"),
    ("Filme em Full HD 1080p", 4.5, "GB"),
    ("Álbum Musical em Alta Fidelidade (FLAC)", 600.0, "MB"),
    ("Atualização de Sistema Operacional", 1.8, "GB"),
]

PRESET_SPEEDS = [
    ("Personalizado", 0),
    ("Banda Larga Fibra 100 Mbps (12,5 MB/s)", 100.0),
    ("Banda Larga Fibra 300 Mbps (37,5 MB/s)", 300.0),
    ("Banda Larga Fibra 500 Mbps (62,5 MB/s)", 500.0),
    ("Banda Larga Fibra 1 Gbps (125 MB/s)", 1000.0),
    ("Conexão Móvel 4G LTE Média (35 Mbps)", 35.0),
    ("Conexão Móvel 5G Real (250 Mbps)", 250.0),
]


@register
class TransferCalcTool(Tool):
    """Estimador de tempo de transferência e download de arquivos com conversão Mbps vs MB/s."""

    id = "calc.transfer"
    name = "Estimador de Tempo de Download & Transferência"
    description = "Calcule o tempo exato para baixar ou transferir arquivos e converta Mbps de planos de internet para MB/s reais."
    category = "calc"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Cabeçalho
        title = QLabel("Estimador de Tempo de Transferência & Download")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Entenda a diferença técnica entre a velocidade contratada pelo provedor (Megabits/s) e a velocidade real de gravação (Megabytes/s)."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        main_box = QHBoxLayout()
        main_box.setSpacing(15)

        # Lado Esquerdo: Parâmetros
        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.cmb_preset_file = QComboBox()
        for name, val, u in PRESET_FILES:
            self.cmb_preset_file.addItem(name, (val, u))
        self.cmb_preset_file.currentIndexChanged.connect(self._on_preset_file_changed)
        f_layout.addRow("Exemplo de Arquivo:", self.cmb_preset_file)

        size_box = QHBoxLayout()
        self.spn_file_size = QDoubleSpinBox()
        self.spn_file_size.setRange(0.01, 100000.0)
        self.spn_file_size.setValue(25.0)
        self.spn_file_size.setDecimals(2)
        self.spn_file_size.valueChanged.connect(self._recalculate)
        self.cmb_size_unit = QComboBox()
        self.cmb_size_unit.addItems(["MB", "GB", "TB", "KB"])
        self.cmb_size_unit.setCurrentText("GB")
        self.cmb_size_unit.currentTextChanged.connect(self._recalculate)
        size_box.addWidget(self.spn_file_size, 2)
        size_box.addWidget(self.cmb_size_unit, 1)
        f_layout.addRow("Tamanho do Arquivo:", size_box)

        self.cmb_preset_speed = QComboBox()
        for name, val in PRESET_SPEEDS:
            self.cmb_preset_speed.addItem(name, val)
        self.cmb_preset_speed.setCurrentIndex(2)  # 300 Mbps
        self.cmb_preset_speed.currentIndexChanged.connect(self._on_preset_speed_changed)
        f_layout.addRow("Plano de Internet:", self.cmb_preset_speed)

        speed_box = QHBoxLayout()
        self.spn_speed = QDoubleSpinBox()
        self.spn_speed.setRange(0.01, 100000.0)
        self.spn_speed.setValue(300.0)
        self.spn_speed.setDecimals(1)
        self.spn_speed.valueChanged.connect(self._recalculate)
        self.cmb_speed_unit = QComboBox()
        self.cmb_speed_unit.addItems(["Mbps", "Gbps", "MB/s", "KB/s", "Kbps"])
        self.cmb_speed_unit.setCurrentText("Mbps")
        self.cmb_speed_unit.currentTextChanged.connect(self._recalculate)
        speed_box.addWidget(self.spn_speed, 2)
        speed_box.addWidget(self.cmb_speed_unit, 1)
        f_layout.addRow("Velocidade do Link:", speed_box)

        self.spn_overhead = QDoubleSpinBox()
        self.spn_overhead.setRange(0.0, 30.0)
        self.spn_overhead.setValue(5.0)
        self.spn_overhead.setSuffix(" %")
        self.spn_overhead.valueChanged.connect(self._recalculate)
        f_layout.addRow("Overhead de Pacotes (Perda):", self.spn_overhead)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        main_box.addWidget(form_frame)

        # Lado Direito: Resultados e Tabela de Comparação
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 12px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(10)

        # Card de Destaque
        card_time = QFrame()
        card_time.setStyleSheet("background-color: rgba(22, 163, 74, 0.15); border-radius: 6px; padding: 12px;")
        v_t = QVBoxLayout(card_time)
        v_t.addWidget(QLabel("TEMPO ESTIMADO DE DOWNLOAD:"))
        self.lbl_time_result = QLabel("Calculando...")
        self.lbl_time_result.setStyleSheet("font-size: 26px; font-weight: bold; color: #16a34a;")
        v_t.addWidget(self.lbl_time_result)
        v_res.addWidget(card_time)

        # Velocidades Reais
        grid_v = QGridLayout()
        grid_v.addWidget(QLabel("Velocidade Contratada:"), 0, 0)
        self.lbl_speed_mbps = QLabel("300,00 Mbps")
        self.lbl_speed_mbps.setStyleSheet("font-weight: bold; color: #0284c7;")
        grid_v.addWidget(self.lbl_speed_mbps, 0, 1)

        grid_v.addWidget(QLabel("Taxa Real de Gravação (MB/s):"), 1, 0)
        self.lbl_speed_mbs = QLabel("35,62 MB/s (com overhead)")
        self.lbl_speed_mbs.setStyleSheet("font-weight: bold; color: #16a34a;")
        grid_v.addWidget(self.lbl_speed_mbs, 1, 1)
        v_res.addLayout(grid_v)

        # Tabela Comparativa de Planos
        v_res.addWidget(QLabel("<b>Comparativo para este mesmo arquivo em outros planos:</b>"))
        self.tbl_compare = QTableWidget(5, 3)
        self.tbl_compare.setHorizontalHeaderLabels(["Velocidade do Plano", "Taxa Real (MB/s)", "Tempo Estimado"])
        self.tbl_compare.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_compare.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_compare.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_compare.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v_res.addWidget(self.tbl_compare, 1)

        main_box.addWidget(res_frame, 1)
        layout.addLayout(main_box, 1)

        self._recalculate()
        return widget

    def _on_preset_file_changed(self) -> None:
        data = self.cmb_preset_file.currentData()
        if data and data[0] > 0:
            self.spn_file_size.setValue(data[0])
            self.cmb_size_unit.setCurrentText(data[1])

    def _on_preset_speed_changed(self) -> None:
        val = self.cmb_preset_speed.currentData()
        if val and val > 0:
            self.spn_speed.setValue(val)
            self.cmb_speed_unit.setCurrentText("Mbps")

    def _recalculate(self) -> None:
        size_val = self.spn_file_size.value()
        size_u = self.cmb_size_unit.currentText()
        speed_val = self.spn_speed.value()
        speed_u = self.cmb_speed_unit.currentText()
        overhead = self.spn_overhead.value()

        res = calculate_transfer_time(size_val, size_u, speed_val, speed_u, overhead)
        self.lbl_time_result.setText(res["tempo_formatado"])
        self.lbl_speed_mbps.setText(f"{res['velocidade_mbps']:,.2f} Mbps".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_speed_mbs.setText(f"{res['velocidade_efetiva_mb_s']:.2f} MB/s (com overhead de {overhead:.0f}%)")

        # Atualiza tabela de comparação
        planos = [
            ("50 Mbps", 50.0),
            ("100 Mbps", 100.0),
            ("300 Mbps", 300.0),
            ("500 Mbps", 500.0),
            ("1 Gbps (1.000 Mbps)", 1000.0),
        ]

        for r, (label, mbps) in enumerate(planos):
            calc_p = calculate_transfer_time(size_val, size_u, mbps, "Mbps", overhead)
            self.tbl_compare.setItem(r, 0, QTableWidgetItem(label))
            self.tbl_compare.setItem(r, 1, QTableWidgetItem(f"{calc_p['velocidade_efetiva_mb_s']:.2f} MB/s"))
            self.tbl_compare.setItem(r, 2, QTableWidgetItem(calc_p["tempo_formatado"]))

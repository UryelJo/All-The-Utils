"""
Interface gráfica da Calculadora do Programador (calc.programmer).
"""
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QRadioButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.programmer.logic import (
    WORD_SIZES, bitwise_and, bitwise_not, bitwise_or, bitwise_rol,
    bitwise_ror, bitwise_sar, bitwise_shl, bitwise_shr, bitwise_xor,
    clamp_to_word, format_all_bases, get_all_bits, get_mask,
    parse_programmer_value, toggle_bit
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("calc.programmer.ui")


@register
class ProgrammerCalculatorTool(Tool):
    id = "calc.programmer"
    name = "Calculadora do Programador"
    category = "Calculadoras"
    description = "Conversão em tempo real entre Hexadecimal, Decimal, Octal e Binário, operações bitwise e manipulador de bits"
    keywords = ["programador", "binario", "hexadecimal", "octal", "decimal", "bitwise", "and", "or", "xor", "shift", "bits"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ProgrammerCalculatorView(self, parent)


class ProgrammerCalculatorView(QWidget):
    def __init__(self, tool: ProgrammerCalculatorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_value: int = 0
        self._word_size: str = "DWORD"
        self._bit_buttons: List[QPushButton] = []
        self._updating = False

        self._build_ui()
        self._sync_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Calculadora do Programador",
            "Conversão e depuração em tempo real entre bases numéricas, operadores lógicos binários e chaveamento de bits."
        ))

        # 1. Barra de Tamanho de Palavra (Word Size)
        ws_frame = QFrame()
        ws_frame.setStyleSheet("QFrame { background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 6px; }")
        ws_layout = QHBoxLayout(ws_frame)
        ws_layout.setContentsMargins(8, 4, 8, 4)
        ws_layout.addWidget(QLabel("Largura de Bits (Word Size):"))

        self.btn_group_ws = QButtonGroup(self)
        self.rb_qword = QRadioButton("QWORD (64-bit)")
        self.rb_dword = QRadioButton("DWORD (32-bit)")
        self.rb_word = QRadioButton("WORD (16-bit)")
        self.rb_byte = QRadioButton("BYTE (8-bit)")

        self.rb_dword.setChecked(True)

        for rb, name in [(self.rb_qword, "QWORD"), (self.rb_dword, "DWORD"), (self.rb_word, "WORD"), (self.rb_byte, "BYTE")]:
            self.btn_group_ws.addButton(rb)
            ws_layout.addWidget(rb)
            rb.toggled.connect(self._on_word_size_changed)

        ws_layout.addStretch(1)

        btn_clear = QPushButton("Zerar (0)")
        btn_clear.clicked.connect(self._clear_all)
        ws_layout.addWidget(btn_clear)

        btn_all_ones = QPushButton("Definir Tudo (1s)")
        btn_all_ones.clicked.connect(self._set_all_ones)
        ws_layout.addWidget(btn_all_ones)

        root.addWidget(ws_frame)

        # 2. Painel de Bases Numéricas (HEX, DEC, OCT, BIN)
        bases_box = QGroupBox("Bases Numéricas (Edição e Conversão Instantânea)")
        grid_bases = QGridLayout(bases_box)
        grid_bases.setSpacing(8)

        # HEX
        grid_bases.addWidget(QLabel("HEX (16):"), 0, 0)
        self.txt_hex = QLineEdit()
        self.txt_hex.setFont(QFont("Cascadia Mono", 11, QFont.Weight.Bold))
        self.txt_hex.setPlaceholderText("Ex: 1A2F")
        self.txt_hex.textEdited.connect(self._on_hex_edited)
        grid_bases.addWidget(self.txt_hex, 0, 1)

        btn_copy_hex = QPushButton("Copiar")
        btn_copy_hex.clicked.connect(lambda: self._copy_to_clip(self.txt_hex.text(), "HEX copiado"))
        grid_bases.addWidget(btn_copy_hex, 0, 2)

        # DEC
        grid_bases.addWidget(QLabel("DEC (10):"), 1, 0)
        self.txt_dec = QLineEdit()
        self.txt_dec.setFont(QFont("Cascadia Mono", 11, QFont.Weight.Bold))
        self.txt_dec.setPlaceholderText("Ex: 4294967295 ou -1")
        self.txt_dec.textEdited.connect(self._on_dec_edited)
        grid_bases.addWidget(self.txt_dec, 1, 1)

        self.lbl_dec_signed = QLabel("Com sinal: 0")
        self.lbl_dec_signed.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        grid_bases.addWidget(self.lbl_dec_signed, 1, 2)

        # OCT
        grid_bases.addWidget(QLabel("OCT (8):"), 2, 0)
        self.txt_oct = QLineEdit()
        self.txt_oct.setFont(QFont("Cascadia Mono", 11))
        self.txt_oct.setPlaceholderText("Ex: 777")
        self.txt_oct.textEdited.connect(self._on_oct_edited)
        grid_bases.addWidget(self.txt_oct, 2, 1)

        btn_copy_oct = QPushButton("Copiar")
        btn_copy_oct.clicked.connect(lambda: self._copy_to_clip(self.txt_oct.text(), "OCT copiado"))
        grid_bases.addWidget(btn_copy_oct, 2, 2)

        # BIN
        grid_bases.addWidget(QLabel("BIN (2):"), 3, 0)
        self.txt_bin = QLineEdit()
        self.txt_bin.setFont(QFont("Cascadia Mono", 11, QFont.Weight.Bold))
        self.txt_bin.setStyleSheet("color: #38BDF8;")
        self.txt_bin.setPlaceholderText("Ex: 1100 1010")
        self.txt_bin.textEdited.connect(self._on_bin_edited)
        grid_bases.addWidget(self.txt_bin, 3, 1)

        btn_copy_bin = QPushButton("Copiar")
        btn_copy_bin.clicked.connect(lambda: self._copy_to_clip(self.txt_bin.text(), "BIN copiado"))
        grid_bases.addWidget(btn_copy_bin, 3, 2)

        root.addWidget(bases_box)

        # 3. Operações Bitwise
        op_box = QGroupBox("Operações Lógicas Bitwise")
        op_layout = QHBoxLayout(op_box)
        op_layout.setSpacing(8)

        op_layout.addWidget(QLabel("Operador:"))
        self.combo_op = QComboBox()
        self.combo_op.addItem("AND (E Lógico)", "AND")
        self.combo_op.addItem("OR (OU Lógico)", "OR")
        self.combo_op.addItem("XOR (OU Exclusivo)", "XOR")
        self.combo_op.addItem("NOT (Inversão Unária)", "NOT")
        self.combo_op.addItem("SHL (Shift Left <<)", "SHL")
        self.combo_op.addItem("SHR (Shift Right >> Lógico)", "SHR")
        self.combo_op.addItem("SAR (Shift Right Aritmético)", "SAR")
        self.combo_op.addItem("ROL (Rotate Left)", "ROL")
        self.combo_op.addItem("ROR (Rotate Right)", "ROR")
        self.combo_op.currentIndexChanged.connect(self._on_op_changed)
        op_layout.addWidget(self.combo_op)

        self.lbl_operand = QLabel("Segundo Operando / Deslocamento:")
        op_layout.addWidget(self.lbl_operand)

        self.txt_operand = QLineEdit()
        self.txt_operand.setPlaceholderText("Número (Dec, 0xHex, 0bBin)")
        self.txt_operand.setText("1")
        op_layout.addWidget(self.txt_operand)

        btn_apply_op = QPushButton("Calcular Operação")
        btn_apply_op.clicked.connect(self._apply_bitwise_op)
        op_layout.addWidget(btn_apply_op)

        root.addWidget(op_box)

        # 4. Visualizador Interativo de Bits (Bit Board)
        board_box = QGroupBox("Chaveador Interativo de Bits (Clique no bit para alternar 0/1)")
        board_vlay = QVBoxLayout(board_box)

        self.bits_container = QWidget()
        self.bits_grid = QGridLayout(self.bits_container)
        self.bits_grid.setSpacing(4)
        self.bits_grid.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.bits_container)
        scroll.setFixedHeight(140)
        board_vlay.addWidget(scroll)

        root.addWidget(board_box, stretch=1)

        self._rebuild_bit_board()

    def _on_word_size_changed(self) -> None:
        if self.rb_qword.isChecked():
            self._word_size = "QWORD"
        elif self.rb_dword.isChecked():
            self._word_size = "DWORD"
        elif self.rb_word.isChecked():
            self._word_size = "WORD"
        else:
            self._word_size = "BYTE"

        self._current_value = clamp_to_word(self._current_value, self._word_size)
        self._rebuild_bit_board()
        self._sync_all()

    def _rebuild_bit_board(self) -> None:
        # Limpa botões existentes
        while self.bits_grid.count():
            item = self.bits_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._bit_buttons.clear()
        total_bits = WORD_SIZES.get(self._word_size, 32)

        # Monta grade com 16 bits por linha (da esquerda [bit mais alto] para a direita [bit mais baixo])
        cols_per_row = 16
        for bit_idx in range(total_bits - 1, -1, -1):
            row_idx = (total_bits - 1 - bit_idx) // cols_per_row * 2
            col_idx = (total_bits - 1 - bit_idx) % cols_per_row

            # Rótulo do índice do bit
            lbl_idx = QLabel(str(bit_idx))
            lbl_idx.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_idx.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 9px;")
            self.bits_grid.addWidget(lbl_idx, row_idx, col_idx)

            # Botão do bit
            btn = QPushButton("0")
            btn.setFixedSize(28, 28)
            btn.setFont(QFont("Cascadia Mono", 10, QFont.Weight.Bold))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, b=bit_idx: self._on_bit_clicked(b))
            self.bits_grid.addWidget(btn, row_idx + 1, col_idx)
            self._bit_buttons.append((bit_idx, btn))

        self._update_bit_buttons()

    def _on_bit_clicked(self, bit_idx: int) -> None:
        self._current_value = toggle_bit(self._current_value, bit_idx, self._word_size)
        self._sync_all()

    def _update_bit_buttons(self) -> None:
        bits = get_all_bits(self._current_value, self._word_size)
        for bit_idx, btn in self._bit_buttons:
            bit_val = bits[bit_idx] if bit_idx < len(bits) else 0
            btn.setText(str(bit_val))
            if bit_val == 1:
                btn.setStyleSheet("QPushButton { background-color: #0284C7; color: #FFFFFF; border-radius: 4px; font-weight: bold; }")
            else:
                btn.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.05); color: rgba(255, 255, 255, 0.6); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 4px; }")

    def _sync_all(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            data = format_all_bases(self._current_value, self._word_size)
            self.txt_hex.setText(data["hex"])
            self.txt_dec.setText(data["dec_unsigned"])
            self.lbl_dec_signed.setText(f"Com sinal: {data['dec_signed']}")
            self.txt_oct.setText(data["oct"])
            self.txt_bin.setText(data["bin"])
            self._update_bit_buttons()
        finally:
            self._updating = False

    def _on_hex_edited(self, text: str) -> None:
        if self._updating:
            return
        try:
            self._current_value = parse_programmer_value(text, default_base=16, word_size=self._word_size)
            self._sync_all()
        except ValueError:
            pass

    def _on_dec_edited(self, text: str) -> None:
        if self._updating:
            return
        try:
            self._current_value = parse_programmer_value(text, default_base=10, word_size=self._word_size)
            self._sync_all()
        except ValueError:
            pass

    def _on_oct_edited(self, text: str) -> None:
        if self._updating:
            return
        try:
            self._current_value = parse_programmer_value(text, default_base=8, word_size=self._word_size)
            self._sync_all()
        except ValueError:
            pass

    def _on_bin_edited(self, text: str) -> None:
        if self._updating:
            return
        try:
            self._current_value = parse_programmer_value(text, default_base=2, word_size=self._word_size)
            self._sync_all()
        except ValueError:
            pass

    def _on_op_changed(self) -> None:
        op = self.combo_op.currentData()
        if op == "NOT":
            self.lbl_operand.setVisible(False)
            self.txt_operand.setVisible(False)
        else:
            self.lbl_operand.setVisible(True)
            self.txt_operand.setVisible(True)

    def _apply_bitwise_op(self) -> None:
        op = self.combo_op.currentData()
        try:
            operand = parse_programmer_value(self.txt_operand.text(), default_base=10, word_size=self._word_size) if op != "NOT" else 0
        except ValueError:
            operand = 0

        val = self._current_value
        ws = self._word_size

        if op == "AND":
            self._current_value = bitwise_and(val, operand, ws)
        elif op == "OR":
            self._current_value = bitwise_or(val, operand, ws)
        elif op == "XOR":
            self._current_value = bitwise_xor(val, operand, ws)
        elif op == "NOT":
            self._current_value = bitwise_not(val, ws)
        elif op == "SHL":
            self._current_value = bitwise_shl(val, operand, ws)
        elif op == "SHR":
            self._current_value = bitwise_shr(val, operand, ws)
        elif op == "SAR":
            self._current_value = bitwise_sar(val, operand, ws)
        elif op == "ROL":
            self._current_value = bitwise_rol(val, operand, ws)
        elif op == "ROR":
            self._current_value = bitwise_ror(val, operand, ws)

        self._sync_all()

    def _clear_all(self) -> None:
        self._current_value = 0
        self._sync_all()

    def _set_all_ones(self) -> None:
        self._current_value = get_mask(self._word_size)
        self._sync_all()

    def _copy_to_clip(self, text: str, msg: str) -> None:
        QApplication.clipboard().setText(text)
        show_toast(self, msg)

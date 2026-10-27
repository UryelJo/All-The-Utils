"""
Interface gráfica Fluent da ferramenta Cifras Clássicas de Criptografia.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.encode.classic_ciphers.logic import (
    atbash_cipher,
    caesar_brute_force,
    caesar_cipher,
    morse_to_text,
    rot13_cipher,
    rot47_cipher,
    text_to_morse,
    vigenere_cipher,
)


@register
class ClassicCiphersTool(Tool):
    """Ferramenta para cifragem e decifragem de cifras históricas da criptografia."""
    id = "encode.classic_ciphers"
    title = "Cifras Clássicas"
    category = "Codificação e Hash"
    description = (
        "Criptografa e decifra mensagens utilizando métodos históricos clássicos: "
        "Cifra de César com brute-force, Vigenère com chave, Código Morse, Cifra Atbash e ROT13/ROT47."
    )
    icon = "Lock"

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._on_process)

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Cifras Clássicas da Criptografia")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Explore o funcionamento dos primeiros algoritmos de criptografia da história: "
            "Cifra de César (Roma Antiga), Vigenère (Renascença), Código Morse (Telegrafia), Atbash e rotações simétricas."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Barra de Configurações
        cfg_frame = QFrame()
        cfg_frame.setFrameShape(QFrame.Shape.StyledPanel)
        cfg_layout = QHBoxLayout(cfg_frame)
        cfg_layout.setContentsMargins(10, 10, 10, 10)
        cfg_layout.setSpacing(14)

        cfg_layout.addWidget(QLabel("Cifra:"))
        self.combo_cipher = QComboBox()
        self.combo_cipher.addItem("Cifra de César", "caesar")
        self.combo_cipher.addItem("Cifra de Vigenère", "vigenere")
        self.combo_cipher.addItem("Código Morse", "morse")
        self.combo_cipher.addItem("Cifra Atbash", "atbash")
        self.combo_cipher.addItem("ROT13", "rot13")
        self.combo_cipher.addItem("ROT47", "rot47")
        self.combo_cipher.currentIndexChanged.connect(self._on_cipher_changed)
        cfg_layout.addWidget(self.combo_cipher)

        cfg_layout.addWidget(QLabel("Operação:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Cifrar (Encriptar)", False)
        self.combo_mode.addItem("Decifrar (Descriptografar)", True)
        self.combo_mode.currentIndexChanged.connect(self._on_process)
        cfg_layout.addWidget(self.combo_mode)

        # Parâmetro César (Shift)
        self.lbl_shift = QLabel("Deslocamento:")
        cfg_layout.addWidget(self.lbl_shift)
        self.spin_shift = QSpinBox()
        self.spin_shift.setRange(1, 25)
        self.spin_shift.setValue(3)
        self.spin_shift.valueChanged.connect(self._on_process)
        cfg_layout.addWidget(self.spin_shift)

        self.btn_brute_force = QPushButton("Brute-Force (25 Deslocamentos)")
        self.btn_brute_force.clicked.connect(self._open_brute_force_dialog)
        cfg_layout.addWidget(self.btn_brute_force)

        # Parâmetro Vigenère (Key)
        self.lbl_key = QLabel("Chave Secreta:")
        cfg_layout.addWidget(self.lbl_key)
        self.edit_key = QLineEdit("LEMON")
        self.edit_key.setMaximumWidth(140)
        self.edit_key.textChanged.connect(self._trigger_debounce)
        cfg_layout.addWidget(self.edit_key)

        cfg_layout.addStretch()
        layout.addWidget(cfg_frame)

        # Splitter com Texto Original e Texto Cifrado
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Esquerda: Entrada
        grp_in = QGroupBox("Texto de Entrada")
        v_in = QVBoxLayout(grp_in)
        self.text_in = QTextEdit()
        self.text_in.setPlaceholderText("Digite ou cole o texto aqui...")
        self.text_in.textChanged.connect(self._trigger_debounce)
        v_in.addWidget(self.text_in)

        bar_in = QHBoxLayout()
        btn_sample = QPushButton("Carregar Exemplo")
        btn_sample.clicked.connect(self._load_sample)
        bar_in.addWidget(btn_sample)

        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(self.text_in.clear)
        bar_in.addWidget(btn_clear)
        bar_in.addStretch()
        v_in.addLayout(bar_in)
        splitter.addWidget(grp_in)

        # Direita: Saída
        grp_out = QGroupBox("Resultado da Cifra")
        v_out = QVBoxLayout(grp_out)
        self.text_out = QTextEdit()
        self.text_out.setReadOnly(True)
        self.text_out.setStyleSheet("font-family: Consolas, monospace; font-size: 14px;")
        v_out.addWidget(self.text_out)

        bar_out = QHBoxLayout()
        btn_copy = QPushButton("Copiar Resultado")
        btn_copy.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_copy.clicked.connect(self._copy_result)
        bar_out.addWidget(btn_copy)

        btn_swap = QPushButton("Inverter (Usar Saída como Entrada)")
        btn_swap.clicked.connect(self._swap_texts)
        bar_out.addWidget(btn_swap)
        bar_out.addStretch()
        v_out.addLayout(bar_out)
        splitter.addWidget(grp_out)

        splitter.setSizes([450, 450])
        layout.addWidget(splitter, 1)

        self._on_cipher_changed()
        self._load_sample()
        return container

    def _trigger_debounce(self) -> None:
        self._debounce_timer.start()

    def _on_cipher_changed(self) -> None:
        cipher = self.combo_cipher.currentData()
        is_caesar = (cipher == "caesar")
        is_vigenere = (cipher == "vigenere")

        self.lbl_shift.setVisible(is_caesar)
        self.spin_shift.setVisible(is_caesar)
        self.btn_brute_force.setVisible(is_caesar)

        self.lbl_key.setVisible(is_vigenere)
        self.edit_key.setVisible(is_vigenere)

        self._on_process()

    def _load_sample(self) -> None:
        cipher = self.combo_cipher.currentData()
        if cipher == "caesar":
            self.text_in.setPlainText("A ligeira raposa marrom salta sobre o cão preguiçoso.")
        elif cipher == "vigenere":
            self.text_in.setPlainText("ATTACK AT DAWN")
        elif cipher == "morse":
            self.text_in.setPlainText("SOS HELLO WORLD")
        else:
            self.text_in.setPlainText("Segurança da Informação e Criptografia Clássica.")
        self._on_process()

    def _on_process(self) -> None:
        text = self.text_in.toPlainText()
        cipher = self.combo_cipher.currentData()
        decrypt = self.combo_mode.currentData()

        if not text:
            self.text_out.setPlainText("")
            return

        try:
            if cipher == "caesar":
                res = caesar_cipher(text, self.spin_shift.value(), decrypt=decrypt)
            elif cipher == "vigenere":
                res = vigenere_cipher(text, self.edit_key.text(), decrypt=decrypt)
            elif cipher == "morse":
                res = morse_to_text(text) if decrypt else text_to_morse(text)
            elif cipher == "atbash":
                res = atbash_cipher(text)
            elif cipher == "rot13":
                res = rot13_cipher(text)
            elif cipher == "rot47":
                res = rot47_cipher(text)
            else:
                res = text

            self.text_out.setPlainText(res)
        except Exception as e:
            self.text_out.setPlainText(f"Erro ao processar cifra: {e}")

    def _swap_texts(self) -> None:
        out_txt = self.text_out.toPlainText()
        if out_txt:
            # Alterna modo de cifrar para decifrar ou vice-versa
            curr = self.combo_mode.currentIndex()
            self.combo_mode.setCurrentIndex(1 if curr == 0 else 0)
            self.text_in.setPlainText(out_txt)
            self._on_process()

    def _copy_result(self) -> None:
        txt = self.text_out.toPlainText()
        if txt:
            cb = QApplication.clipboard()
            if cb:
                cb.setText(txt)

    def _open_brute_force_dialog(self) -> None:
        text = self.text_in.toPlainText()
        if not text.strip():
            return

        rotations = caesar_brute_force(text)
        dlg = QDialog()
        dlg.setWindowTitle("Brute-Force da Cifra de César (25 Deslocamentos)")
        dlg.resize(650, 450)
        v_dlg = QVBoxLayout(dlg)

        lbl = QLabel("Selecione o deslocamento que produz o texto inteligível em linguagem natural:")
        v_dlg.addWidget(lbl)

        tbl = QTableWidget(len(rotations), 2)
        tbl.setHorizontalHeaderLabels(["Deslocamento (Shift)", "Texto Decifrado Resultante"])
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        for row, (shift, decrypted) in enumerate(rotations):
            item_shift = QTableWidgetItem(f"Shift -{shift}")
            item_shift.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_dec = QTableWidgetItem(decrypted)
            tbl.setItem(row, 0, item_shift)
            tbl.setItem(row, 1, item_dec)

        def _on_select(row: int, col: int) -> None:
            self.spin_shift.setValue(row + 1)
            self.combo_mode.setCurrentIndex(1)  # Decifrar
            self._on_process()
            dlg.accept()

        tbl.cellDoubleClicked.connect(_on_select)
        v_dlg.addWidget(tbl)

        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(dlg.accept)
        v_dlg.addWidget(btn_close)

        dlg.exec()

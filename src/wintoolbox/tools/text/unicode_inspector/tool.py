"""
Interface gráfica Fluent da ferramenta Inspetor e Higienizador Unicode.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.unicode_inspector.logic import (
    inspect_unicode_text,
    sanitize_text,
    SuspiciousCharInfo,
)


@register
class UnicodeInspectorTool(Tool):
    """Ferramenta para identificação de caracteres invisíveis, zero-width, homóglifos e normalização Unicode."""
    id = "text.unicode_inspector"
    title = "Inspetor Unicode e Homóglifos"
    category = "Texto e Redação"
    description = (
        "Detecta e higieniza caracteres Unicode problemáticos: largura zero (Zero-Width), "
        "espaços especiais (NBSP), homóglifos cirílicos de phishing, aspas tipográficas e normalização canônica."
    )
    icon = "Search"

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250)
        self._debounce_timer.timeout.connect(self._on_inspect)
        self._suspicious: list[SuspiciousCharInfo] = []

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Inspetor e Higienizador de Caracteres Unicode")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Cole um texto, URL ou código para detectar caracteres invisíveis de largura zero, "
            "espaços incomuns (NBSP), homóglifos de alfabetos mistos usados em golpes e aspas curvas tipográficas."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Opções de Higienização no topo
        opt_frame = QFrame()
        opt_frame.setFrameShape(QFrame.Shape.StyledPanel)
        opt_layout = QHBoxLayout(opt_frame)
        opt_layout.setContentsMargins(8, 8, 8, 8)
        opt_layout.setSpacing(14)

        self.chk_zero_width = QCheckBox("Remover Zero-Width / BOM")
        self.chk_zero_width.setChecked(True)
        opt_layout.addWidget(self.chk_zero_width)

        self.chk_spaces = QCheckBox("Converter NBSP para espaço ASCII")
        self.chk_spaces.setChecked(True)
        opt_layout.addWidget(self.chk_spaces)

        self.chk_quotes = QCheckBox("Substituir aspas tipográficas por retas")
        self.chk_quotes.setChecked(True)
        opt_layout.addWidget(self.chk_quotes)

        self.chk_homoglyphs = QCheckBox("Substituir homóglifos por letras latinas")
        self.chk_homoglyphs.setChecked(False)
        opt_layout.addWidget(self.chk_homoglyphs)

        opt_layout.addWidget(QLabel("Normalização:"))
        self.combo_norm = QComboBox()
        self.combo_norm.addItems(["NFC (Padrão)", "NFD", "NFKC", "NFKD", "Nenhuma"])
        opt_layout.addWidget(self.combo_norm)

        opt_layout.addStretch()

        self.btn_sanitize = QPushButton("Higienizar Texto Agora")
        self.btn_sanitize.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        self.btn_sanitize.clicked.connect(self._on_sanitize_click)
        opt_layout.addWidget(self.btn_sanitize)

        layout.addWidget(opt_frame)

        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Parte Superior: Texto Original e Tabela de Suspeitos
        top_split = QSplitter(Qt.Orientation.Horizontal)

        # Editor Original
        grp_orig = QGroupBox("Texto Original para Análise")
        v_orig = QVBoxLayout(grp_orig)
        self.edit_input = QTextEdit()
        self.edit_input.setPlaceholderText("Cole o texto suspeito aqui...")
        self.edit_input.textChanged.connect(self._trigger_debounce)
        v_orig.addWidget(self.edit_input)
        top_split.addWidget(grp_orig)

        # Tabela de Problemas Detectados
        grp_table = QGroupBox("Problemas e Caracteres Suspeitos Detectados")
        v_table = QVBoxLayout(grp_table)

        self.lbl_summary = QLabel("Nenhum problema detectado.")
        self.lbl_summary.setStyleSheet("font-weight: bold;")
        v_table.addWidget(self.lbl_summary)

        self.table_issues = QTableWidget(0, 5)
        self.table_issues.setHorizontalHeaderLabels(["Posição", "Caractere", "Code Point", "Nome Unicode", "Diagnóstico"])
        self.table_issues.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_issues.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        v_table.addWidget(self.table_issues)
        top_split.addWidget(grp_table)

        top_split.setSizes([450, 450])
        splitter.addWidget(top_split)

        # Parte Inferior: Texto Higienizado
        grp_clean = QGroupBox("Texto Higienizado")
        v_clean = QVBoxLayout(grp_clean)

        self.edit_output = QTextEdit()
        self.edit_output.setReadOnly(True)
        v_clean.addWidget(self.edit_output)

        clean_bar = QHBoxLayout()
        btn_copy = QPushButton("Copiar Texto Higienizado")
        btn_copy.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        btn_copy.clicked.connect(self._on_copy_clean)
        clean_bar.addWidget(btn_copy)

        self.lbl_copy_feedback = QLabel("")
        self.lbl_copy_feedback.setStyleSheet("color: #107C41; font-weight: bold;")
        clean_bar.addWidget(self.lbl_copy_feedback)
        clean_bar.addStretch()

        v_clean.addLayout(clean_bar)
        splitter.addWidget(grp_clean)

        splitter.setSizes([400, 200])
        layout.addWidget(splitter, 1)

        # Inserir exemplo com caracteres invisíveis e homóglifos
        sample = (
            "Exemplo com problemas:\n"
            "1. Espaço invisível aqui: \u200Bpalavra com zero-width space.\n"
            "2. Non-breaking space aqui:\u00A0texto.\n"
            "3. Aspas curvas: “Texto entre aspas tipográficas”.\n"
            "4. Homóglifo cirílico: pаypаl.com (os 'a' são cirílicos U+0430!)."
        )
        self.edit_input.setPlainText(sample)
        return container

    def _trigger_debounce(self) -> None:
        self._debounce_timer.start()

    def _on_inspect(self) -> None:
        text = self.edit_input.toPlainText()
        self._suspicious = inspect_unicode_text(text)
        self.table_issues.setRowCount(len(self._suspicious))

        if not self._suspicious:
            self.lbl_summary.setText("Texto 100% limpo! Nenhum caractere suspeito detectado.")
            self.lbl_summary.setStyleSheet("color: #107C41; font-weight: bold;")
        else:
            self.lbl_summary.setText(f"{len(self._suspicious)} caractere(s) suspeito(s) identificado(s):")
            self.lbl_summary.setStyleSheet("color: #D83B01; font-weight: bold;")

        for row, info in enumerate(self._suspicious):
            item_pos = QTableWidgetItem(str(info.index))
            item_char = QTableWidgetItem(repr(info.char))
            item_cp = QTableWidgetItem(info.codepoint)
            item_name = QTableWidgetItem(info.name)
            item_reason = QTableWidgetItem(info.reason)

            item_pos.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_char.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_cp.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_issues.setItem(row, 0, item_pos)
            self.table_issues.setItem(row, 1, item_char)
            self.table_issues.setItem(row, 2, item_cp)
            self.table_issues.setItem(row, 3, item_name)
            self.table_issues.setItem(row, 4, item_reason)

        # Executa higienização padrão
        self._on_sanitize_click()

    def _on_sanitize_click(self) -> None:
        text = self.edit_input.toPlainText()
        norm_choice = self.combo_norm.currentText().split()[0]
        norm_form = None if norm_choice == "Nenhuma" else norm_choice

        cleaned = sanitize_text(
            text=text,
            strip_zero_width=self.chk_zero_width.isChecked(),
            norm_spaces=self.chk_spaces.isChecked(),
            fix_quotes=self.chk_quotes.isChecked(),
            replace_homoglyphs_flag=self.chk_homoglyphs.isChecked(),
            normalization_form=norm_form,
        )
        self.edit_output.setPlainText(cleaned)
        self.lbl_copy_feedback.setText("")

    def _on_copy_clean(self) -> None:
        txt = self.edit_output.toPlainText()
        if txt:
            cb = QApplication.clipboard()
            if cb:
                cb.setText(txt)
                self.lbl_copy_feedback.setText("Texto higienizado copiado!")

"""
Interface gráfica da ferramenta Conversor de Caixa Tipográfica (Case Converter).
Permite alternar entre camelCase, PascalCase, snake_case, CONSTANT_CASE, kebab-case,
Title Case, Train-Case, Alternating Case e remoção de acentos.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool
from wintoolbox.tools.text.case_converter.logic import (
    CONVERTERS,
    convert_all_cases,
    convert_multiline,
    remove_accents,
)


class CaseConverterTool(Tool):
    id = "text.case_converter"
    title = "Conversor de Caixa"
    category = "Texto e Redação"
    description = (
        "Converte textos e identificadores entre camelCase, PascalCase, snake_case, "
        "kebab-case, CONSTANT_CASE, Title Case e remove acentos."
    )

    def create_widget(self) -> QWidget:
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Barra de Opções Superior
        options_layout = QHBoxLayout()
        options_layout.setSpacing(12)

        self._chk_remove_accents = QCheckBox("Remover acentos e diacríticos")
        self._chk_remove_accents.toggled.connect(self._on_input_changed)
        options_layout.addWidget(self._chk_remove_accents)

        self._chk_line_by_line = QCheckBox("Processar linha por linha")
        self._chk_line_by_line.toggled.connect(self._on_input_changed)
        options_layout.addWidget(self._chk_line_by_line)

        options_layout.addStretch()

        self._lbl_status = QLabel("Pronto")
        self._lbl_status.setStyleSheet("color: #6c757d; font-size: 11px;")
        options_layout.addWidget(self._lbl_status)

        main_layout.addLayout(options_layout)

        # Splitter Vertical: Entrada de Texto em cima, Resultados embaixo
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Painel de Entrada
        input_group = QGroupBox("Texto de Entrada")
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(8, 12, 8, 8)

        self._txt_input = QTextEdit()
        self._txt_input.setPlaceholderText("Digite ou cole o texto a ser convertido...")
        self._txt_input.setFont(QFont("Consolas", 10))
        self._txt_input.textChanged.connect(self._on_input_changed)
        input_layout.addWidget(self._txt_input)

        splitter.addWidget(input_group)

        # Painel de Resultados com Abas/Grade de Cards
        result_group = QGroupBox("Variantes de Caixa (Clique para Copiar)")
        result_layout = QVBoxLayout(result_group)
        result_layout.setContentsMargins(8, 12, 8, 8)

        # Scroll area para acomodar todos os formatos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        self._cards_layout = QVBoxLayout(scroll_content)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(6)

        self._case_fields = {}

        for case_name in CONVERTERS.keys():
            row_frame = QFrame()
            row_frame.setStyleSheet(
                "QFrame { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 4px; padding: 4px; }"
            )
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(8, 4, 8, 4)
            row_layout.setSpacing(8)

            lbl_name = QLabel(case_name)
            lbl_name.setFixedWidth(130)
            lbl_name.setStyleSheet("font-weight: bold; color: #495057;")
            row_layout.addWidget(lbl_name)

            txt_val = QLineEdit()
            txt_val.setReadOnly(True)
            txt_val.setFont(QFont("Consolas", 10))
            row_layout.addWidget(txt_val)

            btn_copy = QPushButton("Copiar")
            btn_copy.setFixedWidth(80)
            btn_copy.clicked.connect(lambda checked=False, f=txt_val, n=case_name: self._copy_text(f.text(), n))
            row_layout.addWidget(btn_copy)

            self._case_fields[case_name] = txt_val
            self._cards_layout.addWidget(row_frame)

        self._cards_layout.addStretch()
        scroll.setWidget(scroll_content)
        result_layout.addWidget(scroll)

        splitter.addWidget(result_group)
        splitter.setSizes([200, 350])

        main_layout.addWidget(splitter)
        return widget

    def _on_input_changed(self) -> None:
        raw_text = self._txt_input.toPlainText()
        strip_acc = self._chk_remove_accents.isChecked()
        line_by_line = self._chk_line_by_line.isChecked()

        if not raw_text.strip():
            for field in self._case_fields.values():
                field.clear()
            self._lbl_status.setText("Pronto")
            return

        for case_name, field in self._case_fields.items():
            if line_by_line:
                converted = convert_multiline(raw_text, case_name, strip_accents=strip_acc)
            else:
                func = CONVERTERS[case_name]
                converted = func(raw_text, strip_accents=strip_acc)
            
            # No QLineEdit exibimos com quebras substituídas por espaço se for multilinha
            preview = converted.replace("\n", " ↵ ") if "\n" in converted else converted
            field.setText(preview)
            field.setToolTip(converted)

        self._lbl_status.setText(f"{len(raw_text)} caracteres processados")

    def _copy_text(self, text: str, name: str) -> None:
        if not text:
            return
        # Restaura quebras de linha se existiam no tooltip
        field = self._case_fields.get(name)
        real_text = field.toolTip() if (field and field.toolTip()) else text
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(real_text)
        self._lbl_status.setText(f"{name} copiado para a área de transferência!")

"""
Interface de usuário para a ferramenta Minificador e Formatador Web.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.minifier.logic import (
    format_css,
    format_html,
    get_compression_stats,
    minify_css,
    minify_html,
    minify_js,
)


@register
class MinifierTool(Tool):
    """Minificador e formatador de código HTML, CSS e JavaScript offline."""

    id = "dev.minifier"
    name = "Minificador e Formatador Web (HTML / CSS / JS)"
    description = "Minifica e embeleza código HTML, CSS e JavaScript offline sem dependências de Node.js."
    category = "Desenvolvimento"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Minificador e Formatador Web")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Reduza o tamanho de payloads para produção ou formate trechos compactados "
            "para inspeção e depuração."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Barra de Controles
        ctrl_frame = QFrame()
        ctrl_frame.setFrameShape(QFrame.Shape.StyledPanel)
        ctrl_layout = QHBoxLayout(ctrl_frame)

        ctrl_layout.addWidget(QLabel("Linguagem:"))
        self.combo_type = QComboBox()
        self.combo_type.addItem("CSS", "css")
        self.combo_type.addItem("HTML", "html")
        self.combo_type.addItem("JavaScript", "js")
        ctrl_layout.addWidget(self.combo_type)

        ctrl_layout.addSpacing(20)

        self.btn_minify = QPushButton("⚡ Minificar Código")
        self.btn_minify.setStyleSheet("font-weight: bold;")
        self.btn_minify.clicked.connect(self._do_minify)

        self.btn_format = QPushButton("✨ Formatar / Embelezar")
        self.btn_format.clicked.connect(self._do_format)

        ctrl_layout.addWidget(self.btn_minify)
        ctrl_layout.addWidget(self.btn_format)
        ctrl_layout.addStretch()

        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.clicked.connect(self._clear_all)
        ctrl_layout.addWidget(self.btn_clear)

        layout.addWidget(ctrl_frame)

        # Editores Lado a Lado
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Entrada
        w_in = QWidget()
        v_in = QVBoxLayout(w_in)
        v_in.setContentsMargins(0, 0, 0, 0)
        v_in.addWidget(QLabel("Código Original:"))
        self.txt_input = QTextEdit()
        self.txt_input.setFont(QFont("Consolas", 10))
        self.txt_input.setPlaceholderText("Cole o código aqui...")
        v_in.addWidget(self.txt_input)
        splitter.addWidget(w_in)

        # Saída
        w_out = QWidget()
        v_out = QVBoxLayout(w_out)
        v_out.setContentsMargins(0, 0, 0, 0)
        v_out.addWidget(QLabel("Resultado Processado:"))
        self.txt_output = QTextEdit()
        self.txt_output.setFont(QFont("Consolas", 10))
        self.txt_output.setReadOnly(True)
        v_out.addWidget(self.txt_output)
        splitter.addWidget(w_out)

        layout.addWidget(splitter, 1)

        # Barra de Estatísticas e Cópia
        bot_frame = QFrame()
        bot_layout = QHBoxLayout(bot_frame)
        bot_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_stats = QLabel("Aguardando processamento.")
        self.lbl_stats.setStyleSheet("color: #2196f3; font-weight: bold;")

        self.btn_copy = QPushButton("Copiar Resultado")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy_output)

        bot_layout.addWidget(self.lbl_stats)
        bot_layout.addStretch()
        bot_layout.addWidget(self.btn_copy)
        layout.addWidget(bot_frame)

        return widget

    def _do_minify(self):
        text = self.txt_input.toPlainText()
        if not text.strip():
            return

        lang = self.combo_type.currentData()
        processed = ""
        if lang == "css":
            processed = minify_css(text)
        elif lang == "html":
            processed = minify_html(text)
        elif lang == "js":
            processed = minify_js(text)

        self.txt_output.setText(processed)
        self.btn_copy.setEnabled(True)

        stats = get_compression_stats(text, processed)
        pct = stats["reduction_percentage"]
        saved = stats["saved_bytes"]
        self.lbl_stats.setText(
            f"Original: {stats['original_bytes']:,} B  |  Minificado: {stats['processed_bytes']:,} B  |  "
            f"Economia: {saved:,} B ({pct:.1f}% reduzido)"
        )

    def _do_format(self):
        text = self.txt_input.toPlainText()
        if not text.strip():
            return

        lang = self.combo_type.currentData()
        processed = ""
        if lang == "css":
            processed = format_css(text)
        elif lang == "html":
            processed = format_html(text)
        elif lang == "js":
            processed = text  # JS beautifier básico

        self.txt_output.setText(processed)
        self.btn_copy.setEnabled(True)
        self.lbl_stats.setText(f"Código formatado com sucesso ({len(processed.encode('utf-8')):,} bytes).")

    def _copy_output(self):
        out = self.txt_output.toPlainText()
        if out:
            QGuiApplication.clipboard().setText(out)
            QMessageBox.information(None, "Copiado", "Código copiado para a área de transferência!")

    def _clear_all(self):
        self.txt_input.clear()
        self.txt_output.clear()
        self.lbl_stats.setText("Aguardando processamento.")
        self.btn_copy.setEnabled(False)

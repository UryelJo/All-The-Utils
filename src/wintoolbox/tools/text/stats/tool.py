"""
Interface gráfica Fluent da ferramenta Estatísticas Textuais e Legibilidade.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.stats.logic import (
    analyze_text,
    format_duration,
    TextStatsResult,
)


@register
class TextStatsTool(Tool):
    """Ferramenta para análise quantitativa e legibilidade de textos."""
    id = "text.stats"
    name = "Estatísticas e Legibilidade"
    title = "Estatísticas e Legibilidade"
    category = "Texto e Redação"
    description = "Contador avançado de caracteres, palavras, linhas, tempos de leitura e métricas Flesch-Brás."
    icon = "DocumentText"

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer: QTimer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250)
        self._debounce_timer.timeout.connect(self._on_analyze)

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Analisador Estatístico Textual e Legibilidade")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Digite ou cole o texto abaixo para obter métricas detalhadas de caracteres, "
            "palavras, densidade vocabular, tempo de fala e índice de legibilidade Flesch-Brás."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Opções de Configuração no topo
        opts_box = QFrame()
        opts_box.setFrameShape(QFrame.Shape.StyledPanel)
        opts_layout = QHBoxLayout(opts_box)
        opts_layout.setContentsMargins(8, 8, 8, 8)
        opts_layout.setSpacing(16)

        opts_layout.addWidget(QLabel("Leitura (PPM):"))
        self.spin_reading_wpm = QSpinBox()
        self.spin_reading_wpm.setRange(50, 600)
        self.spin_reading_wpm.setValue(200)
        self.spin_reading_wpm.valueChanged.connect(self._trigger_debounce)
        opts_layout.addWidget(self.spin_reading_wpm)

        opts_layout.addWidget(QLabel("Fala (PPM):"))
        self.spin_speaking_wpm = QSpinBox()
        self.spin_speaking_wpm.setRange(50, 400)
        self.spin_speaking_wpm.setValue(130)
        self.spin_speaking_wpm.valueChanged.connect(self._trigger_debounce)
        opts_layout.addWidget(self.spin_speaking_wpm)

        self.chk_stopwords = QCheckBox("Ignorar palavras comuns (Stopwords)")
        self.chk_stopwords.setChecked(True)
        self.chk_stopwords.toggled.connect(self._trigger_debounce)
        opts_layout.addWidget(self.chk_stopwords)

        opts_layout.addStretch()

        self.btn_copy_report = QPushButton("Copiar Relatório")
        self.btn_copy_report.clicked.connect(self._on_copy_report)
        opts_layout.addWidget(self.btn_copy_report)

        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.clicked.connect(self._on_clear)
        opts_layout.addWidget(self.btn_clear)

        layout.addWidget(opts_box)

        # Splitter principal: Esquerda (Texto de Entrada) | Direita (Métricas)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Editor de Texto
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        lbl_input = QLabel("Texto de Entrada:")
        lbl_input.setStyleSheet("font-weight: 600;")
        left_layout.addWidget(lbl_input)

        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Cole ou digite o texto aqui para análise em tempo real...")
        self.text_editor.textChanged.connect(self._trigger_debounce)
        left_layout.addWidget(self.text_editor)

        splitter.addWidget(left_widget)

        # Painel de Métricas (Scrollable)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(6, 0, 6, 6)
        right_layout.setSpacing(12)

        # 1. Grupo de Contagens Básicas
        grp_counts = QGroupBox("Contagens Básicas")
        grid_counts = QGridLayout(grp_counts)
        grid_counts.setSpacing(8)

        self.lbl_chars = self._make_stat_badge("Caracteres (totais):", "0")
        self.lbl_chars_no_spaces = self._make_stat_badge("Caracteres (sem espaços):", "0")
        self.lbl_words = self._make_stat_badge("Palavras:", "0")
        self.lbl_lines = self._make_stat_badge("Linhas:", "0 (0 úteis)")
        self.lbl_sentences = self._make_stat_badge("Frases:", "0")
        self.lbl_paragraphs = self._make_stat_badge("Parágrafos:", "0")

        grid_counts.addWidget(QLabel("Caracteres:"), 0, 0)
        grid_counts.addWidget(self.lbl_chars, 0, 1)
        grid_counts.addWidget(QLabel("Sem Espaços:"), 0, 2)
        grid_counts.addWidget(self.lbl_chars_no_spaces, 0, 3)

        grid_counts.addWidget(QLabel("Palavras:"), 1, 0)
        grid_counts.addWidget(self.lbl_words, 1, 1)
        grid_counts.addWidget(QLabel("Linhas:"), 1, 2)
        grid_counts.addWidget(self.lbl_lines, 1, 3)

        grid_counts.addWidget(QLabel("Frases:"), 2, 0)
        grid_counts.addWidget(self.lbl_sentences, 2, 1)
        grid_counts.addWidget(QLabel("Parágrafos:"), 2, 2)
        grid_counts.addWidget(self.lbl_paragraphs, 2, 3)

        right_layout.addWidget(grp_counts)

        # 2. Grupo de Tempos e Médias
        grp_time = QGroupBox("Tempos Estimados e Médias")
        grid_time = QGridLayout(grp_time)
        grid_time.setSpacing(8)

        self.lbl_read_time = self._make_stat_badge("Tempo de Leitura:", "0 s")
        self.lbl_speak_time = self._make_stat_badge("Tempo de Fala:", "0 s")
        self.lbl_avg_word = self._make_stat_badge("Méd. Caract./Palavra:", "0.0")
        self.lbl_avg_sentence = self._make_stat_badge("Méd. Palavras/Frase:", "0.0")

        grid_time.addWidget(QLabel("Leitura:"), 0, 0)
        grid_time.addWidget(self.lbl_read_time, 0, 1)
        grid_time.addWidget(QLabel("Fala (Discurso):"), 0, 2)
        grid_time.addWidget(self.lbl_speak_time, 0, 3)

        grid_time.addWidget(QLabel("Letras / Palavra:"), 1, 0)
        grid_time.addWidget(self.lbl_avg_word, 1, 1)
        grid_time.addWidget(QLabel("Palavras / Frase:"), 1, 2)
        grid_time.addWidget(self.lbl_avg_sentence, 1, 3)

        right_layout.addWidget(grp_time)

        # 3. Legibilidade Flesch-Brás
        grp_flesch = QGroupBox("Índice de Legibilidade Flesch-Brás")
        vbox_flesch = QVBoxLayout(grp_flesch)
        vbox_flesch.setSpacing(6)

        self.lbl_flesch_score = QLabel("Pontuação: 100.0 (Flesch-Brás)")
        self.lbl_flesch_score.setStyleSheet("font-size: 15px; font-weight: bold; color: #0078D4;")
        vbox_flesch.addWidget(self.lbl_flesch_score)

        self.lbl_flesch_desc = QLabel("Classificação: Muito Fácil (Ensino Fundamental 1)")
        self.lbl_flesch_desc.setStyleSheet("font-weight: 500;")
        vbox_flesch.addWidget(self.lbl_flesch_desc)

        right_layout.addWidget(grp_flesch)

        # 4. Palavras Mais Frequentes
        grp_top_words = QGroupBox("Palavras Mais Frequentes")
        vbox_top = QVBoxLayout(grp_top_words)

        self.table_top_words = QTableWidget(0, 2)
        self.table_top_words.setHorizontalHeaderLabels(["Palavra", "Ocorrências"])
        self.table_top_words.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_top_words.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_top_words.setMaximumHeight(160)
        vbox_top.addWidget(self.table_top_words)

        right_layout.addWidget(grp_top_words)
        right_layout.addStretch()

        right_scroll.setWidget(right_content)
        splitter.addWidget(right_scroll)
        splitter.setSizes([450, 450])

        layout.addWidget(splitter, 1)

        self._last_result: TextStatsResult | None = None
        self._on_analyze()
        return container

    def _make_stat_badge(self, label: str, default: str) -> QLabel:
        lbl = QLabel(default)
        lbl.setStyleSheet("font-weight: bold;")
        return lbl

    def _trigger_debounce(self) -> None:
        self._debounce_timer.start()

    def _on_clear(self) -> None:
        self.text_editor.clear()
        self._on_analyze()

    def _on_analyze(self) -> None:
        text = self.text_editor.toPlainText()
        res = analyze_text(
            text=text,
            words_per_minute_reading=self.spin_reading_wpm.value(),
            words_per_minute_speaking=self.spin_speaking_wpm.value(),
            top_n_words=10,
            ignore_stopwords=self.chk_stopwords.isChecked(),
        )
        self._last_result = res

        # Atualizar labels
        self.lbl_chars.setText(str(res.char_count))
        self.lbl_chars_no_spaces.setText(str(res.char_count_no_spaces))
        self.lbl_words.setText(str(res.word_count))
        self.lbl_lines.setText(f"{res.line_count} ({res.non_empty_lines} úteis)")
        self.lbl_sentences.setText(str(res.sentence_count))
        self.lbl_paragraphs.setText(str(res.paragraph_count))

        self.lbl_read_time.setText(format_duration(res.reading_time_seconds))
        self.lbl_speak_time.setText(format_duration(res.speaking_time_seconds))
        self.lbl_avg_word.setText(str(res.avg_word_length))
        self.lbl_avg_sentence.setText(str(res.avg_sentence_length))

        self.lbl_flesch_score.setText(f"Flesch-Brás: {res.flesch_bras} | Flesch Original: {res.flesch_reading_ease}")
        self.lbl_flesch_desc.setText(f"Classificação: {res.flesch_classification}")

        # Tabela de Top Words
        self.table_top_words.setRowCount(len(res.top_words))
        for row, (word, count) in enumerate(res.top_words):
            item_word = QTableWidgetItem(word)
            item_count = QTableWidgetItem(str(count))
            item_count.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_top_words.setItem(row, 0, item_word)
            self.table_top_words.setItem(row, 1, item_count)

    def _on_copy_report(self) -> None:
        if not self._last_result:
            return
        res = self._last_result
        report = (
            "--- RELATÓRIO ESTATÍSTICO DE TEXTO ---\n"
            f"Caracteres: {res.char_count} (sem espaços: {res.char_count_no_spaces})\n"
            f"Palavras: {res.word_count}\n"
            f"Frases: {res.sentence_count}\n"
            f"Linhas: {res.line_count} (não-vazias: {res.non_empty_lines})\n"
            f"Parágrafos: {res.paragraph_count}\n"
            f"Sílabas estimadas: {res.syllable_count}\n"
            f"Média letras/palavra: {res.avg_word_length}\n"
            f"Média palavras/frase: {res.avg_sentence_length}\n"
            f"Tempo estimado de leitura: {format_duration(res.reading_time_seconds)}\n"
            f"Tempo estimado de fala: {format_duration(res.speaking_time_seconds)}\n"
            f"Índice Flesch-Brás: {res.flesch_bras} ({res.flesch_classification})\n"
            f"Índice Flesch Original: {res.flesch_reading_ease}\n"
            "\nPalavras Mais Frequentes:\n"
            + "\n".join(f"- {w}: {c}" for w, c in res.top_words)
        )
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(report)

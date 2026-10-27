"""
Interface gráfica Fluent para o Conversor Universal de Configurações (.env, .ini, .properties, TOML, YAML, JSON).
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.data.config_convert.logic import (
    parse_config_content,
    serialize_config_content,
)


@register
class ConfigConvertTool(Tool):
    id = "data.config_convert"
    name = "Conversor de Configurações"
    description = "Conversor universal entre arquivos de configuração: .env, .ini, .properties, TOML, YAML e JSON."
    category = "data"
    icon = "Settings"
    tags = ["config", "env", "ini", "properties", "toml", "yaml", "json", "converter"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra Superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        top_bar.addWidget(QLabel("Formato de Origem:"))
        self.combo_source = QComboBox()
        self._formats = [
            ("Variáveis de Ambiente (.env)", "env"),
            ("Arquivo INI (.ini)", "ini"),
            ("Java Properties (.properties)", "properties"),
            ("TOML (.toml)", "toml"),
            ("YAML (.yaml / .yml)", "yaml"),
            ("JSON (.json)", "json"),
        ]
        for label, val in self._formats:
            self.combo_source.addItem(label, val)
        self.combo_source.setCurrentIndex(0)  # env
        top_bar.addWidget(self.combo_source)

        top_bar.addWidget(QLabel("Formato de Destino:"))
        self.combo_target = QComboBox()
        for label, val in self._formats:
            self.combo_target.addItem(label, val)
        self.combo_target.setCurrentIndex(5)  # json
        top_bar.addWidget(self.combo_target)

        self.chk_flatten = QCheckBox("Achatar Chaves (Dot Notation)")
        top_bar.addWidget(self.chk_flatten)

        btn_sample = QPushButton("Carregar Exemplo")
        btn_convert = QPushButton("Converter")
        btn_convert.setStyleSheet("font-weight: bold;")

        top_bar.addWidget(btn_sample)
        top_bar.addWidget(btn_convert)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        self.lbl_status = QLabel("Cole a configuração original à esquerda e selecione o formato desejado.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Splitter Horizontal: Entrada vs Saída
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Esquerda
        w_left = QWidget()
        lay_left = QVBoxLayout(w_left)
        lay_left.setContentsMargins(0, 0, 0, 0)
        lay_left.setSpacing(6)
        lay_left.addWidget(QLabel("Conteúdo Original:"))
        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText("Cole o arquivo de configuração aqui...")
        lay_left.addWidget(self.text_input)
        splitter.addWidget(w_left)

        # Direita
        w_right = QWidget()
        lay_right = QVBoxLayout(w_right)
        lay_right.setContentsMargins(0, 0, 0, 0)
        lay_right.setSpacing(6)

        header_right = QHBoxLayout()
        header_right.addWidget(QLabel("Configuração Convertida:"))
        header_right.addStretch()
        btn_copy = QPushButton("Copiar Resultado")
        header_right.addWidget(btn_copy)
        lay_right.addLayout(header_right)

        self.text_output = QPlainTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setPlaceholderText("A saída convertida aparecerá aqui...")
        lay_right.addWidget(self.text_output)
        splitter.addWidget(w_right)

        splitter.setSizes([480, 520])
        layout.addWidget(splitter, 1)

        # Conexões
        btn_sample.clicked.connect(self._on_load_sample)
        btn_convert.clicked.connect(self._on_convert)
        btn_copy.clicked.connect(self._on_copy)

        return container

    def _on_load_sample(self) -> None:
        sample_env = (
            "# Configurações da Aplicação\n"
            "APP_NAME=WinToolbox\n"
            "APP_PORT=8080\n"
            "APP_DEBUG=true\n"
            "DATABASE_HOST=localhost\n"
            "DATABASE_PORT=5432\n"
            "DATABASE_USER=postgres\n"
            "DATABASE_PASSWORD=secreta\n"
        )
        self.combo_source.setCurrentIndex(0)  # env
        self.combo_target.setCurrentIndex(5)  # json
        self.text_input.setPlainText(sample_env)
        self._on_convert()

    def _on_convert(self) -> None:
        raw_text = self.text_input.toPlainText().strip()
        if not raw_text:
            self.lbl_status.setText("Entrada vazia.")
            return

        src_fmt = self.combo_source.currentData()
        dst_fmt = self.combo_target.currentData()
        flatten = self.chk_flatten.isChecked()

        ok_parse, data, err_parse = parse_config_content(raw_text, src_fmt)
        if not ok_parse:
            QMessageBox.warning(None, "Erro de Leitura", f"Falha ao ler formato {src_fmt.upper()}:\n{err_parse}")
            return

        ok_ser, output_str, err_ser = serialize_config_content(data, dst_fmt, flatten=flatten)
        if not ok_ser:
            QMessageBox.critical(None, "Erro de Conversão", f"Falha ao converter para {dst_fmt.upper()}:\n{err_ser}")
            return

        self.text_output.setPlainText(output_str)
        self.lbl_status.setText(f"✅ Conversão de {src_fmt.upper()} para {dst_fmt.upper()} realizada com sucesso!")

    def _on_copy(self) -> None:
        txt = self.text_output.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)
            self.lbl_status.setText("Configuração copiada para a área de transferência!")

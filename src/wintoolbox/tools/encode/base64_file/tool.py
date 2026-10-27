"""
Ferramenta: Conversor de Arquivo para Base64 e Data URI.
Permite transformar imagens, documentos e binários em Base64/Data URI e salvar Base64 como arquivo físico.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.encode.base64_file.logic import (
    base64_to_file,
    detect_mime_type,
    file_to_base64,
    parse_data_uri,
)


@register
class Base64FileTool(Tool):
    id = "encode.base64_file"
    name = "Conversor de Arquivos em Base64"
    category = "Codificação e Hash"
    description = "Converte arquivos para Base64 e Data URI e restaura arquivos físicos a partir de Base64"
    keywords = ["base64", "data uri", "imagem", "arquivo", "b64", "encode", "decode", "binario"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return Base64FileView(self, parent)


class Base64FileView(QWidget):
    def __init__(self, tool: Base64FileTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
        self._selected_input_file: Optional[Path] = None
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Tabs
        self._tabs = QTabWidget()
        self._tab_file_to_b64 = self._build_file_to_b64_tab()
        self._tab_b64_to_file = self._build_b64_to_file_tab()

        self._tabs.addTab(self._tab_file_to_b64, "Arquivo para Base64")
        self._tabs.addTab(self._tab_b64_to_file, "Base64 para Arquivo")
        root_layout.addWidget(self._tabs)

    def _build_file_to_b64_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        # Seleção de arquivo
        sel_box = QHBoxLayout()
        self._txt_file_path = QLineEdit()
        self._txt_file_path.setPlaceholderText("Selecione um arquivo do seu computador...")
        self._txt_file_path.setReadOnly(True)
        sel_box.addWidget(self._txt_file_path)

        btn_browse = QPushButton("Selecionar Arquivo...")
        btn_browse.clicked.connect(self._on_browse_input_file)
        sel_box.addWidget(btn_browse)
        layout.addLayout(sel_box)

        # Opções
        opts_layout = QHBoxLayout()
        self._chk_data_uri = QCheckBox("Gerar como Data URI (data:<mime>;base64,...)")
        self._chk_data_uri.setChecked(True)
        self._chk_data_uri.toggled.connect(self._convert_selected_file)
        opts_layout.addWidget(self._chk_data_uri)

        self._lbl_file_info = QLabel("")
        self._lbl_file_info.setStyleSheet("color: #4b5563; font-size: 11px;")
        opts_layout.addWidget(self._lbl_file_info)
        opts_layout.addStretch()
        layout.addLayout(opts_layout)

        # Saída Base64
        self._txt_b64_output = QPlainTextEdit()
        self._txt_b64_output.setReadOnly(True)
        self._txt_b64_output.setFont(QFont("Consolas", 9))
        self._txt_b64_output.setPlaceholderText("O conteúdo codificado em Base64 aparecerá aqui...")
        layout.addWidget(self._txt_b64_output)

        # Botões de Ação
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("Copiar Base64")
        btn_copy.clicked.connect(self._copy_b64_output)
        btn_layout.addWidget(btn_copy)

        btn_copy_img = QPushButton("Copiar Tag <img> HTML")
        btn_copy_img.clicked.connect(self._copy_html_img_tag)
        btn_layout.addWidget(btn_copy_img)

        btn_copy_css = QPushButton("Copiar CSS background-image")
        btn_copy_css.clicked.connect(self._copy_css_background)
        btn_layout.addWidget(btn_copy_css)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _build_b64_to_file_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        lbl_instruct = QLabel("Cole abaixo o texto Base64 ou Data URI para reconstruir o arquivo:")
        lbl_instruct.setStyleSheet("color: #4b5563;")
        layout.addWidget(lbl_instruct)

        self._txt_b64_input = QPlainTextEdit()
        self._txt_b64_input.setFont(QFont("Consolas", 9))
        self._txt_b64_input.setPlaceholderText("data:image/png;base64,iVBORw0KGgoAAA...")
        layout.addWidget(self._txt_b64_input)

        act_layout = QHBoxLayout()
        btn_save = QPushButton("Salvar Como Arquivo...")
        btn_save.clicked.connect(self._on_save_b64_as_file)
        act_layout.addWidget(btn_save)

        self._lbl_decode_status = QLabel("")
        self._lbl_decode_status.setStyleSheet("color: #059669; font-weight: bold;")
        act_layout.addWidget(self._lbl_decode_status)
        act_layout.addStretch()
        layout.addLayout(act_layout)

        return widget

    def _on_browse_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo para Codificar")
        if not file_path:
            return
        self._selected_input_file = Path(file_path)
        self._txt_file_path.setText(str(self._selected_input_file))
        self._convert_selected_file()

    def _convert_selected_file(self):
        if not self._selected_input_file or not self._selected_input_file.is_file():
            return
        
        include_uri = self._chk_data_uri.isChecked()
        try:
            res = file_to_base64(self._selected_input_file, include_data_uri=include_uri)
            content = res["data_uri"] if include_uri else res["base64_str"]
            self._txt_b64_output.setPlainText(content)
            size_kb = res["file_size"] / 1024
            self._lbl_file_info.setText(
                f"Tamanho: {size_kb:.1f} KB | MIME: {res['mime_type']} | Caracteres B64: {res['char_count']}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro de Conversão", f"Falha ao processar arquivo: {exc}")

    def _copy_b64_output(self):
        txt = self._txt_b64_output.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)

    def _copy_html_img_tag(self):
        txt = self._txt_b64_output.toPlainText()
        if not txt:
            return
        uri = txt if txt.startswith("data:") else f"data:image/png;base64,{txt}"
        tag = f'<img src="{uri}" alt="Imagem Base64" />'
        QGuiApplication.clipboard().setText(tag)

    def _copy_css_background(self):
        txt = self._txt_b64_output.toPlainText()
        if not txt:
            return
        uri = txt if txt.startswith("data:") else f"data:image/png;base64,{txt}"
        css = f'background-image: url("{uri}");'
        QGuiApplication.clipboard().setText(css)

    def _on_save_b64_as_file(self):
        raw_b64 = self._txt_b64_input.toPlainText().strip()
        if not raw_b64:
            QMessageBox.warning(self, "Aviso", "Por favor, insira o texto Base64.")
            return

        try:
            # Testa o parse preliminar para sugerir extensão
            _, detected_mime = parse_data_uri(raw_b64)
            ext_filter = "Todos os Arquivos (*.*)"
            default_name = "arquivo_restaurado"
            if detected_mime == "image/png":
                default_name += ".png"
            elif detected_mime == "image/jpeg":
                default_name += ".jpg"
            elif detected_mime == "application/pdf":
                default_name += ".pdf"

            out_path, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo Restaurado", default_name, ext_filter)
            if not out_path:
                return

            res = base64_to_file(raw_b64, Path(out_path))
            self._lbl_decode_status.setText(f"Salvo com sucesso ({res['file_size']} bytes)!")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao Restaurar", f"Não foi possível converter Base64: {exc}")

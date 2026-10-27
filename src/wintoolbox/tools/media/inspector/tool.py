"""
Interface gráfica do Inspetor Técnico de Mídia (media.inspector).
Exibe informações detalhadas de codecs, streams de vídeo, faixas de áudio e legendas via FFprobe.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.media.inspector.logic import (
    inspect_media_file,
    generate_text_report,
)


@register
class MediaInspectorTool(Tool):
    id = "media.inspector"
    name = "Inspetor Técnico de Mídia (MediaInfo)"
    description = "Exibe relatório técnico detalhado de codecs, resolução, bitrates e faixas de áudio/vídeo via FFprobe."
    category = "media"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Seleção de arquivo
        top_box = QHBoxLayout()
        top_box.addWidget(QLabel("Arquivo de Mídia:"))
        self._edit_file = QLineEdit()
        self._edit_file.setPlaceholderText("Selecione um arquivo de áudio ou vídeo...")
        top_box.addWidget(self._edit_file)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_file)
        top_box.addWidget(btn_browse)

        self._btn_inspect = QPushButton("Inspecionar Mídia")
        self._btn_inspect.clicked.connect(self._on_inspect_click)
        top_box.addWidget(self._btn_inspect)
        layout.addLayout(top_box)

        # Abas de Exibição
        self._tabs = QTabWidget()

        # Aba 1: Relatório de Texto Formatado
        tab_report = QWidget()
        rep_layout = QVBoxLayout(tab_report)
        self._text_report = QTextEdit()
        self._text_report.setReadOnly(True)
        self._text_report.setFont(QFont("Consolas", 10))
        rep_layout.addWidget(self._text_report)
        self._tabs.addTab(tab_report, "Relatório Completo (MediaInfo)")

        # Aba 2: JSON Bruto
        tab_json = QWidget()
        json_layout = QVBoxLayout(tab_json)
        self._text_json = QTextEdit()
        self._text_json.setReadOnly(True)
        self._text_json.setFont(QFont("Consolas", 9))
        json_layout.addWidget(self._text_json)
        self._tabs.addTab(tab_json, "Dados Brutos (JSON)")

        layout.addWidget(self._tabs, 1)

        # Botões de ação
        bot_box = QHBoxLayout()
        btn_copy = QPushButton("Copiar Relatório")
        btn_copy.clicked.connect(self._on_copy_click)
        bot_box.addWidget(btn_copy)

        btn_save = QPushButton("Salvar Relatório em Arquivo...")
        btn_save.clicked.connect(self._on_save_click)
        bot_box.addWidget(btn_save)
        bot_box.addStretch()
        layout.addLayout(bot_box)

        self._lbl_status = QLabel("Selecione um arquivo de áudio ou vídeo.")
        layout.addWidget(self._lbl_status)

        self._current_info: Dict[str, Any] = {}
        return widget

    def _on_browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Arquivo de Mídia",
            "",
            "Mídias (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.flac *.wav *.m4a *.ogg);;Todos os Arquivos (*.*)",
        )
        if path:
            self._edit_file.setText(path)
            self._on_inspect_click()

    def _on_inspect_click(self) -> None:
        raw_path = self._edit_file.text().strip()
        if not raw_path:
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo de mídia.")
            return

        file_path = Path(raw_path)
        if not file_path.is_file():
            QMessageBox.critical(None, "Erro", f"Arquivo não encontrado: {file_path}")
            return

        self._lbl_status.setText("Executando ffprobe e analisando trilhas de mídia...")
        self._btn_inspect.setEnabled(False)

        def worker():
            return inspect_media_file(file_path)

        def on_done(info: Dict[str, Any]):
            self._btn_inspect.setEnabled(True)
            self._current_info = info
            rep_text = generate_text_report(info)
            self._text_report.setPlainText(rep_text)

            import json
            raw_str = json.dumps(info.get("raw_json", {}), indent=2, ensure_ascii=False)
            self._text_json.setPlainText(raw_str)

            gen = info.get("general", {})
            self._lbl_status.setText(
                f"Inspeção concluída: {gen.get('format_name', '')} | {gen.get('duration_formatted', '')} | {gen.get('size_mb', 0)} MB"
            )

        def on_error(err: str):
            self._btn_inspect.setEnabled(True)
            self._lbl_status.setText(f"Erro na inspeção: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao inspecionar mídia: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_copy_click(self) -> None:
        txt = self._text_report.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)
            QMessageBox.information(None, "Sucesso", "Relatório copiado para a área de transferência.")

    def _on_save_click(self) -> None:
        txt = self._text_report.toPlainText()
        if not txt:
            return

        path, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Relatório Técnico",
            "relatorio_mediainfo.txt",
            "Arquivos de Texto (*.txt);;Arquivos JSON (*.json)",
        )
        if path:
            Path(path).write_text(txt, encoding="utf-8")
            QMessageBox.information(None, "Sucesso", f"Relatório salvo em:\n{path}")

"""
Interface gráfica do Gerenciador de Trilhas e Remux de Mídia (media.stream_manager).
Permite selecionar quais faixas de vídeo, áudio e legendas manter em um arquivo sem recodificação.
"""
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.media.stream_manager.logic import (
    list_media_streams,
    remux_streams,
    extract_stream_to_file,
)


@register
class StreamManagerTool(Tool):
    id = "media.stream_manager"
    name = "Gerenciador de Trilhas e Remux"
    description = "Extrai, remove ou reorganiza faixas de áudio, vídeo e legendas sem perda de qualidade (stream copy)."
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
        self._edit_file.setPlaceholderText("Selecione um arquivo de vídeo (MKV, MP4, etc.)...")
        top_box.addWidget(self._edit_file)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_file)
        top_box.addWidget(btn_browse)

        self._btn_load = QPushButton("Carregar Trilhas")
        self._btn_load.clicked.connect(self._on_load_streams)
        top_box.addWidget(self._btn_load)
        layout.addLayout(top_box)

        # Tabela de Trilhas
        lbl_tbl = QLabel("Trilhas Detectadas no Contêiner (Marque para manter no arquivo final):")
        lbl_tbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_tbl)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            "Manter",
            "Índice",
            "Tipo",
            "Codec",
            "Idioma / Detalhes",
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self._table)

        # Ações
        act_box = QHBoxLayout()
        self._btn_remux = QPushButton("Remux (Salvar Novo Arquivo Sem Recodificar)...")
        self._btn_remux.setEnabled(False)
        self._btn_remux.clicked.connect(self._on_remux_click)
        act_box.addWidget(self._btn_remux)

        self._btn_extract_single = QPushButton("Extrair Trilha Selecionada...")
        self._btn_extract_single.setEnabled(False)
        self._btn_extract_single.clicked.connect(self._on_extract_single_click)
        act_box.addWidget(self._btn_extract_single)
        act_box.addStretch()
        layout.addLayout(act_box)

        self._lbl_status = QLabel("Selecione um arquivo para listar as faixas.")
        layout.addWidget(self._lbl_status)

        self._streams: List[Dict[str, Any]] = []
        return widget

    def _on_browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Arquivo de Mídia",
            "",
            "Vídeos (*.mkv *.mp4 *.avi *.webm *.mov);;Todos os Arquivos (*.*)",
        )
        if path:
            self._edit_file.setText(path)
            self._on_load_streams()

    def _on_load_streams(self) -> None:
        raw_path = self._edit_file.text().strip()
        if not raw_path:
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo de mídia.")
            return

        file_path = Path(raw_path)
        if not file_path.is_file():
            QMessageBox.critical(None, "Erro", f"Arquivo não encontrado: {file_path}")
            return

        self._lbl_status.setText("Lendo trilhas do contêiner...")
        self._btn_load.setEnabled(False)

        def worker():
            return list_media_streams(file_path)

        def on_done(streams: List[Dict[str, Any]]):
            self._btn_load.setEnabled(True)
            self._streams = streams
            self._table.setRowCount(len(streams))

            for row, s in enumerate(streams):
                # Checkbox
                chk_item = QTableWidgetItem()
                chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk_item.setCheckState(Qt.Checked)
                self._table.setItem(row, 0, chk_item)

                # Índice
                self._table.setItem(row, 1, QTableWidgetItem(f"#{s['index']}"))

                # Tipo
                self._table.setItem(row, 2, QTableWidgetItem(s["type"].upper()))

                # Codec
                self._table.setItem(row, 3, QTableWidgetItem(s["codec"]))

                # Detalhes
                details = f"{s['details']} (Lang: {s['language']})"
                if s["title"]:
                    details += f" - {s['title']}"
                self._table.setItem(row, 4, QTableWidgetItem(details))

            self._btn_remux.setEnabled(len(streams) > 0)
            self._btn_extract_single.setEnabled(len(streams) > 0)
            self._lbl_status.setText(f"{len(streams)} trilhas carregadas com sucesso.")

        def on_error(err: str):
            self._btn_load.setEnabled(True)
            self._lbl_status.setText(f"Erro: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao carregar trilhas: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _get_selected_stream_indexes(self) -> List[int]:
        selected: List[int] = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                selected.append(self._streams[row]["index"])
        return selected

    def _on_remux_click(self) -> None:
        raw_path = self._edit_file.text().strip()
        if not raw_path:
            return

        src_path = Path(raw_path)
        indexes = self._get_selected_stream_indexes()
        if not indexes:
            QMessageBox.warning(None, "Aviso", "Selecione ao menos uma trilha para manter no vídeo final.")
            return

        out_str, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Mídia Remux Como",
            str(src_path.parent / f"{src_path.stem}_remux{src_path.suffix}"),
            f"Contêiner (*{src_path.suffix});;Todos os Arquivos (*.*)",
        )
        if not out_str:
            return

        out_path = Path(out_str)
        self._lbl_status.setText("Executando remux rápido (sem recodificação)...")
        self._btn_remux.setEnabled(False)

        def worker():
            return remux_streams(src_path, out_path, indexes)

        def on_done(res_path: Path):
            self._btn_remux.setEnabled(True)
            self._lbl_status.setText(f"Remux concluído com sucesso: {res_path.name}")
            QMessageBox.information(
                None,
                "Remux Concluído",
                f"O arquivo remuxado foi gerado instantaneamente em:\n{res_path}",
            )

        def on_error(err: str):
            self._btn_remux.setEnabled(True)
            self._lbl_status.setText(f"Erro no remux: {err}")
            QMessageBox.critical(None, "Erro", f"Falha no remux: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_extract_single_click(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._streams):
            QMessageBox.warning(None, "Aviso", "Selecione uma linha na tabela para extrair a trilha.")
            return

        stream = self._streams[row]
        src_path = Path(self._edit_file.text().strip())

        # Sugere extensão
        c_type = stream["type"]
        codec = stream["codec"]
        if c_type == "audio":
            ext = ".aac" if "aac" in codec else (".mp3" if "mp3" in codec else ".m4a")
        elif c_type == "subtitle":
            ext = ".srt" if "subrip" in codec else ".ass"
        else:
            ext = ".mp4"

        out_str, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Trilha Extraída Como",
            str(src_path.parent / f"{src_path.stem}_trilha_{stream['index']}{ext}"),
            "Todos os Arquivos (*.*)",
        )
        if not out_str:
            return

        out_path = Path(out_str)
        self._lbl_status.setText(f"Extraindo trilha #{stream['index']}...")
        self._btn_extract_single.setEnabled(False)

        def worker():
            return extract_stream_to_file(src_path, out_path, stream["index"])

        def on_done(res_path: Path):
            self._btn_extract_single.setEnabled(True)
            self._lbl_status.setText(f"Trilha extraída com sucesso: {res_path.name}")
            QMessageBox.information(
                None,
                "Extração Concluída",
                f"A faixa foi extraída com sucesso para:\n{res_path}",
            )

        def on_error(err: str):
            self._btn_extract_single.setEnabled(True)
            self._lbl_status.setText(f"Erro ao extrair trilha: {err}")
            QMessageBox.critical(None, "Erro", f"Falha na extração: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

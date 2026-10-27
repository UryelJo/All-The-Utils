"""
Interface gráfica da ferramenta Editor e Conversor de Legendas (media.subtitles).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.media.subtitles.logic import (
    generate_srt, generate_vtt, load_subtitle_file,
    ms_to_srt_time, shift_subtitles
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

_log = get_logger("media.subtitles.ui")


@register
class SubtitlesTool(Tool):
    id = "media.subtitles"
    name = "Editor e Conversor de Legendas (SRT / VTT)"
    category = "Imagens"
    description = "Converta legendas entre SRT e WebVTT, ajuste o sincronismo de tempo (Time Shift) e edite diálogos"
    keywords = ["legendas", "subtitles", "srt", "vtt", "webvtt", "sincronia", "time shift", "atraso", "filme", "video"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SubtitlesView(self, parent)


class SubtitlesView(QWidget):
    def __init__(self, tool: SubtitlesTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._items: List[Dict[str, Any]] = []
        self._current_file: Optional[Path] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(self.tool.name, self.tool.description))

        # Barra de seleção de arquivo
        top_card = QFrame()
        top_card.setObjectName("Card")
        t_lay = QHBoxLayout(top_card)
        t_lay.setContentsMargins(14, 12, 14, 12)
        t_lay.setSpacing(10)

        t_lay.addWidget(QLabel("Arquivo de Legenda:"))
        self.txt_file = QLineEdit()
        self.txt_file.setReadOnly(True)
        self.txt_file.setPlaceholderText("Selecione um arquivo .srt ou .vtt...")
        t_lay.addWidget(self.txt_file, stretch=1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_file)
        t_lay.addWidget(btn_browse)

        layout.addWidget(top_card)

        # Barra de Ferramentas e Ajuste de Sincronia (Time Shift)
        shift_card = QFrame()
        shift_card.setObjectName("Card")
        s_lay = QHBoxLayout(shift_card)
        s_lay.setContentsMargins(14, 10, 14, 10)
        s_lay.setSpacing(10)

        s_lay.addWidget(QLabel("Ajuste de Tempo (Time Shift):"))

        btn_sub_1s = QPushButton("-1.0s")
        btn_sub_1s.setToolTip("Adiantar 1 segundo")
        btn_sub_1s.clicked.connect(lambda: self._apply_shift(-1000))
        s_lay.addWidget(btn_sub_1s)

        btn_sub_05s = QPushButton("-0.5s")
        btn_sub_05s.setToolTip("Adiantar meio segundo")
        btn_sub_05s.clicked.connect(lambda: self._apply_shift(-500))
        s_lay.addWidget(btn_sub_05s)

        self.spin_shift = QSpinBox()
        self.spin_shift.setRange(-60000, 60000)
        self.spin_shift.setSingleStep(100)
        self.spin_shift.setValue(0)
        self.spin_shift.setSuffix(" ms")
        s_lay.addWidget(self.spin_shift)

        btn_apply_spin = QPushButton("Aplicar")
        btn_apply_spin.clicked.connect(lambda: self._apply_shift(self.spin_shift.value()))
        s_lay.addWidget(btn_apply_spin)

        btn_add_05s = QPushButton("+0.5s")
        btn_add_05s.setToolTip("Atrasar meio segundo")
        btn_add_05s.clicked.connect(lambda: self._apply_shift(500))
        s_lay.addWidget(btn_add_05s)

        btn_add_1s = QPushButton("+1.0s")
        btn_add_1s.setToolTip("Atrasar 1 segundo")
        btn_add_1s.clicked.connect(lambda: self._apply_shift(1000))
        s_lay.addWidget(btn_add_1s)

        s_lay.addStretch()

        self.chk_strip = QCheckBox("Remover tags HTML de formatação")
        self.chk_strip.setChecked(False)
        s_lay.addWidget(self.chk_strip)

        layout.addWidget(shift_card)

        # Tabela com as legendas
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["#", "Início", "Fim", "Texto do Diálogo"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        enable_sorting_on_table(self.table)
        layout.addWidget(self.table, stretch=1)

        # Barra inferior de exportação
        bottom_bar = QHBoxLayout()
        self.lbl_count = QLabel("Nenhuma legenda carregada.")
        self.lbl_count.setStyleSheet("color: #888888; font-size: 12px;")
        bottom_bar.addWidget(self.lbl_count)

        bottom_bar.addStretch()

        bottom_bar.addWidget(QLabel("Salvar Formato:"))
        self.cmb_out_fmt = QComboBox()
        self.cmb_out_fmt.addItem("SubRip (.srt)", "srt")
        self.cmb_out_fmt.addItem("WebVTT (.vtt)", "vtt")
        bottom_bar.addWidget(self.cmb_out_fmt)

        self.btn_save = QPushButton("Salvar Legenda...")
        self.btn_save.setProperty("class", "accent")
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet("padding: 8px 18px; font-weight: 600;")
        self.btn_save.clicked.connect(self._save_subtitles)
        bottom_bar.addWidget(self.btn_save)

        layout.addLayout(bottom_bar)

    def _browse_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo de Legenda",
            "",
            "Legendas (*.srt *.vtt);;Todos os Arquivos (*.*)"
        )
        if not p:
            return
        self._current_file = Path(p)
        self.txt_file.setText(str(self._current_file))
        try:
            self._items = load_subtitle_file(self._current_file)
            self._render_table()
            self.btn_save.setEnabled(len(self._items) > 0)
            show_toast(self, f"{len(self._items)} falas carregadas com sucesso!", kind="success")
        except Exception as exc:
            show_toast(self, f"Erro ao ler arquivo: {exc}", kind="error")

    def _render_table(self) -> None:
        with batch_table_update(self.table):
            self.table.setRowCount(len(self._items))
            for row, it in enumerate(self._items):
                self.table.setItem(row, 0, SmartTableWidgetItem(str(it["index"]), sort_value=it["index"], user_data=it))
                self.table.setItem(row, 1, SmartTableWidgetItem(ms_to_srt_time(it["start_ms"]), sort_value=it["start_ms"]))
                self.table.setItem(row, 2, SmartTableWidgetItem(ms_to_srt_time(it["end_ms"]), sort_value=it["end_ms"]))
                txt_item = SmartTableWidgetItem(it["text"].replace("\n", " | "))
                self.table.setItem(row, 3, txt_item)
        self.lbl_count.setText(f"Total: {len(self._items)} entrada(s) de legenda.")

    def _apply_shift(self, offset_ms: int) -> None:
        if not self._items:
            show_toast(self, "Carregue um arquivo de legenda primeiro.", kind="error")
            return
        self._items = shift_subtitles(self._items, offset_ms)
        self._render_table()
        sign = "+" if offset_ms > 0 else ""
        show_toast(self, f"Sincronia ajustada em {sign}{offset_ms} ms", kind="info")

    def _save_subtitles(self) -> None:
        if not self._items:
            return

        fmt = self.cmb_out_fmt.currentData()
        strip_tags = self.chk_strip.isChecked()

        # Atualiza textos da tabela de volta para os itens caso o usuário tenha editado
        for row in range(self.table.rowCount()):
            idx_item = self.table.item(row, 0)
            if idx_item:
                sub_dict = idx_item.data(Qt.UserRole)
                if sub_dict is not None:
                    text_item = self.table.item(row, 3)
                    if text_item:
                        sub_dict["text"] = text_item.text().replace(" | ", "\n")

        # Garante ordem cronológica antes de exportar
        self._items.sort(key=lambda x: x["start_ms"])

        if fmt == "srt":
            out_content = generate_srt(self._items, strip_tags=strip_tags)
            filter_str = "Arquivo SubRip (*.srt)"
            default_name = f"{self._current_file.stem}_ajustado.srt" if self._current_file else "legenda.srt"
        else:
            out_content = generate_vtt(self._items, strip_tags=strip_tags)
            filter_str = "Arquivo WebVTT (*.vtt)"
            default_name = f"{self._current_file.stem}_ajustado.vtt" if self._current_file else "legenda.vtt"

        default_path = (self._current_file.parent / default_name) if self._current_file else Path(default_name)
        dst, _ = QFileDialog.getSaveFileName(self, "Salvar Legenda", str(default_path), filter_str)
        if not dst:
            return

        try:
            Path(dst).write_text(out_content, encoding="utf-8")
            show_toast(self, "Legenda salva com sucesso!", kind="success")
            QMessageBox.information(
                self,
                "Arquivo Salvo",
                f"Legenda exportada com sucesso em:\n{dst}\n\nEntradas: {len(self._items)}"
            )
        except Exception as exc:
            show_toast(self, f"Erro ao salvar: {exc}", kind="error")

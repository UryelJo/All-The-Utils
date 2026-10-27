"""
Ferramenta: Cortador e Juntador de Vídeos e Áudios.
Interface moderna para edição rápida sem reencodagem (Stream Copy).
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.media.ffmpeg_utils import get_media_info
from wintoolbox.tools.media.trim_merge.logic import merge_media_files, trim_media


@register
class MediaTrimMergeTool(Tool):
    id = "media.trim_merge"
    name = "Cortador e Juntador de Mídia"
    category = "Áudio e Vídeo"
    description = "Cortador e juntador de vídeos e músicas: corta trechos indesejados ou une múltiplos clipes sem perda de qualidade e sem reencodar via FFmpeg cópia direta."
    keywords = ["video", "audio", "cortar", "trim", "juntar", "concat", "merge", "ffmpeg", "stream copy"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = QLabel("Cortador e Juntador de Mídia")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        main_layout.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(self._build_trim_tab(), "Cortar Mídia (Trim)")
        tabs.addTab(self._build_merge_tab(), "Juntar Mídias (Concat)")
        main_layout.addWidget(tabs)

        return container

    # -------------------------------------------------------------------------
    # Aba 1: Cortar
    # -------------------------------------------------------------------------
    def _build_trim_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Arquivo de entrada
        grp_src = QGroupBox("Arquivo de Entrada")
        grid_src = QGridLayout(grp_src)
        grid_src.addWidget(QLabel("Mídia de origem:"), 0, 0)
        self.txt_trim_src = QLineEdit()
        self.txt_trim_src.setPlaceholderText("Selecione um arquivo de vídeo ou áudio...")
        grid_src.addWidget(self.txt_trim_src, 0, 1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_trim_src)
        grid_src.addWidget(btn_browse, 0, 2)

        self.lbl_trim_info = QLabel("Duração: - | Resolução / Formato: -")
        self.lbl_trim_info.setStyleSheet("color: gray; font-size: 11px;")
        grid_src.addWidget(self.lbl_trim_info, 1, 1, 1, 2)
        layout.addWidget(grp_src)

        # Intervalo de corte
        grp_range = QGroupBox("Intervalo de Corte (HH:MM:SS ou segundos)")
        grid_range = QGridLayout(grp_range)

        grid_range.addWidget(QLabel("Tempo de início:"), 0, 0)
        self.txt_start_time = QLineEdit("00:00:00")
        grid_range.addWidget(self.txt_start_time, 0, 1)

        grid_range.addWidget(QLabel("Tempo de fim:"), 0, 2)
        self.txt_end_time = QLineEdit("00:01:00")
        grid_range.addWidget(self.txt_end_time, 0, 3)

        self.chk_reencode = QCheckBox("Forçar reencodagem completa (mais lento, porém com precisão exata de frame)")
        self.chk_reencode.setChecked(False)
        grid_range.addWidget(self.chk_reencode, 1, 0, 1, 4)

        layout.addWidget(grp_range)

        # Destino
        grp_dst = QGroupBox("Destino do Trecho Cortado")
        grid_dst = QGridLayout(grp_dst)
        grid_dst.addWidget(QLabel("Salvar em:"), 0, 0)
        self.txt_trim_dst = QLineEdit()
        grid_dst.addWidget(self.txt_trim_dst, 0, 1)

        btn_browse_dst = QPushButton("Procurar...")
        btn_browse_dst.clicked.connect(self._on_browse_trim_dst)
        grid_dst.addWidget(btn_browse_dst, 0, 2)
        layout.addWidget(grp_dst)

        # Ações
        act_box = QHBoxLayout()
        self.lbl_trim_status = QLabel("")
        act_box.addWidget(self.lbl_trim_status)
        act_box.addStretch()

        self.btn_run_trim = QPushButton("Cortar Mídia Agora")
        self.btn_run_trim.setProperty("class", "primary")
        self.btn_run_trim.clicked.connect(self._on_run_trim)
        act_box.addWidget(self.btn_run_trim)

        layout.addLayout(act_box)
        layout.addStretch()
        return tab

    def _on_browse_trim_src(self):
        file, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Vídeo ou Áudio",
            "",
            "Mídias (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.flac *.m4a);;Todos (*.*)"
        )
        if file:
            p = Path(file)
            self.txt_trim_src.setText(str(p))
            if not self.txt_trim_dst.text():
                self.txt_trim_dst.setText(str(p.parent / f"{p.stem}_corte{p.suffix}"))
            try:
                info = get_media_info(p)
                fmt = info.get("format", {})
                dur = float(fmt.get("duration", 0.0))
                m, s = divmod(int(dur), 60)
                h, m = divmod(m, 60)
                dur_str = f"{h:02d}:{m:02d}:{s:02d}"
                self.lbl_trim_info.setText(f"Duração total: {dur_str} ({dur:.1f}s) | Formato: {fmt.get('format_long_name', '-')}")
                self.txt_end_time.setText(dur_str)
            except Exception as e:
                self.lbl_trim_info.setText(f"Info: {e}")

    def _on_browse_trim_dst(self):
        file, _ = QFileDialog.getSaveFileName(None, "Salvar Mídia Cortada", "trecho_cortado.mp4", "Arquivos de Mídia (*.*)")
        if file:
            self.txt_trim_dst.setText(file)

    def _on_run_trim(self):
        src = self.txt_trim_src.text().strip()
        dst = self.txt_trim_dst.text().strip()
        st = self.txt_start_time.text().strip()
        et = self.txt_end_time.text().strip()
        reenc = self.chk_reencode.isChecked()

        if not src or not Path(src).is_file():
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo de mídia válido.")
            return
        if not dst:
            QMessageBox.warning(None, "Aviso", "Informe o destino do corte.")
            return

        self.btn_run_trim.setEnabled(False)
        self.lbl_trim_status.setText("Processando corte via ffmpeg...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, "Cortando arquivo de mídia...")
            res = trim_media(Path(src), Path(dst), start_time=st, end_time=et, reencode=reenc)
            ctx.progress(100, 100, "Corte finalizado com sucesso!")
            return res

        def _done(result, exc):
            self.btn_run_trim.setEnabled(True)
            if exc:
                self.lbl_trim_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha no corte: {exc}")
            else:
                self.lbl_trim_status.setText("Corte concluído!")
                QMessageBox.information(None, "Sucesso", f"Arquivo cortado salvo com sucesso em:\n{result}")

        run_task(_work, on_done=_done)

    # -------------------------------------------------------------------------
    # Aba 2: Juntar
    # -------------------------------------------------------------------------
    def _build_merge_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl_desc = QLabel("Adicione os arquivos de áudio ou vídeo na ordem em que devem ser concatenados:")
        layout.addWidget(lbl_desc)

        list_box = QHBoxLayout()
        self.list_merge = QListWidget()
        self.list_merge.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_merge.setDragDropMode(QAbstractItemView.InternalMove)
        list_box.addWidget(self.list_merge, stretch=1)

        btn_box = QVBoxLayout()
        btn_box.setSpacing(6)

        btn_add = QPushButton("Adicionar Arquivos...")
        btn_add.clicked.connect(self._on_add_merge_files)
        btn_box.addWidget(btn_add)

        btn_up = QPushButton("Mover para Cima")
        btn_up.clicked.connect(self._on_move_merge_up)
        btn_box.addWidget(btn_up)

        btn_down = QPushButton("Mover para Baixo")
        btn_down.clicked.connect(self._on_move_merge_down)
        btn_box.addWidget(btn_down)

        btn_remove = QPushButton("Remover Seleção")
        btn_remove.clicked.connect(self._on_remove_merge_selected)
        btn_box.addWidget(btn_remove)

        btn_clear = QPushButton("Limpar Lista")
        btn_clear.clicked.connect(self.list_merge.clear)
        btn_box.addWidget(btn_clear)

        btn_box.addStretch()
        list_box.addLayout(btn_box)
        layout.addLayout(list_box)

        # Destino
        grp_dst = QGroupBox("Arquivo Resultante Unificado")
        grid_dst = QGridLayout(grp_dst)
        grid_dst.addWidget(QLabel("Salvar em:"), 0, 0)
        self.txt_merge_dst = QLineEdit()
        grid_dst.addWidget(self.txt_merge_dst, 0, 1)

        btn_browse_dst = QPushButton("Procurar...")
        btn_browse_dst.clicked.connect(self._on_browse_merge_dst)
        grid_dst.addWidget(btn_browse_dst, 0, 2)
        layout.addWidget(grp_dst)

        # Ações
        act_box = QHBoxLayout()
        self.lbl_merge_status = QLabel("")
        act_box.addWidget(self.lbl_merge_status)
        act_box.addStretch()

        self.btn_run_merge = QPushButton("Juntar Mídias Agora")
        self.btn_run_merge.setProperty("class", "primary")
        self.btn_run_merge.clicked.connect(self._on_run_merge)
        act_box.addWidget(self.btn_run_merge)

        layout.addLayout(act_box)
        return tab

    def _on_add_merge_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            None,
            "Selecionar Arquivos para Junção",
            "",
            "Mídias (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.flac);;Todos (*.*)"
        )
        for f in files:
            self.list_merge.addItem(f)

    def _on_move_merge_up(self):
        row = self.list_merge.currentRow()
        if row > 0:
            item = self.list_merge.takeItem(row)
            self.list_merge.insertItem(row - 1, item)
            self.list_merge.setCurrentRow(row - 1)

    def _on_move_merge_down(self):
        row = self.list_merge.currentRow()
        if row < self.list_merge.count() - 1:
            item = self.list_merge.takeItem(row)
            self.list_merge.insertItem(row + 1, item)
            self.list_merge.setCurrentRow(row + 1)

    def _on_remove_merge_selected(self):
        for item in self.list_merge.selectedItems():
            self.list_merge.takeItem(self.list_merge.row(item))

    def _on_browse_merge_dst(self):
        file, _ = QFileDialog.getSaveFileName(None, "Salvar Mídia Unificada", "midia_unificada.mp4", "Arquivos de Mídia (*.*)")
        if file:
            self.txt_merge_dst.setText(file)

    def _on_run_merge(self):
        count = self.list_merge.count()
        if count < 2:
            QMessageBox.warning(None, "Aviso", "Adicione pelo menos 2 arquivos para juntar.")
            return

        dst = self.txt_merge_dst.text().strip()
        if not dst:
            QMessageBox.warning(None, "Aviso", "Informe o destino do arquivo unificado.")
            return

        file_list = [Path(self.list_merge.item(i).text()) for i in range(count)]

        self.btn_run_merge.setEnabled(False)
        self.lbl_merge_status.setText("Concatenando arquivos...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, f"Unindo {count} arquivos de mídia...")
            res = merge_media_files(file_list, Path(dst), reencode=False)
            ctx.progress(100, 100, "Junção finalizada com sucesso!")
            return res

        def _done(result, exc):
            self.btn_run_merge.setEnabled(True)
            if exc:
                self.lbl_merge_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha na junção: {exc}")
            else:
                self.lbl_merge_status.setText("Junção concluída com sucesso!")
                QMessageBox.information(None, "Sucesso", f"Arquivo unificado gerado em:\n{result}")

        run_task(_work, on_done=_done)

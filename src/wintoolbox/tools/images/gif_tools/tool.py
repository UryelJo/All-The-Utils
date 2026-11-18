"""
Ferramenta: Montador e Extrator de GIFs Animados Profissional.
Inclui player animado interativo em tempo real (Play/Pause, Step, FPS dinâmico),
timeline horizontal de quadros com reordenação e extração seletiva.
"""
from pathlib import Path
from typing import List, Optional
from PIL import Image

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QStyle,
    QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.images.gif_tools.logic import (
    create_animated_gif, extract_gif_frames
)
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl


@register
class GifToolsTool(Tool):
    id = "images.gif_tools"
    name = "Montador e Extrator de GIF"
    category = "Imagens"
    description = "Criação de GIFs animados com timeline visual, player e extração de quadros"
    keywords = ["gif", "animação", "frames", "quadros", "montador", "extrair", "loop", "timeline", "player"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return GifToolsView(self, parent)


class _GifPlayerWidget(QFrame):
    """Player visual de animação com controles de reprodução e avanço quadro a quadro."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background-color: #16181A; border: 1px solid #2B303A; border-radius: 8px; }")
        self.setFixedHeight(230)

        self._pixmaps: List[QPixmap] = []
        self._current_idx: int = 0
        self._is_playing: bool = True
        self._fps: int = 5

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Tela de visualização do quadro
        self._lbl_display = QLabel("Adicione imagens para visualizar a animação", self)
        self._lbl_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_display.setStyleSheet("color: #8F96A0; font-size: 13px;")
        layout.addWidget(self._lbl_display, stretch=1)

        # Barra de controles
        ctl_row = QHBoxLayout()
        ctl_row.setContentsMargins(4, 0, 4, 0)
        ctl_row.setSpacing(8)

        self._btn_prev = QPushButton("◀ Anterior", self)
        self._btn_prev.setFixedHeight(26)
        self._btn_prev.clicked.connect(self.prev_frame)
        ctl_row.addWidget(self._btn_prev)

        self._btn_play = QPushButton("Pausar", self)
        self._btn_play.setProperty("class", "primary")
        self._btn_play.setFixedHeight(26)
        self._btn_play.clicked.connect(self.toggle_play)
        ctl_row.addWidget(self._btn_play)

        self._btn_next = QPushButton("Próximo ▶", self)
        self._btn_next.setFixedHeight(26)
        self._btn_next.clicked.connect(self.next_frame)
        ctl_row.addWidget(self._btn_next)

        ctl_row.addStretch()

        self._lbl_counter = QLabel("0 / 0 quadros", self)
        self._lbl_counter.setStyleSheet("font-weight: 600; font-size: 12px; color: #57A5FF;")
        ctl_row.addWidget(self._lbl_counter)

        layout.addLayout(ctl_row)

    def set_frames_from_paths(self, paths: List[Path]) -> None:
        self._pixmaps.clear()
        for p in paths:
            if p.is_file():
                pix = QPixmap(str(p))
                if not pix.isNull():
                    self._pixmaps.append(pix)
        self._current_idx = 0
        self._update_display()
        if self._pixmaps and self._is_playing:
            self._start_timer()
        else:
            self._timer.stop()

    def set_frames_from_pixmaps(self, pixmaps: List[QPixmap]) -> None:
        self._pixmaps = list(pixmaps)
        self._current_idx = 0
        self._update_display()
        if self._pixmaps and self._is_playing:
            self._start_timer()
        else:
            self._timer.stop()

    def set_fps(self, fps: int) -> None:
        self._fps = max(1, min(fps, 60))
        if self._timer.isActive():
            self._start_timer()

    def _start_timer(self) -> None:
        interval_ms = max(16, int(1000 / self._fps))
        self._timer.start(interval_ms)

    def toggle_play(self) -> None:
        self._is_playing = not self._is_playing
        self._btn_play.setText("Pausar" if self._is_playing else "Reproduzir")
        if self._is_playing and self._pixmaps:
            self._start_timer()
        else:
            self._timer.stop()

    def prev_frame(self) -> None:
        if not self._pixmaps:
            return
        self._timer.stop()
        self._is_playing = False
        self._btn_play.setText("Reproduzir")
        self._current_idx = (self._current_idx - 1) % len(self._pixmaps)
        self._update_display()

    def next_frame(self) -> None:
        if not self._pixmaps:
            return
        self._timer.stop()
        self._is_playing = False
        self._btn_play.setText("Reproduzir")
        self._current_idx = (self._current_idx + 1) % len(self._pixmaps)
        self._update_display()

    def show_index(self, idx: int) -> None:
        if 0 <= idx < len(self._pixmaps):
            self._timer.stop()
            self._is_playing = False
            self._btn_play.setText("Reproduzir")
            self._current_idx = idx
            self._update_display()

    def _on_tick(self) -> None:
        if not self._pixmaps:
            return
        self._current_idx = (self._current_idx + 1) % len(self._pixmaps)
        self._update_display()

    def _update_display(self) -> None:
        total = len(self._pixmaps)
        if total == 0:
            self._lbl_display.setText("Nenhum quadro carregado")
            self._lbl_counter.setText("0 / 0 quadros")
            return

        self._lbl_counter.setText(f"Quadro {self._current_idx + 1} de {total}")
        pix = self._pixmaps[self._current_idx]
        target_h = self._lbl_display.height() or 140
        target_w = self._lbl_display.width() or 240
        scaled = pix.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._lbl_display.setPixmap(scaled)


class GifToolsView(QWidget):
    def __init__(self, tool: GifToolsTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._frame_paths: List[Path] = []
        self._extracted_frames: List[QPixmap] = []
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_create_tab(), "Criar GIF Animado")
        self.tabs.addTab(self._build_extract_tab(), "Extrair Frames de GIF")
        root_layout.addWidget(self.tabs)

    # -------------------------------------------------------------------------
    # Aba 1: Criar GIF
    # -------------------------------------------------------------------------
    def _build_create_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(10)

        # Player Superior
        self.player_create = _GifPlayerWidget(tab)
        layout.addWidget(self.player_create)

        # Timeline Horizontal de Quadros
        grp_timeline = QGroupBox("Timeline de Quadros (Ordem de Animação)")
        v_tl = QVBoxLayout(grp_timeline)
        v_tl.setContentsMargins(8, 8, 8, 8)
        v_tl.setSpacing(6)

        self.timeline_list = QListWidget()
        self.timeline_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.timeline_list.setIconSize(QSize(56, 56))
        self.timeline_list.setGridSize(QSize(76, 76))
        self.timeline_list.setFixedHeight(94)
        self.timeline_list.setMovement(QListWidget.Movement.Static)
        self.timeline_list.itemClicked.connect(self._on_timeline_item_clicked)
        v_tl.addWidget(self.timeline_list)

        # Botões de controle da Timeline
        row_tl_btns = QHBoxLayout()
        row_tl_btns.setSpacing(8)

        btn_add = QPushButton("Adicionar Fotos...")
        btn_add.setProperty("class", "primary")
        btn_add.clicked.connect(self._on_add_create_images)
        row_tl_btns.addWidget(btn_add)

        btn_dup = QPushButton("Duplicar Quadro")
        btn_dup.clicked.connect(self._on_dup_frame)
        row_tl_btns.addWidget(btn_dup)

        btn_left = QPushButton("◀ Mover Esquerda")
        btn_left.clicked.connect(self._on_move_frame_left)
        row_tl_btns.addWidget(btn_left)

        btn_right = QPushButton("Mover Direita ▶")
        btn_right.clicked.connect(self._on_move_frame_right)
        row_tl_btns.addWidget(btn_right)

        btn_del = QPushButton("Remover Quadro")
        btn_del.clicked.connect(self._on_remove_frame)
        row_tl_btns.addWidget(btn_del)

        btn_clear = QPushButton("Limpar Tudo")
        btn_clear.clicked.connect(self._on_clear_create)
        row_tl_btns.addWidget(btn_clear)

        row_tl_btns.addStretch()
        v_tl.addLayout(row_tl_btns)
        layout.addWidget(grp_timeline)

        # Configurações de Velocidade e Saída
        grp_cfg = QGroupBox("Velocidade e Configurações de Saída")
        grid_cfg = QGridLayout(grp_cfg)
        grid_cfg.setHorizontalSpacing(14)
        grid_cfg.setVerticalSpacing(8)

        grid_cfg.addWidget(QLabel("Velocidade de Animação:"), 0, 0)
        self.slider_fps = SliderSpinControl("", 1, 30, 5, suffix=" fps")
        self.slider_fps.valueChanged.connect(self._on_fps_changed)
        grid_cfg.addWidget(self.slider_fps, 0, 1)

        grid_cfg.addWidget(QLabel("Repetições (Loop):"), 0, 2)
        self.cmb_loop = QComboBox()
        self.cmb_loop.addItem("Infinito (Padrão)", 0)
        self.cmb_loop.addItem("Apenas 1 vez", 1)
        self.cmb_loop.addItem("3 vezes", 3)
        self.cmb_loop.addItem("5 vezes", 5)
        grid_cfg.addWidget(self.cmb_loop, 0, 3)

        grid_cfg.addWidget(QLabel("Salvar GIF em:"), 1, 0)
        row_dest = QHBoxLayout()
        self.txt_create_dest = QLineEdit()
        self.txt_create_dest.setPlaceholderText("Selecione onde salvar o arquivo .gif...")
        row_dest.addWidget(self.txt_create_dest, stretch=1)
        btn_browse_dest = QPushButton("Procurar...")
        btn_browse_dest.clicked.connect(self._on_browse_create_dest)
        row_dest.addWidget(btn_browse_dest)
        grid_cfg.addLayout(row_dest, 1, 1, 1, 3)

        layout.addWidget(grp_cfg)

        # Barra de Ação
        act_box = QHBoxLayout()
        self.lbl_create_status = QLabel("")
        act_box.addWidget(self.lbl_create_status)
        act_box.addStretch()

        self.btn_create_run = QPushButton("Compilar e Gerar GIF")
        self.btn_create_run.setProperty("class", "primary")
        self.btn_create_run.setFixedHeight(34)
        self.btn_create_run.setStyleSheet("font-weight: 600; padding: 6px 20px;")
        self.btn_create_run.clicked.connect(self._on_run_create)
        act_box.addWidget(self.btn_create_run)
        layout.addLayout(act_box)

        return tab

    # -------------------------------------------------------------------------
    # Aba 2: Extrair Frames
    # -------------------------------------------------------------------------
    def _build_extract_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(10)

        # Player de Inspeção do GIF Carregado
        self.player_extract = _GifPlayerWidget(tab)
        layout.addWidget(self.player_extract)

        # Origem e Destino
        grp_ext = QGroupBox("Arquivo de Origem e Extração")
        grid_ext = QGridLayout(grp_ext)
        grid_ext.setHorizontalSpacing(14)
        grid_ext.setVerticalSpacing(8)

        grid_ext.addWidget(QLabel("Arquivo GIF:"), 0, 0)
        row_src = QHBoxLayout()
        self.txt_extract_src = QLineEdit()
        self.txt_extract_src.setPlaceholderText("Selecione o arquivo .gif animado...")
        row_src.addWidget(self.txt_extract_src, stretch=1)
        btn_browse_gif = QPushButton("Selecionar GIF...")
        btn_browse_gif.clicked.connect(self._on_browse_extract_src)
        row_src.addWidget(btn_browse_gif)
        grid_ext.addLayout(row_src, 0, 1, 1, 3)

        grid_ext.addWidget(QLabel("Pasta de Destino:"), 1, 0)
        row_dir = QHBoxLayout()
        self.txt_extract_dir = QLineEdit()
        self.txt_extract_dir.setPlaceholderText("Pasta onde as imagens dos quadros serão salvas...")
        row_dir.addWidget(self.txt_extract_dir, stretch=1)
        btn_browse_dir = QPushButton("Selecionar Pasta...")
        btn_browse_dir.clicked.connect(self._on_browse_extract_dir)
        row_dir.addWidget(btn_browse_dir)
        grid_ext.addLayout(row_dir, 1, 1)

        grid_ext.addWidget(QLabel("Formato de saída:"), 1, 2)
        self.cmb_extract_fmt = QComboBox()
        self.cmb_extract_fmt.addItems(["PNG (Recomendado)", "JPEG", "WEBP", "BMP"])
        grid_ext.addWidget(self.cmb_extract_fmt, 1, 3)

        layout.addWidget(grp_ext)

        # Ação
        act_box = QHBoxLayout()
        self.lbl_extract_status = QLabel("")
        act_box.addWidget(self.lbl_extract_status)
        act_box.addStretch()

        self.btn_extract_run = QPushButton("Extrair Todos os Quadros")
        self.btn_extract_run.setProperty("class", "primary")
        self.btn_extract_run.setFixedHeight(34)
        self.btn_extract_run.setStyleSheet("font-weight: 600; padding: 6px 20px;")
        self.btn_extract_run.clicked.connect(self._on_run_extract)
        act_box.addWidget(self.btn_extract_run)
        layout.addLayout(act_box)

        layout.addStretch()
        return tab

    # Handlers da Aba 1
    def _on_add_create_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Imagens para o GIF",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.heic *.avif);;Todos (*.*)"
        )
        if files:
            for f in files:
                p = Path(f)
                if p not in self._frame_paths:
                    self._frame_paths.append(p)
            self._sync_timeline()

    def _sync_timeline(self):
        self.timeline_list.clear()
        for idx, p in enumerate(self._frame_paths):
            pix = QPixmap(str(p))
            if not pix.isNull():
                thumb = pix.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon = QIcon(thumb)
            else:
                icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)

            item = QListWidgetItem(icon, f"#{idx + 1}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.timeline_list.addItem(item)

        self.player_create.set_frames_from_paths(self._frame_paths)

    def _on_timeline_item_clicked(self, item: QListWidgetItem):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is not None:
            self.player_create.show_index(idx)

    def _on_dup_frame(self):
        curr = self.timeline_list.currentRow()
        if 0 <= curr < len(self._frame_paths):
            self._frame_paths.insert(curr + 1, self._frame_paths[curr])
            self._sync_timeline()
            self.timeline_list.setCurrentRow(curr + 1)

    def _on_move_frame_left(self):
        curr = self.timeline_list.currentRow()
        if curr > 0:
            self._frame_paths[curr - 1], self._frame_paths[curr] = self._frame_paths[curr], self._frame_paths[curr - 1]
            self._sync_timeline()
            self.timeline_list.setCurrentRow(curr - 1)

    def _on_move_frame_right(self):
        curr = self.timeline_list.currentRow()
        if 0 <= curr < len(self._frame_paths) - 1:
            self._frame_paths[curr + 1], self._frame_paths[curr] = self._frame_paths[curr], self._frame_paths[curr + 1]
            self._sync_timeline()
            self.timeline_list.setCurrentRow(curr + 1)

    def _on_remove_frame(self):
        curr = self.timeline_list.currentRow()
        if 0 <= curr < len(self._frame_paths):
            self._frame_paths.pop(curr)
            self._sync_timeline()

    def _on_clear_create(self):
        self._frame_paths.clear()
        self._sync_timeline()

    def _on_fps_changed(self, val):
        self.player_create.set_fps(int(val))

    def _on_browse_create_dest(self):
        f, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar GIF Animado",
            "",
            "GIF Animado (*.gif)"
        )
        if f:
            if not f.lower().endswith(".gif"):
                f += ".gif"
            self.txt_create_dest.setText(f)

    def _on_run_create(self):
        if len(self._frame_paths) < 2:
            QMessageBox.warning(self, "Aviso", "Adicione pelo menos 2 imagens para compor o GIF animado.")
            return

        dest_str = self.txt_create_dest.text().strip()
        if not dest_str:
            self._on_browse_create_dest()
            dest_str = self.txt_create_dest.text().strip()
            if not dest_str:
                return

        fps = int(self.slider_fps.value())
        duration_ms = max(20, int(1000 / fps))
        loop = self.cmb_loop.currentData()
        out_path = Path(dest_str)
        frames = list(self._frame_paths)

        self.btn_create_run.setEnabled(False)
        self.lbl_create_status.setText("Compilando animação GIF...")

        def _worker(ctx):
            create_animated_gif(
                frames=frames,
                output_path=out_path,
                duration_ms=duration_ms,
                loop=loop,
            )
            return out_path

        def _done(res):
            self.btn_create_run.setEnabled(True)
            self.lbl_create_status.setText(f"GIF gravado com sucesso ({len(frames)} quadros)!")
            QMessageBox.information(self, "Sucesso", f"GIF animado gerado com sucesso em:\n{res}")

        def _error(err):
            self.btn_create_run.setEnabled(True)
            self.lbl_create_status.setText("Erro na compilação.")
            QMessageBox.critical(self, "Erro", f"Falha ao criar GIF: {err}")

        run_task(_worker, on_success=_done, on_error=_error)

    # Handlers da Aba 2
    def _on_browse_extract_src(self):
        f, _ = QFileDialog.getOpenFileName(self, "Selecionar GIF", "", "GIF (*.gif)")
        if f:
            self.txt_extract_src.setText(f)
            # Pré-carrega quadros para o player de inspeção
            try:
                with Image.open(f) as im:
                    n_frames = getattr(im, "n_frames", 1) or 1
                    pixmaps = []
                    import io
                    for i in range(n_frames):
                        im.seek(i)
                        buf = io.BytesIO()
                        im.convert("RGBA").save(buf, format="PNG")
                        p = QPixmap()
                        p.loadFromData(buf.getvalue())
                        pixmaps.append(p)
                    self.player_extract.set_frames_from_pixmaps(pixmaps)
            except Exception:
                pass

    def _on_browse_extract_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Saída")
        if d:
            self.txt_extract_dir.setText(d)

    def _on_run_extract(self):
        src_str = self.txt_extract_src.text().strip()
        dir_str = self.txt_extract_dir.text().strip()
        if not src_str or not Path(src_str).is_file():
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo GIF válido.")
            return
        if not dir_str:
            self._on_browse_extract_dir()
            dir_str = self.txt_extract_dir.text().strip()
            if not dir_str:
                return

        fmt_raw = self.cmb_extract_fmt.currentText().split()[0].lower()
        src_path = Path(src_str)
        out_dir = Path(dir_str)

        self.btn_extract_run.setEnabled(False)
        self.lbl_extract_status.setText("Extraindo quadros...")

        def _worker(ctx):
            return extract_gif_frames(src_path, out_dir, output_format=fmt_raw)

        def _done(res):
            self.btn_extract_run.setEnabled(True)
            self.lbl_extract_status.setText(f"{len(res)} quadros extraídos com sucesso!")
            QMessageBox.information(self, "Sucesso", f"{len(res)} quadros extraídos em:\n{out_dir}")

        def _error(err):
            self.btn_extract_run.setEnabled(True)
            self.lbl_extract_status.setText("Erro na extração.")
            QMessageBox.critical(self, "Erro", f"Falha ao extrair quadros: {err}")

        run_task(_worker, on_success=_done, on_error=_error)

"""
Ferramenta: Removedor de Fundo de Imagem (Transparência PNG).
Interface para seleção de imagens, escolha do modo de remoção (detecção automática, fundo branco ou chroma key) e download.
"""
from pathlib import Path
import subprocess
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.images.remove_bg.logic import remove_image_background


@register
class RemoveBgTool(Tool):
    id = "images.remove_bg"
    name = "Removedor de Fundo de Imagem"
    category = "Imagens"
    description = "Remoção de fundo sólido, branco ou chroma key com canal alfa transparente para salvar em PNG"
    keywords = ["fundo", "removebg", "transparência", "png", "alpha", "chromakey", "recorte", "imagem"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RemoveBgView(self, parent)


class RemoveBgView(QWidget):
    def __init__(self, tool: RemoveBgTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_src_path: Optional[Path] = None
        self._custom_color = (0, 255, 0)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Barra Superior: Origem e Destino
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.txt_src = QLineEdit()
        self.txt_src.setPlaceholderText("Selecione uma imagem de origem...")
        top_bar.addWidget(self.txt_src, 1)

        btn_browse_src = QPushButton("Procurar Imagem...")
        btn_browse_src.clicked.connect(self._on_browse_src)
        top_bar.addWidget(btn_browse_src)

        layout.addLayout(top_bar)

        # Configurações de Remoção
        grp_cfg = QGroupBox("Configurações de Remoção")
        cfg_layout = QHBoxLayout(grp_cfg)
        cfg_layout.setSpacing(12)

        cfg_layout.addWidget(QLabel("Modo:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Detecção Automática nos Cantos", "auto_corners")
        self.cmb_mode.addItem("Fundo Branco / Claro", "white")
        self.cmb_mode.addItem("Fundo Preto / Escuro", "black")
        self.cmb_mode.addItem("Cor Específica (Chroma Key)", "custom")
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        cfg_layout.addWidget(self.cmb_mode)

        self.btn_pick_color = QPushButton("Cor")
        self.btn_pick_color.setStyleSheet("background-color: #00FF00; color: #000; border: 1px solid #777;")
        self.btn_pick_color.clicked.connect(self._on_pick_custom_color)
        self.btn_pick_color.setVisible(False)
        cfg_layout.addWidget(self.btn_pick_color)

        cfg_layout.addWidget(QLabel("Tolerância:"))
        self.spin_tol = QSpinBox()
        self.spin_tol.setRange(5, 100)
        self.spin_tol.setValue(35)
        cfg_layout.addWidget(self.spin_tol)

        cfg_layout.addWidget(QLabel("Suavização:"))
        self.spin_feather = QSpinBox()
        self.spin_feather.setRange(0, 30)
        self.spin_feather.setValue(8)
        self.spin_feather.setSuffix(" px")
        cfg_layout.addWidget(self.spin_feather)

        cfg_layout.addStretch()
        layout.addWidget(grp_cfg)

        # Painel Central Dividido: Preview Original vs Preview Resultado
        split_layout = QHBoxLayout()
        split_layout.setSpacing(12)

        grp_orig = QGroupBox("Imagem Original")
        orig_layout = QVBoxLayout(grp_orig)
        self.scroll_orig = QScrollArea()
        self.scroll_orig.setWidgetResizable(True)
        self.lbl_orig = QLabel("Nenhuma imagem selecionada.")
        self.lbl_orig.setAlignment(Qt.AlignCenter)
        self.lbl_orig.setStyleSheet("color: #888890;")
        self.scroll_orig.setWidget(self.lbl_orig)
        orig_layout.addWidget(self.scroll_orig)
        split_layout.addWidget(grp_orig, 1)

        grp_res = QGroupBox("Resultado sem Fundo (PNG Transparente)")
        res_layout = QVBoxLayout(grp_res)
        self.scroll_res = QScrollArea()
        self.scroll_res.setWidgetResizable(True)
        # Fundo xadrez sutil para indicar transparência
        self.lbl_res = QLabel("O resultado aparecerá aqui.")
        self.lbl_res.setAlignment(Qt.AlignCenter)
        self.lbl_res.setStyleSheet("color: #888890; background-color: #2b2b32;")
        self.scroll_res.setWidget(self.lbl_res)
        res_layout.addWidget(self.scroll_res)
        split_layout.addWidget(grp_res, 1)

        layout.addLayout(split_layout)

        # Barra Inferior de Ações
        act_box = QHBoxLayout()
        self.lbl_status = QLabel("")
        act_box.addWidget(self.lbl_status)
        act_box.addStretch()

        self.btn_run = QPushButton("Remover Fundo Agora")
        self.btn_run.setProperty("class", "primary")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 6px 18px;")
        self.btn_run.clicked.connect(self._on_run_remove)
        act_box.addWidget(self.btn_run)

        self.btn_save = QPushButton("Salvar PNG Como...")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._on_save_as)
        act_box.addWidget(self.btn_save)

        layout.addLayout(act_box)

    def _on_mode_changed(self):
        is_custom = self.cmb_mode.currentData() == "custom"
        self.btn_pick_color.setVisible(is_custom)

    def _on_pick_custom_color(self):
        c = QColorDialog.getColor(QColor(self._custom_color[0], self._custom_color[1], self._custom_color[2]), self, "Cor do Fundo")
        if c.isValid():
            self._custom_color = (c.red(), c.green(), c.blue())
            hex_str = c.name()
            self.btn_pick_color.setStyleSheet(f"background-color: {hex_str}; border: 1px solid #777;")

    def _on_browse_src(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp);;Todos os Arquivos (*.*)"
        )
        if f:
            self._current_src_path = Path(f)
            self.txt_src.setText(f)
            pix = QPixmap(f)
            if not pix.isNull():
                self.lbl_orig.setPixmap(pix.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.btn_save.setEnabled(False)

    def _on_run_remove(self):
        if not self._current_src_path or not self._current_src_path.is_file():
            QMessageBox.warning(self, "Aviso", "Selecione uma imagem de origem válida.")
            return

        mode = self.cmb_mode.currentData()
        tol = self.spin_tol.value()
        feather = self.spin_feather.value()
        custom_c = self._custom_color if mode == "custom" else None

        temp_out = Path.home() / "AppData" / "Local" / "Temp" / f"{self._current_src_path.stem}_nobg.png"

        self.btn_run.setEnabled(False)
        self.lbl_status.setText("Removendo fundo e gerando canal de transparência...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, "Calculando distâncias de cor e opacidade...")
            out = remove_image_background(
                self._current_src_path,
                temp_out,
                mode=mode,
                custom_color=custom_c,
                tolerance=tol,
                feather=feather
            )
            ctx.progress(100, 100, "Concluído!")
            return out

        def _done(result, exc):
            self.btn_run.setEnabled(True)
            if exc:
                self.lbl_status.setText(f"Erro: {exc}")
                QMessageBox.critical(self, "Erro", f"Falha ao remover fundo: {exc}")
            else:
                self.lbl_status.setText("Fundo removido com sucesso!")
                pix_res = QPixmap(str(result))
                if not pix_res.isNull():
                    self.lbl_res.setPixmap(pix_res.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.btn_save.setEnabled(True)
                self._temp_nobg_path = result

        def _on_prog(cur, tot, msg):
            if msg:
                self.lbl_status.setText(msg)

        run_task(_work, on_done=_done, on_progress=_on_prog)

    def _on_save_as(self):
        if not hasattr(self, "_temp_nobg_path") or not self._temp_nobg_path.exists():
            return

        default_name = f"{self._current_src_path.stem}_transparente.png" if self._current_src_path else "sem_fundo.png"
        f, _ = QFileDialog.getSaveFileName(self, "Salvar Imagem sem Fundo", default_name, "Imagem PNG (*.png)")
        if f:
            import shutil
            shutil.copy2(self._temp_nobg_path, f)
            ans = QMessageBox.question(
                self,
                "Sucesso",
                f"Imagem com fundo transparente salva em:\n{f}\n\nDeseja abrir a imagem?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ans == QMessageBox.Yes and Path(f).exists():
                subprocess.Popen(f'explorer /select,"{f}"')

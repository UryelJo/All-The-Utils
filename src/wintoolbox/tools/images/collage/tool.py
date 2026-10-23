"""
Ferramenta: Colagens e Montagens de Imagens em Grade.
Interface para seleção de imagens, colunas, espaçamento, cor de fundo e geração de imagem combinada.
"""
from pathlib import Path
import subprocess
from typing import Optional
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.images.collage.logic import create_image_collage


@register
class ImageCollageTool(Tool):
    id = "images.collage"
    name = "Colagens e Montagens de Fotos"
    category = "Imagens"
    description = "Montagem de várias imagens em grade com controle de colunas, espaçamento, bordas e cor de fundo"
    keywords = ["colagem", "montagem", "grade", "grid", "fotos", "painel", "mosaico", "imagens"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ImageCollageView(self, parent)


class ImageCollageView(QWidget):
    def __init__(self, tool: ImageCollageTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._bg_color = (255, 255, 255)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Seleção de Imagens
        grp_imgs = QGroupBox("Imagens para a Colagem")
        imgs_layout = QHBoxLayout(grp_imgs)

        self.list_images = QListWidget()
        imgs_layout.addWidget(self.list_images, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        btn_add = QPushButton("Adicionar Fotos...")
        btn_add.setProperty("class", "primary")
        btn_add.clicked.connect(self._on_add_images)
        btn_col.addWidget(btn_add)

        btn_up = QPushButton("Mover para Cima")
        btn_up.clicked.connect(self._on_move_up)
        btn_col.addWidget(btn_up)

        btn_down = QPushButton("Mover para Baixo")
        btn_down.clicked.connect(self._on_move_down)
        btn_col.addWidget(btn_down)

        btn_remove = QPushButton("Remover Selecionadas")
        btn_remove.clicked.connect(self._on_remove_selected)
        btn_col.addWidget(btn_remove)

        btn_clear = QPushButton("Limpar Tudo")
        btn_clear.clicked.connect(self.list_images.clear)
        btn_col.addWidget(btn_clear)

        btn_col.addStretch()
        imgs_layout.addLayout(btn_col)
        layout.addWidget(grp_imgs)

        # 2. Configurações da Grade
        grp_cfg = QGroupBox("Configurações da Grade e Visual")
        cfg_layout = QHBoxLayout(grp_cfg)
        cfg_layout.setSpacing(12)

        cfg_layout.addWidget(QLabel("Colunas:"))
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 10)
        self.spin_cols.setValue(2)
        cfg_layout.addWidget(self.spin_cols)

        cfg_layout.addWidget(QLabel("Espaçamento:"))
        self.spin_spacing = QSpinBox()
        self.spin_spacing.setRange(0, 100)
        self.spin_spacing.setValue(12)
        self.spin_spacing.setSuffix(" px")
        cfg_layout.addWidget(self.spin_spacing)

        cfg_layout.addWidget(QLabel("Encaixe:"))
        self.cmb_fit = QComboBox()
        self.cmb_fit.addItem("Preencher e Cortar (Quadrado)", "crop")
        self.cmb_fit.addItem("Ajustar Completo (Com Bordas)", "fit")
        cfg_layout.addWidget(self.cmb_fit)

        cfg_layout.addWidget(QLabel("Cor de Fundo:"))
        self.btn_bg_color = QPushButton("Branco")
        self.btn_bg_color.setStyleSheet("background-color: #FFFFFF; color: #000000; border: 1px solid #777;")
        self.btn_bg_color.clicked.connect(self._on_pick_color)
        cfg_layout.addWidget(self.btn_bg_color)

        cfg_layout.addStretch()
        layout.addWidget(grp_cfg)

        # 3. Destino
        dest_box = QHBoxLayout()
        dest_box.addWidget(QLabel("Salvar Colagem em:"))
        self.txt_dest = QLineEdit()
        self.txt_dest.setPlaceholderText("Selecione onde salvar o arquivo resultante (PNG ou JPEG)...")
        dest_box.addWidget(self.txt_dest, 1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_dest)
        dest_box.addWidget(btn_browse)
        layout.addLayout(dest_box)

        # Barra de Ações
        act_box = QHBoxLayout()
        self.lbl_status = QLabel("")
        act_box.addWidget(self.lbl_status)
        act_box.addStretch()

        self.btn_run = QPushButton("Gerar Colagem")
        self.btn_run.setProperty("class", "primary")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 6px 18px;")
        self.btn_run.clicked.connect(self._on_run_collage)
        act_box.addWidget(self.btn_run)
        layout.addLayout(act_box)

    def _on_add_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Fotos para Colagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp);;Todos os Arquivos (*.*)"
        )
        for f in files:
            self.list_images.addItem(f)

    def _on_move_up(self):
        row = self.list_images.currentRow()
        if row > 0:
            item = self.list_images.takeItem(row)
            self.list_images.insertItem(row - 1, item)
            self.list_images.setCurrentRow(row - 1)

    def _on_move_down(self):
        row = self.list_images.currentRow()
        if row < self.list_images.count() - 1:
            item = self.list_images.takeItem(row)
            self.list_images.insertItem(row + 1, item)
            self.list_images.setCurrentRow(row + 1)

    def _on_remove_selected(self):
        for item in self.list_images.selectedItems():
            self.list_images.takeItem(self.list_images.row(item))

    def _on_pick_color(self):
        init_color = QColor(self._bg_color[0], self._bg_color[1], self._bg_color[2])
        color = QColorDialog.getColor(init_color, self, "Escolher Cor de Fundo da Colagem")
        if color.isValid():
            self._bg_color = (color.red(), color.green(), color.blue())
            hex_str = color.name()
            # Ajusta contraste da fonte
            text_color = "#000000" if (color.red() * 0.299 + color.green() * 0.587 + color.blue() * 0.114) > 186 else "#FFFFFF"
            self.btn_bg_color.setText(hex_str.upper())
            self.btn_bg_color.setStyleSheet(f"background-color: {hex_str}; color: {text_color}; border: 1px solid #888;")

    def _on_browse_dest(self):
        f, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Colagem",
            "colagem.png",
            "Imagem PNG (*.png);;Imagem JPEG (*.jpg)"
        )
        if f:
            self.txt_dest.setText(f)

    def _on_run_collage(self):
        count = self.list_images.count()
        if count < 2:
            QMessageBox.warning(self, "Aviso", "Adicione pelo menos 2 imagens para montar a colagem.")
            return

        dest = self.txt_dest.text().strip()
        if not dest:
            QMessageBox.warning(self, "Aviso", "Informe o arquivo de destino para salvar a colagem.")
            return

        image_paths = [Path(self.list_images.item(i).text()) for i in range(count)]
        cols = self.spin_cols.value()
        spacing = self.spin_spacing.value()
        fit_mode = self.cmb_fit.currentData()
        bg_col = self._bg_color

        self.btn_run.setEnabled(False)
        self.lbl_status.setText("Montando e renderizando colagem...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, f"Processando {count} imagens na grade...")
            out = create_image_collage(
                image_paths,
                Path(dest),
                cols=cols,
                spacing=spacing,
                bg_color=bg_col,
                fit_mode=fit_mode
            )
            ctx.progress(100, 100, "Concluído!")
            return out

        def _done(result, exc):
            self.btn_run.setEnabled(True)
            if exc:
                self.lbl_status.setText(f"Erro: {exc}")
                QMessageBox.critical(self, "Erro", f"Falha ao criar colagem: {exc}")
            else:
                self.lbl_status.setText("Colagem gerada com sucesso!")
                ans = QMessageBox.question(
                    self,
                    "Sucesso",
                    f"Colagem de {count} fotos salva com sucesso em:\n{result}\n\nDeseja abrir a imagem agora?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes and Path(result).exists():
                    subprocess.Popen(f'explorer /select,"{result}"')

        def _on_prog(cur, tot, msg):
            if msg:
                self.lbl_status.setText(msg)

        run_task(_work, on_done=_done, on_progress=_on_prog)

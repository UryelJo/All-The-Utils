"""
Ferramenta: Montador e Extrator de GIFs Animados.
Interface gráfica em abas para criar animações a partir de imagens e extrair frames.
"""
from pathlib import Path
import subprocess
from typing import Optional
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.images.gif_tools.logic import (
    create_animated_gif, extract_gif_frames
)


@register
class GifToolsTool(Tool):
    id = "images.gif_tools"
    name = "Montador e Extrator de GIF"
    category = "Imagens"
    description = "Criação de GIFs animados a partir de fotos com controle de FPS/duração e extração de quadros"
    keywords = ["gif", "animação", "frames", "quadros", "montador", "extrair", "loop", "imagens"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return GifToolsView(self, parent)


class GifToolsView(QWidget):
    def __init__(self, tool: GifToolsTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
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
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        # Lista de Imagens
        grp_list = QGroupBox("Sequência de Imagens para o GIF")
        list_layout = QHBoxLayout(grp_list)

        self.list_create = QListWidget()
        list_layout.addWidget(self.list_create, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        btn_add = QPushButton("Adicionar Imagens...")
        btn_add.setProperty("class", "primary")
        btn_add.clicked.connect(self._on_add_create_images)
        btn_col.addWidget(btn_add)

        btn_up = QPushButton("Mover para Cima")
        btn_up.clicked.connect(self._on_create_up)
        btn_col.addWidget(btn_up)

        btn_down = QPushButton("Mover para Baixo")
        btn_down.clicked.connect(self._on_create_down)
        btn_col.addWidget(btn_down)

        btn_remove = QPushButton("Remover Selecionadas")
        btn_remove.clicked.connect(self._on_create_remove)
        btn_col.addWidget(btn_remove)

        btn_clear = QPushButton("Limpar Tudo")
        btn_clear.clicked.connect(self.list_create.clear)
        btn_col.addWidget(btn_clear)

        btn_col.addStretch()
        list_layout.addLayout(btn_col)
        layout.addWidget(grp_list)

        # Configurações do GIF
        grp_cfg = QGroupBox("Configurações da Animação")
        cfg_layout = QHBoxLayout(grp_cfg)

        cfg_layout.addWidget(QLabel("Duração por Frame:"))
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(20, 5000)
        self.spin_duration.setValue(200)
        self.spin_duration.setSuffix(" ms")
        cfg_layout.addWidget(self.spin_duration)

        cfg_layout.addSpacing(16)
        cfg_layout.addWidget(QLabel("Repetições (Loop):"))
        self.cmb_loop = QComboBox()
        self.cmb_loop.addItem("Infinito (Padrão)", 0)
        self.cmb_loop.addItem("Apenas 1 vez", 1)
        self.cmb_loop.addItem("3 vezes", 3)
        self.cmb_loop.addItem("5 vezes", 5)
        cfg_layout.addWidget(self.cmb_loop)

        cfg_layout.addStretch()
        layout.addWidget(grp_cfg)

        # Destino
        dest_box = QHBoxLayout()
        dest_box.addWidget(QLabel("Salvar GIF em:"))
        self.txt_create_dest = QLineEdit()
        self.txt_create_dest.setPlaceholderText("Selecione onde salvar o arquivo .gif...")
        dest_box.addWidget(self.txt_create_dest, 1)

        btn_browse_dest = QPushButton("Procurar...")
        btn_browse_dest.clicked.connect(self._on_browse_create_dest)
        dest_box.addWidget(btn_browse_dest)
        layout.addLayout(dest_box)

        # Ação
        act_box = QHBoxLayout()
        self.lbl_create_status = QLabel("")
        act_box.addWidget(self.lbl_create_status)
        act_box.addStretch()

        self.btn_create_run = QPushButton("Compilar e Gerar GIF")
        self.btn_create_run.setProperty("class", "primary")
        self.btn_create_run.setStyleSheet("font-weight: bold; padding: 6px 18px;")
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
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        grp_src = QGroupBox("Arquivo GIF de Origem")
        src_layout = QHBoxLayout(grp_src)
        self.txt_extract_src = QLineEdit()
        self.txt_extract_src.setPlaceholderText("Selecione o arquivo .gif animado...")
        src_layout.addWidget(self.txt_extract_src, 1)

        btn_browse_gif = QPushButton("Selecionar GIF...")
        btn_browse_gif.clicked.connect(self._on_browse_extract_src)
        src_layout.addWidget(btn_browse_gif)
        layout.addWidget(grp_src)

        grp_out = QGroupBox("Destino dos Frames")
        out_layout = QHBoxLayout(grp_out)
        self.txt_extract_dir = QLineEdit()
        self.txt_extract_dir.setPlaceholderText("Selecione a pasta onde os quadros serão salvos...")
        out_layout.addWidget(self.txt_extract_dir, 1)

        btn_browse_dir = QPushButton("Selecionar Pasta...")
        btn_browse_dir.clicked.connect(self._on_browse_extract_dir)
        out_layout.addWidget(btn_browse_dir)

        out_layout.addSpacing(12)
        out_layout.addWidget(QLabel("Formato:"))
        self.cmb_extract_fmt = QComboBox()
        self.cmb_extract_fmt.addItems(["PNG", "JPEG", "WEBP", "BMP"])
        out_layout.addWidget(self.cmb_extract_fmt)
        layout.addWidget(grp_out)

        # Ação
        act_box = QHBoxLayout()
        self.lbl_extract_status = QLabel("")
        act_box.addWidget(self.lbl_extract_status)
        act_box.addStretch()

        self.btn_extract_run = QPushButton("Extrair Todos os Frames")
        self.btn_extract_run.setProperty("class", "primary")
        self.btn_extract_run.setStyleSheet("font-weight: bold; padding: 6px 18px;")
        self.btn_extract_run.clicked.connect(self._on_run_extract)
        act_box.addWidget(self.btn_extract_run)
        layout.addLayout(act_box)

        layout.addStretch()
        return tab

    # Handlers Aba 1
    def _on_add_create_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Imagens para o GIF",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp);;Todos os Arquivos (*.*)"
        )
        for f in files:
            self.list_create.addItem(f)

    def _on_create_up(self):
        row = self.list_create.currentRow()
        if row > 0:
            item = self.list_create.takeItem(row)
            self.list_create.insertItem(row - 1, item)
            self.list_create.setCurrentRow(row - 1)

    def _on_create_down(self):
        row = self.list_create.currentRow()
        if row < self.list_create.count() - 1:
            item = self.list_create.takeItem(row)
            self.list_create.insertItem(row + 1, item)
            self.list_create.setCurrentRow(row + 1)

    def _on_create_remove(self):
        for item in self.list_create.selectedItems():
            self.list_create.takeItem(self.list_create.row(item))

    def _on_browse_create_dest(self):
        f, _ = QFileDialog.getSaveFileName(self, "Salvar GIF", "animacao.gif", "Arquivo GIF (*.gif)")
        if f:
            self.txt_create_dest.setText(f)

    def _on_run_create(self):
        count = self.list_create.count()
        if count < 2:
            QMessageBox.warning(self, "Aviso", "Adicione pelo menos 2 imagens para compor o GIF animado.")
            return

        dest = self.txt_create_dest.text().strip()
        if not dest:
            QMessageBox.warning(self, "Aviso", "Informe o caminho de destino do arquivo GIF.")
            return

        image_paths = [Path(self.list_create.item(i).text()) for i in range(count)]
        duration = self.spin_duration.value()
        loop = self.cmb_loop.currentData()

        self.btn_create_run.setEnabled(False)
        self.lbl_create_status.setText("Processando imagens e compilando GIF...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, f"Processando {count} imagens...")
            out = create_animated_gif(image_paths, Path(dest), frame_duration_ms=duration, loop=loop)
            ctx.progress(100, 100, "Concluído!")
            return out

        def _done(result, exc):
            self.btn_create_run.setEnabled(True)
            if exc:
                self.lbl_create_status.setText(f"Erro: {exc}")
                QMessageBox.critical(self, "Erro", f"Falha ao gerar GIF: {exc}")
            else:
                self.lbl_create_status.setText("GIF gerado com sucesso!")
                ans = QMessageBox.question(
                    self,
                    "Sucesso",
                    f"GIF animado gerado com sucesso!\nArquivo: {result}\n\nDeseja abrir a pasta do arquivo?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes:
                    subprocess.Popen(f'explorer /select,"{result}"')

        def _on_prog(cur, tot, msg):
            if msg:
                self.lbl_create_status.setText(msg)

        run_task(_work, on_done=_done, on_progress=_on_prog)

    # Handlers Aba 2
    def _on_browse_extract_src(self):
        f, _ = QFileDialog.getOpenFileName(self, "Selecionar GIF", "", "Arquivo GIF (*.gif)")
        if f:
            self.txt_extract_src.setText(f)
            if not self.txt_extract_dir.text():
                p = Path(f)
                self.txt_extract_dir.setText(str(p.parent / f"{p.stem}_frames"))

    def _on_browse_extract_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Salvar Quadros")
        if d:
            self.txt_extract_dir.setText(d)

    def _on_run_extract(self):
        src = self.txt_extract_src.text().strip()
        out_dir = self.txt_extract_dir.text().strip()
        if not src or not Path(src).is_file():
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo GIF válido.")
            return
        if not out_dir:
            QMessageBox.warning(self, "Aviso", "Selecione a pasta de saída para os frames.")
            return

        fmt = self.cmb_extract_fmt.currentText()
        self.btn_extract_run.setEnabled(False)
        self.lbl_extract_status.setText("Extraindo quadros do GIF...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, "Lendo quadros do GIF...")
            frames = extract_gif_frames(Path(src), Path(out_dir), output_format=fmt)
            ctx.progress(100, 100, "Extração concluída!")
            return frames

        def _done(result, exc):
            self.btn_extract_run.setEnabled(True)
            if exc:
                self.lbl_extract_status.setText(f"Erro: {exc}")
                QMessageBox.critical(self, "Erro", f"Falha na extração de frames: {exc}")
            else:
                count = len(result)
                self.lbl_extract_status.setText(f"{count} quadros extraídos com sucesso!")
                ans = QMessageBox.question(
                    self,
                    "Sucesso",
                    f"{count} quadros extraídos com sucesso na pasta:\n{out_dir}\n\nDeseja abrir a pasta?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes and Path(out_dir).exists():
                    subprocess.Popen(f'explorer "{out_dir}"')

        def _on_prog(cur, tot, msg):
            if msg:
                self.lbl_extract_status.setText(msg)

        run_task(_work, on_done=_done, on_progress=_on_prog)

"""
Ferramenta: Organizador Automático de Pastas (Auto Folder Organizer).
Organiza arquivos em lote por categorias, extensões ou datas com simulação prévia (Dry-Run).
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QRadioButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, batch_table_update, enable_sorting_on_table
)
from .logic import OrganizeAction, execute_organization, plan_organization


@register
class AutoOrganizeTool(Tool):
    id = "files.auto_organize"
    name = "Organizador Automático de Pastas"
    category = "Arquivos e Pastas"
    description = "Organização inteligente de arquivos soltos: agrupa automaticamente por tipo (Imagens, Documentos, Vídeos, Áudio, Compactados) ou data de modificação."
    keywords = ["organizar", "pastas", "arquivos", "extensão", "data", "categorias", "limpeza", "downloads"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return AutoOrganizeView(self, parent)


class AutoOrganizeView(QWidget):
    def __init__(self, tool: AutoOrganizeTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.planned_actions: List[OrganizeAction] = []
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Card de Seleção e Configuração
        card = QFrame()
        card.setProperty("class", "card")
        l_card = QVBoxLayout(card)
        l_card.setSpacing(10)

        # Linha 1: Pasta Alvo
        r_path = QHBoxLayout()
        r_path.addWidget(QLabel("Pasta a ser organizada:"))
        self.txt_path = QLineEdit(str(Path.home() / "Downloads"))
        r_path.addWidget(self.txt_path, stretch=1)
        btn_browse = QPushButton("Selecionar Pasta...")
        btn_browse.clicked.connect(self._browse_folder)
        r_path.addWidget(btn_browse)
        l_card.addLayout(r_path)

        # Linha 2: Modo e Opções
        r_opts = QHBoxLayout()
        r_opts.addWidget(QLabel("Critério de Agrupamento:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Por Categorias (Imagens, Vídeos, Documentos...)", "category")
        self.cmb_mode.addItem("Por Extensão Específica (.PNG, .PDF, .MP4...)", "extension")
        self.cmb_mode.addItem("Por Data de Modificação (Ano / Mês)", "date_month")
        self.cmb_mode.addItem("Por Ano de Modificação (Ano)", "date_year")
        r_opts.addWidget(self.cmb_mode, stretch=1)

        self.chk_recursive = QCheckBox("Incluir subpastas (Recursivo)")
        r_opts.addWidget(self.chk_recursive)
        l_card.addLayout(r_opts)

        # Linha 3: Mover vs Copiar
        r_op = QHBoxLayout()
        r_op.addWidget(QLabel("Ação nos arquivos:"))
        self.rb_move = QRadioButton("Mover arquivos (Recomendado para limpeza)")
        self.rb_move.setChecked(True)
        self.rb_copy = QRadioButton("Copiar arquivos (Preservar pasta original)")
        self.btn_group_op = QButtonGroup()
        self.btn_group_op.addButton(self.rb_move)
        self.btn_group_op.addButton(self.rb_copy)
        r_op.addWidget(self.rb_move)
        r_op.addWidget(self.rb_copy)
        r_op.addStretch()
        l_card.addLayout(r_op)

        # Linha 4: Botões de Ação
        r_btns = QHBoxLayout()
        self.btn_simulate = QPushButton("1. Simular Organização (Ver Prévia)")
        self.btn_simulate.setProperty("class", "primary")
        self.btn_simulate.clicked.connect(self._simulate)
        r_btns.addWidget(self.btn_simulate)

        self.btn_execute = QPushButton("2. Executar Organização")
        self.btn_execute.setEnabled(False)
        self.btn_execute.clicked.connect(self._execute)
        r_btns.addWidget(self.btn_execute)
        r_btns.addStretch()
        l_card.addLayout(r_btns)

        layout.addWidget(card)

        # Barra de Progresso e Status
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setVisible(False)
        layout.addWidget(self.prog_bar)

        self.lbl_status = QLabel("Selecione a pasta e clique em 'Simular' para inspecionar os destinos.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        # Tabela de Prévia
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Arquivo Original", "Destino Planejado", "Regra Aplicada", "Status"])
        enable_sorting_on_table(self.table)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _browse_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Organizar", self.txt_path.text())
        if f:
            self.txt_path.setText(f)
            self.btn_execute.setEnabled(False)
            self.table.setRowCount(0)
            self.lbl_status.setText("Pasta alterada. Clique em 'Simular' para atualizar a prévia.")

    def _simulate(self):
        folder_str = self.txt_path.text().strip()
        folder = Path(folder_str)
        if not folder.is_dir():
            QMessageBox.warning(self, "Aviso", "A pasta informada não existe ou é inválida.")
            return

        mode = self.cmb_mode.currentData()
        recursive = self.chk_recursive.isChecked()

        self.btn_simulate.setEnabled(False)
        self.lbl_status.setText("Analisando arquivos e calculando destinos...")

        def worker(ctx):
            return plan_organization(folder, mode=mode, recursive=recursive)

        def on_done(actions: List[OrganizeAction]):
            self.btn_simulate.setEnabled(True)
            self.planned_actions = actions
            with batch_table_update(self.table):
                self.table.setRowCount(len(actions))
                for row, act in enumerate(actions):
                    self.table.setItem(row, 0, SmartTableWidgetItem(act.source_path.name, user_data=act))
                    self.table.setItem(row, 1, SmartTableWidgetItem(str(act.dest_path)))
                    self.table.setItem(row, 2, SmartTableWidgetItem(act.category_label))
                    self.table.setItem(row, 3, SmartTableWidgetItem(act.status))

            count = len(actions)
            if count > 0:
                self.btn_execute.setEnabled(True)
                self.lbl_status.setText(f"Simulação concluída! {count} arquivo(s) serão organizados. Revise a lista e clique em 'Executar'.")
            else:
                self.btn_execute.setEnabled(False)
                self.lbl_status.setText("Nenhum arquivo encontrado para organizar nesta pasta.")

        self.runner.start_task(worker, on_finished=on_done)

    def _execute(self):
        if not self.planned_actions:
            return

        move_files = self.rb_move.isChecked()
        act_verb = "mover" if move_files else "copiar"
        reply = QMessageBox.question(
            self,
            "Confirmar Organização",
            f"Deseja realmente {act_verb} {len(self.planned_actions)} arquivo(s)?\n"
            "Essa operação reorganizará os arquivos nas pastas correspondentes.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_simulate.setEnabled(False)
        self.btn_execute.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)

        def worker(ctx):
            return execute_organization(
                self.planned_actions,
                move_files=move_files,
                progress_cb=ctx.on_progress
            )

        def on_prog(cur, tot, msg):
            pct = int((cur / tot) * 100) if tot > 0 else 0
            self.prog_bar.setValue(pct)
            self.lbl_status.setText(f"Organizando ({cur}/{tot}): {msg}")

        def on_done(res):
            self.btn_simulate.setEnabled(True)
            self.btn_execute.setEnabled(False)
            self.prog_bar.setVisible(False)
            succ, fail = res

            # Atualiza status na tabela preservando ordenação
            for row in range(self.table.rowCount()):
                item_0 = self.table.item(row, 0)
                act = item_0.data(Qt.UserRole) if item_0 else None
                if act:
                    status_text = act.status if not act.error else f"Erro: {act.error}"
                    item = SmartTableWidgetItem(status_text)
                    if act.error:
                        item.setForeground(Qt.red)
                    else:
                        item.setForeground(Qt.darkGreen)
                    self.table.setItem(row, 3, item)

            self.lbl_status.setText(f"Concluído! {succ} arquivo(s) processados com sucesso. Falhas: {fail}.")
            QMessageBox.information(
                self,
                "Organização Concluída",
                f"Processo finalizado com sucesso!\n\nSucessos: {succ}\nFalhas: {fail}"
            )

        self.runner.start_task(worker, on_progress=on_prog, on_finished=on_done)

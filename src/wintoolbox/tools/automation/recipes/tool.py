"""
Interface de usuário para o Encadeador de Ferramentas e Receitas de Automação.
"""
import os
import uuid
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, get_all_tools, register
from wintoolbox.tools.automation.recipes.logic import (
    Recipe,
    RecipeStep,
    execute_pipeline,
    load_recipes_json,
    save_recipes_json,
)


def get_default_recipes_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".wintoolbox", "recipes.json")


@register
class RecipesTool(Tool):
    """Mecanismo de encadeamento de ferramentas do WinToolbox em receitas reutilizáveis."""

    id = "automation.recipes"
    name = "Receitas de Automação (Pipelines Multi-Ferramentas)"
    description = "Crie pipelines reutilizáveis encadeando múltiplas ferramentas (ex: Converter -> Otimizar -> Renomear)."
    category = "Automação"

    def __init__(self):
        super().__init__()
        self.recipes_file = get_default_recipes_path()
        self.recipes: List[Recipe] = load_recipes_json(self.recipes_file)
        if not self.recipes:
            self._create_sample_recipes()

    def _create_sample_recipes(self) -> None:
        r1 = Recipe(
            id=str(uuid.uuid4()),
            name="Otimização Completa de Imagens Web",
            description="Converte imagens para WebP, otimiza o peso e renomeia para publicação web.",
            steps=[
                RecipeStep("images.convert", "Converter Imagens (WebP)"),
                RecipeStep("images.compress", "Otimizar Compressão"),
                RecipeStep("files.batch_rename", "Renomear Padronizado"),
            ]
        )
        r2 = Recipe(
            id=str(uuid.uuid4()),
            name="Preparação de Mídia e Áudio",
            description="Remove silêncios de gravações e ajusta velocidade e volume.",
            steps=[
                RecipeStep("media.silence_remover", "Remover Silêncio de Áudio"),
                RecipeStep("media.speed_changer", "Ajustar Velocidade e Pitch"),
            ]
        )
        self.recipes = [r1, r2]
        save_recipes_json(self.recipes, self.recipes_file)

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        title = QLabel("Receitas de Automação & Pipelines de Processamento")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Encadeie ferramentas do WinToolbox em um fluxo contínuo onde a saída de uma etapa é a entrada da próxima."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: Lista de Receitas
        left_widget = QWidget()
        v_left = QVBoxLayout(left_widget)
        v_left.setContentsMargins(0, 0, 0, 0)
        v_left.setSpacing(8)

        v_left.addWidget(QLabel("<b>Receitas Criadas:</b>"))
        self.list_recipes = QListWidget()
        self.list_recipes.currentRowChanged.connect(self._on_recipe_selected)
        v_left.addWidget(self.list_recipes, 1)

        btn_box = QHBoxLayout()
        btn_add = QPushButton("+ Nova")
        btn_add.clicked.connect(self._on_new_recipe)
        btn_del = QPushButton("Excluir")
        btn_del.clicked.connect(self._on_delete_recipe)
        btn_box.addWidget(btn_add)
        btn_box.addWidget(btn_del)
        v_left.addLayout(btn_box)

        splitter.addWidget(left_widget)

        # Painel Direito: Editor da Receita Selecionada e Execução
        right_widget = QWidget()
        v_right = QVBoxLayout(right_widget)
        v_right.setContentsMargins(10, 0, 0, 0)
        v_right.setSpacing(10)

        form_meta = QFormLayout()
        self.txt_name = QLineEdit()
        self.txt_name.textChanged.connect(self._on_meta_changed)
        form_meta.addRow("Nome da Receita:", self.txt_name)

        self.txt_desc = QLineEdit()
        self.txt_desc.textChanged.connect(self._on_meta_changed)
        form_meta.addRow("Descrição:", self.txt_desc)
        v_right.addLayout(form_meta)

        v_right.addWidget(QLabel("<b>Sequência de Etapas (Pipeline):</b>"))
        self.tbl_steps = QTableWidget(0, 2)
        self.tbl_steps.setHorizontalHeaderLabels(["Ordem & Nome da Ferramenta", "Identificador"])
        self.tbl_steps.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_steps.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tbl_steps.setColumnWidth(1, 180)
        self.tbl_steps.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_steps.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v_right.addWidget(self.tbl_steps, 1)

        step_btn_box = QHBoxLayout()
        btn_add_step = QPushButton("+ Adicionar Ferramenta ao Pipeline")
        btn_add_step.clicked.connect(self._on_add_step)
        btn_up = QPushButton("▲ Subir")
        btn_up.clicked.connect(self._on_move_step_up)
        btn_down = QPushButton("▼ Descer")
        btn_down.clicked.connect(self._on_move_step_down)
        btn_rem_step = QPushButton("Remover Etapa")
        btn_rem_step.clicked.connect(self._on_remove_step)
        step_btn_box.addWidget(btn_add_step)
        step_btn_box.addWidget(btn_up)
        step_btn_box.addWidget(btn_down)
        step_btn_box.addWidget(btn_rem_step)
        v_right.addLayout(step_btn_box)

        # Painel de Execução
        exec_frame = QFrame()
        exec_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 12px; }"
        )
        v_exec = QVBoxLayout(exec_frame)
        v_exec.setSpacing(8)

        v_exec.addWidget(QLabel("<b>Executar esta Receita em Lote:</b>"))
        h_files = QHBoxLayout()
        self.lbl_selected_files = QLabel("Nenhum arquivo de entrada selecionado.")
        self.lbl_selected_files.setStyleSheet("color: #888888;")
        btn_select_files = QPushButton("Selecionar Arquivos...")
        btn_select_files.clicked.connect(self._on_select_files)
        h_files.addWidget(self.lbl_selected_files, 1)
        h_files.addWidget(btn_select_files)
        v_exec.addLayout(h_files)

        self.btn_run_pipeline = QPushButton("▶ Executar Pipeline de Automação")
        self.btn_run_pipeline.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 8px; background-color: #16a34a; color: white;"
        )
        self.btn_run_pipeline.clicked.connect(self._on_run_pipeline)
        v_exec.addWidget(self.btn_run_pipeline)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        v_exec.addWidget(self.progress_bar)

        self.txt_log = QTextEdit()
        self.txt_log.setMaximumHeight(90)
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("Relatório de execução...")
        v_exec.addWidget(self.txt_log)

        v_right.addWidget(exec_frame)

        splitter.addWidget(right_widget)
        splitter.setSizes([260, 580])
        layout.addWidget(splitter, 1)

        self.input_files_to_run: List[str] = []
        self._refresh_recipes_list()
        if self.recipes:
            self.list_recipes.setCurrentRow(0)

        return widget

    def _refresh_recipes_list(self) -> None:
        self.list_recipes.clear()
        for r in self.recipes:
            it = QListWidgetItem(r.name)
            self.list_recipes.addItem(it)

    def _on_recipe_selected(self, index: int) -> None:
        if 0 <= index < len(self.recipes):
            r = self.recipes[index]
            self.txt_name.setText(r.name)
            self.txt_desc.setText(r.description)
            self._refresh_steps_table(r)

    def _refresh_steps_table(self, recipe: Recipe) -> None:
        self.tbl_steps.setRowCount(len(recipe.steps))
        for i, s in enumerate(recipe.steps):
            it_name = QTableWidgetItem(f"Passo {i+1}: {s.tool_name}")
            it_id = QTableWidgetItem(s.tool_id)
            self.tbl_steps.setItem(i, 0, it_name)
            self.tbl_steps.setItem(i, 1, it_id)

    def _on_meta_changed(self) -> None:
        idx = self.list_recipes.currentRow()
        if 0 <= idx < len(self.recipes):
            r = self.recipes[idx]
            r.name = self.txt_name.text().strip() or "Receita Sem Nome"
            r.description = self.txt_desc.text().strip()
            self.list_recipes.item(idx).setText(r.name)
            save_recipes_json(self.recipes, self.recipes_file)

    def _on_new_recipe(self) -> None:
        new_r = Recipe(
            id=str(uuid.uuid4()),
            name=f"Nova Receita {len(self.recipes) + 1}",
            description="Descrição do pipeline de processamento.",
            steps=[]
        )
        self.recipes.append(new_r)
        save_recipes_json(self.recipes, self.recipes_file)
        self._refresh_recipes_list()
        self.list_recipes.setCurrentRow(len(self.recipes) - 1)

    def _on_delete_recipe(self) -> None:
        idx = self.list_recipes.currentRow()
        if 0 <= idx < len(self.recipes):
            del self.recipes[idx]
            save_recipes_json(self.recipes, self.recipes_file)
            self._refresh_recipes_list()
            if self.recipes:
                self.list_recipes.setCurrentRow(0)

    def _on_add_step(self) -> None:
        idx = self.list_recipes.currentRow()
        if not (0 <= idx < len(self.recipes)):
            return

        # Pop-up de seleção de ferramenta registrada
        dlg = QDialog()
        dlg.setWindowTitle("Selecionar Ferramenta para a Etapa")
        dlg.resize(400, 150)
        v = QVBoxLayout(dlg)
        f = QFormLayout()

        cmb = QComboBox()
        # Popula com as ferramentas registradas
        all_tools = get_all_tools()
        for t in all_tools:
            cmb.addItem(f"{t.name} ({t.id})", (t.id, t.name))
        f.addRow("Ferramenta:", cmb)
        v.addLayout(f)

        btn_ok = QPushButton("Adicionar ao Pipeline")
        btn_ok.clicked.connect(dlg.accept)
        v.addWidget(btn_ok)

        if dlg.exec():
            t_id, t_name = cmb.currentData()
            self.recipes[idx].steps.append(RecipeStep(t_id, t_name))
            save_recipes_json(self.recipes, self.recipes_file)
            self._refresh_steps_table(self.recipes[idx])

    def _on_move_step_up(self) -> None:
        idx = self.list_recipes.currentRow()
        row = self.tbl_steps.currentRow()
        if 0 <= idx < len(self.recipes) and row > 0:
            steps = self.recipes[idx].steps
            steps[row - 1], steps[row] = steps[row], steps[row - 1]
            save_recipes_json(self.recipes, self.recipes_file)
            self._refresh_steps_table(self.recipes[idx])
            self.tbl_steps.selectRow(row - 1)

    def _on_move_step_down(self) -> None:
        idx = self.list_recipes.currentRow()
        row = self.tbl_steps.currentRow()
        if 0 <= idx < len(self.recipes) and 0 <= row < len(self.recipes[idx].steps) - 1:
            steps = self.recipes[idx].steps
            steps[row + 1], steps[row] = steps[row], steps[row + 1]
            save_recipes_json(self.recipes, self.recipes_file)
            self._refresh_steps_table(self.recipes[idx])
            self.tbl_steps.selectRow(row + 1)

    def _on_remove_step(self) -> None:
        idx = self.list_recipes.currentRow()
        row = self.tbl_steps.currentRow()
        if 0 <= idx < len(self.recipes) and 0 <= row < len(self.recipes[idx].steps):
            del self.recipes[idx].steps[row]
            save_recipes_json(self.recipes, self.recipes_file)
            self._refresh_steps_table(self.recipes[idx])

    def _on_select_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(None, "Selecionar Arquivos para o Pipeline")
        if paths:
            self.input_files_to_run = paths
            self.lbl_selected_files.setText(f"{len(paths)} arquivo(s) selecionado(s)")

    def _on_run_pipeline(self) -> None:
        idx = self.list_recipes.currentRow()
        if not (0 <= idx < len(self.recipes)):
            return

        recipe = self.recipes[idx]
        if not recipe.steps:
            QMessageBox.warning(None, "Pipeline Vazio", "Adicione pelo menos uma etapa na receita.")
            return

        if not self.input_files_to_run:
            QMessageBox.information(None, "Arquivos Necessários", "Selecione ao menos um arquivo de entrada.")
            return

        self.txt_log.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(recipe.steps))
        self.progress_bar.setValue(0)

        def mock_process(t_id: str, path: str, options: dict) -> str:
            # Em execução real, delega para a ferramenta correspondente se implementada
            return path

        def prog_cb(step_i: int, total: int, msg: str) -> None:
            self.progress_bar.setValue(step_i)
            self.txt_log.append(f"[{step_i}/{total}] {msg}")

        res = execute_pipeline(recipe, self.input_files_to_run, mock_process, prog_cb)
        self.txt_log.append(
            f"✔ Pipeline '{res['recipe_name']}' concluído em {res['duration_seconds']}s com {len(res['final_files'])} arquivo(s)."
        )

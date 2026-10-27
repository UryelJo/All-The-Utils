"""
Interface gráfica do Executor de Macros e Automações (automation.macro_runner).
"""
import ctypes
import os
from typing import Any, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QProgressBar, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import TaskContext, Tool, ToolResult, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.automation.macro_runner.logic import (
    MacroDefinition, MacroStep, get_sample_presets, load_macro,
    run_macro, save_macro
)
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, batch_table_update, enable_sorting_on_table
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("automation.macro_runner.ui")


@register
class MacroRunnerTool(Tool):
    id = "automation.macro_runner"
    name = "Executor de Macros"
    category = "Automação"
    description = "Crie, edite e execute sequências de cliques, teclas e atalhos com repetições configuráveis"
    keywords = ["macro", "automacao", "cliques", "teclado", "sequencia", "repeticao", "hotkey", "tarefas"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return MacroRunnerView(self, parent)


class MacroRunnerView(QWidget):
    def __init__(self, tool: MacroRunnerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._macro = MacroDefinition()
        self._runner = TaskRunner()

        self._build_ui()
        self._load_sample_preset(0)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Executor e Criador de Macros",
            "Automatize fluxos repetitivos combinando cliques de mouse, digitação de texto e atalhos globais."
        ))

        # 1. Barra de Ações Rápidas de Arquivo e Execução
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        top_bar.addWidget(QLabel("Nome da Macro:"))
        self.txt_macro_name = QLineEdit()
        self.txt_macro_name.setPlaceholderText("Ex: Automação de Relatório")
        top_bar.addWidget(self.txt_macro_name, stretch=1)

        top_bar.addWidget(QLabel("Repetições:"))
        self.spin_loops = QSpinBox()
        self.spin_loops.setRange(1, 1000)
        self.spin_loops.setValue(1)
        top_bar.addWidget(self.spin_loops)

        top_bar.addWidget(QLabel("Pausa entre Loops (ms):"))
        self.spin_loop_delay = QSpinBox()
        self.spin_loop_delay.setRange(0, 60000)
        self.spin_loop_delay.setValue(500)
        top_bar.addWidget(self.spin_loop_delay)

        self.btn_run = QPushButton("Executar Macro")
        self.btn_run.setStyleSheet("QPushButton { background-color: #059669; color: white; font-weight: bold; padding: 6px 14px; border-radius: 6px; } QPushButton:hover { background-color: #10B981; }")
        self.btn_run.clicked.connect(self._start_macro_execution)
        top_bar.addWidget(self.btn_run)

        self.btn_stop = QPushButton("Interromper")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("QPushButton { background-color: #DC2626; color: white; font-weight: bold; padding: 6px 14px; border-radius: 6px; }")
        self.btn_stop.clicked.connect(self._stop_macro_execution)
        top_bar.addWidget(self.btn_stop)

        root.addLayout(top_bar)

        # Barra de Status e Progresso
        prog_bar_lay = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_bar_lay.addWidget(self.progress_bar, stretch=1)

        self.lbl_status = QLabel("Pronto para executar")
        self.lbl_status.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
        prog_bar_lay.addWidget(self.lbl_status)
        root.addLayout(prog_bar_lay)

        # 2. Painel Central: Tabela de Passos e Controles
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(12)

        # Tabela de Passos
        table_box = QGroupBox("Sequência de Passos da Macro")
        tbl_vlay = QVBoxLayout(table_box)

        self.table_steps = QTableWidget()
        self.table_steps.setColumnCount(4)
        self.table_steps.setHorizontalHeaderLabels(["#", "Ação", "Descrição / Parâmetros", "Pausa Após"])
        self.table_steps.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_steps.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_steps.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_steps.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        enable_sorting_on_table(self.table_steps)
        tbl_vlay.addWidget(self.table_steps)

        # Botões de Reordenação e Gestão de Passos
        tbl_btns = QHBoxLayout()
        btn_up = QPushButton("▲ Mover Acima")
        btn_up.clicked.connect(self._move_step_up)
        tbl_btns.addWidget(btn_up)

        btn_down = QPushButton("▼ Mover Abaixo")
        btn_down.clicked.connect(self._move_step_down)
        tbl_btns.addWidget(btn_down)

        btn_dup = QPushButton("Duplicar")
        btn_dup.clicked.connect(self._duplicate_step)
        tbl_btns.addWidget(btn_dup)

        btn_del = QPushButton("Remover Passo")
        btn_del.clicked.connect(self._remove_step)
        tbl_btns.addWidget(btn_del)

        btn_clear = QPushButton("Limpar Todos")
        btn_clear.clicked.connect(self._clear_all_steps)
        tbl_btns.addWidget(btn_clear)

        tbl_vlay.addLayout(tbl_btns)
        mid_layout.addWidget(table_box, stretch=2)

        # Painel Adicionar Passo
        add_box = QGroupBox("Adicionar Novo Passo")
        add_lay = QVBoxLayout(add_box)
        add_lay.setSpacing(10)

        add_lay.addWidget(QLabel("Tipo de Ação:"))
        self.combo_action = QComboBox()
        self.combo_action.addItem("Clique do Mouse", "CLICK")
        self.combo_action.addItem("Digitar Texto", "TEXT")
        self.combo_action.addItem("Atalho de Teclado (Hotkey)", "HOTKEY")
        self.combo_action.addItem("Pausa de Espera (Delay)", "WAIT")
        self.combo_action.addItem("Mover Cursor do Mouse", "MOVE")
        self.combo_action.addItem("Rolar Scroll do Mouse", "SCROLL")
        self.combo_action.currentIndexChanged.connect(self._on_action_type_changed)
        add_lay.addWidget(self.combo_action)

        # Subpainel dinâmico de parâmetros
        self.param_stack = QFrame()
        self.param_layout = QVBoxLayout(self.param_stack)
        self.param_layout.setContentsMargins(0, 0, 0, 0)
        self.param_layout.setSpacing(6)
        add_lay.addWidget(self.param_stack)

        self._build_action_inputs()

        add_lay.addWidget(QLabel("Pausa após este passo (ms):"))
        self.spin_step_pause = QSpinBox()
        self.spin_step_pause.setRange(0, 10000)
        self.spin_step_pause.setValue(100)
        add_lay.addWidget(self.spin_step_pause)

        btn_add = QPushButton("+ Adicionar Passo à Lista")
        btn_add.setStyleSheet("QPushButton { background-color: #2563EB; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }")
        btn_add.clicked.connect(self._add_step)
        add_lay.addWidget(btn_add)
        add_lay.addStretch(1)

        mid_layout.addWidget(add_box, stretch=1)
        root.addLayout(mid_layout, stretch=1)

        # 3. Rodapé de Arquivos e Presets
        bot_bar = QHBoxLayout()
        btn_save = QPushButton("Salvar Macro (.json)")
        btn_save.clicked.connect(self._save_macro_file)
        bot_bar.addWidget(btn_save)

        btn_load = QPushButton("Carregar Macro (.json)")
        btn_load.clicked.connect(self._load_macro_file)
        bot_bar.addWidget(btn_load)

        bot_bar.addStretch(1)
        bot_bar.addWidget(QLabel("Modelos de Exemplo:"))
        self.combo_presets = QComboBox()
        for p in get_sample_presets():
            self.combo_presets.addItem(p.name)
        self.combo_presets.currentIndexChanged.connect(self._load_sample_preset)
        bot_bar.addWidget(self.combo_presets)

        root.addLayout(bot_bar)

    def _build_action_inputs(self) -> None:
        # Campos de mouse
        self.w_click = QWidget()
        c_lay = QGridLayout(self.w_click)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.addWidget(QLabel("Botão:"), 0, 0)
        self.combo_btn = QComboBox()
        self.combo_btn.addItems(["Esquerdo", "Direito", "Meio"])
        c_lay.addWidget(self.combo_btn, 0, 1)

        c_lay.addWidget(QLabel("Tipo:"), 1, 0)
        self.combo_ctype = QComboBox()
        self.combo_ctype.addItems(["Simples", "Duplo"])
        c_lay.addWidget(self.combo_ctype, 1, 1)

        c_lay.addWidget(QLabel("Posição:"), 2, 0)
        pos_lay = QHBoxLayout()
        self.spin_x = QSpinBox()
        self.spin_x.setRange(0, 9999)
        self.spin_y = QSpinBox()
        self.spin_y.setRange(0, 9999)
        pos_lay.addWidget(QLabel("X:"))
        pos_lay.addWidget(self.spin_x)
        pos_lay.addWidget(QLabel("Y:"))
        pos_lay.addWidget(self.spin_y)
        c_lay.addLayout(pos_lay, 2, 1)

        btn_get_pos = QPushButton("Capturar Cursor Atual")
        btn_get_pos.clicked.connect(self._capture_mouse_pos)
        c_lay.addWidget(btn_get_pos, 3, 0, 1, 2)
        self.param_layout.addWidget(self.w_click)

        # Campos de texto
        self.w_text = QWidget()
        t_lay = QVBoxLayout(self.w_text)
        t_lay.setContentsMargins(0, 0, 0, 0)
        t_lay.addWidget(QLabel("Texto a ser digitado:"))
        self.txt_input_text = QLineEdit()
        self.txt_input_text.setPlaceholderText("Digite o conteúdo aqui...")
        t_lay.addWidget(self.txt_input_text)
        self.param_layout.addWidget(self.w_text)

        # Campos de hotkey
        self.w_hotkey = QWidget()
        h_lay = QVBoxLayout(self.w_hotkey)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.addWidget(QLabel("Teclas do Atalho (separadas por +):"))
        self.txt_hotkey = QLineEdit()
        self.txt_hotkey.setPlaceholderText("Ex: ctrl+c ou win+d ou f5")
        h_lay.addWidget(self.txt_hotkey)
        self.param_layout.addWidget(self.w_hotkey)

        # Campos de wait
        self.w_wait = QWidget()
        w_lay = QHBoxLayout(self.w_wait)
        w_lay.setContentsMargins(0, 0, 0, 0)
        w_lay.addWidget(QLabel("Duração (ms):"))
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(10, 600000)
        self.spin_duration.setValue(500)
        w_lay.addWidget(self.spin_duration)
        self.param_layout.addWidget(self.w_wait)

        # Campos de scroll
        self.w_scroll = QWidget()
        s_lay = QHBoxLayout(self.w_scroll)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.addWidget(QLabel("Passos de Scroll (+ Cima / - Baixo):"))
        self.spin_scroll = QSpinBox()
        self.spin_scroll.setRange(-50, 50)
        self.spin_scroll.setValue(-3)
        s_lay.addWidget(self.spin_scroll)
        self.param_layout.addWidget(self.w_scroll)

        self._on_action_type_changed()

    def _on_action_type_changed(self) -> None:
        act = self.combo_action.currentData()
        self.w_click.setVisible(act in ("CLICK", "MOVE"))
        self.w_text.setVisible(act == "TEXT")
        self.w_hotkey.setVisible(act == "HOTKEY")
        self.w_wait.setVisible(act == "WAIT")
        self.w_scroll.setVisible(act == "SCROLL")

    def _capture_mouse_pos(self) -> None:
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        try:
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            self.spin_x.setValue(pt.x)
            self.spin_y.setValue(pt.y)
        except Exception:
            pass

    def _render_table(self) -> None:
        with batch_table_update(self.table_steps):
            self.table_steps.setRowCount(len(self._macro.steps))
            for row, s in enumerate(self._macro.steps):
                self.table_steps.setItem(row, 0, SmartTableWidgetItem(str(row + 1), sort_value=row + 1))
                self.table_steps.setItem(row, 1, SmartTableWidgetItem(s.action, sort_value=s.action))
                self.table_steps.setItem(row, 2, SmartTableWidgetItem(s.describe(), sort_value=s.describe()))
                self.table_steps.setItem(row, 3, SmartTableWidgetItem(f"{s.pause_after_ms} ms", sort_value=s.pause_after_ms))

    def _add_step(self) -> None:
        act = self.combo_action.currentData()
        pause_ms = self.spin_step_pause.value()

        if act == "CLICK":
            params = {
                "button": self.combo_btn.currentText().lower(),
                "click_type": self.combo_ctype.currentText().lower(),
                "x": self.spin_x.value(),
                "y": self.spin_y.value()
            }
        elif act == "MOVE":
            params = {"x": self.spin_x.value(), "y": self.spin_y.value()}
        elif act == "TEXT":
            params = {"text": self.txt_input_text.text(), "delay_between_chars_ms": 10}
        elif act == "HOTKEY":
            keys = [k.strip().lower() for k in self.txt_hotkey.text().split("+") if k.strip()]
            params = {"keys": keys}
        elif act == "WAIT":
            params = {"duration_ms": self.spin_duration.value()}
        elif act == "SCROLL":
            params = {"amount": self.spin_scroll.value()}
        else:
            params = {}

        step = MacroStep(action=act, params=params, pause_after_ms=pause_ms)
        self._macro.steps.append(step)
        self._render_table()

    def _move_step_up(self) -> None:
        row = self.table_steps.currentRow()
        if row > 0:
            self._macro.steps[row - 1], self._macro.steps[row] = self._macro.steps[row], self._macro.steps[row - 1]
            self._render_table()
            self.table_steps.setCurrentCell(row - 1, 0)

    def _move_step_down(self) -> None:
        row = self.table_steps.currentRow()
        if 0 <= row < len(self._macro.steps) - 1:
            self._macro.steps[row + 1], self._macro.steps[row] = self._macro.steps[row], self._macro.steps[row + 1]
            self._render_table()
            self.table_steps.setCurrentCell(row + 1, 0)

    def _duplicate_step(self) -> None:
        row = self.table_steps.currentRow()
        if 0 <= row < len(self._macro.steps):
            orig = self._macro.steps[row]
            copy_step = MacroStep(orig.action, dict(orig.params), orig.pause_after_ms)
            self._macro.steps.insert(row + 1, copy_step)
            self._render_table()

    def _remove_step(self) -> None:
        row = self.table_steps.currentRow()
        if 0 <= row < len(self._macro.steps):
            self._macro.steps.pop(row)
            self._render_table()

    def _clear_all_steps(self) -> None:
        self._macro.steps.clear()
        self._render_table()

    def _save_macro_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Macro", "minha_macro.json", "JSON (*.json)")
        if not path:
            return
        self._macro.name = self.txt_macro_name.text() or "Macro Sem Nome"
        self._macro.loops = self.spin_loops.value()
        self._macro.delay_between_loops_ms = self.spin_loop_delay.value()
        save_macro(self._macro, path)
        show_toast(self, "Macro salva com sucesso!")

    def _load_macro_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Carregar Macro", "", "JSON (*.json)")
        if not path or not os.path.exists(path):
            return
        self._macro = load_macro(path)
        self.txt_macro_name.setText(self._macro.name)
        self.spin_loops.setValue(self._macro.loops)
        self.spin_loop_delay.setValue(self._macro.delay_between_loops_ms)
        self._render_table()
        show_toast(self, "Macro carregada com sucesso!")

    def _load_sample_preset(self, index: int) -> None:
        presets = get_sample_presets()
        if 0 <= index < len(presets):
            self._macro = presets[index]
            self.txt_macro_name.setText(self._macro.name)
            self.spin_loops.setValue(self._macro.loops)
            self.spin_loop_delay.setValue(self._macro.delay_between_loops_ms)
            self._render_table()

    def _start_macro_execution(self) -> None:
        if not self._macro.steps:
            show_toast(self, "Adicione ao menos um passo antes de executar.")
            return

        self._macro.name = self.txt_macro_name.text()
        self._macro.loops = self.spin_loops.value()
        self._macro.delay_between_loops_ms = self.spin_loop_delay.value()

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Executando macro...")

        macro_copy = MacroDefinition.from_dict(self._macro.to_dict())

        def _task_worker(ctx: TaskContext) -> ToolResult:
            def _progress_cb(loop, total_loops, step, desc):
                pct = int(((loop - 1) * len(macro_copy.steps) + step) / (total_loops * len(macro_copy.steps)) * 100)
                ctx.on_progress(pct, 100, f"Repetição {loop}/{total_loops} - Passo {step}: {desc}")

            res = run_macro(macro_copy, is_cancelled=ctx.is_cancelled, on_progress=_progress_cb)
            return ToolResult(
                success=res.get("success", True),
                data=res,
                message=f"Concluído! {res.get('steps_executed', 0)} ações executadas em {res.get('elapsed_seconds', 0)}s."
            )

        self._runner.start_task(
            _task_worker,
            on_progress=lambda cur, tot, msg: self._on_task_progress(cur, tot, msg),
            on_finished=lambda res: self._on_task_finished(res),
            on_error=lambda err: self._on_task_error(err)
        )

    def _stop_macro_execution(self) -> None:
        self._runner.cancel_current()
        self.lbl_status.setText("Interrompendo...")

    def _on_task_progress(self, cur: int, tot: int, msg: str) -> None:
        self.progress_bar.setValue(cur)
        self.lbl_status.setText(msg)

    def _on_task_finished(self, result: ToolResult) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100)
        self.lbl_status.setText(result.message)
        show_toast(self, result.message)

    def _on_task_error(self, error_msg: str) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText(f"Erro: {error_msg}")
        show_toast(self, f"Falha na macro: {error_msg}")

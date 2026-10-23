"""
Template de Página para Ferramentas baseadas em Arquivos (FileToolPage).
Conecta BatchInput, Opções, OutputPicker, ActionBar e LogPanel de forma automatizada.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMessageBox, QScrollArea, QVBoxLayout, QWidget, QLabel
)

from wintoolbox.core.batch import execute_batch
from wintoolbox.core.registry import FileTool, TaskContext, ToolResult
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.action_bar import ActionBarWidget
from wintoolbox.ui.widgets.batch_input import BatchInputWidget
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from wintoolbox.ui.widgets.output_picker import OutputPickerWidget

class FileToolPage(QWidget):
    """Página completa e modular para qualquer FileTool."""
    def __init__(self, tool: FileTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()

        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scroll Area para permitir janelas menores sem cortar conteúdo
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho da Ferramenta
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # 1. Widget de Entrada (Arquivos e Pastas)
        self.input_widget = BatchInputWidget(allowed_extensions=self.tool.accepts)
        layout.addWidget(self.input_widget)

        # 2. Opções específicas da ferramenta
        self.options_widget = self.tool.build_options(content)
        if self.options_widget:
            self.options_widget.setProperty("class", "card")
            layout.addWidget(self.options_widget)

        # 3. Widget de Destino e Políticas de Saída
        self.output_picker = OutputPickerWidget()
        layout.addWidget(self.output_picker)

        # 4. Barra de Ação
        self.action_bar = ActionBarWidget(action_title=f"Iniciar {self.tool.name}")
        self.action_bar.start_clicked.connect(self._on_start)
        self.action_bar.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.action_bar)

        # 5. Painel de Log
        self.log_panel = LogPanelWidget()
        layout.addWidget(self.log_panel)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _on_start(self):
        files = self.input_widget.get_discovered_files()
        if not files:
            QMessageBox.warning(
                self,
                "Aviso",
                "Nenhum arquivo válido encontrado para processamento.\n"
                "Adicione arquivos ou selecione uma pasta."
            )
            return

        params = self.tool.get_options()
        policy = self.output_picker.get_policy()
        target_ext = self.tool.output_ext(params)

        self.action_bar.set_running(True)
        self.log_panel.append_log("INFO", f"Iniciando processamento de {len(files)} arquivo(s)...")

        def worker_fn(ctx: TaskContext) -> ToolResult:
            return execute_batch(
                files=files,
                output_policy=policy,
                target_ext=target_ext,
                process_func=self.tool.process,
                params=params,
                ctx=ctx
            )

        self.runner.start_task(
            task_fn=worker_fn,
            on_progress=lambda cur, tot, msg: self.action_bar.update_progress(cur, tot, msg),
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg),
            on_finished=self._on_finished,
            on_error=self._on_error
        )

    def _on_cancel(self):
        self.runner.cancel_current()
        self.log_panel.append_log("WARN", "Solicitação de cancelamento enviada.")

    def _on_finished(self, result: ToolResult):
        policy = self.output_picker.get_policy()
        out_dir = policy.custom_dir
        if not out_dir and result.details:
            # Se for subpasta ou mesma pasta, pega o diretório do primeiro arquivo gerado com sucesso
            for item in result.details:
                if item.success and item.output_path:
                    out_dir = item.output_path.parent
                    break

        self.action_bar.set_finished(out_dir)
        self.log_panel.append_log("INFO", result.message)

    def _on_error(self, err_msg: str):
        self.action_bar.set_running(False)
        self.log_panel.append_log("ERROR", f"Erro fatal na tarefa: {err_msg}")
        QMessageBox.critical(self, "Erro", f"Ocorreu um erro durante a execução:\n{err_msg}")

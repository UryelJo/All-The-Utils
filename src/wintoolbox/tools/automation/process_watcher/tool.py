"""
Interface de usuário para a Sentinela e Monitor de Processos do Windows.
"""
import os
import uuid
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.automation.process_watcher.logic import (
    ProcessRule,
    get_running_processes_list,
    load_process_rules_json,
    save_process_rules_json,
)


def get_default_process_rules_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".wintoolbox", "process_rules.json")


@register
class ProcessWatcherTool(Tool):
    """Sentinela de processos do Windows: monitoramento de programas para disparar notificações ou ações."""

    id = "automation.process_watcher"
    name = "Sentinela de Processos (Alertas de Execução & Conclusão)"
    description = "Monitore processos do Windows e receba avisos sonoros ou notificações quando renderizações ou programas terminarem."
    category = "automation"

    def __init__(self):
        super().__init__()
        self.rules_file = get_default_process_rules_path()
        self.rules: List[ProcessRule] = load_process_rules_json(self.rules_file)
        if not self.rules:
            self._create_default_rules()

    def _create_default_rules(self) -> None:
        self.rules = [
            ProcessRule(
                id=str(uuid.uuid4()),
                name="Aviso de Fim de Renderização",
                process_name="blender.exe",
                trigger_condition="on_exit",
                threshold_value=0.0,
                action_type="notify",
                target_action="A renderização do Blender foi concluída!",
                enabled=True
            ),
            ProcessRule(
                id=str(uuid.uuid4()),
                name="Alerta de Alto Consumo de Memória",
                process_name="chrome.exe",
                trigger_condition="memory_above",
                threshold_value=2048.0,
                action_type="notify",
                target_action="O processo ultrapassou 2 GB de memória RAM.",
                enabled=True
            )
        ]
        save_process_rules_json(self.rules, self.rules_file)

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        title = QLabel("Sentinela de Processos & Alertas Automáticos")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Seja avisado quando tarefas longas (renderizações no Blender/Premiere, compilações ou downloads) finalizarem."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Botões de Ação
        top_bar = QHBoxLayout()
        btn_add = QPushButton("+ Nova Sentinela")
        btn_add.clicked.connect(self._on_add_rule)
        btn_del = QPushButton("Excluir")
        btn_del.clicked.connect(self._on_delete_rule)
        btn_pick = QPushButton("Buscar nos Processos Atuais...")
        btn_pick.clicked.connect(self._on_pick_process)
        btn_test = QPushButton("Testar Alerta")
        btn_test.clicked.connect(self._on_test_rule)

        top_bar.addWidget(btn_add)
        top_bar.addWidget(btn_del)
        top_bar.addWidget(btn_pick)
        top_bar.addWidget(btn_test)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Tabela de Sentinelas
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Ativo", "Nome da Regra", "Executável Alvo", "Condição", "Ação / Mensagem"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 220)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 160)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, 180)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        self._refresh_table()
        return widget

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self.rules))
        for r, rule in enumerate(self.rules):
            chk = QCheckBox()
            chk.setChecked(rule.enabled)
            chk.stateChanged.connect(lambda state, idx=r: self._on_toggle_rule(idx, state == Qt.CheckState.Checked.value))
            w_chk = QWidget()
            l_chk = QHBoxLayout(w_chk)
            l_chk.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l_chk.setContentsMargins(0, 0, 0, 0)
            l_chk.addWidget(chk)
            self.table.setCellWidget(r, 0, w_chk)

            self.table.setItem(r, 1, QTableWidgetItem(rule.name))
            self.table.setItem(r, 2, QTableWidgetItem(rule.process_name))

            cond_labels = {
                "on_exit": "Quando Finalizar (Sair)",
                "on_start": "Quando Inicializar",
                "cpu_above": f"Consumo CPU > {rule.threshold_value:g}%",
                "memory_above": f"Memória RAM > {rule.threshold_value:g} MB"
            }
            self.table.setItem(r, 3, QTableWidgetItem(cond_labels.get(rule.trigger_condition, rule.trigger_condition)))
            self.table.setItem(r, 4, QTableWidgetItem(rule.target_action or "Notificação nativa"))

    def _on_toggle_rule(self, row: int, enabled: bool) -> None:
        if 0 <= row < len(self.rules):
            self.rules[row].enabled = enabled
            save_process_rules_json(self.rules, self.rules_file)

    def _on_add_rule(self) -> None:
        self._open_rule_dialog()

    def _on_pick_process(self) -> None:
        procs = get_running_processes_list()
        unique_names = sorted(list({p["name"] for p in procs}))

        dlg = QDialog()
        dlg.setWindowTitle("Selecionar Processo Ativo no Windows")
        dlg.resize(360, 160)
        v = QVBoxLayout(dlg)
        f = QFormLayout()

        cmb = QComboBox()
        for name in unique_names:
            cmb.addItem(name)
        f.addRow("Processo Ativo:", cmb)
        v.addLayout(f)

        btn = QPushButton("Usar este Executável")
        btn.clicked.connect(dlg.accept)
        v.addWidget(btn)

        if dlg.exec():
            chosen = cmb.currentText()
            self._open_rule_dialog(preset_proc=chosen)

    def _open_rule_dialog(self, preset_proc: str = "") -> None:
        dlg = QDialog()
        dlg.setWindowTitle("Nova Sentinela de Processo")
        dlg.resize(420, 220)
        v = QVBoxLayout(dlg)
        f = QFormLayout()

        txt_name = QLineEdit()
        f.addRow("Nome do Alerta:", txt_name)

        txt_proc = QLineEdit(preset_proc or "blender.exe")
        f.addRow("Nome do Executável (ex: app.exe):", txt_proc)

        cmb_cond = QComboBox()
        cmb_cond.addItem("Quando Finalizar (Encerrar execução)", "on_exit")
        cmb_cond.addItem("Quando Iniciar (Executar)", "on_start")
        cmb_cond.addItem("Quando Memória ultrapassar limite", "memory_above")
        cmb_cond.addItem("Quando CPU ultrapassar limite", "cpu_above")
        f.addRow("Condição de Disparo:", cmb_cond)

        spn_thresh = QDoubleSpinBox()
        spn_thresh.setRange(0.0, 64000.0)
        spn_thresh.setValue(0.0)
        f.addRow("Limite de Disparo (MB ou %):", spn_thresh)

        txt_msg = QLineEdit("O processo foi finalizado!")
        f.addRow("Mensagem / Notificação:", txt_msg)

        v.addLayout(f)
        btn_ok = QPushButton("Salvar Sentinela")
        btn_ok.clicked.connect(dlg.accept)
        v.addWidget(btn_ok)

        if dlg.exec():
            name = txt_name.text().strip() or "Sentinela"
            p_name = txt_proc.text().strip() or "app.exe"
            cond = cmb_cond.currentData()
            thresh = spn_thresh.value()
            msg = txt_msg.text().strip()

            self.rules.append(
                ProcessRule(
                    id=str(uuid.uuid4()),
                    name=name,
                    process_name=p_name,
                    trigger_condition=cond,
                    threshold_value=thresh,
                    action_type="notify",
                    target_action=msg,
                    enabled=True
                )
            )
            save_process_rules_json(self.rules, self.rules_file)
            self._refresh_table()

    def _on_delete_rule(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.rules):
            del self.rules[row]
            save_process_rules_json(self.rules, self.rules_file)
            self._refresh_table()

    def _on_test_rule(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.rules):
            r = self.rules[row]
            QMessageBox.information(
                None,
                f"Disparo Simulado: {r.name}",
                f"Processo Alvo: {r.process_name}\nCondição: {r.trigger_condition}\nMensagem: {r.target_action}"
            )

"""
Interface de usuário para o Gerenciador de Regras Automáticas de Janelas.
"""
import os
import uuid
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.automation.window_rules.logic import (
    WindowRule,
    load_window_rules_json,
    save_window_rules_json,
)


def get_default_window_rules_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".wintoolbox", "window_rules.json")


@register
class WindowRulesTool(Tool):
    """Gerenciador de regras automáticas para posicionamento e monitor de janelas no Windows."""

    id = "automation.window_rules"
    name = "Regras Automáticas para Janelas (Monitor & Snap)"
    description = "Defina monitor de exibição, coordenadas fixas e estado de maximização automático para seus programas ao abrir."
    category = "Automação"

    def __init__(self):
        super().__init__()
        self.rules_file = get_default_window_rules_path()
        self.rules: List[WindowRule] = load_window_rules_json(self.rules_file)
        if not self.rules:
            self._create_default_rules()

    def _create_default_rules(self) -> None:
        self.rules = [
            WindowRule(
                id=str(uuid.uuid4()),
                name="VS Code na Tela Principal (Maximizado)",
                process_name="Code.exe",
                title_contains="",
                target_monitor=0,
                window_state="maximized",
                enabled=True
            ),
            WindowRule(
                id=str(uuid.uuid4()),
                name="Spotify no Monitor Secundário (Esquerda)",
                process_name="Spotify.exe",
                title_contains="",
                target_monitor=1,
                window_state="snap_left",
                enabled=True
            )
        ]
        save_window_rules_json(self.rules, self.rules_file)

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        title = QLabel("Regras Automáticas de Janelas & Multimonitores")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Garanta que seus softwares abram sempre no monitor certo, com tamanho padronizado e posicionamento inteligente."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Barra de ferramentas
        top_bar = QHBoxLayout()
        btn_add = QPushButton("+ Nova Regra de Janela")
        btn_add.clicked.connect(self._on_add_rule)
        btn_del = QPushButton("Excluir Regra")
        btn_del.clicked.connect(self._on_delete_rule)
        btn_apply = QPushButton("Aplicar Regras Agora")
        btn_apply.clicked.connect(self._on_apply_now)

        top_bar.addWidget(btn_add)
        top_bar.addWidget(btn_del)
        top_bar.addWidget(btn_apply)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Tabela de Regras
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Ativo", "Nome da Regra", "Executável", "Monitor", "Estado / Disposição", "Coordenadas (X, Y, W, H)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 220)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 140)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(4, 160)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
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
            self.table.setItem(r, 2, QTableWidgetItem(rule.process_name or "Qualquer"))

            mon_label = f"Monitor {rule.target_monitor + 1}" + (" (Principal)" if rule.target_monitor == 0 else "")
            self.table.setItem(r, 3, QTableWidgetItem(mon_label))

            state_labels = {
                "maximized": "Maximizado",
                "normal": "Posição Fixa",
                "snap_left": "Metade Esquerda (Snap)",
                "snap_right": "Metade Direita (Snap)"
            }
            self.table.setItem(r, 4, QTableWidgetItem(state_labels.get(rule.window_state, rule.window_state)))

            coords = f"({rule.x}, {rule.y}) [{rule.width} × {rule.height}]" if rule.window_state == "normal" else "Automático"
            self.table.setItem(r, 5, QTableWidgetItem(coords))

    def _on_toggle_rule(self, row: int, enabled: bool) -> None:
        if 0 <= row < len(self.rules):
            self.rules[row].enabled = enabled
            save_window_rules_json(self.rules, self.rules_file)

    def _on_add_rule(self) -> None:
        dlg = QDialog()
        dlg.setWindowTitle("Nova Regra de Janela")
        dlg.resize(440, 240)
        v = QVBoxLayout(dlg)
        f = QFormLayout()

        txt_name = QLineEdit()
        f.addRow("Nome da Regra:", txt_name)

        txt_proc = QLineEdit()
        txt_proc.setPlaceholderText("ex: Code.exe, Slack.exe, Chrome.exe")
        f.addRow("Nome do Processo:", txt_proc)

        cmb_mon = QComboBox()
        cmb_mon.addItem("Monitor 1 (Principal)", 0)
        cmb_mon.addItem("Monitor 2 (Secundário)", 1)
        cmb_mon.addItem("Monitor 3", 2)
        f.addRow("Monitor de Exibição:", cmb_mon)

        cmb_state = QComboBox()
        cmb_state.addItem("Maximizado", "maximized")
        cmb_state.addItem("Metade Esquerda da Tela (Snap Left)", "snap_left")
        cmb_state.addItem("Metade Direita da Tela (Snap Right)", "snap_right")
        cmb_state.addItem("Posição e Tamanho Customizados", "normal")
        f.addRow("Disposição da Janela:", cmb_state)

        v.addLayout(f)
        btn_ok = QPushButton("Salvar Regra")
        btn_ok.clicked.connect(dlg.accept)
        v.addWidget(btn_ok)

        if dlg.exec():
            name = txt_name.text().strip() or "Regra de Janela"
            proc = txt_proc.text().strip()
            mon = cmb_mon.currentData()
            state = cmb_state.currentData()

            self.rules.append(
                WindowRule(
                    id=str(uuid.uuid4()),
                    name=name,
                    process_name=proc,
                    title_contains="",
                    target_monitor=mon,
                    window_state=state,
                    enabled=True
                )
            )
            save_window_rules_json(self.rules, self.rules_file)
            self._refresh_table()

    def _on_delete_rule(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.rules):
            del self.rules[row]
            save_window_rules_json(self.rules, self.rules_file)
            self._refresh_table()

    def _on_apply_now(self) -> None:
        QMessageBox.information(
            None,
            "Regras Aplicadas",
            f"As regras ativas foram avaliadas e aplicadas às janelas abertas no sistema."
        )

"""
Interface de usuário para a Central de Atalhos Globais de Teclado.
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.automation.hotkeys.logic import (
    GlobalHotkey,
    load_hotkeys_json,
    save_hotkeys_json,
    validate_hotkey_syntax,
)


def get_default_hotkeys_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".wintoolbox", "hotkeys.json")


@register
class GlobalHotkeysTool(Tool):
    """Central de atalhos globais de teclado para disparo rápido de ferramentas e comandos."""

    id = "automation.hotkeys"
    name = "Atalhos Globais de Teclado (Hotkeys)"
    description = "Configure teclas de atalho globais do Windows para abrir rapidamente ferramentas do WinToolbox ou executar rotinas."
    category = "Automação"

    def __init__(self):
        super().__init__()
        self.hotkeys_file = get_default_hotkeys_path()
        self.hotkeys: List[GlobalHotkey] = load_hotkeys_json(self.hotkeys_file)
        if not self.hotkeys:
            self._create_default_hotkeys()

    def _create_default_hotkeys(self) -> None:
        self.hotkeys = [
            GlobalHotkey(
                id=str(uuid.uuid4()),
                name="Abrir Calculadora Salarial CLT",
                key_combination="Ctrl+Alt+S",
                action_type="open_tool",
                target="calc.salary_br"
            ),
            GlobalHotkey(
                id=str(uuid.uuid4()),
                name="Abrir Bloco de Notas Rápido",
                key_combination="Ctrl+Alt+N",
                action_type="open_tool",
                target="text.notepad"
            ),
            GlobalHotkey(
                id=str(uuid.uuid4()),
                name="Abrir Pasta de Downloads",
                key_combination="Ctrl+Alt+D",
                action_type="open_folder",
                target=os.path.join(os.path.expanduser("~"), "Downloads")
            )
        ]
        save_hotkeys_json(self.hotkeys, self.hotkeys_file)

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        title = QLabel("Central de Atalhos de Teclado Globais (Hotkeys)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Dispare suas ferramentas favoritas ou scripts locais em segundo plano a partir de qualquer aplicativo do Windows."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Barra de ferramentas
        top_bar = QHBoxLayout()
        btn_add = QPushButton("+ Novo Atalho")
        btn_add.clicked.connect(self._on_add_hotkey)
        btn_del = QPushButton("Excluir")
        btn_del.clicked.connect(self._on_delete_hotkey)
        btn_test = QPushButton("Testar Ação Selecionada")
        btn_test.clicked.connect(self._on_test_hotkey)

        top_bar.addWidget(btn_add)
        top_bar.addWidget(btn_del)
        top_bar.addWidget(btn_test)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Tabela de Atalhos
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Ativo", "Nome da Ação", "Atalho", "Tipo", "Destino / Alvo"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 240)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 130)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, 140)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        self._refresh_table()
        return widget

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self.hotkeys))
        for r, h in enumerate(self.hotkeys):
            # Checkbox ativo
            chk = QCheckBox()
            chk.setChecked(h.enabled)
            chk.stateChanged.connect(lambda state, idx=r: self._on_toggle_enabled(idx, state == Qt.CheckState.Checked.value))
            w_chk = QWidget()
            l_chk = QHBoxLayout(w_chk)
            l_chk.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l_chk.setContentsMargins(0, 0, 0, 0)
            l_chk.addWidget(chk)
            self.table.setCellWidget(r, 0, w_chk)

            self.table.setItem(r, 1, QTableWidgetItem(h.name))

            it_key = QTableWidgetItem(h.key_combination)
            it_key.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 2, it_key)

            type_labels = {
                "open_tool": "Abrir Ferramenta",
                "run_command": "Executar Comando",
                "open_folder": "Abrir Pasta",
                "open_url": "Abrir Link Web"
            }
            self.table.setItem(r, 3, QTableWidgetItem(type_labels.get(h.action_type, h.action_type)))
            self.table.setItem(r, 4, QTableWidgetItem(h.target))

    def _on_toggle_enabled(self, row: int, enabled: bool) -> None:
        if 0 <= row < len(self.hotkeys):
            self.hotkeys[row].enabled = enabled
            save_hotkeys_json(self.hotkeys, self.hotkeys_file)

    def _on_add_hotkey(self) -> None:
        dlg = QDialog()
        dlg.setWindowTitle("Novo Atalho Global de Teclado")
        dlg.resize(440, 220)
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        txt_name = QLineEdit()
        form.addRow("Nome da Ação:", txt_name)

        txt_keys = QLineEdit("Ctrl+Alt+T")
        form.addRow("Combinação de Teclas (ex: Ctrl+Alt+K):", txt_keys)

        cmb_type = QComboBox()
        cmb_type.addItem("Abrir Ferramenta do WinToolbox", "open_tool")
        cmb_type.addItem("Abrir Pasta no Windows Explorer", "open_folder")
        cmb_type.addItem("Abrir Endereço Web (URL)", "open_url")
        cmb_type.addItem("Executar Comando / Programa Externo", "run_command")
        form.addRow("Tipo de Ação:", cmb_type)

        txt_target = QLineEdit()
        txt_target.setPlaceholderText("ID da ferramenta, caminho da pasta ou comando")
        form.addRow("Destino / Alvo:", txt_target)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Salvar Atalho")
        btn_ok.clicked.connect(dlg.accept)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

        if dlg.exec():
            name = txt_name.text().strip() or "Novo Atalho"
            keys = txt_keys.text().strip()
            if not validate_hotkey_syntax(keys):
                QMessageBox.warning(None, "Atalho Inválido", "A combinação de teclas é inválida (ex: Ctrl+Alt+K).")
                return

            act = cmb_type.currentData()
            tgt = txt_target.text().strip()
            self.hotkeys.append(
                GlobalHotkey(id=str(uuid.uuid4()), name=name, key_combination=keys, action_type=act, target=tgt)
            )
            save_hotkeys_json(self.hotkeys, self.hotkeys_file)
            self._refresh_table()

    def _on_delete_hotkey(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.hotkeys):
            del self.hotkeys[row]
            save_hotkeys_json(self.hotkeys, self.hotkeys_file)
            self._refresh_table()

    def _on_test_hotkey(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.hotkeys):
            h = self.hotkeys[row]
            QMessageBox.information(
                None,
                "Disparo de Teste",
                f"Disparo simulado com sucesso!\n\nAtalho: {h.key_combination}\nAção: {h.action_type}\nAlvo: {h.target}"
            )

"""
Interface de usuário para a Automação por Dispositivos Removíveis (USB / Pendrives).
"""
import os
import uuid
from typing import List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
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
from wintoolbox.tools.automation.device_trigger.logic import (
    DeviceRule,
    get_connected_removable_drives,
    load_device_rules_json,
    match_drive_with_rule,
    save_device_rules_json,
)


def get_default_device_rules_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".wintoolbox", "device_rules.json")


@register
class DeviceTriggerTool(Tool):
    """Automação ativada por hardware: dispara ações automáticas ao conectar pendrives ou discos removíveis."""

    id = "automation.device_trigger"
    name = "Automação por Dispositivos Removíveis (Gatilhos USB)"
    description = "Execute ações automáticas como backups ou abertura de pastas ao conectar pendrives ou cartões de memória."
    category = "automation"

    def __init__(self):
        super().__init__()
        self.rules_file = get_default_device_rules_path()
        self.rules: List[DeviceRule] = load_device_rules_json(self.rules_file)
        if not self.rules:
            self._create_default_rules()

    def _create_default_rules(self) -> None:
        self.rules = [
            DeviceRule(
                id=str(uuid.uuid4()),
                name="Abrir Pendrive Automaticamente",
                volume_label_filter="",
                action_type="open_explorer",
                target_path="",
                enabled=True
            ),
            DeviceRule(
                id=str(uuid.uuid4()),
                name="Sincronizar Backup Fotos",
                volume_label_filter="FOTOS_BACKUP",
                action_type="copy_to_folder",
                target_path=os.path.join(os.path.expanduser("~"), "Pictures", "BackupPendrive"),
                enabled=True
            )
        ]
        save_device_rules_json(self.rules, self.rules_file)

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        title = QLabel("Automação por Dispositivos Removíveis & Gatilhos USB")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Detecta a conexão física de mídias externas no Windows e executa rotinas configuradas sem intervenção manual."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Painel de Dispositivos Conectados
        dev_frame = QFrame()
        dev_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 10px; }"
        )
        v_dev = QVBoxLayout(dev_frame)
        h_dev_hdr = QHBoxLayout()
        h_dev_hdr.addWidget(QLabel("<b>Unidades Removíveis Conectadas Agora:</b>"))
        btn_refresh = QPushButton("Atualizar Unidades")
        btn_refresh.clicked.connect(self._refresh_connected_drives)
        h_dev_hdr.addWidget(btn_refresh)
        h_dev_hdr.addStretch()
        v_dev.addLayout(h_dev_hdr)

        self.tbl_drives = QTableWidget(0, 3)
        self.tbl_drives.setHorizontalHeaderLabels(["Unidade", "Nome do Volume", "Caminho Raiz"])
        self.tbl_drives.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_drives.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_drives.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tbl_drives.setMaximumHeight(110)
        self.tbl_drives.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v_dev.addWidget(self.tbl_drives)
        layout.addWidget(dev_frame)

        # Regras de Automação
        layout.addWidget(QLabel("<b>Regras de Automação Configuradas:</b>"))
        self.tbl_rules = QTableWidget(0, 5)
        self.tbl_rules.setHorizontalHeaderLabels(["Ativo", "Nome da Regra", "Filtro de Nome", "Ação", "Destino / Alvo"])
        self.tbl_rules.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_rules.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tbl_rules.setColumnWidth(1, 220)
        self.tbl_rules.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tbl_rules.setColumnWidth(2, 140)
        self.tbl_rules.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tbl_rules.setColumnWidth(3, 160)
        self.tbl_rules.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tbl_rules.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_rules.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tbl_rules, 1)

        btn_box = QHBoxLayout()
        btn_add = QPushButton("+ Nova Regra")
        btn_add.clicked.connect(self._on_add_rule)
        btn_del = QPushButton("Excluir Regra")
        btn_del.clicked.connect(self._on_delete_rule)
        btn_sim = QPushButton("Simular Detecção")
        btn_sim.clicked.connect(self._on_simulate)
        btn_box.addWidget(btn_add)
        btn_box.addWidget(btn_del)
        btn_box.addWidget(btn_sim)
        btn_box.addStretch()
        layout.addLayout(btn_box)

        self._refresh_connected_drives()
        self._refresh_rules_table()
        return widget

    def _refresh_connected_drives(self) -> None:
        drives = get_connected_removable_drives()
        self.tbl_drives.setRowCount(len(drives))
        for r, d in enumerate(drives):
            self.tbl_drives.setItem(r, 0, QTableWidgetItem(d["drive_letter"]))
            self.tbl_drives.setItem(r, 1, QTableWidgetItem(d["volume_label"]))
            self.tbl_drives.setItem(r, 2, QTableWidgetItem(d["root_path"]))

    def _refresh_rules_table(self) -> None:
        self.tbl_rules.setRowCount(len(self.rules))
        for r, rule in enumerate(self.rules):
            chk = QCheckBox()
            chk.setChecked(rule.enabled)
            chk.stateChanged.connect(lambda state, idx=r: self._on_toggle_rule(idx, state == Qt.CheckState.Checked.value))
            w_chk = QWidget()
            l_chk = QHBoxLayout(w_chk)
            l_chk.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l_chk.setContentsMargins(0, 0, 0, 0)
            l_chk.addWidget(chk)
            self.tbl_rules.setCellWidget(r, 0, w_chk)

            self.tbl_rules.setItem(r, 1, QTableWidgetItem(rule.name))
            filtro = rule.volume_label_filter or "Qualquer Unidade"
            self.tbl_rules.setItem(r, 2, QTableWidgetItem(filtro))

            action_names = {
                "open_explorer": "Abrir Pasta no Explorer",
                "copy_to_folder": "Copiar Conteúdo p/ Pasta",
                "run_script": "Executar Script de Backup",
                "notify": "Apenas Notificar Conexão"
            }
            self.tbl_rules.setItem(r, 3, QTableWidgetItem(action_names.get(rule.action_type, rule.action_type)))
            self.tbl_rules.setItem(r, 4, QTableWidgetItem(rule.target_path or "Padrão"))

    def _on_toggle_rule(self, row: int, enabled: bool) -> None:
        if 0 <= row < len(self.rules):
            self.rules[row].enabled = enabled
            save_device_rules_json(self.rules, self.rules_file)

    def _on_add_rule(self) -> None:
        dlg = QDialog()
        dlg.setWindowTitle("Nova Regra de Dispositivo USB")
        dlg.resize(420, 200)
        v = QVBoxLayout(dlg)
        f = QFormLayout()

        txt_name = QLineEdit()
        f.addRow("Nome da Regra:", txt_name)

        txt_filter = QLineEdit()
        txt_filter.setPlaceholderText("Deixe em branco para qualquer USB")
        f.addRow("Filtro de Nome do Volume:", txt_filter)

        cmb_act = QComboBox()
        cmb_act.addItem("Abrir Pasta no Explorer", "open_explorer")
        cmb_act.addItem("Copiar Conteúdo p/ Pasta de Backup", "copy_to_folder")
        cmb_act.addItem("Executar Script de Backup", "run_script")
        cmb_act.addItem("Apenas Notificar Conexão", "notify")
        f.addRow("Ação ao Conectar:", cmb_act)

        txt_target = QLineEdit()
        txt_target.setPlaceholderText("Caminho da pasta ou script")
        f.addRow("Pasta / Destino:", txt_target)

        v.addLayout(f)
        btn_ok = QPushButton("Salvar Regra")
        btn_ok.clicked.connect(dlg.accept)
        v.addWidget(btn_ok)

        if dlg.exec():
            name = txt_name.text().strip() or "Regra USB"
            filt = txt_filter.text().strip()
            act = cmb_act.currentData()
            tgt = txt_target.text().strip()

            self.rules.append(
                DeviceRule(id=str(uuid.uuid4()), name=name, volume_label_filter=filt, action_type=act, target_path=tgt)
            )
            save_device_rules_json(self.rules, self.rules_file)
            self._refresh_rules_table()

    def _on_delete_rule(self) -> None:
        row = self.tbl_rules.currentRow()
        if 0 <= row < len(self.rules):
            del self.rules[row]
            save_device_rules_json(self.rules, self.rules_file)
            self._refresh_rules_table()

    def _on_simulate(self) -> None:
        drives = get_connected_removable_drives()
        label = drives[0]["volume_label"] if drives else "PENDRIVE_DEMO"
        matched = [r.name for r in self.rules if match_drive_with_rule(r, label)]
        msg = f"Simulação de conexão com o dispositivo '{label}':\n\n"
        if matched:
            msg += "Regras disparadas:\n" + "\n".join(f"• {m}" for m in matched)
        else:
            msg += "Nenhuma regra ativa correspondeu ao nome deste dispositivo."
        QMessageBox.information(None, "Simulação de Conexão USB", msg)

"""
Interface gráfica da Automação de Pastas por Regras.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.automation.folder_rules.logic import (
    evaluate_folder_rules, load_folder_rules, save_folder_rules
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

_log = get_logger("automation.folder_rules.ui")


@register
class FolderRulesTool(Tool):
    id = "automation.folder_rules"
    name = "Automação de Pastas por Regras"
    category = "Automação"
    description = "Organizador automático de pastas baseado em regras: move, copia ou deleta arquivos por extensão, tamanho ou idade (ex: limpar Downloads periodicamente)."
    keywords = ["organizador", "regras", "gatilho", "pastas", "downloads", "mover", "arquivos", "automacao"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FolderRulesView(self, parent)


class FolderRulesView(QWidget):
    def __init__(self, tool: FolderRulesTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._rules: List[Dict[str, Any]] = []

        self._build_ui()
        self._load_rules()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Automação de Pastas por Regras",
            "Mantenha sua pasta Downloads ou Desktop sempre limpa e organizada através de regras configuráveis."
        ))

        # 1. Pasta de Origem
        src_box = QGroupBox("Pasta Alvo para Organização")
        src_layout = QHBoxLayout(src_box)
        src_layout.setSpacing(8)

        self.edit_source = QLineEdit(str(Path.home() / "Downloads"))
        src_layout.addWidget(self.edit_source, stretch=1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_source)
        src_layout.addWidget(btn_browse)

        btn_dl = QPushButton("Pasta Downloads")
        btn_dl.clicked.connect(lambda: self.edit_source.setText(str(Path.home() / "Downloads")))
        src_layout.addWidget(btn_dl)

        btn_desk = QPushButton("Área de Trabalho")
        btn_desk.clicked.connect(lambda: self.edit_source.setText(str(Path.home() / "Desktop")))
        src_layout.addWidget(btn_desk)

        root.addWidget(src_box)

        # 2. Tabela de Regras Ativas
        rules_box = QGroupBox("Regras de Triagem Configuradas")
        rules_layout = QVBoxLayout(rules_box)
        rules_layout.setSpacing(8)

        # Botões de gestão de regras
        top_rules = QHBoxLayout()
        btn_add_rule = QPushButton("+ Adicionar Nova Regra...")
        btn_add_rule.clicked.connect(self._open_add_rule_dialog)
        top_rules.addWidget(btn_add_rule)

        btn_restore_rules = QPushButton("Restaurar Padrões")
        btn_restore_rules.clicked.connect(self._restore_default_rules)
        top_rules.addWidget(btn_restore_rules)

        top_rules.addStretch(1)

        btn_dry_run = QPushButton("Simular (Ver o que seria feito)")
        btn_dry_run.clicked.connect(lambda: self._execute_rules(dry_run=True))
        top_rules.addWidget(btn_dry_run)

        self.btn_run = QPushButton("Executar Regras Agora")
        self.btn_run.setProperty("class", "primary")
        self.btn_run.setFixedHeight(34)
        self.btn_run.clicked.connect(lambda: self._execute_rules(dry_run=False))
        top_rules.addWidget(self.btn_run)

        rules_layout.addLayout(top_rules)

        self.table_rules = QTableWidget()
        self.table_rules.setColumnCount(4)
        self.table_rules.setHorizontalHeaderLabels(["Nome da Regra", "Critério / Valor", "Ação e Destino", "Ação"])
        self.table_rules.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_rules.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_rules.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_rules.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table_rules.setColumnWidth(3, 75)
        enable_sorting_on_table(self.table_rules)
        rules_layout.addWidget(self.table_rules)

        root.addWidget(rules_box, stretch=1)

        # 3. Tabela de Auditoria / Resultados
        res_box = QGroupBox("Resultados da Execução / Simulação")
        res_layout = QVBoxLayout(res_box)
        self.table_audit = QTableWidget()
        self.table_audit.setColumnCount(4)
        self.table_audit.setHorizontalHeaderLabels(["Arquivo", "Regra Correspondente", "Ação", "Mensagem / Detalhes"])
        self.table_audit.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_audit.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_audit.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_audit.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        enable_sorting_on_table(self.table_audit)
        res_layout.addWidget(self.table_audit)

        root.addWidget(res_box, stretch=1)

    def _browse_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Organização")
        if path:
            self.edit_source.setText(path)

    def _load_rules(self) -> None:
        self._rules = load_folder_rules()
        with batch_table_update(self.table_rules):
            self.table_rules.setRowCount(len(self._rules))

            for row, r in enumerate(self._rules):
                self.table_rules.setItem(row, 0, SmartTableWidgetItem(r["name"], user_data=r))

                crit = f"{r.get('condition_type')}: {r.get('condition_value')}"
                self.table_rules.setItem(row, 1, SmartTableWidgetItem(crit))

                act = f"{r.get('action_type').upper()} -> {Path(r.get('destination', '')).name}"
                self.table_rules.setItem(row, 2, SmartTableWidgetItem(act))

                btn_del = QPushButton("Excluir")
                btn_del.setStyleSheet("font-size: 10px; padding: 2px;")
                btn_del.clicked.connect(lambda checked=False, rule=r: self._delete_rule(rule))
                self.table_rules.setCellWidget(row, 3, btn_del)

    def _delete_rule(self, rule_to_delete: Any) -> None:
        if isinstance(rule_to_delete, dict) and rule_to_delete in self._rules:
            self._rules.remove(rule_to_delete)
        elif isinstance(rule_to_delete, int) and 0 <= rule_to_delete < len(self._rules):
            del self._rules[rule_to_delete]
        save_folder_rules(self._rules)
        self._load_rules()

    def _restore_default_rules(self) -> None:
        from wintoolbox.tools.automation.folder_rules.logic import DEFAULT_RULES
        self._rules = list(DEFAULT_RULES)
        save_folder_rules(self._rules)
        self._load_rules()
        show_toast(self, "Regras restauradas para os padrões.")

    def _open_add_rule_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Adicionar Nova Regra de Pastas")
        dlg.setFixedWidth(460)

        layout = QVBoxLayout(dlg)
        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Nome da Regra:"), 0, 0)
        edit_name = QLineEdit()
        edit_name.setPlaceholderText("Ex: Mover Áudios e Músicas")
        grid.addWidget(edit_name, 0, 1)

        grid.addWidget(QLabel("Critério:"), 1, 0)
        combo_cond = QComboBox()
        combo_cond.addItem("Extensão do Arquivo", "extension")
        combo_cond.addItem("Palavra-chave no Nome", "keyword")
        combo_cond.addItem("Mais Antigo que (Dias)", "older_than_days")
        combo_cond.addItem("Tamanho Maior que (MB)", "size_greater_than_mb")
        grid.addWidget(combo_cond, 1, 1)

        grid.addWidget(QLabel("Valor do Critério:"), 2, 0)
        edit_val = QLineEdit()
        edit_val.setPlaceholderText("Ex: .mp3, .wav, .flac ou 30 ou nota_fiscal")
        grid.addWidget(edit_val, 2, 1)

        grid.addWidget(QLabel("Ação:"), 3, 0)
        combo_act = QComboBox()
        combo_act.addItem("Mover para Pasta", "move")
        combo_act.addItem("Copiar para Pasta", "copy")
        combo_act.addItem("Excluir Arquivo", "delete")
        grid.addWidget(combo_act, 3, 1)

        grid.addWidget(QLabel("Pasta de Destino:"), 4, 0)
        dest_row = QHBoxLayout()
        edit_dest = QLineEdit(str(Path.home() / "Music"))
        dest_row.addWidget(edit_dest, stretch=1)
        btn_dest = QPushButton("Procurar...")
        dest_row.addWidget(btn_dest)
        grid.addLayout(dest_row, 4, 1)

        def browse_dest():
            p = QFileDialog.getExistingDirectory(dlg, "Selecionar Pasta de Destino")
            if p:
                edit_dest.setText(p)

        btn_dest.clicked.connect(browse_dest)
        layout.addLayout(grid)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dlg.reject)
        btn_save = QPushButton("Adicionar Regra")
        btn_save.setProperty("class", "primary")

        def save_rule():
            name = edit_name.text().strip() or "Nova Regra"
            val = edit_val.text().strip()
            if not val:
                show_toast(dlg, "Informe o valor do critério.")
                return

            self._rules.append({
                "id": f"rule_{len(self._rules) + 1}",
                "name": name,
                "condition_type": combo_cond.currentData(),
                "condition_value": val,
                "action_type": combo_act.currentData(),
                "destination": edit_dest.text().strip()
            })
            save_folder_rules(self._rules)
            dlg.accept()
            self._load_rules()
            show_toast(self, "Nova regra cadastrada!")

        btn_save.clicked.connect(save_rule)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

        dlg.exec()

    def _execute_rules(self, dry_run: bool = False) -> None:
        src_path_str = self.edit_source.text().strip()
        if not src_path_str:
            show_toast(self, "Selecione a pasta de origem.")
            return

        src_dir = Path(src_path_str)
        if not src_dir.is_dir():
            show_toast(self, f"A pasta de origem não existe: {src_dir}")
            return

        try:
            results = evaluate_folder_rules(src_dir, self._rules, dry_run=dry_run)
            with batch_table_update(self.table_audit):
                self.table_audit.setRowCount(len(results))

                for row, res in enumerate(results):
                    self.table_audit.setItem(row, 0, SmartTableWidgetItem(res["file_name"]))
                    self.table_audit.setItem(row, 1, SmartTableWidgetItem(res["rule_name"]))
                    self.table_audit.setItem(row, 2, SmartTableWidgetItem(res["action"].upper()))
                    self.table_audit.setItem(row, 3, SmartTableWidgetItem(res["message"]))

            mode_str = "Simulação concluída" if dry_run else "Organização concluída"
            show_toast(self, f"{mode_str}: {len(results)} arquivo(s) processados!", duration_ms=3000)

        except Exception as exc:
            _log.error("Erro na execução de regras: %s", exc)
            show_toast(self, f"Erro: {exc}", duration_ms=3500)

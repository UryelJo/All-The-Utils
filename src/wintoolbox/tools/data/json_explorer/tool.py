"""
Interface gráfica Fluent para o Explorador de JSON.
Visualizador em árvore interativo, busca em chaves/valores e consultas JSONPath.
"""
import json
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.data.json_explorer.logic import (
    calculate_statistics,
    get_value_type_label,
    parse_json,
    query_by_jsonpath,
    search_nodes,
)


@register
class JsonExplorerTool(Tool):
    id = "json_explorer"
    name = "Explorador de JSON"
    description = "Visualizador em árvore interativo para arquivos JSON complexos, com busca e consultas JSONPath."
    category = "Dados e Estruturas"
    icon = "Code"
    tags = ["json", "explorer", "árvore", "jsonpath", "visualizador", "dados"]

    def __init__(self) -> None:
        super().__init__()
        self._parsed_data: Any = None

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra superior com ações rápidas
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        btn_open = QPushButton("Abrir Arquivo JSON...")
        btn_sample = QPushButton("Carregar Exemplo")
        btn_expand = QPushButton("Expandir Tudo")
        btn_collapse = QPushButton("Recolher Tudo")
        btn_stats = QPushButton("Estatísticas")

        top_bar.addWidget(btn_open)
        top_bar.addWidget(btn_sample)
        top_bar.addWidget(btn_expand)
        top_bar.addWidget(btn_collapse)
        top_bar.addWidget(btn_stats)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        # Barra de Pesquisa e Filtro / JSONPath
        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)

        lbl_search = QLabel("Buscar:")
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Digite texto para buscar em chaves/valores ou expressão JSONPath (ex: $..title)...")

        self.chk_jsonpath = QCheckBox("Modo JSONPath")
        btn_search = QPushButton("Buscar")
        btn_clear_search = QPushButton("Limpar")

        search_bar.addWidget(lbl_search)
        search_bar.addWidget(self.edit_search, 1)
        search_bar.addWidget(self.chk_jsonpath)
        search_bar.addWidget(btn_search)
        search_bar.addWidget(btn_clear_search)

        layout.addLayout(search_bar)

        self.lbl_status = QLabel("Cole um JSON à esquerda ou abra um arquivo para explorar.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Splitter principal: Editor de texto à esquerda vs Árvore à direita
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel esquerdo: Entrada de texto
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("Entrada JSON:"))
        btn_parse = QPushButton("Analisar / Recarregar Árvore")
        btn_format = QPushButton("Formatar JSON")
        left_header.addStretch()
        left_header.addWidget(btn_format)
        left_header.addWidget(btn_parse)
        left_layout.addLayout(left_header)

        self.text_editor = QPlainTextEdit()
        self.text_editor.setPlaceholderText("Cole seu texto JSON aqui...")
        left_layout.addWidget(self.text_editor)

        splitter.addWidget(left_widget)

        # Painel direito: Árvore hierárquica e preview do nó
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        right_layout.addWidget(QLabel("Estrutura Hierárquica:"))

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Chave / Índice", "Tipo", "Valor Resumido"])
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_widget.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree_widget.setColumnWidth(0, 200)

        right_layout.addWidget(self.tree_widget, 3)

        # Preview do nó selecionado
        right_layout.addWidget(QLabel("Valor Completo do Nó Selecionado:"))
        self.node_preview = QPlainTextEdit()
        self.node_preview.setReadOnly(True)
        self.node_preview.setMaximumHeight(130)
        right_layout.addWidget(self.node_preview, 1)

        splitter.addWidget(right_widget)
        splitter.setSizes([380, 620])

        layout.addWidget(splitter, 1)

        # Conexões
        btn_open.clicked.connect(self._on_open_file)
        btn_sample.clicked.connect(self._on_load_sample)
        btn_parse.clicked.connect(self._on_parse_input)
        btn_format.clicked.connect(self._on_format_json)
        btn_expand.clicked.connect(self.tree_widget.expandAll)
        btn_collapse.clicked.connect(self.tree_widget.collapseAll)
        btn_stats.clicked.connect(self._on_show_stats)
        btn_search.clicked.connect(self._on_search)
        btn_clear_search.clicked.connect(self._on_clear_search)
        self.edit_search.returnPressed.connect(self._on_search)
        self.tree_widget.currentItemChanged.connect(self._on_tree_item_selected)

        return container

    def _on_format_json(self) -> None:
        text = self.text_editor.toPlainText().strip()
        if not text:
            return
        ok, data, err = parse_json(text)
        if not ok:
            QMessageBox.warning(None, "JSON Inválido", f"Não foi possível formatar: {err}")
            return
        self.text_editor.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))

    def _on_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(None, "Abrir Arquivo JSON", "", "Arquivos JSON (*.json);;Todos os Arquivos (*.*)")
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.text_editor.setPlainText(content)
            self._on_parse_input()
        except Exception as exc:
            QMessageBox.critical(None, "Erro ao Ler Arquivo", f"Falha ao abrir {file_path}: {exc}")

    def _on_load_sample(self) -> None:
        sample = {
            "loja": {
                "nome": "Livraria do Desenvolvedor",
                "aberta": True,
                "fundacao": 2021,
                "endereco": {
                    "cidade": "São Paulo",
                    "uf": "SP",
                    "cep": "01310-100",
                },
                "catalogo": [
                    {
                        "id": 1,
                        "titulo": "Arquitetura Limpa em Python",
                        "preco": 89.9,
                        "estoque": 15,
                        "autores": ["Robert", "Martin"],
                    },
                    {
                        "id": 2,
                        "titulo": "Design Patterns Modernos",
                        "preco": 120.0,
                        "estoque": 5,
                        "autores": ["GoF", "Refatorado"],
                    },
                    {
                        "id": 3,
                        "titulo": "Guia Prático do Windows 11 Fluent",
                        "preco": 65.5,
                        "estoque": 30,
                        "autores": ["Microsoft", "Comunidade"],
                    },
                ],
            }
        }
        self.text_editor.setPlainText(json.dumps(sample, indent=2, ensure_ascii=False))
        self._on_parse_input()

    def _on_parse_input(self) -> None:
        text = self.text_editor.toPlainText().strip()
        if not text:
            self.tree_widget.clear()
            self._parsed_data = None
            self.lbl_status.setText("Entrada vazia.")
            return

        ok, data, err = parse_json(text)
        if not ok:
            self.lbl_status.setText(f"❌ {err}")
            QMessageBox.warning(None, "Erro de JSON", err)
            return

        self._parsed_data = data
        self._populate_tree(data)
        stats = calculate_statistics(data)
        self.lbl_status.setText(
            f"✅ JSON carregado com sucesso. {stats['total_nodes']} nós, {stats['total_keys']} chaves, profundidade máx: {stats['max_depth']}."
        )

    def _populate_tree(self, data: Any) -> None:
        self.tree_widget.clear()

        def _build_nodes(parent_item: Optional[QTreeWidgetItem], key: str, val: Any) -> None:
            type_label = get_value_type_label(val)
            val_preview = ""
            if not isinstance(val, (dict, list)):
                val_preview = str(val)

            item = QTreeWidgetItem([str(key), type_label, val_preview])
            item.setData(0, Qt.ItemDataRole.UserRole, val)

            if parent_item is None:
                self.tree_widget.addTopLevelItem(item)
            else:
                parent_item.addChild(item)

            if isinstance(val, dict):
                for k, v in val.items():
                    _build_nodes(item, str(k), v)
            elif isinstance(val, list):
                for idx, v in enumerate(val):
                    _build_nodes(item, f"[{idx}]", v)

        _build_nodes(None, "$", data)
        self.tree_widget.expandToDepth(1)

    def _on_tree_item_selected(self, current: Optional[QTreeWidgetItem], previous: Optional[QTreeWidgetItem]) -> None:
        if not current:
            self.node_preview.clear()
            return

        raw_val = current.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(raw_val, (dict, list)):
            self.node_preview.setPlainText(json.dumps(raw_val, indent=2, ensure_ascii=False))
        else:
            self.node_preview.setPlainText(str(raw_val))

    def _on_show_stats(self) -> None:
        if self._parsed_data is None:
            QMessageBox.information(None, "Estatísticas", "Nenhum JSON analisado ainda.")
            return

        stats = calculate_statistics(self._parsed_data)
        counts = stats["type_counts"]
        msg = (
            f"Total de nós: {stats['total_nodes']}\n"
            f"Total de chaves em objetos: {stats['total_keys']}\n"
            f"Profundidade máxima: {stats['max_depth']}\n\n"
            f"Contagem por tipo:\n"
            f"  - Objetos: {counts['object']}\n"
            f"  - Arrays: {counts['array']}\n"
            f"  - Strings: {counts['string']}\n"
            f"  - Números: {counts['number']}\n"
            f"  - Booleanos: {counts['boolean']}\n"
            f"  - Nulos: {counts['null']}"
        )
        QMessageBox.information(None, "Estatísticas do JSON", msg)

    def _on_search(self) -> None:
        if self._parsed_data is None:
            return

        query = self.edit_search.text().strip()
        if not query:
            self._populate_tree(self._parsed_data)
            return

        if self.chk_jsonpath.isChecked():
            try:
                results = query_by_jsonpath(self._parsed_data, query)
                self.tree_widget.clear()
                for r in results:
                    item = QTreeWidgetItem([r["path"], r["type"], str(r["value"])[:250]])
                    item.setData(0, Qt.ItemDataRole.UserRole, r.get("raw_value", r["value"]))
                    self.tree_widget.addTopLevelItem(item)
                self.lbl_status.setText(f"JSONPath '{query}': {len(results)} correspondências encontradas.")
            except Exception as exc:
                QMessageBox.warning(None, "Erro JSONPath", f"Expressão inválida: {exc}")
        else:
            matches = search_nodes(self._parsed_data, query)
            self.tree_widget.clear()
            for m in matches:
                item = QTreeWidgetItem([m["path"], m["type"], str(m["value"])[:250]])
                item.setData(0, Qt.ItemDataRole.UserRole, m["value"])
                self.tree_widget.addTopLevelItem(item)
            self.lbl_status.setText(f"Busca por '{query}': {len(matches)} nós encontrados.")

    def _on_clear_search(self) -> None:
        self.edit_search.clear()
        if self._parsed_data is not None:
            self._populate_tree(self._parsed_data)
            self.lbl_status.setText("Árvore restaurada.")

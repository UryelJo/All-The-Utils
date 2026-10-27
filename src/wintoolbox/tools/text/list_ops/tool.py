"""
Interface gráfica Fluent da ferramenta Operações entre Listas de Texto.
"""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.list_ops.logic import (
    execute_list_operation,
    ListOperation,
    parse_lines,
)


@register
class ListOpsTool(Tool):
    """Ferramenta para operações de teoria dos conjuntos entre duas listas de texto."""
    id = "text.list_ops"
    title = "Operações entre Listas"
    category = "Texto e Redação"
    description = (
        "Compara e combina listas de texto: união, interseção, diferença (A - B e B - A), "
        "diferença simétrica, deduplicação e ordenação natural."
    )
    icon = "List"

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Operações entre Listas de Texto")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Cole duas listas (uma linha por item) para calcular união, itens em comum (interseção), "
            "itens exclusivos de cada lista ou diferença simétrica com deduplicação e ordenação inteligente."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Barra de Opções Superior
        opt_frame = QFrame()
        opt_frame.setFrameShape(QFrame.Shape.StyledPanel)
        opt_layout = QHBoxLayout(opt_frame)
        opt_layout.setContentsMargins(8, 8, 8, 8)
        opt_layout.setSpacing(14)

        self.chk_case_sensitive = QCheckBox("Diferenciar Maiúsculas/Minúsculas")
        self.chk_case_sensitive.setChecked(False)
        opt_layout.addWidget(self.chk_case_sensitive)

        self.chk_strip = QCheckBox("Remover espaços das pontas (Trim)")
        self.chk_strip.setChecked(True)
        opt_layout.addWidget(self.chk_strip)

        self.chk_ignore_empty = QCheckBox("Ignorar linhas vazias")
        self.chk_ignore_empty.setChecked(True)
        opt_layout.addWidget(self.chk_ignore_empty)

        opt_layout.addWidget(QLabel("Ordenação:"))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["Sem Ordenar (Ordem Original)", "Alfabética A-Z", "Alfabética Z-A", "Ordenação Natural"])
        opt_layout.addWidget(self.combo_sort)

        opt_layout.addStretch()
        layout.addWidget(opt_frame)

        # Splitter Vertical (Entradas em cima, Resultado embaixo)
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Splitter Horizontal para as Listas A e B
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Lista A
        grp_a = QGroupBox("Lista A")
        v_a = QVBoxLayout(grp_a)
        self.lbl_count_a = QLabel("0 itens")
        v_a.addWidget(self.lbl_count_a)

        self.text_a = QTextEdit()
        self.text_a.setPlaceholderText("Cole os itens da Lista A aqui (um por linha)...")
        self.text_a.textChanged.connect(self._update_counts)
        v_a.addWidget(self.text_a)

        btn_bar_a = QHBoxLayout()
        btn_load_a = QPushButton("Abrir Arquivo...")
        btn_load_a.clicked.connect(lambda: self._load_file_to(self.text_a))
        btn_bar_a.addWidget(btn_load_a)
        btn_clear_a = QPushButton("Limpar")
        btn_clear_a.clicked.connect(self.text_a.clear)
        btn_bar_a.addWidget(btn_clear_a)
        v_a.addLayout(btn_bar_a)

        top_splitter.addWidget(grp_a)

        # Painel Central de Ações
        center_widget = QWidget()
        v_center = QVBoxLayout(center_widget)
        v_center.setSpacing(8)
        v_center.addStretch()

        btn_union = QPushButton("União (A ∪ B)")
        btn_union.clicked.connect(lambda: self._on_operation(ListOperation.UNION))
        v_center.addWidget(btn_union)

        btn_intersect = QPushButton("Interseção (A ∩ B)")
        btn_intersect.setStyleSheet("font-weight: bold;")
        btn_intersect.clicked.connect(lambda: self._on_operation(ListOperation.INTERSECTION))
        v_center.addWidget(btn_intersect)

        btn_diff_a = QPushButton("Apenas em A (A - B)")
        btn_diff_a.clicked.connect(lambda: self._on_operation(ListOperation.DIFF_A_MINUS_B))
        v_center.addWidget(btn_diff_a)

        btn_diff_b = QPushButton("Apenas em B (B - A)")
        btn_diff_b.clicked.connect(lambda: self._on_operation(ListOperation.DIFF_B_MINUS_A))
        v_center.addWidget(btn_diff_b)

        btn_sym_diff = QPushButton("Diferença Simétrica (A Δ B)")
        btn_sym_diff.clicked.connect(lambda: self._on_operation(ListOperation.SYMMETRIC_DIFF))
        v_center.addWidget(btn_sym_diff)

        btn_concat = QPushButton("Concatenar (A + B)")
        btn_concat.clicked.connect(lambda: self._on_operation(ListOperation.CONCAT))
        v_center.addWidget(btn_concat)

        v_center.addStretch()
        top_splitter.addWidget(center_widget)

        # Lista B
        grp_b = QGroupBox("Lista B")
        v_b = QVBoxLayout(grp_b)
        self.lbl_count_b = QLabel("0 itens")
        v_b.addWidget(self.lbl_count_b)

        self.text_b = QTextEdit()
        self.text_b.setPlaceholderText("Cole os itens da Lista B aqui (um por linha)...")
        self.text_b.textChanged.connect(self._update_counts)
        v_b.addWidget(self.text_b)

        btn_bar_b = QHBoxLayout()
        btn_load_b = QPushButton("Abrir Arquivo...")
        btn_load_b.clicked.connect(lambda: self._load_file_to(self.text_b))
        btn_bar_b.addWidget(btn_load_b)
        btn_clear_b = QPushButton("Limpar")
        btn_clear_b.clicked.connect(self.text_b.clear)
        btn_bar_b.addWidget(btn_clear_b)
        v_b.addLayout(btn_bar_b)

        top_splitter.addWidget(grp_b)
        top_splitter.setSizes([380, 140, 380])
        main_splitter.addWidget(top_splitter)

        # Resultado
        grp_res = QGroupBox("Resultado da Operação")
        v_res = QVBoxLayout(grp_res)

        self.lbl_res_info = QLabel("Nenhuma operação executada ainda.")
        self.lbl_res_info.setStyleSheet("font-weight: bold; color: #0078D4;")
        v_res.addWidget(self.lbl_res_info)

        self.text_res = QTextEdit()
        self.text_res.setReadOnly(True)
        v_res.addWidget(self.text_res)

        res_bar = QHBoxLayout()
        btn_copy = QPushButton("Copiar Resultado")
        btn_copy.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_copy.clicked.connect(self._on_copy_result)
        res_bar.addWidget(btn_copy)

        btn_save = QPushButton("Salvar em Arquivo...")
        btn_save.clicked.connect(self._on_save_file)
        res_bar.addWidget(btn_save)

        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setStyleSheet("color: #107C41; font-weight: bold;")
        res_bar.addWidget(self.lbl_feedback)
        res_bar.addStretch()

        v_res.addLayout(res_bar)
        main_splitter.addWidget(grp_res)

        main_splitter.setSizes([360, 240])
        layout.addWidget(main_splitter, 1)

        # Exemplo inicial
        self.text_a.setPlainText("item1\nitem2\nitem3\nitem4\nitem10")
        self.text_b.setPlainText("item3\nitem4\nitem5\nitem6")
        self._update_counts()

        return container

    def _update_counts(self) -> None:
        lines_a = parse_lines(self.text_a.toPlainText(), self.chk_strip.isChecked(), self.chk_ignore_empty.isChecked())
        lines_b = parse_lines(self.text_b.toPlainText(), self.chk_strip.isChecked(), self.chk_ignore_empty.isChecked())
        self.lbl_count_a.setText(f"{len(lines_a)} itens")
        self.lbl_count_b.setText(f"{len(lines_b)} itens")

    def _load_file_to(self, target: QTextEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Abrir Arquivo de Lista", "", "Arquivos de Texto (*.txt *.csv);;Todos (*.*)")
        if path:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            target.setPlainText(text)

    def _on_operation(self, op: ListOperation) -> None:
        lines_a = parse_lines(self.text_a.toPlainText(), self.chk_strip.isChecked(), self.chk_ignore_empty.isChecked())
        lines_b = parse_lines(self.text_b.toPlainText(), self.chk_strip.isChecked(), self.chk_ignore_empty.isChecked())

        sort_map = {0: "none", 1: "asc", 2: "desc", 3: "natural"}
        sort_mode = sort_map.get(self.combo_sort.currentIndex(), "none")

        res_lines = execute_list_operation(
            list_a=lines_a,
            list_b=lines_b,
            operation=op,
            case_sensitive=self.chk_case_sensitive.isChecked(),
            deduplicate=True,
            sort_order=sort_mode,
        )

        self.text_res.setPlainText("\n".join(res_lines))
        self.lbl_res_info.setText(f"Operação '{op.value}' concluída: {len(res_lines)} resultado(s)")
        self.lbl_feedback.setText("")

    def _on_copy_result(self) -> None:
        txt = self.text_res.toPlainText()
        if txt:
            cb = QApplication.clipboard()
            if cb:
                cb.setText(txt)
                self.lbl_feedback.setText("Copiado!")

    def _on_save_file(self) -> None:
        txt = self.text_res.toPlainText()
        if not txt:
            return
        dest, _ = QFileDialog.getSaveFileName(None, "Salvar Lista Resultante", "resultado_listas.txt", "Texto (*.txt);;Todos (*.*)")
        if dest:
            Path(dest).write_text(txt, encoding="utf-8")
            self.lbl_feedback.setText(f"Salvo em {Path(dest).name}")

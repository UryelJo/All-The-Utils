"""
Interface gráfica Fluent para geração automática de esquemas e modelos de tipagem.
"""
import json
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.data.schema_infer.logic import (
    generate_dataclass,
    generate_pydantic_v2,
    generate_typescript,
    infer_json_schema,
)


@register
class SchemaInferTool(Tool):
    id = "data.schema_infer"
    name = "Inferência de Schemas e Modelos"
    description = "Gera automaticamente JSON Schema, modelos Pydantic v2, Python Dataclasses e TypeScript a partir de JSON."
    category = "Dados e Estruturas"
    icon = "Code"
    tags = ["schema", "pydantic", "typescript", "dataclass", "json", "tipagem", "modelos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra Superior de Controles
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        top_bar.addWidget(QLabel("Formato de Saída:"))
        self.combo_target = QComboBox()
        self.combo_target.addItem("JSON Schema (Draft 2020-12)", "json_schema")
        self.combo_target.addItem("Pydantic v2 (Python)", "pydantic")
        self.combo_target.addItem("Python Dataclass (@dataclass)", "dataclass")
        self.combo_target.addItem("TypeScript (Interfaces)", "typescript")
        top_bar.addWidget(self.combo_target)

        top_bar.addWidget(QLabel("Nome do Modelo Raiz:"))
        self.edit_root_name = QLineEdit("UsuarioResponse")
        self.edit_root_name.setMaximumWidth(180)
        top_bar.addWidget(self.edit_root_name)

        btn_sample = QPushButton("Carregar Exemplo")
        btn_generate = QPushButton("Gerar Esquema / Código")
        btn_generate.setStyleSheet("font-weight: bold;")

        top_bar.addWidget(btn_sample)
        top_bar.addWidget(btn_generate)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        self.lbl_status = QLabel("Cole um documento JSON de exemplo à esquerda e clique em Gerar.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Splitter Horizontal: Entrada JSON (Esquerda) vs Saída Tipada (Direita)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Lado Esquerdo
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(QLabel("Entrada JSON de Amostra:"))
        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText("Cole seu JSON de exemplo aqui...")
        left_layout.addWidget(self.text_input)
        splitter.addWidget(left_widget)

        # Lado Direito
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        right_header = QHBoxLayout()
        right_header.addWidget(QLabel("Código / Esquema Gerado:"))
        right_header.addStretch()
        btn_copy = QPushButton("Copiar Código")
        right_header.addWidget(btn_copy)
        right_layout.addLayout(right_header)

        self.text_output = QPlainTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setPlaceholderText("O código ou esquema gerado aparecerá aqui...")
        right_layout.addWidget(self.text_output)
        splitter.addWidget(right_widget)

        splitter.setSizes([450, 550])
        layout.addWidget(splitter, 1)

        # Conexões
        btn_sample.clicked.connect(self._on_load_sample)
        btn_generate.clicked.connect(self._on_generate)
        btn_copy.clicked.connect(self._on_copy)

        return container

    def _on_load_sample(self) -> None:
        sample = {
            "id": 1042,
            "nome_completo": "Ana Beatriz Costa",
            "ativo": True,
            "salario": 8450.75,
            "cargo": "Desenvolvedora Sênior",
            "skills": ["Python", "Qt", "TypeScript", "SQL"],
            "endereco": {
                "rua": "Av. Paulista, 1000",
                "cidade": "São Paulo",
                "uf": "SP",
                "cep": "01310-100",
            },
        }
        self.text_input.setPlainText(json.dumps(sample, indent=2, ensure_ascii=False))
        self._on_generate()

    def _on_generate(self) -> None:
        raw_text = self.text_input.toPlainText().strip()
        if not raw_text:
            self.lbl_status.setText("Entrada JSON vazia.")
            return

        try:
            data = json.loads(raw_text)
        except Exception as exc:
            QMessageBox.warning(None, "JSON Inválido", f"Erro ao decodificar JSON:\n{exc}")
            return

        root_name = self.edit_root_name.text().strip() or "RootModel"
        target_fmt = self.combo_target.currentData()

        try:
            if target_fmt == "json_schema":
                schema = infer_json_schema(data, title=root_name)
                code = json.dumps(schema, indent=2, ensure_ascii=False)
            elif target_fmt == "pydantic":
                code = generate_pydantic_v2(data, root_name=root_name)
            elif target_fmt == "dataclass":
                code = generate_dataclass(data, root_name=root_name)
            elif target_fmt == "typescript":
                code = generate_typescript(data, root_name=root_name)
            else:
                code = ""

            self.text_output.setPlainText(code)
            self.lbl_status.setText(f"✅ Esquema gerado com sucesso no formato '{self.combo_target.currentText()}'.")
        except Exception as exc:
            QMessageBox.critical(None, "Erro na Geração", f"Falha ao gerar modelos: {exc}")

    def _on_copy(self) -> None:
        code = self.text_output.toPlainText()
        if code:
            QApplication.clipboard().setText(code)
            self.lbl_status.setText("Código copiado para a área de transferência!")

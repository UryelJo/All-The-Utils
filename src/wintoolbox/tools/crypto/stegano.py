"""Ferramenta de esteganografia em imagens e áudio (FileTool).

Permite ocultar e extrair dados confidenciais em imagens PNG/BMP e arquivos
de áudio WAV PCM não comprimidos utilizando técnica LSB (Least Significant Bit),
com cabeçalho estruturado WTBXSTEG, validação de integridade por SHA-256 e
proteção opcional por senha.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.crypto.stegano_logic import (
    EXTENSOES_SUPORTADAS,
    ErroEstegano,
    embutir_em_arquivo,
    extrair_de_arquivo,
)


class SteganoOptionsWidget(QWidget):
    """Widget de opções com abas para ocultação e extração de dados esteganográficos."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Aba Ocultar
        tab_ocultar = QWidget()
        lay_ocultar = QVBoxLayout(tab_ocultar)
        lay_ocultar.setSpacing(8)

        grupo_tipo = QGroupBox("Tipo de Carga")
        lay_tipo = QHBoxLayout(grupo_tipo)
        self.rb_texto = QRadioButton("Texto Puro")
        self.rb_texto.setChecked(True)
        self.rb_arquivo = QRadioButton("Arquivo Binário")
        self.grupo_botoes_tipo = QButtonGroup(self)
        self.grupo_botoes_tipo.addButton(self.rb_texto)
        self.grupo_botoes_tipo.addButton(self.rb_arquivo)
        lay_tipo.addWidget(self.rb_texto)
        lay_tipo.addWidget(self.rb_arquivo)
        lay_tipo.addStretch()
        lay_ocultar.addWidget(grupo_tipo)

        self.txt_mensagem = QPlainTextEdit()
        self.txt_mensagem.setPlaceholderText("Digite a mensagem secreta a ser ocultada no contêiner...")
        self.txt_mensagem.setMaximumHeight(90)
        lay_ocultar.addWidget(self.txt_mensagem)

        # Seleção de arquivo
        linha_arquivo = QHBoxLayout()
        self.txt_caminho_arquivo = QLineEdit()
        self.txt_caminho_arquivo.setPlaceholderText("Selecione um arquivo para esconder...")
        self.txt_caminho_arquivo.setEnabled(False)
        self.btn_procurar = QPushButton("Procurar...")
        self.btn_procurar.setEnabled(False)
        self.btn_procurar.clicked.connect(self._selecionar_arquivo_carga)
        linha_arquivo.addWidget(self.txt_caminho_arquivo, stretch=1)
        linha_arquivo.addWidget(self.btn_procurar)
        lay_ocultar.addLayout(linha_arquivo)

        form_params = QFormLayout()
        self.txt_senha_ocultar = QLineEdit()
        self.txt_senha_ocultar.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_senha_ocultar.setPlaceholderText("Opcional: senha de proteção (XOR SHA-256)")
        form_params.addRow("Senha:", self.txt_senha_ocultar)

        self.spn_profundidade = QSpinBox()
        self.spn_profundidade.setRange(1, 4)
        self.spn_profundidade.setValue(1)
        self.spn_profundidade.setSuffix(" bit(s) por amostra")
        form_params.addRow("Profundidade LSB:", self.spn_profundidade)
        lay_ocultar.addLayout(form_params)

        self.tabs.addTab(tab_ocultar, "Ocultar Carga")

        # Aba Extrair
        tab_extrair = QWidget()
        lay_extrair = QVBoxLayout(tab_extrair)
        lay_extrair.setSpacing(8)

        lbl_info = QLabel(
            "Extrai cargas esteganográficas gravadas no formato WTBXSTEG.\n"
            "Se o arquivo foi protegido por senha, ela deve ser informada abaixo."
        )
        lbl_info.setStyleSheet("color: rgba(255,255,255,0.7);")
        lay_extrair.addWidget(lbl_info)

        form_extrair = QFormLayout()
        self.txt_senha_extrair = QLineEdit()
        self.txt_senha_extrair.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_senha_extrair.setPlaceholderText("Senha informada na gravação (se houver)")
        form_extrair.addRow("Senha:", self.txt_senha_extrair)
        lay_extrair.addLayout(form_extrair)
        lay_extrair.addStretch()

        self.tabs.addTab(tab_extrair, "Extrair Carga")

        # Conectar eventos de rádio
        self.rb_texto.toggled.connect(self._ao_mudar_tipo_carga)

    def _ao_mudar_tipo_carga(self) -> None:
        usar_texto = self.rb_texto.isChecked()
        self.txt_mensagem.setEnabled(usar_texto)
        self.txt_caminho_arquivo.setEnabled(not usar_texto)
        self.btn_procurar.setEnabled(not usar_texto)

    def _selecionar_arquivo_carga(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo para Ocultar")
        if caminho:
            self.txt_caminho_arquivo.setText(caminho)

    def get_options(self) -> Dict[str, Any]:
        """Extrai os parâmetros da interface para execução no worker."""
        modo = "ocultar" if self.tabs.currentIndex() == 0 else "extrair"
        if modo == "ocultar":
            is_texto = self.rb_texto.isChecked()
            return {
                "modo": "ocultar",
                "tipo_carga": "texto" if is_texto else "arquivo",
                "texto": self.txt_mensagem.toPlainText(),
                "arquivo_carga": self.txt_caminho_arquivo.text().strip(),
                "senha": self.txt_senha_ocultar.text(),
                "profundidade": self.spn_profundidade.value(),
            }
        return {
            "modo": "extrair",
            "senha": self.txt_senha_extrair.text(),
        }


@register
class SteganoTool(FileTool):
    """Ocultação e extração de dados esteganográficos em imagem e áudio."""

    id = "crypto.stegano"
    name = "Esteganografia em Imagem e Áudio"
    category = "Segurança e Análise"
    description = (
        "Oculta e extrai mensagens ou arquivos dentro de contêineres PNG, BMP e WAV "
        "via modulação LSB com integridade SHA-256 e cifra XOR opcional."
    )
    keywords = [
        "esteganografia",
        "stegano",
        "lsb",
        "ocultar",
        "esconder",
        "png",
        "bmp",
        "wav",
        "áudio",
        "imagem",
        "forense",
    ]
    accepts = list(EXTENSOES_SUPORTADAS)
    batch_kind = "per_file"
    parallel_mode = "thread"

    def build_options_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        self._options_widget = SteganoOptionsWidget(parent)
        return self._options_widget

    def get_options(self) -> Dict[str, Any]:
        if hasattr(self, "_options_widget") and self._options_widget is not None:
            return self._options_widget.get_options()
        return {"modo": "ocultar", "tipo_carga": "texto", "texto": "", "senha": "", "profundidade": 1}

    def output_ext(self, params: Dict[str, Any]) -> str:
        modo = (params or {}).get("modo", "ocultar")
        if modo == "extrair":
            return ".txt"
        return ""

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        src = Path(src)
        dst = Path(dst)
        opcoes = params or {}
        modo = opcoes.get("modo", "ocultar")
        tamanho_origem = src.stat().st_size if src.exists() else 0

        try:
            if ctx is not None and ctx.cancelled():
                return ItemResult(success=False, source_path=src, error="Operação cancelada pelo usuário.")

            if modo == "ocultar":
                tipo_carga = opcoes.get("tipo_carga", "texto")
                if tipo_carga == "texto":
                    texto = opcoes.get("texto", "")
                    if not texto:
                        return ItemResult(
                            success=False,
                            source_path=src,
                            error="Texto da mensagem vazia. Informe a mensagem a ser escondida.",
                        )
                    carga = texto.encode("utf-8")
                    eh_texto = True
                else:
                    caminho_carga = Path(opcoes.get("arquivo_carga", ""))
                    if not caminho_carga.exists() or not caminho_carga.is_file():
                        return ItemResult(
                            success=False,
                            source_path=src,
                            error=f"Arquivo de carga não encontrado: {caminho_carga}",
                        )
                    carga = caminho_carga.read_bytes()
                    eh_texto = False

                senha = opcoes.get("senha", "")
                profundidade = int(opcoes.get("profundidade", 1))

                resumo = embutir_em_arquivo(
                    caminho_origem=src,
                    caminho_destino=dst,
                    carga=carga,
                    senha=senha,
                    profundidade=profundidade,
                    texto=eh_texto,
                )

                tamanho_saida = dst.stat().st_size if dst.exists() else 0
                return ItemResult(
                    success=True,
                    source_path=src,
                    output_path=dst,
                    message=f"{len(carga)} bytes embutidos ({resumo['ocupacao']:.1f}% da capacidade usada)",
                    bytes_in=tamanho_origem,
                    bytes_out=tamanho_saida,
                )

            # Modo Extrair
            senha = opcoes.get("senha", "")
            extracao = extrair_de_arquivo(src, senha=senha)
            carga_extraida = extracao.get("carga", b"")
            texto_extraido = extracao.get("texto")

            if texto_extraido is not None:
                dst.write_text(texto_extraido, encoding="utf-8")
            else:
                dst.write_bytes(carga_extraida)

            tamanho_saida = dst.stat().st_size if dst.exists() else 0
            tipo_desc = "Texto" if texto_extraido is not None else "Binário"
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=f"{tipo_desc} extraído com sucesso ({len(carga_extraida)} bytes)",
                bytes_in=tamanho_origem,
                bytes_out=tamanho_saida,
            )

        except ErroEstegano as exc:
            return ItemResult(success=False, source_path=src, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return ItemResult(success=False, source_path=src, error=f"Erro inesperado: {exc}")

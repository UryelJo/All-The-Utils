"""
Interface gráfica do Criador e Juntador de Volumes Múltiplos (archive.multi_volume).
Permite dividir arquivos em partes de tamanho fixo (.001, .part01) e reconstruir arquivos a partir de partes.
"""
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.archive.multi_volume.logic import (
    VOLUME_PRESETS,
    split_file_into_volumes,
    find_volume_parts,
    join_volumes_to_file,
)


@register
class MultiVolumeTool(Tool):
    id = "archive.multi_volume"
    name = "Divisor e Juntador de Volumes"
    description = "Compactador em múltiplos volumes: divide arquivos grandes em pacotes particionados (.part1.rar, .z01, .001) para transporte fácil em pendrives ou e-mail."
    category = "Compactação"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tabs = QTabWidget()

        # Aba 1: Dividir em Volumes
        tab_split = QWidget()
        split_layout = QVBoxLayout(tab_split)
        split_layout.setSpacing(10)

        form_split = QFormLayout()

        # Arquivo de entrada
        self._edit_split_src = QLineEdit()
        self._edit_split_src.setPlaceholderText("Selecione o arquivo para dividir...")
        btn_browse_src = QPushButton("Procurar...")
        btn_browse_src.clicked.connect(self._on_browse_split_src)
        box_src = QHBoxLayout()
        box_src.addWidget(self._edit_split_src)
        box_src.addWidget(btn_browse_src)
        form_split.addRow("Arquivo Original:", box_src)

        # Pasta de saída
        self._edit_split_dst = QLineEdit()
        self._edit_split_dst.setPlaceholderText("Pasta onde os volumes serão salvos...")
        btn_browse_dst = QPushButton("Procurar...")
        btn_browse_dst.clicked.connect(self._on_browse_split_dst)
        box_dst = QHBoxLayout()
        box_dst.addWidget(self._edit_split_dst)
        box_dst.addWidget(btn_browse_dst)
        form_split.addRow("Pasta de Saída:", box_dst)

        # Tamanho do Volume
        self._combo_presets = QComboBox()
        for label, sz in VOLUME_PRESETS.items():
            self._combo_presets.addItem(label, sz)
        self._combo_presets.addItem("Tamanho Personalizado (MB)", -1)
        self._combo_presets.currentIndexChanged.connect(self._on_preset_changed)
        form_split.addRow("Tamanho do Volume:", self._combo_presets)

        self._spin_custom_mb = QSpinBox()
        self._spin_custom_mb.setRange(1, 100000)
        self._spin_custom_mb.setValue(25)
        self._spin_custom_mb.setSuffix(" MB")
        self._spin_custom_mb.setEnabled(False)
        form_split.addRow("Valor Customizado:", self._spin_custom_mb)

        # Padrão de Nomenclatura
        self._combo_pattern = QComboBox()
        self._combo_pattern.addItem("Extensão Numérica (ex: arquivo.zip.001, .002)", "EXT_NUM")
        self._combo_pattern.addItem("Sufixo de Parte (ex: arquivo.part01.zip, .part02.zip)", "PART_NUM")
        form_split.addRow("Padrão dos Nomes:", self._combo_pattern)

        split_layout.addLayout(form_split)

        self._btn_start_split = QPushButton("Dividir Arquivo em Volumes")
        self._btn_start_split.clicked.connect(self._on_split_click)
        split_layout.addWidget(self._btn_start_split)

        self._lbl_split_status = QLabel("Pronto.")
        split_layout.addWidget(self._lbl_split_status)
        split_layout.addStretch()
        tabs.addTab(tab_split, "Dividir em Volumes")

        # Aba 2: Juntar Volumes
        tab_join = QWidget()
        join_layout = QVBoxLayout(tab_join)
        join_layout.setSpacing(10)

        form_join = QFormLayout()

        # Primeiro volume
        self._edit_join_first = QLineEdit()
        self._edit_join_first.setPlaceholderText("Selecione a primeira parte (.001 ou .part01)...")
        btn_browse_first = QPushButton("Procurar...")
        btn_browse_first.clicked.connect(self._on_browse_join_first)
        box_first = QHBoxLayout()
        box_first.addWidget(self._edit_join_first)
        box_first.addWidget(btn_browse_first)
        form_join.addRow("Primeiro Volume:", box_first)

        # Arquivo de Saída Consolidado
        self._edit_join_out = QLineEdit()
        self._edit_join_out.setPlaceholderText("Caminho do arquivo consolidado de saída...")
        btn_browse_out = QPushButton("Salvar Como...")
        btn_browse_out.clicked.connect(self._on_browse_join_out)
        box_out = QHBoxLayout()
        box_out.addWidget(self._edit_join_out)
        box_out.addWidget(btn_browse_out)
        form_join.addRow("Arquivo Reconstruído:", box_out)

        join_layout.addLayout(form_join)

        # Tabela das partes detectadas
        lbl_detected = QLabel("Partes Detectadas na Sequência:")
        lbl_detected.setStyleSheet("font-weight: bold;")
        join_layout.addWidget(lbl_detected)

        self._table_parts = QTableWidget(0, 2)
        self._table_parts.setHorizontalHeaderLabels(["Arquivo de Parte", "Tamanho"])
        self._table_parts.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table_parts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        join_layout.addWidget(self._table_parts)

        self._btn_start_join = QPushButton("Juntar Volumes e Reconstruir Arquivo")
        self._btn_start_join.clicked.connect(self._on_join_click)
        join_layout.addWidget(self._btn_start_join)

        self._lbl_join_status = QLabel("Selecione a primeira parte para detectar os volumes.")
        join_layout.addWidget(self._lbl_join_status)
        tabs.addTab(tab_join, "Juntar Volumes")

        layout.addWidget(tabs)
        self._detected_parts: List[Path] = []
        return widget

    def _on_preset_changed(self, idx: int) -> None:
        val = self._combo_presets.currentData()
        self._spin_custom_mb.setEnabled(val == -1)

    def _on_browse_split_src(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Selecionar Arquivo para Dividir")
        if path:
            self._edit_split_src.setText(path)
            if not self._edit_split_dst.text():
                self._edit_split_dst.setText(str(Path(path).parent))

    def _on_browse_split_dst(self) -> None:
        path = QFileDialog.getExistingDirectory(None, "Selecionar Pasta de Saída dos Volumes")
        if path:
            self._edit_split_dst.setText(path)

    def _on_split_click(self) -> None:
        src_str = self._edit_split_src.text().strip()
        dst_str = self._edit_split_dst.text().strip()
        if not src_str or not dst_str:
            QMessageBox.warning(None, "Aviso", "Selecione o arquivo de origem e a pasta de destino.")
            return

        src_path = Path(src_str)
        dst_path = Path(dst_str)

        preset_val = self._combo_presets.currentData()
        if preset_val == -1:
            vol_size = self._spin_custom_mb.value() * 1024 * 1024
        else:
            vol_size = preset_val

        pattern = self._combo_pattern.currentData()
        self._lbl_split_status.setText("Dividindo arquivo em volumes...")
        self._btn_start_split.setEnabled(False)

        def worker():
            return split_file_into_volumes(src_path, dst_path, vol_size, pattern)

        def on_done(vols: List[Path]):
            self._btn_start_split.setEnabled(True)
            self._lbl_split_status.setText(f"Sucesso! {len(vols)} volumes gerados em {dst_path.name}.")
            QMessageBox.information(
                None,
                "Divisão Concluída",
                f"{len(vols)} arquivos de volume foram gerados com sucesso na pasta:\n{dst_path}",
            )

        def on_error(err: str):
            self._btn_start_split.setEnabled(True)
            self._lbl_split_status.setText(f"Erro na divisão: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao dividir arquivo: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_browse_join_first(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Primeiro Volume (.001 ou .part01)",
            "",
            "Volumes (*.001 *.part01* *.part1*);;Todos os Arquivos (*.*)",
        )
        if path:
            first_p = Path(path)
            self._edit_join_first.setText(path)
            # Detecta partes
            parts = find_volume_parts(first_p)
            self._detected_parts = parts
            self._table_parts.setRowCount(len(parts))
            for row, p in enumerate(parts):
                self._table_parts.setItem(row, 0, QTableWidgetItem(p.name))
                self._table_parts.setItem(row, 1, QTableWidgetItem(f"{p.stat().st_size:,} B"))

            # Sugere nome de saída reconstruído
            name = first_p.name
            if name.endswith(f".{first_p.suffix[1:]}") and first_p.suffix[1:].isdigit():
                # ex: arquivo.zip.001 -> arquivo.zip
                out_name = first_p.stem
            elif ".part" in name.lower():
                import re
                out_name = re.sub(r"\.part\d+", "", name, flags=re.IGNORECASE)
            else:
                out_name = f"reconstruido_{first_p.name}"

            self._edit_join_out.setText(str(first_p.parent / out_name))
            self._lbl_join_status.setText(f"{len(parts)} partes sequenciais detectadas.")

    def _on_browse_join_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(None, "Salvar Arquivo Reconstruído Como")
        if path:
            self._edit_join_out.setText(path)

    def _on_join_click(self) -> None:
        if not self._detected_parts:
            QMessageBox.warning(None, "Aviso", "Selecione o primeiro volume para detectar a sequência.")
            return

        out_str = self._edit_join_out.text().strip()
        if not out_str:
            QMessageBox.warning(None, "Aviso", "Informe o caminho do arquivo de saída reconstruído.")
            return

        out_path = Path(out_str)
        self._lbl_join_status.setText("Juntando volumes...")
        self._btn_start_join.setEnabled(False)

        def worker():
            return join_volumes_to_file(self._detected_parts, out_path)

        def on_done(res_path: Path):
            self._btn_start_join.setEnabled(True)
            self._lbl_join_status.setText(f"Arquivo reconstruído com sucesso: {res_path.name}")
            QMessageBox.information(
                None,
                "Junção Concluída",
                f"O arquivo foi reconstruído com sucesso em:\n{res_path}",
            )

        def on_error(err: str):
            self._btn_start_join.setEnabled(True)
            self._lbl_join_status.setText(f"Erro na junção: {err}")
            QMessageBox.critical(None, "Erro", f"Falha na junção: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

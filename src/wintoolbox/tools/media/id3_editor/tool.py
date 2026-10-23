"""
Ferramenta: Editor de Metadados e Tags ID3 (MP3) em Lote.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.media.id3_editor.logic import edit_mp3_tags


@register
class Id3EditorTool(FileTool):
    id = "media.id3_editor"
    name = "Editor de Tags ID3 (MP3)"
    category = "Áudio e Vídeo"
    description = "Edite metadados de músicas MP3 em lote (Artista, Álbum, Ano, Gênero e Capa do Álbum)"
    keywords = ["mp3", "tags", "id3", "musica", "artista", "album", "capa", "metadados", "lote"]
    accepts = [".mp3"]
    batch_kind = "per_file"
    parallel_mode = "thread"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Metadados a Aplicar nos Arquivos MP3")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("Artista:"), 0, 0)
        self.txt_artist = QLineEdit()
        self.txt_artist.setPlaceholderText("(Manter original ou definir em lote)")
        grid.addWidget(self.txt_artist, 0, 1)

        grid.addWidget(QLabel("Álbum:"), 1, 0)
        self.txt_album = QLineEdit()
        grid.addWidget(self.txt_album, 1, 1)

        grid.addWidget(QLabel("Ano:"), 2, 0)
        self.txt_year = QLineEdit()
        self.txt_year.setPlaceholderText("Ex: 2024")
        grid.addWidget(self.txt_year, 2, 1)

        grid.addWidget(QLabel("Gênero:"), 3, 0)
        self.txt_genre = QLineEdit()
        self.txt_genre.setPlaceholderText("Ex: Rock, Pop, Instrumental")
        grid.addWidget(self.txt_genre, 3, 1)

        grid.addWidget(QLabel("Capa do álbum (PNG/JPG):"), 4, 0)
        self.txt_cover = QLineEdit()
        grid.addWidget(self.txt_cover, 4, 1)

        btn_browse_cov = QPushButton("Procurar...")
        btn_browse_cov.clicked.connect(self._on_browse_cover)
        grid.addWidget(btn_browse_cov, 4, 2)

        layout.addLayout(grid)
        return panel

    def _on_browse_cover(self):
        file, _ = QFileDialog.getOpenFileName(None, "Selecionar Imagem de Capa", "", "Imagens (*.jpg *.jpeg *.png)")
        if file:
            self.txt_cover.setText(file)

    def get_params(self) -> Dict[str, Any]:
        return {
            "artist": self.txt_artist.text().strip(),
            "album": self.txt_album.text().strip(),
            "year": self.txt_year.text().strip(),
            "genre": self.txt_genre.text().strip(),
            "cover_path": self.txt_cover.text().strip(),
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ".mp3"

    def process(
        self,
        src: Path,
        dst: Path,
        params: Dict[str, Any],
        ctx: TaskContext
    ) -> ItemResult:
        try:
            # Se dst for diferente de src, copia primeiro
            if src.resolve() != dst.resolve():
                import shutil
                shutil.copy2(src, dst)
                target_file = dst
            else:
                target_file = src

            cov_str = params.get("cover_path", "")
            cov_p = Path(cov_str) if cov_str and Path(cov_str).is_file() else None

            edit_mp3_tags(
                target_file,
                artist=params.get("artist") or None,
                album=params.get("album") or None,
                year=params.get("year") or None,
                genre=params.get("genre") or None,
                cover_image_path=cov_p
            )

            return ItemResult(
                success=True,
                output_path=target_file,
                message=f"Tags ID3 atualizadas: {target_file.name}"
            )
        except Exception as e:
            return ItemResult(
                success=False,
                error=f"Falha ao editar tags de {src.name}: {e}"
            )

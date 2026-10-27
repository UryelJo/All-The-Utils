"""
Lógica pura para interpretação e fatiamento de arquivos CUE Sheet (.cue).
Permite dividir arquivos contínuos de álbum de áudio em faixas individuais nomeadas e tagueadas.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe


@dataclass
class CueTrack:
    """Representa uma faixa individual descrita no CUE sheet."""
    number: int
    title: str
    performer: str
    start_seconds: float
    end_seconds: Optional[float] = None


@dataclass
class CueSheet:
    """Representa os metadados e lista de faixas de um arquivo CUE."""
    album_title: str
    album_performer: str
    referenced_file: str
    tracks: List[CueTrack] = field(default_factory=list)


def parse_cue_time(time_str: str) -> float:
    """
    Converte timestamp CUE (MM:SS:FF, onde 75 frames = 1 segundo) para segundos decimais.
    Exemplo: 03:45:30 -> 3*60 + 45 + 30/75 = 225.40 segundos.
    """
    parts = time_str.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Formato de tempo CUE inválido: {time_str}")

    minutes = int(parts[0])
    seconds = int(parts[1])
    frames = int(parts[2])

    return (minutes * 60.0) + seconds + (frames / 75.0)


def format_seconds_to_time(seconds: float) -> str:
    """Converte segundos para MM:SS."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def parse_cue_content(content: str) -> CueSheet:
    """Interpreta o texto de um CUE sheet e retorna a estrutura CueSheet."""
    album_title = "Álbum Desconhecido"
    album_performer = "Artista Desconhecido"
    referenced_file = ""
    tracks: List[CueTrack] = []

    current_track_num: Optional[int] = None
    current_track_title = ""
    current_track_performer = ""
    current_track_start: Optional[float] = None

    lines = content.splitlines()
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        # PERFORMER global ou da faixa
        match_perf = re.match(r'^PERFORMER\s+"?([^"]+)"?$', line_clean, re.IGNORECASE)
        if match_perf:
            perf_val = match_perf.group(1).strip()
            if current_track_num is None:
                album_performer = perf_val
            else:
                current_track_performer = perf_val
            continue

        # TITLE global ou da faixa
        match_title = re.match(r'^TITLE\s+"?([^"]+)"?$', line_clean, re.IGNORECASE)
        if match_title:
            title_val = match_title.group(1).strip()
            if current_track_num is None:
                album_title = title_val
            else:
                current_track_title = title_val
            continue

        # FILE referenciado
        match_file = re.match(r'^FILE\s+"?([^"]+)"?\s+.*$', line_clean, re.IGNORECASE)
        if match_file:
            referenced_file = match_file.group(1).strip()
            continue

        # Início de nova TRACK
        match_track = re.match(r'^TRACK\s+(\d+)\s+AUDIO', line_clean, re.IGNORECASE)
        if match_track:
            # Salva faixa anterior se houver
            if current_track_num is not None and current_track_start is not None:
                tracks.append(
                    CueTrack(
                        number=current_track_num,
                        title=current_track_title or f"Faixa {current_track_num:02d}",
                        performer=current_track_performer or album_performer,
                        start_seconds=current_track_start,
                    )
                )

            current_track_num = int(match_track.group(1))
            current_track_title = ""
            current_track_performer = album_performer
            current_track_start = None
            continue

        # INDEX 01 (marca de início real da música)
        match_index = re.match(r'^INDEX\s+01\s+([0-9:]+)', line_clean, re.IGNORECASE)
        if match_index and current_track_num is not None:
            time_raw = match_index.group(1)
            try:
                current_track_start = parse_cue_time(time_raw)
            except ValueError:
                current_track_start = 0.0

    # Adiciona a última faixa pendente
    if current_track_num is not None and current_track_start is not None:
        tracks.append(
            CueTrack(
                number=current_track_num,
                title=current_track_title or f"Faixa {current_track_num:02d}",
                performer=current_track_performer or album_performer,
                start_seconds=current_track_start,
            )
        )

    # Ordena faixas por número
    tracks.sort(key=lambda t: t.number)

    # Calcula end_seconds com base no início da próxima faixa
    for i in range(len(tracks) - 1):
        tracks[i].end_seconds = tracks[i + 1].start_seconds

    return CueSheet(
        album_title=album_title,
        album_performer=album_performer,
        referenced_file=referenced_file,
        tracks=tracks
    )


def parse_cue_file(cue_path: Path) -> CueSheet:
    """Lê um arquivo .cue do disco com fallback para múltiplas codificações."""
    cue_path = Path(cue_path).resolve()
    if not cue_path.is_file():
        raise FileNotFoundError(f"Arquivo CUE não encontrado: {cue_path}")

    content = ""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            content = cue_path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue

    if not content:
        raise ValueError(f"Não foi possível ler o arquivo CUE com codificações conhecidas: {cue_path}")

    return parse_cue_content(content)


def find_audio_file(cue_path: Path, referenced_name: str) -> Optional[Path]:
    """
    Localiza o arquivo de áudio real associado ao CUE na mesma pasta.
    Testa o nome exato e alternativas comuns com extensões .flac, .wav, .ape, .mp3, .m4a.
    """
    cue_dir = cue_path.resolve().parent

    # 1. Tenta exatamente o nome referenciado
    if referenced_name:
        direct_path = cue_dir / referenced_name
        if direct_path.is_file():
            return direct_path

        # Tenta trocar a extensão do arquivo referenciado
        base_stem = Path(referenced_name).stem
        for ext in [".flac", ".wav", ".ape", ".mp3", ".m4a", ".ogg", ".wv"]:
            cand = cue_dir / f"{base_stem}{ext}"
            if cand.is_file():
                return cand

    # 2. Tenta o mesmo nome do próprio arquivo .cue
    cue_stem = cue_path.stem
    for ext in [".flac", ".wav", ".ape", ".mp3", ".m4a", ".ogg", ".wv"]:
        cand = cue_dir / f"{cue_stem}{ext}"
        if cand.is_file():
            return cand

    # 3. Procura o maior arquivo de áudio na pasta
    audio_files = [
        f for f in cue_dir.iterdir()
        if f.is_file() and f.suffix.lower() in [".flac", ".wav", ".ape", ".mp3", ".m4a", ".ogg", ".wv"]
    ]
    if audio_files:
        audio_files.sort(key=lambda x: x.stat().st_size, reverse=True)
        return audio_files[0]

    return None


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivos no Windows."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def split_cue_audio(
    cue_path: Path,
    audio_file: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    filename_pattern: str = "{track:02d} - {title}",
    output_format: str = "keep"
) -> List[Path]:
    """
    Fatia um arquivo de áudio único em faixas separadas de acordo com as faixas do CUE.
    """
    cue_path = Path(cue_path).resolve()
    sheet = parse_cue_file(cue_path)

    if not sheet.tracks:
        raise ValueError("Nenhuma faixa de áudio encontrada no arquivo CUE.")

    # Resolução do arquivo de áudio
    if not audio_file:
        resolved_audio = find_audio_file(cue_path, sheet.referenced_file)
        if not resolved_audio:
            raise FileNotFoundError(
                f"Arquivo de áudio associado '{sheet.referenced_file}' não foi encontrado "
                f"na pasta do CUE: {cue_path.parent}"
            )
        audio_file = resolved_audio
    else:
        audio_file = Path(audio_file).resolve()
        if not audio_file.is_file():
            raise FileNotFoundError(f"Arquivo de áudio informado não existe: {audio_file}")

    if not output_dir:
        output_dir = cue_path.parent / sanitize_filename(sheet.album_title or "Faixas_CUE")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg = get_ffmpeg_exe()
    output_files: List[Path] = []
    total_tracks = len(sheet.tracks)

    target_ext = audio_file.suffix if output_format == "keep" else f".{output_format}"

    for track in sheet.tracks:
        safe_title = sanitize_filename(track.title)
        safe_artist = sanitize_filename(track.performer)
        filename = filename_pattern.format(
            track=track.number,
            title=safe_title,
            artist=safe_artist,
            album=sanitize_filename(sheet.album_title)
        )
        safe_filename_clean = sanitize_filename(filename) + target_ext
        out_track_path = output_dir / safe_filename_clean

        cmd = [
            ffmpeg, "-y",
            "-ss", f"{track.start_seconds:.3f}",
        ]

        if track.end_seconds is not None:
            duration = track.end_seconds - track.start_seconds
            cmd.extend(["-t", f"{duration:.3f}"])

        cmd.extend([
            "-i", str(audio_file),
            "-metadata", f"title={track.title}",
            "-metadata", f"artist={track.performer}",
            "-metadata", f"album={sheet.album_title}",
            "-metadata", f"track={track.number}/{total_tracks}",
        ])

        if output_format == "keep" and target_ext.lower() == audio_file.suffix.lower():
            # Tenta cópia rápida de fluxo
            cmd.extend(["-c", "copy"])
        else:
            if target_ext.lower() == ".flac":
                cmd.extend(["-c:a", "flac"])
            elif target_ext.lower() == ".mp3":
                cmd.extend(["-c:a", "libmp3lame", "-q:a", "0"])
            elif target_ext.lower() == ".wav":
                cmd.extend(["-c:a", "pcm_s16le"])

        cmd.append(str(out_track_path))

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

        if proc.returncode != 0:
            raise RuntimeError(f"Erro ao fatiar faixa {track.number}: {proc.stderr.decode('utf-8', 'replace')}")

        if out_track_path.is_file() and out_track_path.stat().st_size > 0:
            output_files.append(out_track_path)

    return output_files

"""
Lógica pura de geração e verificação de arquivos de manifesto de checksums (.sha256 / .md5).
Compatível com o formato padrão GNU sha256sum (hash  caminho_relativo).
Totalmente desacoplada de bibliotecas de interface visual.
"""
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("files.checksum_manifest")


def _calc_file_hash(path: Path, algo: str = "sha256") -> str:
    """Calcula o hash criptográfico do arquivo em blocos de 64 KB."""
    h = hashlib.sha256() if algo.lower() == "sha256" else hashlib.md5()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_folder_manifest(
    folder_path: Path,
    algo: str = "sha256",
    recursive: bool = True
) -> Tuple[List[Dict[str, str]], str]:
    """
    Calcula hashes de todos os arquivos de um diretório e gera o conteúdo formatado
    no padrão GNU: '<hash>  <caminho_relativo>'.
    """
    if not folder_path.is_dir():
        raise ValueError(f"O caminho informado não é uma pasta válida: {folder_path}")

    items: List[Dict[str, str]] = []
    lines: List[str] = []

    pattern = "**/*" if recursive else "*"
    for p in folder_path.glob(pattern):
        if p.is_file():
            # Não inclui arquivos de manifesto anteriores dentro da pasta
            if p.suffix.lower() in (".sha256", ".md5") and "manifest" in p.name.lower():
                continue

            try:
                rel_path = p.relative_to(folder_path).as_posix()
                f_hash = _calc_file_hash(p, algo)
                items.append({"file": rel_path, "hash": f_hash})
                lines.append(f"{f_hash}  {rel_path}")
            except Exception as exc:
                _log.warning("Falha ao calcular hash de %s: %s", p.name, exc)

    manifest_text = "\n".join(lines) + "\n"
    return items, manifest_text


def verify_manifest_file(manifest_file: Path) -> List[Dict[str, Any]]:
    """
    Lê um arquivo de manifesto e verifica a integridade de cada arquivo em disco.
    Retorna lista de resultados: OK, MODIFICADO, AUSENTE.
    """
    if not manifest_file.is_file():
        raise ValueError(f"Arquivo de manifesto não encontrado: {manifest_file}")

    base_dir = manifest_file.parent
    algo = "md5" if manifest_file.suffix.lower() == ".md5" else "sha256"

    results: List[Dict[str, Any]] = []

    try:
        content = manifest_file.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Falha ao ler arquivo de manifesto: {exc}")

    for line in content.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue

        parts = line_clean.split(None, 1)
        if len(parts) != 2:
            continue

        expected_hash = parts[0].strip().lower()
        rel_path_str = parts[1].strip().lstrip("*")  # Trata modo binário '*file'

        target_file = base_dir / rel_path_str

        if not target_file.exists():
            results.append({
                "file": rel_path_str,
                "status": "AUSENTE",
                "expected": expected_hash,
                "actual": "-"
            })
            continue

        try:
            actual_hash = _calc_file_hash(target_file, algo).lower()
            if actual_hash == expected_hash:
                status = "OK"
            else:
                status = "MODIFICADO"

            results.append({
                "file": rel_path_str,
                "status": status,
                "expected": expected_hash,
                "actual": actual_hash
            })
        except Exception as exc:
            results.append({
                "file": rel_path_str,
                "status": f"ERRO ({exc})",
                "expected": expected_hash,
                "actual": "-"
            })

    return results

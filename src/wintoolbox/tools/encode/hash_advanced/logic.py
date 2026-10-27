"""
Lógica pura para cálculo, geração de manifestos (.sha256, .sfv) e verificação de integridade em lote.
Suporta BLAKE2b, BLAKE2s, SHA3-256, SHA3-512, SHA-256, SHA-512, MD5 e CRC32.
Leitura eficiente em fluxo (streaming em blocos) para arquivos de qualquer tamanho.

Zero dependências de interface gráfica.
"""
import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import zlib


def _get_hasher(algorithm: str) -> Any:
    alg = algorithm.lower().strip()
    if alg == "sha256":
        return hashlib.sha256()
    elif alg == "sha512":
        return hashlib.sha512()
    elif alg == "sha3_256" or alg == "sha3-256":
        return hashlib.sha3_256()
    elif alg == "sha3_512" or alg == "sha3-512":
        return hashlib.sha3_512()
    elif alg == "blake2b":
        return hashlib.blake2b()
    elif alg == "blake2s":
        return hashlib.blake2s()
    elif alg == "md5":
        return hashlib.md5()
    elif alg == "crc32":
        return None  # Tratado separadamente com zlib
    else:
        raise ValueError(f"Algoritmo de hash não suportado: {algorithm}")


def compute_file_hash_stream(
    file_path: Path,
    algorithm: str = "sha256",
    chunk_size: int = 65536,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> str:
    """
    Calcula o hash de um arquivo em streaming sem sobrecarregar a memória.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    alg = algorithm.lower().strip()
    total_size = path.stat().st_size
    read_bytes = 0

    if alg == "crc32":
        crc = 0
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                crc = zlib.crc32(chunk, crc)
                read_bytes += len(chunk)
                if progress_cb:
                    progress_cb(read_bytes, total_size)
        return f"{crc & 0xFFFFFFFF:08X}"
    else:
        hasher = _get_hasher(alg)
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
                read_bytes += len(chunk)
                if progress_cb:
                    progress_cb(read_bytes, total_size)
        return hasher.hexdigest().lower()


def generate_manifest_content(files: List[Path], algorithm: str = "sha256") -> str:
    """
    Gera o conteúdo de um arquivo de manifesto no formato padrão GNU coreutils:
    <hash>  <filename>
    Ou no formato SFV para CRC32:
    <filename> <crc32>
    """
    alg = algorithm.lower().strip()
    lines = []

    for fpath in files:
        path = Path(fpath)
        if not path.is_file():
            continue
        hval = compute_file_hash_stream(path, algorithm=alg)
        if alg == "crc32":
            lines.append(f"{path.name} {hval}")
        else:
            lines.append(f"{hval}  {path.name}")

    return "\n".join(lines) + "\n" if lines else ""


def parse_manifest_lines(content: str) -> List[Dict[str, str]]:
    """
    Interpreta linhas de um manifesto .sha256, .md5 ou .sfv.
    Ignora comentários (iniciando com ';') e linhas em branco.
    """
    entries = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue

        # Formato SFV: <filename> <crc32> (8 caracteres hex no final)
        parts = line.split()
        if len(parts) >= 2:
            last = parts[-1]
            if len(last) == 8 and all(c in "0123456789abcdefABCDEF" for c in last):
                filename = " ".join(parts[:-1])
                entries.append({"filename": filename, "expected_hash": last.upper(), "type": "sfv"})
                continue

        # Formato padrão coreutils: <hash>  <filename> ou <hash> *<filename>
        if len(parts) >= 2:
            expected_hash = parts[0].strip().lower()
            filename = line[len(parts[0]):].strip().lstrip("*").strip()
            entries.append({"filename": filename, "expected_hash": expected_hash, "type": "standard"})

    return entries


def verify_manifest_file(
    manifest_path: Path,
    override_algorithm: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Lê um arquivo de manifesto e verifica a integridade de todos os arquivos listados.
    Retorna uma lista de resultados estruturados para exibição em tabela.
    """
    mpath = Path(manifest_path)
    if not mpath.is_file():
        raise FileNotFoundError(f"Manifesto não encontrado: {mpath}")

    base_dir = mpath.parent
    content = mpath.read_text(encoding="utf-8", errors="replace")
    entries = parse_manifest_lines(content)

    results = []
    for entry in entries:
        fname = entry["filename"]
        expected = entry["expected_hash"]
        entry_type = entry["type"]

        target_file = base_dir / fname
        if not target_file.is_file():
            results.append({
                "status": "AUSENTE",
                "filename": fname,
                "expected": expected,
                "computed": "-",
                "details": "Arquivo não encontrado no diretório do manifesto",
            })
            continue

        # Determina o algoritmo pelo tipo ou comprimento do hash
        if entry_type == "sfv" or len(expected) == 8:
            alg = "crc32"
        elif override_algorithm:
            alg = override_algorithm
        elif len(expected) == 32:
            alg = "md5"
        elif len(expected) == 64:
            alg = "sha256"
        elif len(expected) == 128:
            alg = "sha512"
        else:
            alg = "sha256"

        try:
            computed = compute_file_hash_stream(target_file, algorithm=alg)
            if alg == "crc32":
                matched = (computed.upper() == expected.upper())
            else:
                matched = (computed.lower() == expected.lower())

            status = "OK" if matched else "FALHOU"
            details = "Hash verificado com sucesso" if matched else "Divergência de hash (arquivo corrompido ou modificado)"
            results.append({
                "status": status,
                "filename": fname,
                "expected": expected,
                "computed": computed,
                "details": details,
            })
        except Exception as exc:
            results.append({
                "status": "ERRO",
                "filename": fname,
                "expected": expected,
                "computed": "-",
                "details": str(exc),
            })

    return results

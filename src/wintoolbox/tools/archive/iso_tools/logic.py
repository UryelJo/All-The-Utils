"""
Lógica pura para montagem, desmontagem e extração de imagens de disco (ISO, VHD, VHDX).
Utiliza comandos nativos do PowerShell do Windows e utilitário nativo tar.exe.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional


def mount_disk_image(image_path: Path, read_only: bool = True) -> Dict[str, Any]:
    """
    Monta uma imagem de disco (ISO, VHD ou VHDX) utilizando o cmdlet nativo Mount-DiskImage.
    """
    image_path = Path(image_path).resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Arquivo de imagem não encontrado: {image_path}")

    ext = image_path.suffix.lower()
    if ext not in [".iso", ".vhd", ".vhdx"]:
        raise ValueError(f"Extensão de imagem não suportada: {ext}")

    ro_flag = "-Access ReadOnly" if read_only else ""
    ps_cmd = (
        f"$img = Mount-DiskImage -ImagePath '{str(image_path)}' {ro_flag} -PassThru; "
        f"$vol = $img | Get-Volume; "
        f"if ($vol) {{ "
        f"  [PSCustomObject]@{{ DriveLetter = $vol.DriveLetter; FileSystemLabel = $vol.FileSystemLabel; Size = $vol.Size }} | ConvertTo-Json -Compress "
        f"}} else {{ "
        f"  [PSCustomObject]@{{ DriveLetter = $null; FileSystemLabel = $null; Size = 0 }} | ConvertTo-Json -Compress "
        f"}}"
    )

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    res = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        startupinfo=startupinfo,
        check=False,
    )

    if res.returncode != 0:
        raise RuntimeError(f"Falha ao montar imagem: {res.stderr.strip()}")

    drive_letter = None
    label = None
    size = 0

    out_text = res.stdout.strip()
    if out_text:
        try:
            data = json.loads(out_text)
            if isinstance(data, dict):
                drive_letter = data.get("DriveLetter")
                label = data.get("FileSystemLabel")
                size = data.get("Size") or 0
        except json.JSONDecodeError:
            pass

    return {
        "status": "MONTADO",
        "image_path": str(image_path),
        "drive_letter": f"{drive_letter}:" if drive_letter else None,
        "label": label,
        "size": size,
        "read_only": read_only,
    }


def dismount_disk_image(image_path: Path) -> Dict[str, Any]:
    """
    Desmonta a imagem de disco virtual especificada.
    """
    image_path = Path(image_path).resolve()
    ps_cmd = f"Dismount-DiskImage -ImagePath '{str(image_path)}'"

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    res = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        startupinfo=startupinfo,
        check=False,
    )

    if res.returncode != 0:
        raise RuntimeError(f"Falha ao desmontar imagem: {res.stderr.strip()}")

    return {
        "status": "DESMONTADO",
        "image_path": str(image_path),
    }


def list_mounted_disk_images() -> List[Dict[str, Any]]:
    """
    Lista todas as imagens de disco virtuais que se encontram montadas no sistema no momento.
    """
    ps_cmd = (
        "$imgs = Get-DiskImage -DevicePath (Get-Volume | Where-Object { $_.DriveType -eq 'CD-ROM' -or $_.DriveType -eq 'Fixed' } | Select-Object -ExpandProperty DevicePath) 2>$null; "
        "if (-not $imgs) { $imgs = Get-DiskImage 2>$null }; "
        "if ($imgs) { "
        "  $results = foreach ($i in $imgs) { "
        "    $vol = $i | Get-Volume 2>$null; "
        "    [PSCustomObject]@{ ImagePath = $i.ImagePath; Attached = $i.Attached; StorageType = $i.StorageType; DriveLetter = if ($vol) { $vol.DriveLetter } else { $null } } "
        "  }; "
        "  $results | ConvertTo-Json -Compress "
        "} else { '[]' }"
    )

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            check=False,
            timeout=10,
        )
        if res.returncode == 0 and res.stdout.strip():
            raw = json.loads(res.stdout.strip())
            if isinstance(raw, dict):
                raw = [raw]
            if isinstance(raw, list):
                return [
                    {
                        "image_path": item.get("ImagePath"),
                        "attached": item.get("Attached", True),
                        "storage_type": item.get("StorageType"),
                        "drive_letter": f"{item.get('DriveLetter')}:" if item.get("DriveLetter") else None,
                    }
                    for item in raw
                    if item.get("ImagePath")
                ]
    except Exception:
        pass

    return []


def extract_iso_contents(
    iso_path: Path,
    output_dir: Path,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Dict[str, Any]:
    """
    Extrai diretamente os arquivos de uma imagem ISO para uma pasta de destino.
    Primeiro tenta via utilitário bsdtar (nativo em Windows 10/11: C:\\Windows\\System32\\tar.exe).
    Se falhar, faz a montagem temporária, cópia e desmontagem.
    """
    iso_path = Path(iso_path).resolve()
    if not iso_path.is_file():
        raise FileNotFoundError(f"Arquivo ISO não encontrado: {iso_path}")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_count = 0
    total_bytes = 0

    # 1. Tentativa via tar.exe nativo do Windows
    tar_exe = shutil.which("tar") or r"C:\Windows\System32\tar.exe"
    if os.path.isfile(tar_exe):
        cmd = [tar_exe, "-xf", str(iso_path), "-C", str(output_dir)]
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            check=False,
        )
        if res.returncode == 0:
            for r, _, fl in os.walk(output_dir):
                for f in fl:
                    extracted_count += 1
                    total_bytes += (Path(r) / f).stat().st_size
            if progress_cb:
                progress_cb(100)
            return {
                "status": "CONCLUIDO",
                "method": "tar_bsd",
                "files_count": extracted_count,
                "total_bytes": total_bytes,
                "output_dir": str(output_dir),
            }

    # 2. Fallback: Montagem temporária, cópia de arquivos e desmontagem segura
    mount_res = mount_disk_image(iso_path, read_only=True)
    drive = mount_res.get("drive_letter")
    if not drive:
        raise RuntimeError("Não foi possível identificar a letra da unidade virtual montada.")

    try:
        drive_path = Path(drive) / "\\"
        for root, dirs, files in os.walk(drive_path):
            rel_root = Path(root).relative_to(drive_path)
            dest_root = output_dir / rel_root
            dest_root.mkdir(parents=True, exist_ok=True)

            for f in files:
                src_f = Path(root) / f
                dst_f = dest_root / f
                shutil.copy2(src_f, dst_f)
                extracted_count += 1
                total_bytes += dst_f.stat().st_size

        if progress_cb:
            progress_cb(100)

        return {
            "status": "CONCLUIDO",
            "method": "windows_mount_copy",
            "files_count": extracted_count,
            "total_bytes": total_bytes,
            "output_dir": str(output_dir),
        }
    finally:
        dismount_disk_image(iso_path)

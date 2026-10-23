"""
Build do All the Utils (WinToolbox): uma única fonte de configuração do PyInstaller/Inno Setup.

Uso:
    python build.py                      # pasta (onedir) + autoteste
    python build.py --mode installer     # pasta + instalador Inno Setup (recomendado)
    python build.py --mode onefile       # .exe único portátil
    python build.py --mode all           # instalador + portátil + zip
    python build.py --with-ffmpeg        # empacota ffmpeg/ffprobe (ferramentas de mídia sem dependências)

Decisões:
  * onedir + instalador é o formato principal: o onefile extrai ~200 MB para %TEMP% a cada
    abertura (inicialização lenta) e é o formato que mais gera falso positivo em antivírus.
  * --noupx: compressão UPX em DLLs do Qt quebra plugins e dispara heurísticas de antivírus.
  * Módulos Qt não usados (WebEngine, QML/Quick, 3D, Charts...) e ferramentas de dev ficam de fora.
  * Recurso de versão no .exe (propriedades do arquivo) e autoteste do executável gerado.
"""
import argparse
import os
import shutil
import subprocess
import sys
import re
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "WinToolbox"
PRODUCT_NAME = "All the Utils"

DATA_FILES = [
    ("ui/Icon.png", "ui"),
    ("ui/icon.ico", "ui"),
    ("src/wintoolbox/ui/icon.png", "wintoolbox/ui"),
    ("src/wintoolbox/ui/icon.ico", "wintoolbox/ui"),
    ("src/wintoolbox/tools/images/ocr/win_ocr.ps1", "wintoolbox/tools/images/ocr"),
]

# O app usa apenas QtCore, QtGui, QtWidgets, QtNetwork e QtMultimedia(+Widgets)
EXCLUDED_MODULES = [
    "tkinter", "_tkinter", "pytest", "_pytest", "pytestqt", "PyInstaller", "IPython",
    *(f"PySide6.{m}" for m in (
        "QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngineQuick", "QtWebChannel", "QtWebSockets",
        "QtWebView", "QtQml", "QtQuick", "QtQuickWidgets", "QtQuick3D", "QtQuickControls2",
        "Qt3DCore", "Qt3DRender", "Qt3DInput", "Qt3DLogic", "Qt3DAnimation", "Qt3DExtras",
        "QtCharts", "QtDataVisualization", "QtGraphs", "QtGraphsWidgets", "QtPdf", "QtPdfWidgets",
        "QtDesigner", "QtUiTools", "QtHelp", "QtSql", "QtTest", "QtBluetooth", "QtNfc", "QtPositioning",
        "QtLocation", "QtSensors", "QtSerialPort", "QtSerialBus", "QtRemoteObjects", "QtScxml",
        "QtStateMachine", "QtTextToSpeech", "QtSpatialAudio", "QtHttpServer", "QtOpenGLWidgets",
    )),
]


def read_version() -> str:
    # Regex em vez de tomllib: o projeto ainda suporta Python 3.10
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else "0.0.0"


def write_version_file(version: str, work: Path) -> Path:
    """Recurso VERSIONINFO do Windows (Propriedades > Detalhes do .exe)."""
    parts = [int(p) for p in (version.split(".") + ["0", "0", "0"])[:4]]
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tuple(parts)}, prodvers={tuple(parts)}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', '{PRODUCT_NAME} Team'),
      StringStruct('FileDescription', '{PRODUCT_NAME} - Caixa de Ferramentas para Windows'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{APP_NAME}'),
      StringStruct('OriginalFilename', '{APP_NAME}.exe'),
      StringStruct('ProductName', '{PRODUCT_NAME}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])
  ]
)
"""
    work.mkdir(parents=True, exist_ok=True)
    path = work / "version_info.txt"
    path.write_text(content, encoding="utf-8")
    return path


def find_ffmpeg() -> dict:
    """Localiza ffmpeg/ffprobe (PATH ou pacote static-ffmpeg) para empacotar."""
    found = {}
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception:
        pass
    for name in ("ffmpeg", "ffprobe"):
        path = shutil.which(name)
        if path:
            found[name] = Path(path)
    return found


def run_pyinstaller(onefile: bool, version_file: Path, dist: Path, work: Path, ffmpeg: dict) -> Path:
    name = f"{APP_NAME}_Portable" if onefile else APP_NAME
    sep = os.pathsep
    args = [
        sys.executable, "-m", "PyInstaller", str(ROOT / "main.py"),
        "--noconfirm", "--clean", "--windowed", "--noupx",
        "--onefile" if onefile else "--onedir",
        "--name", name,
        "--icon", str(ROOT / "ui" / "icon.ico"),
        "--version-file", str(version_file),
        "--paths", str(ROOT / "src"),
        "--collect-submodules", "wintoolbox",
        # O registro carrega as categorias por nome (__import__ de string), invisível à análise
        # estática; e o pywin32 importa win32timezone dinamicamente ao converter datas COM.
        "--hidden-import", "win32timezone",
        "--optimize", "1",  # remove asserts (o código não depende deles); mantém docstrings
        "--distpath", str(dist),
        "--workpath", str(work / name),
        "--specpath", str(work),
    ]
    for src, dst in DATA_FILES:
        args += ["--add-data", f"{ROOT / src}{sep}{dst}"]
    if onefile:
        for exe in ffmpeg.values():
            args += ["--add-binary", f"{exe}{sep}ffmpeg"]
    for mod in EXCLUDED_MODULES:
        args += ["--exclude-module", mod]

    print(f"\n==> PyInstaller ({'onefile' if onefile else 'onedir'}): {name}")
    # --collect-submodules roda antes de o --paths entrar no sys.path: sem o PYTHONPATH o
    # pacote 'wintoolbox' não é encontrado e nenhum submódulo é coletado.
    pythonpath = os.pathsep.join(filter(None, [str(ROOT / "src"), os.environ.get("PYTHONPATH")]))
    subprocess.run(args, check=True, cwd=ROOT, env=dict(os.environ, PYTHONPATH=pythonpath))

    if not onefile and ffmpeg:
        target = dist / name / "ffmpeg"
        target.mkdir(exist_ok=True)
        for exe in ffmpeg.values():
            shutil.copy2(exe, target / exe.name.lower())
    return dist / (f"{name}.exe" if onefile else name)


def self_test(exe: Path) -> bool:
    print(f"\n==> Autoteste do executável: {exe}")
    started = time.time()
    proc = subprocess.run([str(exe), "--self-test"], timeout=600)
    report = Path(os.environ.get("APPDATA", Path.home())) / "AllTheUtils" / "logs" / "self_test.txt"
    if report.exists() and report.stat().st_mtime >= started - 1:
        print(report.read_text(encoding="utf-8").split("\nAmbiente:")[0])
    ok = proc.returncode == 0
    print("Autoteste:", "SUCESSO" if ok else f"{proc.returncode} falha(s)")
    return ok


def find_iscc() -> Path:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    raise SystemExit("Inno Setup (ISCC.exe) não encontrado. Instale com: winget install JRSoftware.InnoSetup")


def folder_size_mb(path: Path) -> float:
    if path.is_file():
        return path.stat().st_size / 1e6
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["onedir", "installer", "onefile", "all"], default="onedir")
    ap.add_argument("--with-ffmpeg", action="store_true", help="empacota ffmpeg/ffprobe junto do app")
    ap.add_argument("--skip-selftest", action="store_true")
    ap.add_argument("--dist", type=Path, default=ROOT / "dist")
    ap.add_argument("--work", type=Path, default=ROOT / "build")
    opts = ap.parse_args()

    version = read_version()
    version_file = write_version_file(version, opts.work)
    ffmpeg = find_ffmpeg() if opts.with_ffmpeg else {}
    if opts.with_ffmpeg and len(ffmpeg) < 2:
        raise SystemExit("ffmpeg/ffprobe não encontrados (instale no PATH ou: pip install static-ffmpeg)")
    print(f"{PRODUCT_NAME} {version} | Python {sys.version.split()[0]} | ffmpeg: {'sim' if ffmpeg else 'não'}")

    outputs = []
    if opts.mode in ("onedir", "installer", "all"):
        folder = run_pyinstaller(False, version_file, opts.dist, opts.work, ffmpeg)
        outputs.append(folder)
        if not opts.skip_selftest and not self_test(folder / f"{APP_NAME}.exe"):
            return 1
        if opts.mode == "all":
            zip_path = opts.dist / f"{APP_NAME}-{version}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in folder.rglob("*"):
                    zf.write(f, f.relative_to(folder.parent))
            outputs.append(zip_path)
        if opts.mode in ("installer", "all"):
            print("\n==> Inno Setup")
            subprocess.run([str(find_iscc()), f"/DMyAppVersion={version}", f"/DSourceDir={folder}",
                            f"/O{opts.dist}", str(ROOT / "installer.iss")], check=True, cwd=ROOT)
            outputs.append(opts.dist / "WinToolbox_Setup.exe")
    if opts.mode in ("onefile", "all"):
        exe = run_pyinstaller(True, version_file, opts.dist, opts.work, ffmpeg)
        outputs.append(exe)

    print("\nArtefatos gerados:")
    for out in outputs:
        if out.exists():
            print(f"  {out}  ({folder_size_mb(out):.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

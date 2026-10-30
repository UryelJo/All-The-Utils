"""
Autoteste do pacote: `WinToolbox.exe --self-test` ou `python main.py --self-test`.
Carrega todas as categorias, monta a tela/opções de cada ferramenta sem exibir janelas e
confere os recursos empacotados. Pega imports ocultos que o PyInstaller deixou de fora.
O relatório vai para logs/self_test.txt (o .exe --windowed não tem console) e o código
de saída é o número de falhas.
"""
import logging
import os
import sys
import time
import traceback
from pathlib import Path
from typing import List, Tuple

from wintoolbox.core import logging_setup as ls


def run_self_test() -> int:
    ls.setup_logging()
    log = ls.get_logger("selftest")
    lines: List[str] = []
    failures: List[Tuple[str, str]] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        lines.append(f"[{'OK' if ok else 'FALHA'}] {label}{(' - ' + detail) if detail else ''}")
        if not ok:
            failures.append((label, detail))

    t0 = time.perf_counter()
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    ls.install_qt_message_handler()

    from wintoolbox.core.registry import FileTool, Tool, get_all_tools, get_categories
    from wintoolbox.ui.theme import apply_theme
    apply_theme(app)

    # Uma categoria ausente = dependência faltando no pacote (o registro a ignora sem travar o app)
    expected = {"Arquivos e Pastas", "Codificação e Hash", "Compactação", "Dados e Estruturas", "Imagens",
                "PDF", "Rede e Internet", "Sistema", "Texto e Redação", "Áudio e Vídeo",
                "Segurança", "Criptografia", "Web", "Forense", "OSINT", "Reverse Engineering"}
    cats = get_categories()
    tools = get_all_tools()
    check(f"Ferramentas registradas: {len(tools)} em {len(cats)} categorias", len(tools) > 0)
    for cat in sorted(expected - set(cats)):
        check(f"Categoria carregada: {cat}", False, "veja o app.log (logger wintoolbox.registry)")

    keep = []
    for tool in sorted(tools, key=lambda t: t.id):
        try:
            if isinstance(tool, FileTool):
                keep.append(tool.build_options(None))
                tool.get_options()
            elif isinstance(tool, Tool):
                w = tool.build_view(None)
                keep.append(w)
            check(f"Tela: {tool.id}", True)
        except Exception as e:
            log.exception("Autoteste: falha ao montar %s", tool.id)
            check(f"Tela: {tool.id}", False, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")
        app.processEvents()

    try:
        from wintoolbox.tools.system.task_scheduler.logic import _list_via_com
        check("API COM do Agendador de Tarefas", len(_list_via_com()) > 0)
    except Exception as e:
        check("API COM do Agendador de Tarefas", False, f"{type(e).__name__}: {e}")
    from PySide6.QtGui import QImageReader
    check("Plugin de imagem SVG (setas do tema)", b"svg" in [bytes(f) for f in QImageReader.supportedImageFormats()])

    # Motores nativos/opcionais: dependem de DLLs e módulos que o PyInstaller pode não coletar
    import tempfile
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        try:
            from wintoolbox.tools.images.qrcode.logic import decode_qrcode_from_image, generate_qrcode
            generate_qrcode("autoteste-qr", tmp_dir / "qr.png")
            check("Leitura de QR Code (zxing-cpp)", decode_qrcode_from_image(tmp_dir / "qr.png") == "autoteste-qr")
        except Exception as e:
            check("Leitura de QR Code (zxing-cpp)", False, f"{type(e).__name__}: {e}")
        try:
            img = Image.new("RGB", (600, 120), "white")
            ImageDraw.Draw(img).text((10, 30), "TESTE OCR 123", fill="black", font_size=48)
            img.save(tmp_dir / "ocr.png")
            from wintoolbox.tools.images.ocr.logic import _ocr_winrt
            text = _ocr_winrt(tmp_dir / "ocr.png")
            check("OCR nativo do Windows (WinRT)", "OCR" in text.upper(), repr(text))
        except Exception as e:
            check("OCR nativo do Windows (WinRT)", False, f"{type(e).__name__}: {e}")
        try:
            img.save(tmp_dir / "teste.heic")
            img.save(tmp_dir / "teste.avif")
            check("Imagens HEIC/AVIF (pillow-heif / Pillow)", Image.open(tmp_dir / "teste.heic").size == img.size)
        except Exception as e:
            check("Imagens HEIC/AVIF (pillow-heif / Pillow)", False, f"{type(e).__name__}: {e}")
        try:
            img.save(tmp_dir / "doc.pdf")
            from wintoolbox.tools.pdf.compress.logic import compress_pdf_file
            from wintoolbox.tools.pdf.extract.logic import render_pdf_pages
            res = compress_pdf_file(tmp_dir / "doc.pdf", tmp_dir / "doc_c.pdf")
            pages = render_pdf_pages(tmp_dir / "doc.pdf", tmp_dir / "pg", dpi=72)
            check("PDF (pikepdf + pypdfium2)", res["engine"] == "pikepdf" and len(pages) == 1)
        except Exception as e:
            check("PDF (pikepdf + pypdfium2)", False, f"{type(e).__name__}: {e}")
    try:
        from wintoolbox.tools.media.speech.logic import get_available_voices
        voices = get_available_voices()
        check("Vozes de síntese (WinRT/SAPI)", len(voices) > 0, f"{len(voices)} voz(es)")
    except Exception as e:
        check("Vozes de síntese (WinRT/SAPI)", False, f"{type(e).__name__}: {e}")

    from wintoolbox.tools.images.ocr.logic import PS_SCRIPT_PATH
    check("Recurso: win_ocr.ps1", PS_SCRIPT_PATH.exists(), str(PS_SCRIPT_PATH))
    from wintoolbox.ui.icons import get_app_icon
    check("Recurso: ícone do app", not get_app_icon().isNull())
    try:
        import pythoncom  # noqa: F401
        import win32com.client  # noqa: F401
        check("pywin32 (COM)", True)
    except Exception as e:
        check("pywin32 (COM)", False, str(e))
    try:
        from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe
        lines.append(f"[INFO] ffmpeg: {get_ffmpeg_exe()}")
    except Exception as e:
        lines.append(f"[AVISO] ffmpeg indisponível (ferramentas de mídia limitadas): {e}")

    # Telas montadas disparam cargas em segundo plano: aguarda antes de encerrar o processo
    from wintoolbox.core.tasks import shutdown_tasks
    shutdown_tasks(15000)

    env = ls.collect_environment_info()
    report = [
        f"Autoteste All the Utils - {time.strftime('%Y-%m-%d %H:%M:%S')} ({time.perf_counter() - t0:.1f} s)",
        f"Resultado: {'SUCESSO' if not failures else f'{len(failures)} FALHA(S)'}",
        "",
        *lines,
        "",
        "Ambiente:",
        *(f"  {k}: {v}" for k, v in env.items()),
    ]
    out = ls.get_logs_dir() / "self_test.txt"
    out.write_text("\n".join(report), encoding="utf-8")
    if sys.stdout is not None:
        try:
            print("\n".join(report[:2] + [l for l in lines if not l.startswith("[OK]")]))
            print(f"Relatório completo: {out}")
        except Exception:
            pass
    log.info("Autoteste concluído: %d falha(s). Relatório: %s", len(failures), out)
    logging.shutdown()
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None:
                stream.flush()  # os._exit não esvazia os buffers
        except Exception:
            pass
    # Encerra sem a finalização do Python: os ~80 widgets órfãos montados acima (players de
    # mídia, timers) seriam destruídos fora de ordem após o QApplication -> 0xC0000005.
    os._exit(min(len(failures), 125))

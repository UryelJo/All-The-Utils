"""
Lógica para conversão de documentos do Microsoft Office para PDF usando automação COM nativa do Windows.
Suporta Word (.docx/.doc), Excel (.xlsx/.xls) e PowerPoint (.pptx/.ppt).
"""
import sys
from pathlib import Path
from typing import Optional


def convert_office_doc_to_pdf(src_path: Path, dst_path: Path) -> Path:
    """
    Converte um arquivo de documento do Office para PDF usando automação COM.
    Requer que o Microsoft Office esteja instalado no Windows.
    """
    src_path = Path(src_path).resolve()
    dst_path = Path(dst_path).resolve()
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {src_path}")

    ext = src_path.suffix.lower()

    try:
        import win32com.client
        import pythoncom
    except ImportError:
        raise RuntimeError("A biblioteca 'pywin32' (win32com) não está instalada no ambiente Python.")

    # Inicializa COM para a thread corrente
    pythoncom.CoInitialize()

    try:
        if ext in (".docx", ".doc"):
            _convert_word_to_pdf(src_path, dst_path, win32com.client)
        elif ext in (".xlsx", ".xls"):
            _convert_excel_to_pdf(src_path, dst_path, win32com.client)
        elif ext in (".pptx", ".ppt"):
            _convert_powerpoint_to_pdf(src_path, dst_path, win32com.client)
        else:
            raise ValueError(f"Formato de documento não suportado para conversão: {ext}")
    finally:
        pythoncom.CoUninitialize()

    return dst_path


def _convert_word_to_pdf(src: Path, dst: Path, client) -> None:
    word = None
    doc = None
    try:
        word = client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        doc = word.Documents.Open(str(src), ReadOnly=True, ConfirmConversions=False)
        # wdFormatPDF = 17
        doc.SaveAs(str(dst), FileFormat=17)
    except Exception as e:
        raise RuntimeError(f"Erro na conversão do Word (verifique se o Microsoft Word está instalado): {e}")
    finally:
        if doc:
            try:
                doc.Close(False)
            except Exception:
                pass
        if word:
            try:
                word.Quit()
            except Exception:
                pass


def _convert_excel_to_pdf(src: Path, dst: Path, client) -> None:
    excel = None
    wb = None
    try:
        excel = client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(str(src), ReadOnly=True)
        # xlTypePDF = 0
        wb.ExportAsFixedFormat(0, str(dst))
    except Exception as e:
        raise RuntimeError(f"Erro na conversão do Excel (verifique se o Microsoft Excel está instalado): {e}")
    finally:
        if wb:
            try:
                wb.Close(False)
            except Exception:
                pass
        if excel:
            try:
                excel.Quit()
            except Exception:
                pass


def _convert_powerpoint_to_pdf(src: Path, dst: Path, client) -> None:
    ppt = None
    pres = None
    try:
        ppt = client.DispatchEx("PowerPoint.Application")
        # WithWindow=False (0)
        pres = ppt.Presentations.Open(str(src), 0, False, False)
        # ppSaveAsPDF = 32
        pres.SaveAs(str(dst), 32)
    except Exception as e:
        raise RuntimeError(f"Erro na conversão do PowerPoint (verifique se o PowerPoint está instalado): {e}")
    finally:
        if pres:
            try:
                pres.Close()
            except Exception:
                pass
        if ppt:
            try:
                ppt.Quit()
            except Exception:
                pass

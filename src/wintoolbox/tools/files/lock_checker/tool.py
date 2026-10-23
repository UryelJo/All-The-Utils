"""
Ferramenta: Quem Está Usando Este Arquivo? (Restart Manager API do Windows).
Identifica processos que estão travando arquivos ou pastas no Windows e permite encerrá-los.
"""
import ctypes
import os
import psutil
from ctypes import wintypes
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner

class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [
        ("dwProcessId", wintypes.DWORD),
        ("ProcessStartTime", wintypes.FILETIME),
    ]

class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [
        ("Process", RM_UNIQUE_PROCESS),
        ("strAppName", wintypes.WCHAR * 256),
        ("strServiceShortName", wintypes.WCHAR * 64),
        ("ApplicationType", wintypes.DWORD),
        ("AppStatus", wintypes.ULONG),
        ("TSSessionId", wintypes.DWORD),
        ("bRestartable", wintypes.BOOL),
    ]

def find_locking_processes(target_path: str) -> List[Dict[str, str]]:
    """Descobre os processos que travam o arquivo utilizando a API nativa Restart Manager do Windows."""
    results: List[Dict[str, str]] = []

    try:
        rm = ctypes.WinDLL("rstrtmgr.dll")
        session_handle = wintypes.DWORD()
        session_key = (wintypes.WCHAR * 33)()

        res = rm.RmStartSession(ctypes.byref(session_handle), 0, session_key)
        if res == 0:
            try:
                path_arr = (wintypes.LPCWSTR * 1)(target_path)
                res = rm.RmRegisterResources(session_handle, 1, path_arr, 0, None, 0, None)
                if res == 0:
                    n_needed = wintypes.UINT(0)
                    n_proc = wintypes.UINT(0)
                    reboot_reasons = wintypes.DWORD()

                    # Chama primeira vez para obter a contagem necessária
                    res = rm.RmGetList(session_handle, ctypes.byref(n_needed), ctypes.byref(n_proc), None, ctypes.byref(reboot_reasons))
                    if res == 234 and n_needed.value > 0:  # ERROR_MORE_DATA
                        proc_info_arr = (RM_PROCESS_INFO * n_needed.value)()
                        n_proc.value = n_needed.value
                        res = rm.RmGetList(session_handle, ctypes.byref(n_needed), ctypes.byref(n_proc), proc_info_arr, ctypes.byref(reboot_reasons))
                        if res == 0:
                            for i in range(n_proc.value):
                                item = proc_info_arr[i]
                                pid = item.Process.dwProcessId
                                proc_name = item.strAppName
                                if not proc_name:
                                    try:
                                        proc_name = psutil.Process(pid).name()
                                    except Exception:
                                        proc_name = "Desconhecido"
                                results.append({
                                    "pid": str(pid),
                                    "name": proc_name,
                                    "service": item.strServiceShortName or "-"
                                })
            finally:
                rm.RmEndSession(session_handle)
    except Exception:
        pass

    # Fallback complementar caso a API não retorne e o arquivo seja local
    if not results and os.path.exists(target_path) and os.path.isfile(target_path):
        target_norm = os.path.normcase(os.path.abspath(target_path))
        try:
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    for of in p.open_files():
                        if os.path.normcase(os.path.abspath(of.path)) == target_norm:
                            results.append({
                                "pid": str(p.info['pid']),
                                "name": p.info['name'] or "Processo",
                                "service": "-"
                            })
                            break
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue
        except Exception:
            pass

    return results

@register
class LockCheckerTool(Tool):
    id = "files.lock_checker"
    name = "Quem Está Usando Este Arquivo?"
    category = "Arquivos e Pastas"
    description = "Descobre quais programas ou processos estão bloqueando um arquivo no Windows e permite liberá-lo"
    keywords = ["bloqueado", "trava", "processo", "lock", "fechar", "arquivo", "em uso", "restart manager"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return LockCheckerView(self, parent)

class LockCheckerView(QWidget):
    def __init__(self, tool: LockCheckerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.processes: List[Dict[str, str]] = []
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Seletor do Arquivo Bloqueado
        card_sel = QFrame()
        card_sel.setProperty("class", "card")
        l_sel = QVBoxLayout(card_sel)
        l_sel.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Arquivo ou Pasta Travada:"))
        self.txt_path = QLineEdit()
        self.txt_path.setPlaceholderText("Cole o caminho do arquivo ou selecione abaixo...")
        row1.addWidget(self.txt_path, stretch=1)

        btn_browse_f = QPushButton("Arquivo...")
        btn_browse_f.clicked.connect(self._browse_file)
        row1.addWidget(btn_browse_f)

        btn_browse_d = QPushButton("Pasta...")
        btn_browse_d.clicked.connect(self._browse_dir)
        row1.addWidget(btn_browse_d)

        self.btn_check = QPushButton("Verificar Bloqueios")
        self.btn_check.setProperty("class", "primary")
        self.btn_check.clicked.connect(self._start_check)
        row1.addWidget(self.btn_check)
        l_sel.addLayout(row1)

        layout.addWidget(card_sel)

        # Status
        self.lbl_status = QLabel("Nenhum arquivo analisado no momento.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        # Tabela de Processos
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["PID", "Nome do Programa / Processo", "Serviço", "Ação"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setFixedHeight(260)
        layout.addWidget(self.table)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _browse_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo Bloqueado")
        if f:
            self.txt_path.setText(f)
            self._start_check()

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta Bloqueada")
        if d:
            self.txt_path.setText(d)
            self._start_check()

    def _start_check(self):
        target = self.txt_path.text().strip()
        if not target or not Path(target).exists():
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo ou pasta existente.")
            return

        self.btn_check.setEnabled(False)
        self.lbl_status.setText("Consultando API do Windows Restart Manager...")

        def worker(ctx):
            return find_locking_processes(target)

        def on_done(procs: List[Dict[str, str]]):
            self.btn_check.setEnabled(True)
            self.processes = procs
            self._populate_table()

            if procs:
                self.lbl_status.setText(f"{len(procs)} processo(s) estão utilizando ou bloqueando este item.")
                self.lbl_status.setStyleSheet("color: #ffa198; font-weight: 600;")
            else:
                self.lbl_status.setText("[LIVRE] Nenhum processo está travando este arquivo ou pasta no momento.")
                self.lbl_status.setStyleSheet("color: #7ee787; font-weight: 600;")

        def on_error(err):
            self.btn_check.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha ao consultar bloqueios:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def _populate_table(self):
        self.table.setRowCount(len(self.processes))
        for row, p in enumerate(self.processes):
            self.table.setItem(row, 0, QTableWidgetItem(p["pid"]))
            self.table.setItem(row, 1, QTableWidgetItem(p["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(p["service"]))

            btn_kill = QPushButton("Encerrar Processo")
            btn_kill.setProperty("class", "danger")
            btn_kill.clicked.connect(lambda _, pid=int(p["pid"]), name=p["name"]: self._kill_process(pid, name))
            self.table.setCellWidget(row, 3, btn_kill)

    def _kill_process(self, pid: int, name: str):
        reply = QMessageBox.question(
            self,
            "Confirmar Encerramento",
            f"Deseja realmente forçar o encerramento do processo '{name}' (PID: {pid})?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                QMessageBox.information(self, "Sucesso", f"Processo {name} finalizado!")
                self._start_check()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Não foi possível finalizar o processo:\n{str(e)}")

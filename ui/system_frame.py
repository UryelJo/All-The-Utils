import os
import subprocess
import threading
import customtkinter as ctk
from tkinter import messagebox
from core.system_tools import is_admin, run_as_admin, run_command_async, clean_temp_folder

class SystemToolsFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._build_ui()

    def _build_ui(self):
        # Título
        title = ctk.CTkLabel(
            self,
            text="🛠️ Ferramentas & Manutenção do Windows",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(anchor="w", padx=20, pady=(20, 5))

        subtitle = ctk.CTkLabel(
            self,
            text="Otimize discos, faça diagnóstico de sistema e limpe arquivos residuais.",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        subtitle.pack(anchor="w", padx=20, pady=(0, 15))

        # Banner de Administrador
        admin_card = ctk.CTkFrame(self)
        admin_card.pack(fill="x", padx=20, pady=5)

        has_admin = is_admin()
        status_text = "🔒 Privilégios: Administrador (Todos os recursos liberados)" if has_admin else "⚠️ Privilégios: Usuário comum (Algumas tarefas exigem Administrador)"
        status_color = "#2fa572" if has_admin else "#d9822b"

        lbl_admin = ctk.CTkLabel(admin_card, text=status_text, text_color=status_color, font=ctk.CTkFont(weight="bold"))
        lbl_admin.pack(side="left", padx=15, pady=10)

        if not has_admin:
            btn_elevate = ctk.CTkButton(
                admin_card,
                text="Elevar para Administrador",
                fg_color="#d9822b",
                hover_color="#b86b20",
                command=run_as_admin,
                height=28
            )
            btn_elevate.pack(side="right", padx=15, pady=10)

        # Container em Grade com Ações
        grid_container = ctk.CTkFrame(self)
        grid_container.pack(fill="x", padx=20, pady=10)
        grid_container.columnconfigure((0, 1), weight=1)

        # Card 1: Desfragmentação / Otimização de Disco
        c1 = ctk.CTkFrame(grid_container)
        c1.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(c1, text="💽 Otimização de Disco", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(c1, text="Analisa e otimiza unidades SSD/HDD (defrag C: /O).", text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(0, 10))
        btn_defrag = ctk.CTkButton(c1, text="Executar Otimização (C:)", command=self._run_defrag)
        btn_defrag.pack(side="left", padx=12, pady=10)
        btn_defrag_gui = ctk.CTkButton(c1, text="Abrir Painel Nativo", fg_color="gray30", hover_color="gray40", command=lambda: subprocess.Popen("dfrgui.exe"))
        btn_defrag_gui.pack(side="left", padx=5, pady=10)

        # Card 2: Limpeza de Cache & Temporários
        c2 = ctk.CTkFrame(grid_container)
        c2.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(c2, text="🧹 Limpeza de Arquivos Temporários", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(c2, text="Libera espaço apagando itens do diretório %TEMP%.", text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(0, 10))
        btn_clean = ctk.CTkButton(c2, text="Limpar %TEMP%", fg_color="#1f538d", command=self._clean_temp)
        btn_clean.pack(side="left", padx=12, pady=10)
        btn_cleanmgr = ctk.CTkButton(c2, text="Limpeza de Disco do Windows", fg_color="gray30", hover_color="gray40", command=lambda: subprocess.Popen("cleanmgr.exe"))
        btn_cleanmgr.pack(side="left", padx=5, pady=10)

        # Card 3: Verificação de Integridade do Sistema (SFC)
        c3 = ctk.CTkFrame(grid_container)
        c3.grid(row=1, column=0, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(c3, text="🩺 Verificação de Arquivos (SFC)", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(c3, text="Examina e repara arquivos corrompidos do Windows.", text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(0, 10))
        btn_sfc_scan = ctk.CTkButton(c3, text="Escanear e Reparar (sfc /scannow)", command=self._run_sfc)
        btn_sfc_scan.pack(side="left", padx=12, pady=10)

        # Card 4: Rede & Utilitários
        c4 = ctk.CTkFrame(grid_container)
        c4.grid(row=1, column=1, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(c4, text="🌐 Rede & Diagnóstico", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(c4, text="Limpa cache de resolução DNS ou testa memória RAM.", text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(0, 10))
        btn_dns = ctk.CTkButton(c4, text="Limpar DNS (Flush DNS)", command=self._run_flush_dns)
        btn_dns.pack(side="left", padx=12, pady=10)
        btn_mem = ctk.CTkButton(c4, text="Diag. Memória", fg_color="gray30", hover_color="gray40", command=lambda: subprocess.Popen("mdsched.exe"))
        btn_mem.pack(side="left", padx=5, pady=10)

        # Log Terminal de Saída
        lbl_log = ctk.CTkLabel(self, text="Console de Saída em Tempo Real:", font=ctk.CTkFont(weight="bold"))
        lbl_log.pack(anchor="w", padx=20, pady=(10, 2))

        self.log_box = ctk.CTkTextbox(self, height=180, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_box.insert("end", "[Terminal Pronto] Clique em uma ação acima para iniciar o processo...\n")

    def _log(self, text: str):
        self.log_box.insert("end", f"{text}\n")
        self.log_box.see("end")

    def _run_defrag(self):
        if not is_admin():
            messagebox.showwarning("Atenção", "Para executar desfragmentação via linha de comando, é necessário executar como Administrador.")
        self._log("\n>>> Iniciando Otimização de Disco (C:)...")
        run_command_async("defrag C: /O /U /V", on_output=self._log, on_done=lambda code: self._log(f">>> Otimização concluída com código: {code}\n"))

    def _clean_temp(self):
        self._log("\n>>> Iniciando limpeza da pasta temporária (%TEMP%)...")
        def worker():
            clean_temp_folder(on_log=self._log)
        threading.Thread(target=worker, daemon=True).start()

    def _run_sfc(self):
        if not is_admin():
            messagebox.showwarning("Atenção", "O utilitário SFC requer privilégios de Administrador. Clique em 'Elevar para Administrador'.")
            return
        self._log("\n>>> Iniciando verificação SFC (sfc /scannow)... Esse processo pode levar alguns minutos.")
        run_command_async("sfc /scannow", on_output=self._log, on_done=lambda code: self._log(f">>> SFC finalizado com código: {code}\n"))

    def _run_flush_dns(self):
        self._log("\n>>> Executando ipconfig /flushdns...")
        run_command_async("ipconfig /flushdns", on_output=self._log, on_done=lambda code: self._log(">>> Cache DNS limpo com sucesso!\n"))

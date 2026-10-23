import customtkinter as ctk
from core.system_tools import get_system_metrics

class HardwareMonitorFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.disk_widgets = {}
        self._build_ui()
        self._update_metrics()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self,
            text="📊 Monitor do Sistema & Hardware",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(anchor="w", padx=20, pady=(20, 5))

        subtitle = ctk.CTkLabel(
            self,
            text="Acompanhamento em tempo real de consumo de processador, memória e armazenamento.",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        subtitle.pack(anchor="w", padx=20, pady=(0, 15))

        # Card de CPU & Memória
        metrics_card = ctk.CTkFrame(self)
        metrics_card.pack(fill="x", padx=20, pady=10)
        metrics_card.columnconfigure((0, 1), weight=1)

        # CPU
        cpu_box = ctk.CTkFrame(metrics_card)
        cpu_box.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(cpu_box, text="⚡ Processador (CPU)", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=15, pady=(10, 2))
        self.lbl_cpu_detail = ctk.CTkLabel(cpu_box, text="Uso: 0% | Núcleos: -", text_color="gray", font=ctk.CTkFont(size=12))
        self.lbl_cpu_detail.pack(anchor="w", padx=15, pady=(0, 10))

        self.progress_cpu = ctk.CTkProgressBar(cpu_box)
        self.progress_cpu.pack(fill="x", padx=15, pady=(0, 15))
        self.progress_cpu.set(0)

        # RAM
        ram_box = ctk.CTkFrame(metrics_card)
        ram_box.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(ram_box, text="🧠 Memória RAM", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=15, pady=(10, 2))
        self.lbl_ram_detail = ctk.CTkLabel(ram_box, text="Uso: 0% (0 GB / 0 GB)", text_color="gray", font=ctk.CTkFont(size=12))
        self.lbl_ram_detail.pack(anchor="w", padx=15, pady=(0, 10))

        self.progress_ram = ctk.CTkProgressBar(ram_box)
        self.progress_ram.pack(fill="x", padx=15, pady=(0, 15))
        self.progress_ram.set(0)

        # Armazenamento (Discos)
        lbl_disks = ctk.CTkLabel(self, text="💽 Unidades de Armazenamento:", font=ctk.CTkFont(weight="bold", size=15))
        lbl_disks.pack(anchor="w", padx=20, pady=(10, 5))

        self.disks_container = ctk.CTkScrollableFrame(self, height=220)
        self.disks_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _update_metrics(self):
        try:
            data = get_system_metrics()

            # Atualiza CPU
            cpu_p = data["cpu_percent"]
            self.lbl_cpu_detail.configure(text=f"Uso: {cpu_p}% | Núcleos: {data['cpu_count']}")
            self.progress_cpu.set(cpu_p / 100.0)

            # Atualiza RAM
            mem_p = data["mem_percent"]
            self.lbl_ram_detail.configure(
                text=f"Uso: {mem_p}% ({data['mem_used_gb']} GB de {data['mem_total_gb']} GB)"
            )
            self.progress_ram.set(mem_p / 100.0)

            # Atualiza Discos
            for disk in data["disks"]:
                dev = disk["device"]
                if dev not in self.disk_widgets:
                    card = ctk.CTkFrame(self.disks_container)
                    card.pack(fill="x", pady=5, padx=5)

                    lbl_name = ctk.CTkLabel(card, text=f"Unidade {disk['mountpoint']} ({disk['fstype']})", font=ctk.CTkFont(weight="bold"))
                    lbl_name.pack(anchor="w", padx=10, pady=(6, 2))

                    lbl_info = ctk.CTkLabel(card, text="", text_color="gray", font=ctk.CTkFont(size=12))
                    lbl_info.pack(anchor="w", padx=10, pady=(0, 6))

                    prog = ctk.CTkProgressBar(card)
                    prog.pack(fill="x", padx=10, pady=(0, 10))

                    self.disk_widgets[dev] = {
                        "lbl_info": lbl_info,
                        "prog": prog
                    }

                w = self.disk_widgets[dev]
                pct = disk["percent"]
                w["lbl_info"].configure(
                    text=f"Ocupado: {disk['used_gb']} GB | Livre: {disk['free_gb']} GB | Total: {disk['total_gb']} GB ({pct}%)"
                )
                w["prog"].set(pct / 100.0)

        except Exception:
            pass

        # Repete a cada 2 segundos se a janela continuar aberta
        self.after(2000, self._update_metrics)

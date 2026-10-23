import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.image_converter import convert_single_image, SUPPORTED_OUTPUTS

class ImageConverterFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.selected_files = []
        self.output_directory = None

        self._build_ui()

    def _build_ui(self):
        # Título
        title = ctk.CTkLabel(
            self,
            text="🖼️ Conversor de Imagens",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(anchor="w", padx=20, pady=(20, 10))

        subtitle = ctk.CTkLabel(
            self,
            text="Converta imagens individuais ou em lote para múltiplos formatos de forma rápida.",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        subtitle.pack(anchor="w", padx=20, pady=(0, 20))

        # Card de Seleção de Arquivos
        file_card = ctk.CTkFrame(self)
        file_card.pack(fill="x", padx=20, pady=10)

        self.btn_select_files = ctk.CTkButton(
            file_card,
            text="Selecionar Imagens...",
            command=self._select_files,
            height=36
        )
        self.btn_select_files.pack(side="left", padx=15, pady=15)

        self.lbl_file_count = ctk.CTkLabel(
            file_card,
            text="Nenhum arquivo selecionado.",
            font=ctk.CTkFont(size=13)
        )
        self.lbl_file_count.pack(side="left", padx=10, pady=15)

        # Card de Configurações
        settings_card = ctk.CTkFrame(self)
        settings_card.pack(fill="x", padx=20, pady=10)

        # Formato de saída
        lbl_format = ctk.CTkLabel(settings_card, text="Formato de Saída:", font=ctk.CTkFont(weight="bold"))
        lbl_format.grid(row=0, column=0, padx=15, pady=12, sticky="w")

        self.format_menu = ctk.CTkOptionMenu(
            settings_card,
            values=SUPPORTED_OUTPUTS,
            command=self._on_format_changed
        )
        self.format_menu.set("WEBP")
        self.format_menu.grid(row=0, column=1, padx=15, pady=12, sticky="w")

        # Qualidade (para JPEG/WEBP)
        self.lbl_quality = ctk.CTkLabel(settings_card, text="Qualidade (90%):")
        self.lbl_quality.grid(row=0, column=2, padx=15, pady=12, sticky="w")

        self.slider_quality = ctk.CTkSlider(
            settings_card,
            from_=10,
            to=100,
            number_of_steps=90,
            command=self._on_quality_changed
        )
        self.slider_quality.set(90)
        self.slider_quality.grid(row=0, column=3, padx=15, pady=12, sticky="w")

        # Pasta de Saída
        lbl_dest = ctk.CTkLabel(settings_card, text="Pasta de Destino:", font=ctk.CTkFont(weight="bold"))
        lbl_dest.grid(row=1, column=0, padx=15, pady=12, sticky="w")

        self.btn_dest = ctk.CTkButton(
            settings_card,
            text="Mesma pasta da imagem",
            fg_color="gray30",
            hover_color="gray40",
            command=self._select_output_dir
        )
        self.btn_dest.grid(row=1, column=1, columnspan=2, padx=15, pady=12, sticky="w")

        # Ação e Progresso
        action_card = ctk.CTkFrame(self)
        action_card.pack(fill="x", padx=20, pady=10)

        self.btn_convert = ctk.CTkButton(
            action_card,
            text="🚀 Iniciar Conversão",
            command=self._start_conversion,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_convert.pack(side="left", padx=15, pady=15)

        self.progress_bar = ctk.CTkProgressBar(action_card)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=15, pady=15)
        self.progress_bar.set(0)

        # Log de saída
        self.log_box = ctk.CTkTextbox(self, height=180, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        self.log_box.insert("end", "[Pronto] Selecione suas imagens e clique em 'Iniciar Conversão'.\n")

    def _select_files(self):
        files = filedialog.askopenfilenames(
            title="Escolha as imagens",
            filetypes=[("Imagens Comuns", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.gif *.ico"), ("Todos os arquivos", "*.*")]
        )
        if files:
            self.selected_files = list(files)
            self.lbl_file_count.configure(text=f"{len(self.selected_files)} arquivo(s) selecionado(s)")
            self.log_box.insert("end", f"[Info] {len(self.selected_files)} arquivo(s) carregado(s).\n")
            self.log_box.see("end")

    def _select_output_dir(self):
        folder = filedialog.askdirectory(title="Selecione a pasta de destino")
        if folder:
            self.output_directory = folder
            self.btn_dest.configure(text=folder)

    def _on_format_changed(self, choice):
        if choice in ["JPG", "WEBP"]:
            self.slider_quality.configure(state="normal")
            self.lbl_quality.configure(text_color=("black", "white"))
        else:
            self.slider_quality.configure(state="disabled")
            self.lbl_quality.configure(text_color="gray")

    def _on_quality_changed(self, value):
        self.lbl_quality.configure(text=f"Qualidade ({int(value)}%):")

    def _start_conversion(self):
        if not self.selected_files:
            messagebox.showwarning("Aviso", "Nenhum arquivo selecionado para conversão.")
            return

        fmt = self.format_menu.get()
        quality = int(self.slider_quality.get())
        dest_dir = self.output_directory

        self.btn_convert.configure(state="disabled")
        self.progress_bar.set(0)

        def worker():
            total = len(self.selected_files)
            sucessos = 0
            erros = 0

            for idx, file_path in enumerate(self.selected_files, start=1):
                fname = os.path.basename(file_path)
                try:
                    out = convert_single_image(file_path, fmt, dest_dir, quality)
                    sucessos += 1
                    self.log_box.insert("end", f"✔ [OK] {fname} -> {os.path.basename(out)}\n")
                except Exception as e:
                    erros += 1
                    self.log_box.insert("end", f"❌ [ERRO] {fname}: {e}\n")

                self.progress_bar.set(idx / total)
                self.log_box.see("end")

            self.log_box.insert("end", f"\n🏁 Conversão concluída! Sucessos: {sucessos} | Erros: {erros}\n\n")
            self.log_box.see("end")
            self.btn_convert.configure(state="normal")

        threading.Thread(target=worker, daemon=True).start()

import sys
import os
import customtkinter as ctk

# Garante que os módulos locais sejam encontrados
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.image_frame import ImageConverterFrame
from ui.system_frame import SystemToolsFrame
from ui.hardware_frame import HardwareMonitorFrame

# Configuração global de aparência
ctk.set_appearance_mode("Dark")  # Opções: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Temas padrão: "blue", "green", "dark-blue"

class WinToolboxApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Windows Toolbox - Caixa de Ferramentas")
        self.geometry("980x640")
        self.minsize(850, 550)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_views()

        # Seleciona a primeira visão por padrão
        self._select_view("images")

    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        # Logo / Título
        lbl_logo = ctk.CTkLabel(
            self.sidebar_frame,
            text="🧰 WinToolbox",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        lbl_logo.grid(row=0, column=0, padx=20, pady=(25, 20))

        # Botões de Navegação
        self.btn_nav_images = ctk.CTkButton(
            self.sidebar_frame,
            text="🖼️ Conversor Imagem",
            height=38,
            anchor="w",
            command=lambda: self._select_view("images")
        )
        self.btn_nav_images.grid(row=1, column=0, padx=15, pady=8, sticky="ew")

        self.btn_nav_system = ctk.CTkButton(
            self.sidebar_frame,
            text="🛠️ Ferramentas Windows",
            height=38,
            anchor="w",
            command=lambda: self._select_view("system")
        )
        self.btn_nav_system.grid(row=2, column=0, padx=15, pady=8, sticky="ew")

        self.btn_nav_hardware = ctk.CTkButton(
            self.sidebar_frame,
            text="📊 Monitor do Sistema",
            height=38,
            anchor="w",
            command=lambda: self._select_view("hardware")
        )
        self.btn_nav_hardware.grid(row=3, column=0, padx=15, pady=8, sticky="ew")

        # Configuração de Tema na base da sidebar
        lbl_theme = ctk.CTkLabel(self.sidebar_frame, text="Aparência:", font=ctk.CTkFont(size=12))
        lbl_theme.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="w")

        self.theme_menu = ctk.CTkOptionMenu(
            self.sidebar_frame,
            values=["Escuro", "Claro", "Sistema"],
            command=self._change_appearance_mode
        )
        self.theme_menu.set("Escuro")
        self.theme_menu.grid(row=6, column=0, padx=20, pady=(5, 20), sticky="ew")

    def _build_views(self):
        # Cria as telas
        self.view_images = ImageConverterFrame(self)
        self.view_system = SystemToolsFrame(self)
        self.view_hardware = HardwareMonitorFrame(self)

    def _select_view(self, name: str):
        # Esconde todas as visões
        self.view_images.grid_forget()
        self.view_system.grid_forget()
        self.view_hardware.grid_forget()

        # Reseta estilos dos botões
        normal_color = ("gray75", "gray25")
        active_color = ("#3a7ebf", "#1f538d")

        self.btn_nav_images.configure(fg_color=normal_color)
        self.btn_nav_system.configure(fg_color=normal_color)
        self.btn_nav_hardware.configure(fg_color=normal_color)

        # Mostra a tela selecionada e destaca o botão
        if name == "images":
            self.view_images.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
            self.btn_nav_images.configure(fg_color=active_color)
        elif name == "system":
            self.view_system.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
            self.btn_nav_system.configure(fg_color=active_color)
        elif name == "hardware":
            self.view_hardware.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
            self.btn_nav_hardware.configure(fg_color=active_color)

    def _change_appearance_mode(self, mode: str):
        mode_map = {"Escuro": "Dark", "Claro": "Light", "Sistema": "System"}
        ctk.set_appearance_mode(mode_map.get(mode, "Dark"))

if __name__ == "__main__":
    app = WinToolboxApp()
    app.mainloop()

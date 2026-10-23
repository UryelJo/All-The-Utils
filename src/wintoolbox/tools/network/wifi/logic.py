"""
Lógica pura da ferramenta Visualizador de Senhas Wi-Fi e Gerador de QR Code.
Consulta de perfis salvos no Windows e geração de payload/imagem QR com Pillow e qrcode.
"""
from dataclasses import dataclass
import subprocess
from typing import List, Optional
from PIL import Image
import qrcode


@dataclass
class WifiProfileItem:
    ssid: str
    auth: str
    password: str


def get_saved_wifi_profiles() -> List[WifiProfileItem]:
    """Recupera redes Wi-Fi e senhas salvas no Windows via netsh."""
    profiles: List[WifiProfileItem] = []
    try:
        out = subprocess.check_output(
            "netsh wlan show profiles",
            shell=True,
            text=True,
            errors="replace",
        )
        profile_names: List[str] = []
        for line in out.splitlines():
            if ":" in line and (
                "Todos os Perfis de Usurios" in line
                or "All User Profile" in line
                or "Perfil de Todos os Usurios" in line
                or "Perfil" in line
            ):
                p_name = line.split(":", 1)[1].strip()
                if p_name:
                    profile_names.append(p_name)

        for name in profile_names:
            try:
                cmd = f'netsh wlan show profile name="{name}" key=clear'
                p_out = subprocess.check_output(cmd, shell=True, text=True, errors="replace")
                auth = "WPA2"
                key = "(Sem senha / Aberta)"
                for pline in p_out.splitlines():
                    if ":" in pline:
                        k, v = pline.split(":", 1)
                        k = k.strip()
                        v = v.strip()
                        if "Autenticao" in k or "Authentication" in k:
                            auth = v
                        elif "Contedo da Chave" in k or "Key Content" in k:
                            key = v
                profiles.append(WifiProfileItem(ssid=name, auth=auth, password=key))
            except Exception:
                continue
    except Exception:
        pass
    return profiles


def generate_wifi_qr_image(ssid: str, password: str, auth_type: str = "WPA") -> Image.Image:
    """Gera o objeto PIL Image do QR code para conexão automática de celular ao Wi-Fi."""
    if auth_type == "Aberta":
        payload = f"WIFI:S:{ssid};T:nopass;;"
    else:
        payload = f"WIFI:T:{auth_type};S:{ssid};P:{password};;"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")

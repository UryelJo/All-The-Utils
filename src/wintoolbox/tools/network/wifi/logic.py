"""
Lógica pura da ferramenta Visualizador de Senhas Wi-Fi e Gerador de QR Code.
Consulta de perfis salvos no Windows e geração de payload/imagem QR com Pillow e qrcode.
"""
from dataclasses import dataclass
import subprocess
from typing import List, Optional
from PIL import Image
import qrcode

from wintoolbox.core.shell import CREATE_NO_WINDOW, decode_console_output


@dataclass
class WifiProfileItem:
    ssid: str
    auth: str
    password: str


def _run_netsh(args: List[str]) -> str:
    """Executa netsh sem shell e decodifica a saída na página de código OEM do console."""
    res = subprocess.run(
        ["netsh", *args],
        capture_output=True,
        timeout=15,
        creationflags=CREATE_NO_WINDOW,
    )
    return decode_console_output(res.stdout)


def get_saved_wifi_profiles() -> List[WifiProfileItem]:
    """Recupera redes Wi-Fi e senhas salvas no Windows via netsh."""
    profiles: List[WifiProfileItem] = []
    try:
        out = _run_netsh(["wlan", "show", "profiles"])
        profile_names: List[str] = []
        for line in out.splitlines():
            # "    Todos os Perfis de Usuários: MinhaRede" / "    All User Profile     : MyNet"
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key_norm = key.strip().lower()
            if ("perfi" in key_norm and "usu" in key_norm) or "all user profile" in key_norm:
                p_name = value.strip()
                if p_name:
                    profile_names.append(p_name)

        for name in profile_names:
            try:
                # O nome vai como argumento isolado: SSIDs com aspas ou '&' não viram comandos
                p_out = _run_netsh(["wlan", "show", "profile", f"name={name}", "key=clear"])
                auth = "WPA2"
                key = "(Sem senha / Aberta)"
                for pline in p_out.splitlines():
                    if ":" in pline:
                        k, v = pline.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip()
                        if k.startswith("autentica") or k == "authentication":
                            auth = v
                        elif "chave" in k and "conte" in k or k == "key content":
                            key = v
                profiles.append(WifiProfileItem(ssid=name, auth=auth, password=key))
            except Exception:
                continue
    except Exception:
        pass
    return profiles


def _escape_wifi_field(value: str) -> str:
    """Escapa caracteres reservados do formato WIFI: barra invertida, ponto e vírgula, vírgula, dois-pontos e aspas."""
    for ch in ("\\", ";", ",", ":", '"'):
        value = value.replace(ch, "\\" + ch)
    return value


def generate_wifi_qr_image(ssid: str, password: str, auth_type: str = "WPA") -> Image.Image:
    """Gera o objeto PIL Image do QR code para conexão automática de celular ao Wi-Fi."""
    # O formato WIFI: só reconhece WEP, WPA (cobre WPA/WPA2) e SAE (WPA3)
    auth_type = {"WPA2": "WPA", "WPA3": "SAE"}.get(auth_type, auth_type)
    if auth_type == "Aberta":
        payload = f"WIFI:S:{_escape_wifi_field(ssid)};T:nopass;;"
    else:
        payload = f"WIFI:T:{auth_type};S:{_escape_wifi_field(ssid)};P:{_escape_wifi_field(password)};;"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")

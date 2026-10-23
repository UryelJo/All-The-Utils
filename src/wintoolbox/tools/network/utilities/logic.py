"""
Lógica de utilitários de rede (Wake-on-LAN, Encurtamento e Expansão de Links, Download com Retomada).
"""
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional


def send_wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255", port: int = 9) -> None:
    """Monta e dispara o Magic Packet de 102 bytes para Wake-on-LAN."""
    clean_mac = mac_address.replace(":", "").replace("-", "").replace(".", "").upper()
    if len(clean_mac) != 12:
        raise ValueError("O endereço MAC deve conter 12 caracteres hexadecimais (ex: 00:11:22:33:44:55).")

    mac_bytes = bytes.fromhex(clean_mac)
    magic_packet = b"\xff" * 6 + mac_bytes * 16

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.sendto(magic_packet, (broadcast_ip, port))
    finally:
        sock.close()


def shorten_url(url: str, provider: str = "tinyurl") -> str:
    """Encurta uma URL longa usando serviços públicos sem necessidade de token/API key."""
    if not url.startswith("http"):
        url = f"https://{url}"

    encoded = urllib.parse.quote(url)
    if provider == "is.gd":
        endpoint = f"https://is.gd/create.php?format=simple&url={encoded}"
    else:
        endpoint = f"https://tinyurl.com/api-create.php?url={encoded}"

    req = urllib.request.Request(endpoint, headers={"User-Agent": "WinToolbox/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8").strip()


def expand_url_chain(url: str, max_redirects: int = 10) -> List[Dict[str, str]]:
    """Rastreia toda a cadeia de redirecionamentos (301/302) de um link até a URL final."""
    if not url.startswith("http"):
        url = f"https://{url}"

    chain: List[Dict[str, str]] = []
    current_url = url

    for _ in range(max_redirects):
        try:
            req = urllib.request.Request(current_url, headers={"User-Agent": "WinToolbox/1.0"}, method="HEAD")

            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            opener = urllib.request.build_opener(NoRedirect)
            resp = opener.open(req, timeout=6)
            code = resp.getcode()
            chain.append({"url": current_url, "status": f"{code} OK (Final)"})
            break
        except urllib.error.HTTPError as e:
            code = e.code
            loc = e.headers.get("Location")
            chain.append({"url": current_url, "status": f"{code} Redirecionamento"})
            if loc and code in (301, 302, 303, 307, 308):
                if loc.startswith("/"):
                    base = "/".join(current_url.split("/", 3)[:3])
                    current_url = f"{base}{loc}"
                else:
                    current_url = loc
            else:
                break
        except Exception as e:
            chain.append({"url": current_url, "status": f"Erro: {str(e)}"})
            break
    return chain


def download_file_resumable(
    url: str,
    target_file: Path,
    progress_cb: Optional[Callable[[int, Optional[int], str], None]] = None,
    is_cancelled_fn: Optional[Callable[[], bool]] = None,
    chunk_size: int = 64 * 1024,
) -> int:
    """
    Realiza o download de um arquivo com suporte a continuação (HTTP Range request).
    Retorna o número total de bytes baixados ou existentes.
    """
    target_file = Path(target_file)
    existing_size = target_file.stat().st_size if target_file.exists() else 0
    headers = {"User-Agent": "WinToolbox/1.0"}
    if existing_size > 0:
        headers["Range"] = f"bytes={existing_size}-"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        content_len = resp.getheader("Content-Length")
        total_bytes = int(content_len) + existing_size if content_len else None

        mode = "ab" if existing_size > 0 else "wb"
        downloaded = existing_size

        with open(target_file, mode) as fp:
            while True:
                if is_cancelled_fn and is_cancelled_fn():
                    break
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                fp.write(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    pct_str = f"{int((downloaded / total_bytes) * 100)}%" if total_bytes else ""
                    progress_cb(downloaded, total_bytes, pct_str)

        return downloaded

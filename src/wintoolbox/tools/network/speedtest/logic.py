"""
Lógica para medição de velocidade de conexão à internet (Speedtest).
"""
import time
import urllib.request
from typing import Callable, Dict, Optional, Any

def run_speedtest(progress_cb: Optional[Callable[[str, int], None]] = None) -> Dict[str, Any]:
    """
    Executa o teste de velocidade medindo latência (ping), taxa de download e upload.
    Utiliza speedtest-cli com fallback automático caso os servidores Ookla estejam inacessíveis.
    """
    if progress_cb:
        progress_cb("Localizando servidores mais próximos...", 10)

    try:
        import speedtest
        st = speedtest.Speedtest()
        
        if progress_cb:
            progress_cb("Obtendo melhor servidor...", 20)
        best = st.get_best_server()
        ping_ms = round(best.get("latency", 0.0), 1)
        server_info = f"{best.get('sponsor', 'Servidor')} ({best.get('name', '')}, {best.get('country', '')})"

        if progress_cb:
            progress_cb(f"Testando velocidade de Download... (Ping: {ping_ms} ms)", 40)
        st.download()
        download_bps = st.results.download
        download_mbps = round(download_bps / 1_000_000, 2)

        if progress_cb:
            progress_cb(f"Testando velocidade de Upload... (Download: {download_mbps} Mbps)", 70)
        st.upload()
        upload_bps = st.results.upload
        upload_mbps = round(upload_bps / 1_000_000, 2)

        client_info = st.results.client or {}

        if progress_cb:
            progress_cb("Teste concluído com sucesso!", 100)

        return {
            "success": True,
            "ping_ms": ping_ms,
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "server": server_info,
            "isp": client_info.get("isp", "Desconhecido"),
            "ip": client_info.get("ip", "Desconhecido"),
            "source": "speedtest-cli"
        }
    except Exception as e:
        # Fallback resiliente caso Ookla bloqueie API ou dê timeout
        if progress_cb:
            progress_cb("Fallback: medindo latência e download direto...", 30)

        try:
            return _fallback_speedtest(progress_cb)
        except Exception as fb_err:
            return {
                "success": False,
                "error": f"Erro no teste: {str(e)} | Fallback: {str(fb_err)}",
                "ping_ms": 0.0,
                "download_mbps": 0.0,
                "upload_mbps": 0.0,
                "server": "Inacessível",
                "isp": "Desconhecido",
                "ip": "Desconhecido"
            }

def _fallback_speedtest(progress_cb: Optional[Callable[[str, int], None]] = None) -> Dict[str, Any]:
    """Fallback leve medindo latência e taxa de transferência via CDN estável."""
    test_url = "https://speed.cloudflare.com/__down?bytes=15000000"  # 15MB
    
    t0 = time.time()
    req = urllib.request.Request("https://speed.cloudflare.com/__down?bytes=0", headers={"User-Agent": "WinToolbox/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        r.read()
    ping_ms = round((time.time() - t0) * 1000, 1)

    if progress_cb:
        progress_cb(f"Medindo taxa de download... (Ping: {ping_ms} ms)", 50)

    t_start = time.time()
    bytes_read = 0
    req_dl = urllib.request.Request(test_url, headers={"User-Agent": "WinToolbox/1.0"})
    with urllib.request.urlopen(req_dl, timeout=15) as dl_resp:
        while True:
            chunk = dl_resp.read(65536)
            if not chunk:
                break
            bytes_read += len(chunk)
            elapsed = time.time() - t_start
            if elapsed >= 8.0:
                break

    duration = max(time.time() - t_start, 0.1)
    download_mbps = round((bytes_read * 8) / (duration * 1_000_000), 2)

    if progress_cb:
        progress_cb("Teste de contingência finalizado!", 100)

    return {
        "success": True,
        "ping_ms": ping_ms,
        "download_mbps": download_mbps,
        "upload_mbps": 0.0,
        "server": "Cloudflare CDN Edge",
        "isp": "Detecção Direta",
        "ip": "-",
        "source": "fallback-cdn"
    }

"""
Lógica para medição de velocidade de conexão à internet (Speedtest).
Usa os endpoints públicos do teste da Cloudflare (speed.cloudflare.com) apenas com a
biblioteca padrão. Substitui o speedtest-cli, sem manutenção desde 2021 e frequentemente
bloqueado pelos servidores Ookla (HTTP 403).
"""
import http.client
import json
import os
import ssl
import statistics
import threading
import time
from typing import Any, Callable, Dict, List, Optional

HOST = "speed.cloudflare.com"
USER_AGENT = "AllTheUtils/1.0"
PARALLEL_STREAMS = 4
DOWNLOAD_SECONDS = 8.0
UPLOAD_SECONDS = 6.0
DOWNLOAD_CHUNK_BYTES = 25_000_000
UPLOAD_CHUNK_BYTES = 4_000_000

ProgressCb = Optional[Callable[[str, int], None]]


def _connect(timeout: float = 10.0) -> http.client.HTTPSConnection:
    return http.client.HTTPSConnection(HOST, timeout=timeout, context=ssl.create_default_context())


def _get_meta() -> Dict[str, Any]:
    """IP público, provedor (AS) e ponto de presença da Cloudflare usado no teste."""
    conn = _connect()
    try:
        # Sem Referer o /meta responde 403
        conn.request("GET", "/meta", headers={"User-Agent": USER_AGENT, "Referer": f"https://{HOST}/"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", "replace")
        if resp.status == 200 and body.startswith("{"):
            return json.loads(body)
        # Reserva: /cdn-cgi/trace traz IP, ponto de presença e país (sem o nome do provedor)
        conn.request("GET", "/cdn-cgi/trace", headers={"User-Agent": USER_AGENT})
        trace = dict(line.split("=", 1) for line in conn.getresponse().read().decode().splitlines() if "=" in line)
        return {"clientIp": trace.get("ip", ""), "colo": trace.get("colo", ""), "country": trace.get("loc", "")}
    except Exception:
        return {}
    finally:
        conn.close()


def _measure_latency(samples: int = 12) -> Dict[str, float]:
    """Latência em conexão persistente (exclui o handshake TCP/TLS da medição) e jitter."""
    conn = _connect()
    times: List[float] = []
    try:
        for _ in range(samples):
            t0 = time.perf_counter()
            conn.request("GET", "/__down?bytes=0", headers={"User-Agent": USER_AGENT})
            conn.getresponse().read()
            times.append((time.perf_counter() - t0) * 1000)
    finally:
        conn.close()
    measured = times[1:] or times  # a primeira requisição ainda paga o handshake
    jitter = statistics.mean(abs(a - b) for a, b in zip(measured, measured[1:])) if len(measured) > 1 else 0.0
    return {"ping_ms": round(statistics.median(measured), 1), "jitter_ms": round(jitter, 1)}


def _run_parallel(worker: Callable[[float, List[int]], None], seconds: float,
                  progress_cb: ProgressCb, label: str, start_pct: int, end_pct: int) -> float:
    """Executa `worker` em PARALLEL_STREAMS conexões por `seconds` e retorna Mbps."""
    counters = [0] * PARALLEL_STREAMS
    deadline = time.perf_counter() + seconds
    threads = [threading.Thread(target=worker, args=(deadline, counters, i), daemon=True)
               for i in range(PARALLEL_STREAMS)]
    started = time.perf_counter()
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        elapsed = time.perf_counter() - started
        if progress_cb:
            mbps = sum(counters) * 8 / max(elapsed, 0.1) / 1e6
            pct = start_pct + int((end_pct - start_pct) * min(elapsed / seconds, 1.0))
            progress_cb(f"{label}... {mbps:.1f} Mbps", pct)
        time.sleep(0.25)
    duration = max(time.perf_counter() - started, 0.1)
    return round(sum(counters) * 8 / duration / 1e6, 2)


def _download_worker(deadline: float, counters: List[int], idx: int) -> None:
    while time.perf_counter() < deadline:
        conn = _connect(timeout=15)
        try:
            conn.request("GET", f"/__down?bytes={DOWNLOAD_CHUNK_BYTES}", headers={"User-Agent": USER_AGENT})
            resp = conn.getresponse()
            while time.perf_counter() < deadline:
                chunk = resp.read(65536)
                if not chunk:
                    break
                counters[idx] += len(chunk)
        except Exception:
            time.sleep(0.2)
        finally:
            conn.close()


def _upload_worker(deadline: float, counters: List[int], idx: int) -> None:
    payload = os.urandom(UPLOAD_CHUNK_BYTES)  # aleatório: não pode ser comprimido no caminho
    conn = _connect(timeout=15)
    try:
        while time.perf_counter() < deadline:
            conn.putrequest("POST", "/__up")
            conn.putheader("User-Agent", USER_AGENT)
            conn.putheader("Content-Type", "application/octet-stream")
            conn.putheader("Content-Length", str(len(payload)))
            conn.endheaders()
            view = memoryview(payload)
            sent = 0
            while sent < len(view):
                piece = view[sent:sent + 65536]
                conn.send(piece)
                sent += len(piece)
                counters[idx] += len(piece)
            conn.getresponse().read()
    except Exception:
        pass
    finally:
        conn.close()


def run_speedtest(progress_cb: ProgressCb = None) -> Dict[str, Any]:
    """
    Executa o teste de velocidade medindo latência (ping/jitter), download e upload.
    Retorna um dict com success, ping_ms, jitter_ms, download_mbps, upload_mbps, server, isp, ip.
    """
    try:
        if progress_cb:
            progress_cb("Localizando servidor Cloudflare mais próximo...", 5)
        meta = _get_meta()
        latency = _measure_latency()
        if progress_cb:
            progress_cb(f"Latência: {latency['ping_ms']} ms (jitter {latency['jitter_ms']} ms)", 15)

        download = _run_parallel(_download_worker, DOWNLOAD_SECONDS, progress_cb, "Medindo download", 15, 60)
        upload = _run_parallel(_upload_worker, UPLOAD_SECONDS, progress_cb, "Medindo upload", 60, 98)
        if download <= 0:
            raise RuntimeError("Nenhum dado recebido do servidor de teste.")

        if progress_cb:
            progress_cb("Teste concluído com sucesso!", 100)

        colo = meta.get("colo", "")
        if isinstance(colo, dict):  # /meta: {"iata": "GRU", "city": "Sao Paulo", ...}
            place = ", ".join(x for x in (colo.get("city"), colo.get("cca2")) if x)
            colo = colo.get("iata", "")
        else:  # /cdn-cgi/trace: colo é o código IATA
            place = ", ".join(x for x in (meta.get("city"), meta.get("country")) if x)
        return {
            "success": True,
            "ping_ms": latency["ping_ms"],
            "jitter_ms": latency["jitter_ms"],
            "download_mbps": download,
            "upload_mbps": upload,
            "server": f"Cloudflare {colo}" + (f" ({place})" if place else ""),
            "isp": meta.get("asOrganization", "Desconhecido"),
            "ip": meta.get("clientIp", "Desconhecido"),
            "source": "cloudflare",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro no teste de velocidade: {e}",
            "ping_ms": 0.0,
            "jitter_ms": 0.0,
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "server": "Inacessível",
            "isp": "Desconhecido",
            "ip": "Desconhecido",
        }

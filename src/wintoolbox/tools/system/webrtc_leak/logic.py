"""Lógica de detecção de vazamento de IP via WebRTC (sem dependências externas).

Diagnostica o comportamento do WebRTC contra vazamento de endereços IP locais e públicos:
1. Sobe um servidor de teste local HTTP temporário para execução segura do teste de ICE candidates;
2. Analisa candidatos STUN/ICE (host e srflx) detectados pelo navegador;
3. Compara os IPs reportados com o IP de conexão pública e classifica o risco de vazamento;
4. Fornece recomendações específicas para mitigação no Google Chrome, Mozilla Firefox e Microsoft Edge.
"""
from __future__ import annotations

import http.server
import ipaddress
import json
import socket
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


PAGINA_TESTE_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>WinToolbox - Teste de WebRTC Leak</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #121212; color: #fff; text-align: center; padding: 40px; }
    .card { background: #1e1e1e; border: 1px solid #333; border-radius: 8px; max-width: 520px; margin: 0 auto; padding: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
    h2 { margin-top: 0; color: #0078d4; }
    p { color: #aaa; font-size: 14px; }
    .status { margin-top: 20px; font-weight: bold; color: #00bc70; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Teste de Vazamento WebRTC</h2>
    <p>O navegador está colhendo candidatos ICE via STUN para verificar se seus IPs reais estão expostos.</p>
    <div id="status" class="status">Coletando candidatos...</div>
  </div>
  <script>
    const ips = new Set();
    const pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });
    pc.createDataChannel("");
    
    pc.onicecandidate = (e) => {
      if (e.candidate && e.candidate.candidate) {
        const linha = e.candidate.candidate;
        const partes = linha.split(" ");
        if (partes.length >= 5) {
          const ip = partes[4];
          if (ip && !ip.endsWith(".local")) {
            ips.add(ip);
          }
        }
      } else {
        enviarResultado();
      }
    };
    
    pc.createOffer().then(offer => pc.setLocalDescription(offer)).catch(err => {
      document.getElementById("status").innerText = "WebRTC bloqueado ou não suportado neste navegador.";
      enviarResultado();
    });

    setTimeout(() => { enviarResultado(); }, 3500);

    let enviado = false;
    function enviarResultado() {
      if (enviado) return;
      enviado = true;
      document.getElementById("status").innerText = "Diagnóstico concluído! Pode retornar ao WinToolbox.";
      fetch("/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ips: Array.from(ips) })
      }).catch(() => {});
    }
  </script>
</body>
</html>
"""


def _eh_ip_privado(ip_str: str) -> bool:
    """Verifica se o IP pertence a faixas privadas (RFC 1918) ou loopback."""
    try:
        obj = ipaddress.ip_address(ip_str)
        return obj.is_private or obj.is_loopback or obj.is_link_local
    except ValueError:
        return False


def analisar_candidatos_webrtc(ips_detectados: List[str], ip_publico_esperado: str = "") -> Dict[str, Any]:
    """Classifica os IPs colhidos via WebRTC e avalia o risco de vazamento."""
    ips_privados: List[str] = []
    ips_publicos: List[str] = []

    for ip in ips_detectados:
        ip = ip.strip()
        if not ip:
            continue
        if _eh_ip_privado(ip):
            ips_privados.append(ip)
        else:
            ips_publicos.append(ip)

    score = 100
    alertas: List[Dict[str, str]] = []
    recoms: List[str] = []
    vazamento = False

    if ips_publicos:
        if ip_publico_esperado and any(ip != ip_publico_esperado for ip in ips_publicos):
            vazamento = True
            score -= 50
            alertas.append({
                "severidade": "Crítico",
                "titulo": "Vazamento Crítico de IP Público Real via WebRTC",
                "detalhe": f"WebRTC expôs o endereço IP {', '.join(ips_publicos)}, diferente do IP do túnel VPN ({ip_publico_esperado}).",
            })
            recoms.append("Desative o WebRTC no navegador ou use extensões como WebRTC Control / uBlock Origin para evitar vazamento.")
        else:
            alertas.append({
                "severidade": "Médio",
                "titulo": f"IP Público Exposto via WebRTC ({', '.join(ips_publicos)})",
                "detalhe": "WebRTC permite que websites consultem seu endereço IP público diretamente sem passar por proxies normais.",
            })

    if ips_privados:
        score -= 20
        alertas.append({
            "severidade": "Baixo",
            "titulo": f"IP da Rede Local Exposto ({', '.join(ips_privados)})",
            "detalhe": "Sites visitados podem identificar a topologia e a numeração da sua rede local (LAN).",
        })
        recoms.append("No Firefox, configure 'media.peerconnection.ice.default_address_only = true' para omitir IPs locais.")

    if not ips_detectados:
        score = 100
        recoms.append("O WebRTC está devidamente protegido ou desabilitado neste navegador.")

    return {
        "total_ips": len(ips_detectados),
        "ips_privados": ips_privados,
        "ips_publicos": ips_publicos,
        "vazamento_detectado": vazamento,
        "score_privacidade": max(0, min(100, score)),
        "alertas": alertas,
        "recomendacoes": recoms,
    }


class _WebRtcHttpHandler(http.server.BaseHTTPRequestHandler):
    ao_receber_dados: Optional[Callable[[List[str]], None]] = None

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGINA_TESTE_HTML.encode("utf-8"))

    def do_POST(self) -> None:
        if self.path == "/report":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                dados = json.loads(body.decode("utf-8"))
                ips = dados.get("ips", [])
                if self.ao_receber_dados:
                    self.ao_receber_dados(ips)
            except Exception:
                pass
            self.send_response(204)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Silencia logs de requisição no terminal
        pass


def iniciar_servidor_diagnostico(
    ao_concluir: Callable[[List[str]], None],
) -> Tuple[str, http.server.HTTPServer, Callable[[], None]]:
    """Inicia um servidor local efêmero em porta livre para diagnóstico WebRTC."""
    handler = _WebRtcHttpHandler
    handler.ao_receber_dados = ao_concluir

    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    porta = server.server_address[1]
    url = f"http://127.0.0.1:{porta}/"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def _encerrar() -> None:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass

    return url, server, _encerrar


def gerar_relatorio_webrtc(dados: Dict[str, Any]) -> str:
    """Gera laudo técnico da auditoria de WebRTC Leak."""
    linhas: List[str] = [
        "=" * 72,
        "RELATÓRIO DE AUDITORIA — DETECTOR DE VAZAMENTO WEBRTC (LEAK TEST)",
        "=" * 72,
        f"Data da Auditoria     : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Score de Privacidade : {dados['score_privacidade']}/100",
        f"Vazamento Crítico     : {'SIM (DETECTADO)' if dados['vazamento_detectado'] else 'NÃO DETECTADO'}",
        "",
        f"1. ENDEREÇOS IP EXPOSTOS VIA WEBRTC ({dados['total_ips']})",
        f"   IPs Locais (Privados) : {', '.join(dados['ips_privados']) or 'Nenhum'}",
        f"   IPs Públicos          : {', '.join(dados['ips_publicos']) or 'Nenhum'}",
        "",
        f"2. ALERTAS DE PRIVACIDADE ({len(dados['alertas'])})",
    ]
    if not dados["alertas"]:
        linhas.append("   Nenhum IP exposto por candidatos ICE WebRTC. Proteção ativa.")
    else:
        for al in dados["alertas"]:
            linhas.append(f"   [{al['severidade'].upper()}] {al['titulo']}")
            linhas.append(f"     Detalhe: {al['detalhe']}")

    linhas.append("")
    linhas.append(f"3. RECOMENDAÇÕES DE MITIGAÇÃO ({len(dados['recomendacoes'])})")
    for rec in dados["recomendacoes"]:
        linhas.append(f"   - {rec}")

    linhas.append("")
    linhas.append("4. COMO DESATIVAR WEBRTC POR NAVEGADOR")
    linhas.append("   - Mozilla Firefox  : Digite 'about:config' -> media.peerconnection.enabled = false")
    linhas.append("   - Google Chrome    : Instale a extensão oficial 'WebRTC Network Limiter' ou use uBlock Origin")
    linhas.append("   - Microsoft Edge   : Instale a extensão WebRTC Control ou ative proteção avançada de VPN")
    linhas.append("=" * 72)
    return "\n".join(linhas)


"""Lógica pura de auditoria do Gerenciador de Credenciais do Windows (sem Qt).

Lê as credenciais salvas no perfil do usuário atual via Windows Credential Manager
(win32cred.CredEnumerate), calculando métricas de força, detecção de senhas em branco
e reutilização de credenciais por hash SHA-256 anônimo, preservando o sigilo sem
expor segredos em texto claro nos laudos.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import win32cred
except ImportError:
    win32cred = None  # type: ignore[assignment]


TIPOS_CREDENCIAL = {
    1: "Genérica",
    2: "Senha de Domínio",
    3: "Certificado de Domínio",
    4: "Certificado Visível",
}

TIPOS_PERSISTENCIA = {
    1: "Sessão Atual",
    2: "Máquina Local (Permanente)",
    3: "Enterprise (Roaming)",
}


def _analisar_forca_senha(segredo_bytes: bytes) -> Dict[str, Any]:
    """Calcula métricas de complexidade e hash sem expor a senha."""
    if not segredo_bytes:
        return {
            "tamanho": 0,
            "forca": "Vazia",
            "tem_maiuscula": False,
            "tem_numero": False,
            "tem_simbolo": False,
            "hash_anonimo": "",
        }

    try:
        texto = segredo_bytes.decode("utf-8")
        if not texto.isprintable() or "\x00" in texto:
            raise ValueError("Não é texto UTF-8 imprimível")
    except Exception:
        try:
            texto = segredo_bytes.decode("utf-16le", errors="replace").rstrip("\x00")
        except Exception:
            texto = segredo_bytes.decode("latin-1", errors="replace")

    tam = len(texto)
    tem_mai = any(c.isupper() for c in texto)
    tem_min = any(c.islower() for c in texto)
    tem_num = any(c.isdigit() for c in texto)
    tem_sim = any(not c.isalnum() for c in texto)

    # Hash para detectar repetição
    hash_anon = hashlib.sha256(segredo_bytes).hexdigest()[:12]

    pontos = 0
    if tam >= 8:
        pontos += 1
    if tam >= 14:
        pontos += 1
    if tem_mai and tem_min:
        pontos += 1
    if tem_num:
        pontos += 1
    if tem_sim:
        pontos += 1

    if tam == 0:
        forca = "Vazia"
    elif pontos >= 4:
        forca = "Forte"
    elif pontos >= 2:
        forca = "Média"
    else:
        forca = "Fraca"

    return {
        "tamanho": tam,
        "forca": forca,
        "tem_maiuscula": tem_mai,
        "tem_numero": tem_num,
        "tem_simbolo": tem_sim,
        "hash_anonimo": hash_anon,
    }


def coletar_credenciais_locais() -> Dict[str, Any]:
    """Enumera e audita as credenciais do perfil do usuário."""
    if win32cred is None:
        raise RuntimeError("Módulo pywin32 (win32cred) não disponível.")

    try:
        raw_creds = win32cred.CredEnumerate(None, 0)
    except Exception as exc:
        raise RuntimeError(f"Falha ao ler o Gerenciador de Credenciais: {exc}") from exc

    itens: List[Dict[str, Any]] = []
    hashes_vistos: Dict[str, List[str]] = {}

    for c in raw_creds:
        target = str(c.get("TargetName") or "Sem Alvo")
        user = str(c.get("UserName") or "Sem Usuário")
        tipo_id = int(c.get("Type") or 1)
        persist_id = int(c.get("Persist") or 1)
        last_written = c.get("LastWritten")

        data_mod = "Desconhecida"
        if last_written:
            try:
                data_mod = str(last_written)
            except Exception:
                pass

        blob = c.get("CredentialBlob") or b""
        if isinstance(blob, str):
            blob = blob.encode("utf-8")
        elif not isinstance(blob, bytes):
            blob = bytes(blob)

        metadados = _analisar_forca_senha(blob)
        hash_anon = metadados["hash_anonimo"]

        if hash_anon:
            hashes_vistos.setdefault(hash_anon, []).append(target)

        itens.append({
            "alvo": target,
            "usuario": user,
            "tipo": TIPOS_CREDENCIAL.get(tipo_id, f"Tipo {tipo_id}"),
            "persistencia": TIPOS_PERSISTENCIA.get(persist_id, f"Persist {persist_id}"),
            "data_modificacao": data_mod,
            "tamanho_senha": metadados["tamanho"],
            "forca": metadados["forca"],
            "hash_anonimo": hash_anon,
            "reutilizada": False,  # atualizado abaixo
        })

    # Marcar reutilizações
    total_reutilizadas = 0
    for it in itens:
        h = it["hash_anonimo"]
        if h and len(hashes_vistos.get(h, [])) > 1:
            it["reutilizada"] = True
            total_reutilizadas += 1

    # Alertas e Score
    score = 100
    alertas: List[Dict[str, str]] = []

    vazias = [it for it in itens if it["forca"] == "Vazia"]
    if vazias:
        score -= len(vazias) * 10
        alertas.append({
            "severidade": "Crítico",
            "titulo": f"{len(vazias)} Credencial(is) com Senha Vazia",
            "detalhe": f"Alvos: {', '.join(x['alvo'] for x in vazias[:3])}...",
        })

    fracas = [it for it in itens if it["forca"] == "Fraca"]
    if fracas:
        score -= len(fracas) * 5
        alertas.append({
            "severidade": "Médio",
            "titulo": f"{len(fracas)} Credencial(is) com Complexidade Baixa",
            "detalhe": "Senhas com menos de 8 caracteres ou sem variação de tipos de caracteres.",
        })

    if total_reutilizadas > 0:
        score -= min(30, total_reutilizadas * 5)
        alertas.append({
            "severidade": "Alto",
            "titulo": f"{total_reutilizadas} Credencial(is) com Senhas Idênticas Reutilizadas",
            "detalhe": "Mesma senha compartilhada entre múltiplos serviços locais ou de rede.",
        })

    return {
        "total_credenciais": len(itens),
        "itens": itens,
        "score_higiene": max(0, min(100, score)),
        "alertas": alertas,
        "total_vazias": len(vazias),
        "total_fracas": len(fracas),
        "total_reutilizadas": total_reutilizadas,
    }


def gerar_relatorio_credenciais(dados: Dict[str, Any]) -> str:
    """Gera laudo técnico de higiene e auditoria de credenciais."""
    linhas: List[str] = [
        "=" * 72,
        "RELATÓRIO DE AUDITORIA — GERENCIADOR DE CREDENCIAIS DO WINDOWS",
        "=" * 72,
        f"Data da Auditoria        : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Score de Higiene         : {dados['score_higiene']}/100",
        f"Total de Credenciais     : {dados['total_credenciais']}",
        f"Senhas Vazias            : {dados['total_vazias']}",
        f"Senhas Fracas            : {dados['total_fracas']}",
        f"Senhas Reutilizadas      : {dados['total_reutilizadas']}",
        "",
        "1. CREDENCIAIS MAPEADAS (SEGREDO SANITIZADO)",
        "   ALVO                                | USUÁRIO              | TIPO        | FORÇA   | REÚSO",
        "   " + "-" * 78,
    ]
    for it in dados["itens"]:
        alvo = it["alvo"][:35]
        user = it["usuario"][:20]
        tipo = it["tipo"][:11]
        forca = it["forca"][:7]
        reuso = "SIM" if it["reutilizada"] else "NÃO"
        linhas.append(f"   {alvo:<35} | {user:<20} | {tipo:<11} | {forca:<7} | {reuso}")

    linhas.append("")
    linhas.append(f"2. ALERTAS DE HIGIENE ({len(dados['alertas'])})")
    if not dados["alertas"]:
        linhas.append("   Nenhuma inconformidade de complexidade detectada nas credenciais locais.")
    else:
        for al in dados["alertas"]:
            linhas.append(f"   [{al['severidade'].upper()}] {al['titulo']}")
            linhas.append(f"     Detalhe: {al['detalhe']}")

    linhas.append("=" * 72)
    return "\n".join(linhas)

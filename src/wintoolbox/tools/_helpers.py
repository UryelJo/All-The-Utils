"""Auxiliares compartilhados pelas ferramentas de segurança, forense e OSINT.

Concentra validações de dependências opcionais, consentimento ético, elevação de
privilégios e pequenas rotinas de sistema. Nenhuma biblioteca pesada é importada
no topo deste módulo: as importações acontecem dentro das funções que as usam.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from PySide6.QtWidgets import QMessageBox, QWidget

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.logging_setup import get_logger

_log = get_logger("tools.security_common")

_CONSENTIMENTOS: set[str] = set()

TEXTO_ETICO_PADRAO = (
    "Esta ferramenta deve ser usada apenas em sistemas, redes, arquivos e contas "
    "dos quais você é o proprietário legítimo ou possui autorização expressa e "
    "por escrito.\n\n"
    "O uso não autorizado pode configurar crime previsto na Lei 12.737/2012 "
    "(art. 154-A do Código Penal), além de violar a Lei Geral de Proteção de "
    "Dados (Lei 13.709/2018).\n\n"
    "Você confirma que assume integral responsabilidade pelo uso?"
)


class DependenciaAusente(RuntimeError):
    """Erro amigável para dependência opcional não instalada."""

    def __init__(self, recurso: str, modulo: str, pacote: Optional[str] = None) -> None:
        self.recurso = recurso
        self.modulo = modulo
        self.pacote = pacote or modulo
        super().__init__(
            f"Esta ferramenta requer {recurso}. "
            f"Instale com: pip install {self.pacote}"
        )


def require_module(modulo: str, recurso: str, pacote: Optional[str] = None):
    """Importa um módulo opcional e traduz ImportError em mensagem acionável."""
    try:
        return __import__(modulo, fromlist=["*"])
    except ImportError as exc:
        raise DependenciaAusente(recurso, modulo, pacote) from exc


def dependencia_disponivel(modulo: str) -> bool:
    """Verifica se um módulo opcional pode ser importado, sem carregá-lo."""
    import importlib.util

    try:
        return importlib.util.find_spec(modulo) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def confirmar_termo_etico(
    parent: Optional[QWidget],
    tool_id: str,
    texto: Optional[str] = None,
) -> bool:
    """Exibe o termo de responsabilidade uma única vez por ferramenta na sessão."""
    if tool_id in _CONSENTIMENTOS:
        return True

    caixa = QMessageBox(parent)
    caixa.setWindowTitle("Aviso de Uso Responsável")
    caixa.setIcon(QMessageBox.Icon.Warning)
    caixa.setText("Confirmação de uso autorizado")
    caixa.setInformativeText(texto or TEXTO_ETICO_PADRAO)
    btn_concordo = caixa.addButton("Entendo e concordo", QMessageBox.ButtonRole.AcceptRole)
    caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    caixa.setDefaultButton(btn_concordo)
    caixa.exec()
    if caixa.clickedButton() is btn_concordo:
        _CONSENTIMENTOS.add(tool_id)
        return True
    return False


def redefinir_consentimentos() -> None:
    """Limpa os consentimentos da sessão (usado em testes)."""
    _CONSENTIMENTOS.clear()


def garantir_admin(
    parent: Optional[QWidget],
    nome_ferramenta: str,
    permitir_continuar: bool = False,
) -> bool:
    """Verifica privilégios e oferece reinício elevado quando necessário.

    Retorna True quando o usuário pode prosseguir. Quando ``permitir_continuar``
    é True, o usuário pode optar por seguir em modo somente leitura.
    """
    if is_admin():
        return True

    caixa = QMessageBox(parent)
    caixa.setWindowTitle("Privilégios de Administrador")
    caixa.setIcon(QMessageBox.Icon.Warning)
    caixa.setText(f"{nome_ferramenta} requer privilégios elevados.")
    caixa.setInformativeText(
        "Algumas operações de captura, acesso a memória de outros processos ou "
        "leitura de áreas protegidas do sistema exigem Administrador.\n\n"
        "Você pode reiniciar o aplicativo com elevação ou continuar em modo "
        "restrito, quando essa opção estiver disponível."
    )
    btn_reiniciar = caixa.addButton(
        "Reiniciar como Administrador", QMessageBox.ButtonRole.AcceptRole
    )
    if permitir_continuar:
        btn_continuar = caixa.addButton(
            "Continuar em modo restrito", QMessageBox.ButtonRole.ActionRole
        )
    else:
        btn_continuar = None
    caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    caixa.exec()

    clicado = caixa.clickedButton()
    if clicado is btn_reiniciar:
        if request_elevation():
            return False
        QMessageBox.warning(
            parent,
            "Elevação indisponível",
            "Não foi possível solicitar a elevação. Execute o aplicativo como Administrador.",
        )
        return False
    if btn_continuar is not None and clicado is btn_continuar:
        return True
    return False


def aviso_dependencia(parent: Optional[QWidget], exc: Exception) -> None:
    """Mostra uma falha de dependência opcional sem stacktrace cru."""
    QMessageBox.warning(parent, "Dependência necessária", str(exc))


def copiar_texto(texto: str) -> None:
    """Copia texto para a área de transferência na thread principal."""
    from PySide6.QtWidgets import QApplication

    QApplication.clipboard().setText(texto or "")


def formatar_bytes(valor: float) -> str:
    """Formata bytes em unidade legível usando separadores pt-BR."""
    unidades = ["B", "KB", "MB", "GB", "TB", "PB"]
    numero = float(max(0, valor))
    indice = 0
    while numero >= 1024 and indice < len(unidades) - 1:
        numero /= 1024.0
        indice += 1
    texto = f"{numero:.2f}".rstrip("0").rstrip(".")
    return f"{texto} {unidades[indice]}".replace(".", ",")


def formatar_numero(valor: int) -> str:
    """Formata inteiro com ponto como separador de milhar."""
    return f"{int(valor):,}".replace(",", ".")


def truncar(texto: str, limite: int = 120) -> str:
    """Encurta texto preservando o final informativo."""
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def executar_powershell(script: str, timeout: int = 60) -> str:
    """Executa PowerShell sem janela e devolve stdout decodificado.

    O chamador deve usar a partir de uma thread de trabalho (TaskRunner).
    """
    if os.name != "nt":
        raise OSError("Recurso disponível apenas no Windows.")

    comando = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=flags,
    )
    if proc.returncode != 0:
        detalhe = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detalhe[:1000] or f"PowerShell retornou código {proc.returncode}.")
    return proc.stdout


def executar_powershell_json(script: str, timeout: int = 60) -> Any:
    """Executa PowerShell com ConvertTo-Json e devolve objeto Python."""
    saida = executar_powershell(
        "$ErrorActionPreference='Stop'; " + script + " | ConvertTo-Json -Depth 6 -Compress",
        timeout=timeout,
    ).strip()
    if not saida:
        return None
    return json.loads(saida)


def hash_arquivo(caminho: Path, algoritmo: str = "sha256", bloco: int = 1024 * 1024) -> str:
    """Calcula hash de arquivo em streaming."""
    digest = hashlib.new(algoritmo)
    with open(caminho, "rb") as fp:
        for pedaco in iter(lambda: fp.read(bloco), b""):
            digest.update(pedaco)
    return digest.hexdigest()


def base64url_decode(valor: str) -> bytes:
    """Decodifica Base64URL com padding tolerante (JWT)."""
    limpo = str(valor or "").strip().replace("-", "+").replace("_", "/")
    limpo += "=" * (-len(limpo) % 4)
    return base64.b64decode(limpo)


def base64url_encode(dados: bytes) -> str:
    """Codifica bytes em Base64URL sem padding (JWT)."""
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def ler_json(caminho: Path, padrao: Any = None) -> Any:
    """Lê JSON tolerando BOM e erros de codificação."""
    try:
        with open(caminho, "r", encoding="utf-8-sig") as fp:
            return json.load(fp)
    except Exception:
        return padrao


def salvar_texto(parent: Optional[QWidget], conteudo: str, nome_sugerido: str, filtro: str = "Todos os arquivos (*.*)") -> bool:
    """Solicita destino e grava texto em UTF-8. Retorna True quando gravou."""
    from PySide6.QtWidgets import QFileDialog

    destino, _ = QFileDialog.getSaveFileName(parent, "Salvar arquivo", nome_sugerido, filtro)
    if not destino:
        return False
    try:
        Path(destino).write_text(conteudo, encoding="utf-8")
        return True
    except OSError as exc:
        QMessageBox.warning(parent, "Falha ao salvar", f"Não foi possível gravar o arquivo:\n{exc}")
        return False


def extrair_strings(dados: bytes, minimo: int = 4, utf16: bool = True) -> List[Tuple[int, str, str]]:
    """Extrai strings ASCII e UTF-16LE, devolvendo (offset, codificação, texto)."""
    resultados: List[Tuple[int, str, str]] = []
    padrao_ascii = re.compile(rb"[\x20-\x7e]{%d,}" % max(1, minimo))
    for achado in padrao_ascii.finditer(dados):
        texto = achado.group().decode("ascii", errors="ignore")
        resultados.append((achado.start(), "ASCII", texto))

    if utf16:
        padrao_utf16 = re.compile((rb"(?:[\x20-\x7e]\x00){%d,}" % max(1, minimo)))
        for achado in padrao_utf16.finditer(dados):
            texto = achado.group().decode("utf-16le", errors="ignore")
            resultados.append((achado.start(), "UTF-16LE", texto))

    resultados.sort(key=lambda item: item[0])
    return resultados


def ip_local() -> str:
    """Descobre o IP da interface usada para alcançar a internet, sem enviar dados."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def validar_url(url: str, permitir_local: bool = False) -> str:
    """Valida e normaliza uma URL HTTP(S), bloqueando esquemas perigosos."""
    from urllib.parse import urlparse

    texto = str(url or "").strip()
    if not texto:
        raise ValueError("Informe uma URL.")
    if "://" not in texto:
        texto = "https://" + texto
    partes = urlparse(texto)
    if partes.scheme not in {"http", "https"}:
        raise ValueError("Apenas URLs HTTP e HTTPS são aceitas.")
    if not partes.hostname:
        raise ValueError("URL sem host válido.")
    if not permitir_local and partes.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Este recurso não aceita endereços locais.")
    return texto


def chave_servico(nome: str) -> str:
    """Normaliza o identificador de serviço para get_api_token."""
    return re.sub(r"[^a-z0-9_.-]+", "", str(nome or "").lower().strip())


def abrir_no_explorer(caminho: Path) -> None:
    """Abre uma pasta no Explorer (somente Windows)."""
    if not caminho.exists():
        raise FileNotFoundError(f"Caminho não encontrado: {caminho}")
    if os.name == "nt":
        os.startfile(str(caminho))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(caminho)])


def abrir_regedit(chave: str) -> None:
    """Abre o Editor do Registro em uma chave específica."""
    if os.name != "nt":
        raise OSError("Recurso disponível apenas no Windows.")
    subprocess.Popen(["regedit.exe", chave])


def caminhos_unicos(caminhos: Iterable[str]) -> List[str]:
    """Remove duplicatas preservando a ordem."""
    vistos: set[str] = set()
    saida: List[str] = []
    for item in caminhos:
        chave = os.path.normcase(str(item))
        if chave not in vistos:
            vistos.add(chave)
            saida.append(str(item))
    return saida


def contar_linhas(caminho: Path) -> int:
    """Conta linhas de um arquivo de texto de forma tolerante."""
    total = 0
    with open(caminho, "rb") as fp:
        for _ in fp:
            total += 1
    return total


def normalizar_espacos(texto: str) -> str:
    """Colapsa espaços em branco consecutivos."""
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def limitar_lista(itens: List[Dict[str, Any]], limite: int = 5000) -> List[Dict[str, Any]]:
    """Limita resultados para manter a interface responsiva."""
    return itens[: max(0, limite)]

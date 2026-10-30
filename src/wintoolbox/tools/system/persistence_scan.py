"""Varredura defensiva de persistência no Windows.

Audita os principais pontos de inicialização automática do sistema:

* chaves ``Run`` e ``RunOnce`` em ``HKCU``, ``HKLM`` e ``Wow6432Node``;
* serviços configurados para início automático;
* tarefas agendadas habilitadas;
* assinaturas de eventos WMI (``root\\subscription``);
* pastas ``Startup`` do usuário e de todos os usuários;
* ``AppInit_DLLs`` (inclusive no ramo ``Wow6432Node``);
* valores sensíveis do ``Winlogon``;
* entradas de ``Image File Execution Options`` (IFEO).

Para cada item a ferramenta tenta resolver o executável, calcular o hash
SHA-256 e verificar a assinatura Authenticode, destacando caminhos graváveis
pelo usuário, binários não assinados, comandos ofuscados e nomes semelhantes
a binários do sistema (typosquatting).

A varredura é estritamente somente leitura: nada é criado, alterado ou
removido. A execução ocorre fora da thread da interface, por meio do
``TaskRunner`` do projeto.
"""
from __future__ import annotations

import io
import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QWidget,
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.tools._helpers import (
    abrir_no_explorer,
    abrir_regedit,
    executar_powershell,
    formatar_numero,
    hash_arquivo,
    salvar_texto,
    truncar,
)
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    botao_copiar,
    criar_saida_texto,
    criar_tabela,
    executar_assincrono,
    mostrar_erro,
    preencher_tabela,
)

# Limites defensivos para manter a varredura rápida e previsível.
LIMITE_HASH_BYTES = 32 * 1024 * 1024
ORCAMENTO_HASH_SEGUNDOS = 45.0
LIMITE_ITENS_TABELA = 4000

ORDEM_RISCO: Dict[str, int] = {"Informativo": 0, "Baixo": 1, "Médio": 2, "Alto": 3}

# Pastas em que um binário de inicialização é considerado incomum. Um executável
# nesses locais pode ser legítimo, mas merece verificação manual.
PASTAS_SUSPEITAS: Sequence[str] = (
    "\\appdata\\local\\temp\\",
    "\\appdata\\roaming\\",
    "\\appdata\\local\\",
    "\\temp\\",
    "\\tmp\\",
    "\\downloads\\",
    "\\users\\public\\",
    "\\$recycle.bin\\",
    "\\windows\\tasks\\",
    "\\programdata\\",
    "\\recycler\\",
    "\\perflogs\\",
)

EXTENSOES_PE = {".exe", ".dll", ".sys", ".scr", ".com", ".cpl", ".ocx", ".msi", ".drv"}
EXTENSOES_SCRIPT = {".ps1", ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".hta"}
EXTENSOES_ASSINAVEIS = EXTENSOES_PE

# Binários do sistema usados como referência na detecção de typosquatting.
BINARIOS_REFERENCIA: Sequence[str] = (
    "explorer",
    "svchost",
    "lsass",
    "services",
    "winlogon",
    "wininit",
    "csrss",
    "smss",
    "conhost",
    "taskhostw",
    "dwm",
    "spoolsv",
    "rundll32",
    "regsvr32",
    "schtasks",
    "powershell",
    "pwsh",
    "cmd",
    "mshta",
    "wscript",
    "cscript",
    "certutil",
    "bitsadmin",
    "net",
    "sc",
    "reg",
    "atbroker",
    "userinit",
    "logonui",
    "fontdrvhost",
    "securityhealthservice",
    "msmpeng",
)

PADROES_OFUSCACAO: Sequence[str] = (
    "-encodedcommand",
    "-enc ",
    "-enc\"",
    "frombase64string",
    "downloadstring",
    "invoke-expression",
    "iex(",
    "iex ",
    "hidden",
    "-w hidden",
    "bypass",
)

_MAPA_ASSINATURA = {
    "valid": "Válida",
    "notsigned": "Não assinada",
    "hashmismatch": "Inválida (hash divergente)",
    "nottrusted": "Não confiável",
    "unknownerror": "Indeterminada",
    "incompatible": "Formato incompatível",
    "indisponivel": "Indisponível",
}

_SCRIPT_INVENTARIO = r"""
$ProgressPreference = 'SilentlyContinue'
$resultado = @{}
$resultado['run'] = @()
$resultado['servicos'] = @()
$resultado['tarefas'] = @()
$resultado['wmi'] = @()
$resultado['inicio'] = @()
$resultado['appinit'] = @()
$resultado['winlogon'] = @()
$resultado['ifeo'] = @()
$resultado['fontes'] = @()

$chavesRun = @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce',
    'HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run',
    'HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\RunOnce',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunServices',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunServicesOnce'
)
foreach ($chave in $chavesRun) {
    if (-not (Test-Path -LiteralPath $chave)) { continue }
    $item = Get-Item -LiteralPath $chave -ErrorAction SilentlyContinue
    if (-not $item) { continue }
    foreach ($nome in $item.GetValueNames()) {
        if ([string]::IsNullOrWhiteSpace($nome)) { continue }
        $valor = [string]$item.GetValue($nome, '', 'DoNotExpandEnvironmentNames')
        $resultado['run'] += [pscustomobject]@{ nome = $nome; comando = $valor; local = $chave }
    }
}

# Serviços automáticos lidos diretamente do Registro: não depende de WMI/CIM,
# funciona sem privilégios elevados e inclui drivers de início automático.
$estadosServico = @{}
try {
    Get-Service -ErrorAction Stop | ForEach-Object { $estadosServico[[string]$_.Name] = [string]$_.Status }
} catch { }
try {
    $contadorServicos = 0
    foreach ($chave in @(Get-ChildItem -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Services' -ErrorAction Stop)) {
        $item = Get-Item -LiteralPath $chave.PSPath -ErrorAction SilentlyContinue
        if (-not $item) { continue }
        if ([string]$item.GetValue('Start') -ne '2') { continue }
        $nomeServico = [string]$item.PSChildName
        $tipoServico = 0
        try { $tipoServico = [int]$item.GetValue('Type') } catch { $tipoServico = 0 }
        $estadoServico = 'Desconhecido'
        if ($estadosServico.ContainsKey($nomeServico)) { $estadoServico = [string]$estadosServico[$nomeServico] }
        $resultado['servicos'] += [pscustomobject]@{
            nome = $nomeServico
            exibicao = [string]$item.GetValue('DisplayName')
            comando = [string]$item.GetValue('ImagePath', '', 'DoNotExpandEnvironmentNames')
            conta = [string]$item.GetValue('ObjectName')
            estado = $estadoServico
            tipo = $tipoServico
        }
        $contadorServicos++
    }
    $resultado['fontes'] += [pscustomobject]@{ nome = 'Serviços automáticos (Registro)'; ok = $true; erro = ''; total = $contadorServicos }
} catch {
    $resultado['fontes'] += [pscustomobject]@{ nome = 'Serviços automáticos (Registro)'; ok = $false; erro = [string]$_.Exception.Message; total = 0 }
}

$tarefasOk = $false
$erroTarefas = ''
try {
    $tarefas = Get-ScheduledTask -ErrorAction Stop | Where-Object { $_.State -ne 'Disabled' }
    foreach ($t in $tarefas) {
        $acoes = @()
        foreach ($a in @($t.Actions)) {
            $executavel = [string]$a.Execute
            if ([string]::IsNullOrWhiteSpace($executavel)) { continue }
            $acoes += ($executavel + ' ' + ([string]$a.Arguments)).Trim()
        }
        if ($acoes.Count -eq 0) { continue }
        $resultado['tarefas'] += [pscustomobject]@{
            nome = [string]$t.TaskName
            pasta = [string]$t.TaskPath
            estado = [string]$t.State
            comando = ($acoes -join ' | ')
            autor = [string]$t.Author
        }
    }
    $tarefasOk = $true
} catch {
    $erroTarefas = [string]$_.Exception.Message
}

if (-not $tarefasOk) {
    $resultado['tarefas'] = @()
    try {
        $servicoAgenda = New-Object -ComObject Schedule.Service
        $servicoAgenda.Connect()
        $fila = New-Object System.Collections.Queue
        $fila.Enqueue($servicoAgenda.GetFolder('\'))
        $limite = 3000
        while ($fila.Count -gt 0 -and $resultado['tarefas'].Count -lt $limite) {
            $pastaAtual = $fila.Dequeue()
            foreach ($t in @($pastaAtual.GetTasks(1))) {
                $acoes = @()
                foreach ($acao in @($t.Definition.Actions)) {
                    $executavel = [string]$acao.Execute
                    if ([string]::IsNullOrWhiteSpace($executavel)) { continue }
                    $acoes += ($executavel + ' ' + ([string]$acao.Arguments)).Trim()
                }
                if ($acoes.Count -eq 0) { continue }
                $codigoEstado = -1
                try { $codigoEstado = [int]$t.State } catch { $codigoEstado = -1 }
                $estadoTarefa = switch ($codigoEstado) {
                    0 { 'Desconhecido' }
                    1 { 'Desabilitada' }
                    2 { 'Em fila' }
                    3 { 'Pronta' }
                    4 { 'Em execução' }
                    default { [string]$t.State }
                }
                $resultado['tarefas'] += [pscustomobject]@{
                    nome = [string]$t.Name
                    pasta = [string]$pastaAtual.Path
                    estado = $estadoTarefa
                    comando = ($acoes -join ' | ')
                    autor = [string]$t.Definition.RegistrationInfo.Author
                }
            }
            foreach ($sub in @($pastaAtual.GetFolders(0))) { $fila.Enqueue($sub) }
        }
        $tarefasOk = $true
    } catch {
        if ([string]::IsNullOrWhiteSpace($erroTarefas)) { $erroTarefas = [string]$_.Exception.Message }
    }
}

if ($tarefasOk) {
    $resultado['fontes'] += [pscustomobject]@{ nome = 'Tarefas agendadas'; ok = $true; erro = ''; total = $resultado['tarefas'].Count }
} else {
    $resultado['fontes'] += [pscustomobject]@{ nome = 'Tarefas agendadas'; ok = $false; erro = $erroTarefas; total = 0 }
}

$wmiOk = $false
$erroWmi = ''
try {
    foreach ($f in @(Get-CimInstance -Namespace 'root\subscription' -ClassName '__EventFilter' -ErrorAction Stop)) {
        $resultado['wmi'] += [pscustomobject]@{ tipo = 'Filtro de evento'; nome = [string]$f.Name; detalhe = [string]$f.Query }
    }
    foreach ($c in @(Get-CimInstance -Namespace 'root\subscription' -ClassName 'CommandLineEventConsumer' -ErrorAction Stop)) {
        $resultado['wmi'] += [pscustomobject]@{ tipo = 'Consumidor de linha de comando'; nome = [string]$c.Name; detalhe = [string]$c.CommandLineTemplate }
    }
    foreach ($c in @(Get-CimInstance -Namespace 'root\subscription' -ClassName 'ActiveScriptEventConsumer' -ErrorAction Stop)) {
        $resultado['wmi'] += [pscustomobject]@{ tipo = 'Consumidor de script'; nome = [string]$c.Name; detalhe = [string]$c.ScriptText }
    }
    $wmiOk = $true
} catch {
    $erroWmi = [string]$_.Exception.Message
}

if (-not $wmiOk) {
    $resultado['wmi'] = @()
    try {
        foreach ($f in @(Get-WmiObject -Namespace 'root\subscription' -Class '__EventFilter' -ErrorAction Stop)) {
            $resultado['wmi'] += [pscustomobject]@{ tipo = 'Filtro de evento'; nome = [string]$f.Name; detalhe = [string]$f.Query }
        }
        foreach ($c in @(Get-WmiObject -Namespace 'root\subscription' -Class 'CommandLineEventConsumer' -ErrorAction Stop)) {
            $resultado['wmi'] += [pscustomobject]@{ tipo = 'Consumidor de linha de comando'; nome = [string]$c.Name; detalhe = [string]$c.CommandLineTemplate }
        }
        foreach ($c in @(Get-WmiObject -Namespace 'root\subscription' -Class 'ActiveScriptEventConsumer' -ErrorAction Stop)) {
            $resultado['wmi'] += [pscustomobject]@{ tipo = 'Consumidor de script'; nome = [string]$c.Name; detalhe = [string]$c.ScriptText }
        }
        $wmiOk = $true
    } catch {
        if ([string]::IsNullOrWhiteSpace($erroWmi)) { $erroWmi = [string]$_.Exception.Message }
    }
}

if ($wmiOk) {
    $resultado['fontes'] += [pscustomobject]@{ nome = 'Assinaturas WMI'; ok = $true; erro = ''; total = $resultado['wmi'].Count }
} else {
    $resultado['fontes'] += [pscustomobject]@{ nome = 'Assinaturas WMI'; ok = $false; erro = 'Requer privilégios de administrador. ' + $erroWmi; total = 0 }
}

$pastasInicio = @()
try { $pastasInicio += [Environment]::GetFolderPath('Startup') } catch { }
try { $pastasInicio += [Environment]::GetFolderPath('CommonStartup') } catch { }
foreach ($pasta in ($pastasInicio | Where-Object { $_ } | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $pasta)) { continue }
    foreach ($arq in @(Get-ChildItem -LiteralPath $pasta -File -ErrorAction SilentlyContinue)) {
        $resultado['inicio'] += [pscustomobject]@{ nome = [string]$arq.Name; comando = [string]$arq.FullName; local = $pasta }
    }
}

$chavesAppInit = @(
    'HKLM:\Software\Microsoft\Windows NT\CurrentVersion\Windows',
    'HKLM:\Software\Wow6432Node\Microsoft\Windows NT\CurrentVersion\Windows'
)
foreach ($chave in $chavesAppInit) {
    if (-not (Test-Path -LiteralPath $chave)) { continue }
    $item = Get-Item -LiteralPath $chave -ErrorAction SilentlyContinue
    if (-not $item) { continue }
    $dlls = [string]$item.GetValue('AppInit_DLLs')
    $carga = [string]$item.GetValue('LoadAppInit_DLLs')
    foreach ($dll in ($dlls -split '[,;\s]+')) {
        $dll = $dll.Trim()
        if ([string]::IsNullOrWhiteSpace($dll)) { continue }
        $resultado['appinit'] += [pscustomobject]@{ nome = $dll; comando = $dll; local = $chave; carga = $carga }
    }
}

$chaveWinlogon = 'HKLM:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon'
if (Test-Path -LiteralPath $chaveWinlogon) {
    $item = Get-Item -LiteralPath $chaveWinlogon -ErrorAction SilentlyContinue
    if ($item) {
        $valores = @('Shell', 'Userinit', 'Taskman', 'AppSetup', 'GinaDLL', 'VMApplet', 'System', 'UIHost')
        foreach ($nome in $valores) {
            if ($item.GetValueNames() -contains $nome) {
                $resultado['winlogon'] += [pscustomobject]@{
                    nome = $nome
                    comando = [string]$item.GetValue($nome, '', 'DoNotExpandEnvironmentNames')
                    local = $chaveWinlogon
                }
            }
        }
    }
}

$chaveIfeo = 'HKLM:\Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options'
if (Test-Path -LiteralPath $chaveIfeo) {
    foreach ($sub in @(Get-ChildItem -LiteralPath $chaveIfeo -ErrorAction SilentlyContinue)) {
        $item = Get-Item -LiteralPath $sub.PSPath -ErrorAction SilentlyContinue
        if (-not $item) { continue }
        $depurador = [string]$item.GetValue('Debugger')
        $verificador = [string]$item.GetValue('VerifierDlls')
        $flags = [string]$item.GetValue('GlobalFlag')
        if ([string]::IsNullOrWhiteSpace($depurador) -and [string]::IsNullOrWhiteSpace($verificador) -and [string]::IsNullOrWhiteSpace($flags)) {
            continue
        }
        $resultado['ifeo'] += [pscustomobject]@{
            nome = [string]$sub.PSChildName
            depurador = $depurador
            verificador = $verificador
            flags = $flags
            local = [string]$sub.Name
        }
    }
}

$resultado
"""

_SCRIPT_ASSINATURA = r"""
$ProgressPreference = 'SilentlyContinue'
$saida = @()
$alvos = @(__CAMINHOS__)
foreach ($alvo in $alvos) {
    $status = 'Indisponivel'
    $assinante = ''
    try {
        $assinatura = Get-AuthenticodeSignature -LiteralPath $alvo -ErrorAction Stop
        if ($assinatura) {
            $status = [string]$assinatura.Status
            if ($assinatura.SignerCertificate) { $assinante = [string]$assinatura.SignerCertificate.Subject }
        }
    } catch { }
    $saida += [pscustomobject]@{ caminho = $alvo; status = $status; assinante = $assinante }
}
$saida
"""


# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------
def _citar_ps(texto: str) -> str:
    """Converte um texto em literal de string do PowerShell."""
    return "'" + str(texto).replace("'", "''") + "'"


def _powershell_json(script: str, timeout: int = 120) -> Any:
    """Executa PowerShell e devolve o JSON decodificado.

    O resultado é transportado em Base64 para não depender do code page do
    console (o PowerShell 5.1 grava a saída redirecionada na página OEM, o que
    corromperia acentos e nomes de produtos).
    """
    envelope = (
        "$__dados = & { " + script.rstrip() + " } | ConvertTo-Json -Depth 6 -Compress; "
        "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($__dados))"
    )
    saida = executar_powershell(envelope, timeout=timeout).strip()
    if not saida:
        return None
    import base64

    return json.loads(base64.b64decode(saida).decode("utf-8"))


def _como_lista(valor: Any) -> List[Any]:
    """Normaliza a saída do PowerShell para uma lista de dicionários."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return [item for item in valor if isinstance(item, dict)]
    if isinstance(valor, dict):
        return [valor]
    return []


def _resolver_nome_exibicao(texto: str) -> str:
    """Resolve nomes indiretos do Registro (``@arquivo.dll,-123``) via shlwapi."""
    valor = str(texto or "").strip()
    if not valor or not valor.startswith("@") or os.name != "nt":
        return valor
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(512)
        if ctypes.windll.shlwapi.SHLoadIndirectString(valor, buffer, 512, None) == 0:
            return buffer.value
    except (OSError, AttributeError):
        return valor
    return valor


def _logar(ctx: Optional[TaskContext], nivel: str, mensagem: str) -> None:
    """Envia mensagem ao log da tarefa quando houver contexto."""
    if ctx is not None:
        ctx.log(nivel, mensagem)


def _progresso(ctx: Optional[TaskContext], atual: int, mensagem: str) -> None:
    """Atualiza o progresso percentual da tarefa."""
    if ctx is not None:
        ctx.progress(atual, 100, mensagem)


def extrair_caminho_comando(comando: str) -> str:
    """Extrai o caminho do executável de uma linha de comando do Windows.

    Lida com caminhos entre aspas, com argumentos e com sufixos executáveis
    conhecidos. Devolve string vazia quando nada é encontrado.
    """
    texto = str(comando or "").strip()
    if not texto:
        return ""

    # Consumidores WMI podem trazer várias ações separadas por barra vertical.
    texto = texto.split("|")[0].strip()

    if texto.startswith('"'):
        fim = texto.find('"', 1)
        if fim > 1:
            return texto[1:fim]
        return texto[1:]

    baixo = texto.lower()
    for extensao in (".exe", ".dll", ".sys", ".scr", ".com", ".cpl", ".ocx", ".msi",
                     ".ps1", ".bat", ".cmd", ".vbs", ".js", ".hta"):
        indice = baixo.find(extensao)
        if indice >= 0:
            fim = indice + len(extensao)
            return texto[:fim].strip().strip('"')

    return texto.split(" ")[0].strip().strip('"')


def resolver_caminho(caminho: str) -> Optional[Path]:
    """Expande variáveis de ambiente e tenta localizar o arquivo real.

    Nomes relativos (como ``explorer.exe`` no Winlogon) são procurados em
    ``System32``, ``SysWOW64`` e no ``PATH``. Quando nada é encontrado, devolve
    o caminho informado mesmo inexistente, para que o item relate o alvo.
    """
    texto = os.path.expandvars(str(caminho or "").strip().strip('"'))
    if not texto:
        return None

    raiz_windows = os.environ.get("SystemRoot", r"C:\Windows")
    if texto.startswith("\\??\\"):
        texto = texto[4:]
    if texto.lower().startswith("\\systemroot\\"):
        texto = os.path.join(raiz_windows, texto[len("\\systemroot\\"):])
    elif texto.lower().startswith("system32\\"):
        texto = os.path.join(raiz_windows, texto)
    elif texto.startswith("\\") and not texto.startswith("\\\\"):
        texto = os.path.join(raiz_windows, texto.lstrip("\\"))

    candidato = Path(texto)
    if candidato.is_absolute():
        return candidato

    nome = candidato.name
    if not nome:
        return None

    raiz = Path(raiz_windows)
    sufixos = [""]
    if not Path(nome).suffix:
        sufixos = [".exe", ".dll", ""]

    for pasta in (raiz / "System32", raiz / "SysWOW64"):
        for sufixo in sufixos:
            alvo = pasta / (nome + sufixo)
            if alvo.exists():
                return alvo

    for pasta in os.environ.get("PATH", "").split(os.pathsep):
        if not pasta:
            continue
        for sufixo in sufixos:
            alvo = Path(pasta) / (nome + sufixo)
            if alvo.exists():
                return alvo

    return candidato


def distancia_levenshtein(a: str, b: str) -> int:
    """Calcula a distância de edição entre duas cadeias curtas."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        atual = [i]
        for j, cb in enumerate(b, start=1):
            custo = 0 if ca == cb else 1
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + custo))
        anterior = atual
    return anterior[-1]


def detectar_typosquatting(nome_arquivo: str) -> Optional[str]:
    """Detecta nomes muito parecidos com binários do sistema.

    Devolve o nome legítimo imitado ou ``None`` quando nada é semelhante.
    Nomes exatamente iguais não são reportados: apenas imitações.
    """
    base = Path(str(nome_arquivo or "")).stem.lower()
    if len(base) < 4:
        return None
    for referencia in BINARIOS_REFERENCIA:
        if base == referencia:
            return None
        if abs(len(base) - len(referencia)) > 2:
            continue
        if distancia_levenshtein(base, referencia) <= 2:
            return referencia
    return None


def _em_pasta_sistema(caminho: str) -> bool:
    """Indica se o caminho está em uma pasta protegida do Windows."""
    baixo = str(caminho or "").lower()
    raiz = os.environ.get("SystemRoot", r"C:\Windows").lower()
    return (
        baixo.startswith(raiz + "\\system32\\")
        or baixo.startswith(raiz + "\\syswow64\\")
        or baixo.startswith(raiz + "\\winsxs\\")
        or baixo.startswith(raiz + "\\servicing\\")
    )


def _pasta_suspeita(caminho: str) -> bool:
    """Indica se o caminho está em local tipicamente gravável pelo usuário."""
    baixo = "\\" + str(caminho or "").replace("/", "\\").lower().lstrip("\\")
    for trecho in PASTAS_SUSPEITAS:
        if trecho in baixo:
            return True
    return False


def _adicionar_alerta(item: Dict[str, Any], texto: str, risco: str) -> None:
    """Registra um alerta e eleva o risco consolidado do item."""
    alertas = item.setdefault("alertas", [])
    if texto not in alertas:
        alertas.append(texto)
    if ORDEM_RISCO.get(risco, 0) > ORDEM_RISCO.get(str(item.get("risco", "Informativo")), 0):
        item["risco"] = risco


def _normalizar_assinatura(status: str) -> str:
    """Traduz o status do Authenticode para um rótulo em português."""
    chave = str(status or "").strip().lower()
    return _MAPA_ASSINATURA.get(chave, status or "Indisponível")


def _consultar_assinaturas(caminhos: Sequence[str]) -> Dict[str, Dict[str, str]]:
    """Consulta a assinatura Authenticode de vários arquivos em lotes."""
    unicos = [c for c in dict.fromkeys(str(c) for c in caminhos) if c]
    resultado: Dict[str, Dict[str, str]] = {}
    for inicio in range(0, len(unicos), 60):
        lote = unicos[inicio:inicio + 60]
        lista = ", ".join(_citar_ps(caminho) for caminho in lote)
        script = _SCRIPT_ASSINATURA.replace("__CAMINHOS__", lista)
        try:
            dados = _powershell_json(script, timeout=180)
        except Exception:
            continue
        for registro in _como_lista(dados):
            chave = str(registro.get("caminho", ""))
            if chave:
                resultado[chave.lower()] = {
                    "status": _normalizar_assinatura(registro.get("status", "")),
                    "assinante": str(registro.get("assinante", "") or ""),
                }
    return resultado


def _converter_itens(bruto: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Converte o inventário bruto do PowerShell na lista normalizada de itens."""
    itens: List[Dict[str, Any]] = []

    for registro in _como_lista(bruto.get("run")):
        local = str(registro.get("local", ""))
        categoria = "Run (usuário atual)" if local.upper().startswith("HKCU") else "Run (todos os usuários)"
        if "RunOnce" in local:
            categoria = categoria.replace("Run", "RunOnce", 1)
        if "Wow6432Node" in local:
            categoria += " - 32 bits"
        if "\\Policies\\" in local:
            categoria += " - política"
        if "RunServices" in local:
            categoria = "RunServices (legado)"
        itens.append(
            {
                "categoria": categoria,
                "nome": str(registro.get("nome", "") or "(sem nome)"),
                "local": local,
                "comando": str(registro.get("comando", "") or ""),
            }
        )

    for registro in _como_lista(bruto.get("servicos")):
        try:
            tipo = int(registro.get("tipo", 0) or 0)
        except (TypeError, ValueError):
            tipo = 0
        eh_driver = bool(tipo & 0x0F)
        estado = str(registro.get("estado", "") or "")
        exibicao = _resolver_nome_exibicao(str(registro.get("exibicao", "") or ""))
        local = f"Serviço: {exibicao}" if exibicao else "Serviço"
        if estado:
            local += f" ({estado})"
        if eh_driver:
            local += " - driver"
        itens.append(
            {
                "categoria": "Driver automático" if eh_driver else "Serviço automático",
                "nome": str(registro.get("nome", "") or ""),
                "local": local,
                "comando": str(registro.get("comando", "") or ""),
                "conta": str(registro.get("conta", "") or ""),
                "estado": estado,
            }
        )

    for registro in _como_lista(bruto.get("tarefas")):
        pasta = str(registro.get("pasta", "") or "\\")
        autor = str(registro.get("autor", "") or "")
        itens.append(
            {
                "categoria": "Tarefa agendada",
                "nome": str(registro.get("nome", "") or ""),
                "local": pasta if not autor else f"{pasta} (autor: {autor})",
                "comando": str(registro.get("comando", "") or ""),
                "estado": str(registro.get("estado", "") or ""),
            }
        )

    for registro in _como_lista(bruto.get("wmi")):
        itens.append(
            {
                "categoria": "Assinatura WMI",
                "nome": f"{registro.get('tipo', 'Assinatura')}: {registro.get('nome', '')}",
                "local": "root\\subscription",
                "comando": truncar(str(registro.get("detalhe", "") or ""), 400),
            }
        )

    for registro in _como_lista(bruto.get("inicio")):
        local = str(registro.get("local", "") or "")
        categoria = "Pasta Startup (todos os usuários)" if "ProgramData" in local else "Pasta Startup (usuário)"
        itens.append(
            {
                "categoria": categoria,
                "nome": str(registro.get("nome", "") or ""),
                "local": local,
                "comando": str(registro.get("comando", "") or ""),
            }
        )

    for registro in _como_lista(bruto.get("appinit")):
        carga = str(registro.get("carga", "") or "0").strip()
        itens.append(
            {
                "categoria": "AppInit_DLLs",
                "nome": str(registro.get("nome", "") or ""),
                "local": str(registro.get("local", "") or "") + f" (LoadAppInit_DLLs={carga})",
                "comando": str(registro.get("comando", "") or ""),
            }
        )

    for registro in _como_lista(bruto.get("winlogon")):
        itens.append(
            {
                "categoria": "Winlogon",
                "nome": str(registro.get("nome", "") or ""),
                "local": str(registro.get("local", "") or ""),
                "comando": str(registro.get("comando", "") or ""),
            }
        )

    for registro in _como_lista(bruto.get("ifeo")):
        depurador = str(registro.get("depurador", "") or "")
        verificador = str(registro.get("verificador", "") or "")
        flags = str(registro.get("flags", "") or "")
        comando = depurador or verificador
        itens.append(
            {
                "categoria": "IFEO",
                "nome": str(registro.get("nome", "") or ""),
                "local": str(registro.get("local", "") or ""),
                "comando": comando,
                "detalhe": "VerifierDlls=" + verificador if verificador else "",
                "flags": flags,
            }
        )

    return itens


def _resolver_arquivos(itens: List[Dict[str, Any]], ctx: Optional[TaskContext]) -> None:
    """Resolve o caminho, o tamanho e o hash SHA-256 de cada item."""
    inicio = time.monotonic()
    total = max(1, len(itens))
    hashes_restantes = True

    for indice, item in enumerate(itens, start=1):
        comando = str(item.get("comando", "") or "")
        caminho_texto = extrair_caminho_comando(comando)
        caminho = resolver_caminho(caminho_texto) if caminho_texto else None

        item["caminho"] = str(caminho) if caminho else ""
        item["existe"] = False
        item["tamanho"] = 0
        item["hash_sha256"] = ""
        item["assinatura"] = "Não verificada"
        item["assinante"] = ""

        if caminho is not None and caminho.exists() and caminho.is_file():
            item["existe"] = True
            try:
                item["tamanho"] = caminho.stat().st_size
            except OSError:
                item["tamanho"] = 0

            if hashes_restantes:
                gasto = time.monotonic() - inicio
                if gasto > ORCAMENTO_HASH_SEGUNDOS:
                    hashes_restantes = False
                    item["hash_sha256"] = "não calculado (limite de tempo)"
                elif item["tamanho"] > LIMITE_HASH_BYTES:
                    item["hash_sha256"] = "não calculado (arquivo grande)"
                else:
                    try:
                        item["hash_sha256"] = hash_arquivo(caminho)
                    except OSError:
                        item["hash_sha256"] = "não calculado (acesso negado)"

        if indice % 25 == 0 or indice == total:
            _progresso(ctx, 20 + int(35 * indice / total), f"Analisando arquivos: {indice} de {total}...")


def _aplicar_assinaturas(itens: List[Dict[str, Any]], ctx: Optional[TaskContext]) -> None:
    """Consulta a assinatura Authenticode dos arquivos existentes e assináveis."""
    alvos = [
        item["caminho"]
        for item in itens
        if item.get("existe")
        and Path(str(item.get("caminho", ""))).suffix.lower() in EXTENSOES_ASSINAVEIS
    ]
    if not alvos:
        return

    _progresso(ctx, 60, f"Consultando assinaturas de {len(set(alvos))} arquivo(s)...")
    assinaturas = _consultar_assinaturas(alvos)
    for item in itens:
        chave = str(item.get("caminho", "")).lower()
        registro = assinaturas.get(chave)
        if registro:
            item["assinatura"] = registro["status"]
            item["assinante"] = registro["assinante"]


def _avaliar_item(item: Dict[str, Any]) -> None:
    """Aplica as heurísticas de risco e consolida o nível de cada item."""
    alertas: List[str] = []
    item["alertas"] = alertas
    item["risco"] = "Informativo"

    categoria = str(item.get("categoria", ""))
    comando = str(item.get("comando", "") or "")
    caminho = str(item.get("caminho", "") or "")
    assinatura = str(item.get("assinatura", ""))
    existe = bool(item.get("existe"))
    sufixo = Path(caminho).suffix.lower() if caminho else ""

    # Regras específicas por categoria.
    if categoria == "Assinatura WMI":
        _adicionar_alerta(
            item,
            "Assinatura de evento WMI ativa: mecanismo clássico de persistência silenciosa",
            "Alto",
        )

    if categoria == "IFEO":
        _adicionar_alerta(
            item,
            "Chave IFEO configurada: pode desviar a execução de um binário legítimo",
            "Alto",
        )

    if categoria.startswith("Run") and "\\Policies\\" in str(item.get("local", "")):
        _adicionar_alerta(item, "Chave Run em ramo de políticas do sistema", "Médio")

    if categoria == "AppInit_DLLs":
        if "LoadAppInit_DLLs=1" in str(item.get("local", "")):
            _adicionar_alerta(
                item,
                "AppInit_DLLs habilitado: qualquer DLL listada é injetada em todos os processos",
                "Alto",
            )
        else:
            _adicionar_alerta(item, "AppInit_DLLs presente, porém desabilitado", "Baixo")

    if categoria == "Winlogon":
        nome = str(item.get("nome", "")).lower()
        valor = comando.strip().strip(",").lower()
        padrao_ok = False
        if nome == "shell" and valor in ("explorer.exe", ""):
            padrao_ok = True
        elif nome == "userinit" and valor.endswith("userinit.exe"):
            padrao_ok = True
        elif nome in ("vmapplet",) and not valor:
            padrao_ok = True
        if nome in ("shell", "userinit") and not padrao_ok:
            _adicionar_alerta(
                item,
                "Valor do Winlogon diferente do padrão do Windows",
                "Alto",
            )
        elif nome in ("taskman", "appsetup", "ginadll") and valor:
            _adicionar_alerta(item, f"Valor legado '{nome}' definido no Winlogon", "Médio")

    # Caminho em local gravável pelo usuário.
    if caminho and _pasta_suspeita(caminho):
        _adicionar_alerta(
            item,
            "Executável em pasta gravável pelo usuário (TEMP, AppData, Downloads ou ProgramData)",
            "Alto",
        )

    # Caminho de rede.
    if comando.strip().startswith("\\\\") or caminho.startswith("\\\\"):
        _adicionar_alerta(item, "Execução a partir de caminho de rede (UNC)", "Médio")

    # Assinatura digital.
    if existe and sufixo in EXTENSOES_ASSINAVEIS:
        if assinatura in ("Inválida (hash divergente)", "Não confiável"):
            _adicionar_alerta(item, f"Assinatura digital {assinatura.lower()}", "Alto")
        elif assinatura == "Não assinada":
            if not _em_pasta_sistema(caminho):
                _adicionar_alerta(item, "Binário não assinado fora das pastas do sistema", "Alto")
            else:
                _adicionar_alerta(item, "Binário do sistema sem assinatura verificável", "Médio")
        elif assinatura in ("Indisponível", "Indeterminada", "Formato incompatível"):
            _adicionar_alerta(item, f"Assinatura {assinatura.lower()} (verifique manualmente)", "Baixo")

    # Scripts interpretados.
    if sufixo in EXTENSOES_SCRIPT:
        _adicionar_alerta(item, "Inicialização por script interpretado", "Médio")

    # Ofuscação na linha de comando.
    baixo = comando.lower()
    for padrao in PADROES_OFUSCACAO:
        if padrao in baixo:
            _adicionar_alerta(item, "Linha de comando com indício de execução ofuscada", "Alto")
            break

    # Typosquatting apenas fora das pastas do sistema, para reduzir falsos positivos.
    if caminho and not _em_pasta_sistema(caminho):
        imitado = detectar_typosquatting(Path(caminho).name)
        if imitado:
            _adicionar_alerta(
                item,
                f"Nome semelhante ao binário do sistema '{imitado}.exe' (possível typosquatting)",
                "Alto",
            )

    # Arquivo ausente.
    if caminho and not existe:
        _adicionar_alerta(item, "Arquivo referenciado não existe no disco", "Médio")

    # Item sem caminho resolvido.
    if not caminho and comando:
        _adicionar_alerta(item, "Não foi possível determinar o executável do item", "Baixo")

    # Serviço ou driver automático fora das pastas do sistema.
    if categoria in ("Serviço automático", "Driver automático") and caminho and not _em_pasta_sistema(caminho):
        rotulo = "Driver automático" if categoria == "Driver automático" else "Serviço automático"
        _adicionar_alerta(item, f"{rotulo} fora das pastas do sistema", "Médio")


def coletar_persistencia(ctx: Optional[TaskContext] = None) -> Dict[str, Any]:
    """Executa a varredura completa e devolve o inventário avaliado.

    Pode ser chamada a partir de uma thread de trabalho; não toca em widgets.
    """
    if os.name != "nt":
        raise RuntimeError("A varredura de persistência está disponível apenas no Windows.")

    inicio = time.monotonic()
    _progresso(ctx, 5, "Consultando Registro, serviços, tarefas agendadas e WMI...")
    _logar(ctx, "INFO", "Iniciando inventário dos pontos de persistência.")

    bruto = _powershell_json(_SCRIPT_INVENTARIO, timeout=240) or {}
    itens = _converter_itens(bruto)
    _logar(ctx, "INFO", f"{len(itens)} ponto(s) de persistência encontrados no inventário bruto.")

    fontes: List[Dict[str, Any]] = []
    for fonte in _como_lista(bruto.get("fontes")):
        registro = {
            "nome": str(fonte.get("nome", "") or ""),
            "ok": bool(fonte.get("ok", False)),
            "erro": str(fonte.get("erro", "") or ""),
            "total": int(fonte.get("total", 0) or 0),
        }
        fontes.append(registro)
        if not registro["ok"]:
            _logar(ctx, "AVISO", f"Fonte indisponível: {registro['nome']} - {registro['erro']}")

    _progresso(ctx, 20, "Resolvendo executáveis e calculando hashes SHA-256...")
    _resolver_arquivos(itens, ctx)

    _aplicar_assinaturas(itens, ctx)

    _progresso(ctx, 80, "Aplicando heurísticas de risco...")
    for item in itens:
        _avaliar_item(item)

    itens.sort(key=lambda registro: (-ORDEM_RISCO.get(str(registro.get("risco")), 0), str(registro.get("categoria")), str(registro.get("nome"))))
    itens = itens[:LIMITE_ITENS_TABELA]

    por_risco: Dict[str, int] = {"Alto": 0, "Médio": 0, "Baixo": 0, "Informativo": 0}
    por_categoria: Dict[str, int] = {}
    for item in itens:
        risco = str(item.get("risco", "Informativo"))
        por_risco[risco] = por_risco.get(risco, 0) + 1
        chave = str(item.get("categoria", "Outros"))
        por_categoria[chave] = por_categoria.get(chave, 0) + 1

    duracao = time.monotonic() - inicio
    _progresso(ctx, 100, f"Varredura concluída em {duracao:.1f} s.")
    _logar(
        ctx,
        "INFO",
        f"Concluído: {len(itens)} item(ns), {por_risco['Alto']} de risco alto, "
        f"{por_risco['Médio']} de risco médio.",
    )

    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "duracao_s": round(duracao, 2),
        "total": len(itens),
        "alertas": por_risco["Alto"] + por_risco["Médio"],
        "por_risco": por_risco,
        "por_categoria": por_categoria,
        "fontes": fontes,
        "itens": itens,
    }


# ---------------------------------------------------------------------------
# Relatórios e exportação
# ---------------------------------------------------------------------------
def gerar_relatorio_texto(dados: Dict[str, Any]) -> str:
    """Monta o relatório textual legível da varredura."""
    linhas: List[str] = [
        "RELATÓRIO DE PERSISTÊNCIA DO WINDOWS",
        "=" * 60,
        f"Gerado em: {dados.get('gerado_em', '')}",
        f"Duração: {dados.get('duracao_s', 0)} s",
        f"Itens analisados: {formatar_numero(int(dados.get('total', 0)))}",
        "",
        "Distribuição por risco:",
    ]
    por_risco = dados.get("por_risco", {}) or {}
    for risco in ("Alto", "Médio", "Baixo", "Informativo"):
        linhas.append(f"  {risco}: {por_risco.get(risco, 0)}")

    linhas.append("")
    linhas.append("Distribuição por categoria:")
    for categoria, quantidade in sorted((dados.get("por_categoria", {}) or {}).items()):
        linhas.append(f"  {categoria}: {quantidade}")

    indisponiveis = [fonte for fonte in (dados.get("fontes", []) or []) if not fonte.get("ok")]
    if indisponiveis:
        linhas.append("")
        linhas.append("Fontes indisponíveis nesta execução:")
        for fonte in indisponiveis:
            motivo = fonte.get("erro") or "motivo desconhecido"
            linhas.append(f"  {fonte.get('nome')}: {motivo}")

    linhas.append("")
    linhas.append("Itens com alerta:")
    linhas.append("-" * 60)

    itens = [item for item in dados.get("itens", []) if item.get("alertas")]
    if not itens:
        linhas.append("Nenhum alerta encontrado nesta varredura.")
    for item in itens:
        linhas.append(f"[{item.get('risco')}] {item.get('categoria')} - {item.get('nome')}")
        linhas.append(f"  Local: {item.get('local', '')}")
        if item.get("comando"):
            linhas.append(f"  Comando: {truncar(str(item.get('comando')), 300)}")
        if item.get("caminho"):
            linhas.append(f"  Caminho: {item.get('caminho')}")
        if item.get("hash_sha256"):
            linhas.append(f"  SHA-256: {item.get('hash_sha256')}")
        if item.get("assinatura"):
            assinante = item.get("assinante") or "sem assinante"
            linhas.append(f"  Assinatura: {item.get('assinatura')} ({truncar(assinante, 120)})")
        for alerta in item.get("alertas", []):
            linhas.append(f"  Alerta: {alerta}")
        linhas.append("")

    return "\n".join(linhas).rstrip() + "\n"


def gerar_json(dados: Dict[str, Any]) -> str:
    """Serializa o resultado completo em JSON UTF-8."""
    return json.dumps(dados, ensure_ascii=False, indent=2)


def gerar_csv(dados: Dict[str, Any]) -> str:
    """Serializa os itens em CSV com ponto e vírgula (compatível com Excel pt-BR)."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    escritor.writerow(
        [
            "Categoria",
            "Item",
            "Local",
            "Comando",
            "Caminho",
            "Existe",
            "Tamanho (bytes)",
            "SHA-256",
            "Assinatura",
            "Assinante",
            "Risco",
            "Alertas",
        ]
    )
    for item in dados.get("itens", []):
        escritor.writerow(
            [
                item.get("categoria", ""),
                item.get("nome", ""),
                item.get("local", ""),
                item.get("comando", ""),
                item.get("caminho", ""),
                "Sim" if item.get("existe") else "Não",
                item.get("tamanho", 0),
                item.get("hash_sha256", ""),
                item.get("assinatura", ""),
                item.get("assinante", ""),
                item.get("risco", ""),
                " | ".join(item.get("alertas", [])),
            ]
        )
    return "\ufeff" + buffer.getvalue()


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
@register
class PersistenceScanTool(Tool):
    """Ferramenta de auditoria dos pontos de inicialização automática."""

    id = "system.persistence_scan"
    name = "Varredura de Persistência"
    category = "Sistema"
    description = (
        "Auditoria somente leitura dos pontos de inicialização do Windows (Run/RunOnce, "
        "serviços, tarefas agendadas, WMI, Startup, AppInit_DLLs, Winlogon e IFEO) com "
        "hash SHA-256, assinatura digital e alertas de caminho suspeito"
    )
    keywords = [
        "persistência",
        "persistencia",
        "run",
        "runonce",
        "startup",
        "inicialização",
        "inicializacao",
        "serviços",
        "servicos",
        "tarefas agendadas",
        "wmi",
        "appinit",
        "winlogon",
        "ifeo",
        "typosquatting",
        "autorun",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return PersistenceScanPanel(self, parent)


class PersistenceScanPanel(PainelFerramenta):
    """Tela de varredura, filtragem e exportação do inventário de persistência."""

    COLUNAS = ["Categoria", "Item", "Risco", "Assinatura", "Caminho", "Primeiro alerta"]

    def __init__(self, tool: PersistenceScanTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._dados: Dict[str, Any] = {}
        self._itens_visiveis: List[Dict[str, Any]] = []
        self._construir_interface()

    # -- construção ---------------------------------------------------------
    def _construir_interface(self) -> None:
        """Monta cartões, tabela, saída textual e log."""
        self.adicionar_aviso(
            "Esta auditoria é somente leitura: nenhum item é criado, alterado ou removido. "
            "Os resultados indicam pontos que merecem verificação manual, não uma conclusão "
            "definitiva de infecção.",
            destaque=True,
        )

        _, layout_controles = self.adicionar_card("Execução")
        linha = QHBoxLayout()
        linha.setSpacing(8)

        self.btn_executar = QPushButton("Executar varredura")
        self.btn_executar.setProperty("class", "primary")
        self.btn_executar.clicked.connect(self._executar)
        linha.addWidget(self.btn_executar)

        linha.addWidget(QLabel("Filtro:"))
        self.cmb_filtro = QComboBox()
        self.cmb_filtro.addItem("Todos os itens", "todos")
        self.cmb_filtro.addItem("Somente com alerta", "alerta")
        self.cmb_filtro.addItem("Somente risco alto", "alto")
        self.cmb_filtro.currentIndexChanged.connect(self._aplicar_filtro)
        linha.addWidget(self.cmb_filtro)

        self.btn_regedit = QPushButton("Abrir Regedit em Run (HKCU)")
        self.btn_regedit.clicked.connect(self._abrir_regedit)
        linha.addWidget(self.btn_regedit)

        self.btn_startup = QPushButton("Abrir pasta Startup")
        self.btn_startup.clicked.connect(self._abrir_startup)
        linha.addWidget(self.btn_startup)

        linha.addStretch(1)
        self.btn_copiar = botao_copiar(lambda: self.saida.toPlainText(), self, "Copiar relatório")
        linha.addWidget(self.btn_copiar)
        layout_controles.addLayout(linha)

        self.lbl_status = QLabel("Pronto. Clique em Executar varredura para iniciar a auditoria.")
        self.lbl_status.setProperty("class", "secondary")
        self.lbl_status.setWordWrap(True)
        layout_controles.addWidget(self.lbl_status)

        _, layout_tabela = self.adicionar_card("Itens de inicialização encontrados")
        self.tabela: QTableWidget = criar_tabela(self.COLUNAS, self)
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(4, QHeaderView.Stretch)
        cabecalho.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.tabela.setMinimumHeight(280)
        self.tabela.itemSelectionChanged.connect(self._mostrar_detalhe)
        layout_tabela.addWidget(self.tabela)

        linha_exportar = QHBoxLayout()
        self.btn_json = QPushButton("Exportar JSON...")
        self.btn_json.setEnabled(False)
        self.btn_json.clicked.connect(lambda: self._exportar("json"))
        linha_exportar.addWidget(self.btn_json)

        self.btn_csv = QPushButton("Exportar CSV...")
        self.btn_csv.setEnabled(False)
        self.btn_csv.clicked.connect(lambda: self._exportar("csv"))
        linha_exportar.addWidget(self.btn_csv)

        self.btn_abrir_local = QPushButton("Abrir pasta do item selecionado")
        self.btn_abrir_local.clicked.connect(self._abrir_pasta_item)
        linha_exportar.addWidget(self.btn_abrir_local)
        linha_exportar.addStretch(1)
        layout_tabela.addLayout(linha_exportar)

        _, layout_saida = self.adicionar_card("Detalhes do item selecionado")
        self.saida = criar_saida_texto(170, self)
        self.saida.setPlainText(
            "Selecione um item da tabela para ver comando, hash, assinatura e alertas."
        )
        layout_saida.addWidget(self.saida)

        self._log = adicionar_log_painel(self, "Log da varredura de persistência")
        self.adicionar_espaco()

    # -- ações --------------------------------------------------------------
    def _executar(self) -> None:
        """Dispara a varredura assíncrona e atualiza a interface ao concluir."""
        self.btn_executar.setEnabled(False)
        self.btn_json.setEnabled(False)
        self.btn_csv.setEnabled(False)
        self.lbl_status.setText("Varredura em andamento. Isso pode levar alguns minutos...")
        self._log.clear()
        self.saida.setPlainText("Varredura em andamento...")

        def tarefa(ctx: TaskContext) -> Dict[str, Any]:
            return coletar_persistencia(ctx)

        def concluiu(dados: Any) -> None:
            self.btn_executar.setEnabled(True)
            if not isinstance(dados, dict):
                self.lbl_status.setText("A varredura não devolveu dados.")
                return
            self._dados = dados
            self._log.append_log(
                "SUCESSO",
                f"Varredura concluída: {dados.get('total', 0)} item(ns) analisado(s).",
            )
            self._preencher()
            self.btn_json.setEnabled(True)
            self.btn_csv.setEnabled(bool(dados.get("itens")))
            por_risco = dados.get("por_risco", {}) or {}
            self.lbl_status.setText(
                f"Concluído em {dados.get('duracao_s', 0)} s. "
                f"{dados.get('total', 0)} item(ns), "
                f"{por_risco.get('Alto', 0)} de risco alto e "
                f"{por_risco.get('Médio', 0)} de risco médio."
            )

        def falhou(erro: Exception) -> None:
            self.btn_executar.setEnabled(True)
            self.lbl_status.setText("A varredura falhou. Consulte o log de execução.")
            self.saida.setPlainText(f"Falha na varredura: {erro}")
            self._log.append_log("ERRO", str(erro))
            mostrar_erro(self, "Falha na varredura de persistência", erro)

        def progrediu(atual: int, total: int, mensagem: str) -> None:
            if mensagem:
                self.lbl_status.setText(mensagem)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_progredir=progrediu,
            ao_logar=self._log.append_log,
        )

    def _preencher(self) -> None:
        """Recria a tabela conforme o filtro atual."""
        self._aplicar_filtro()

    def _aplicar_filtro(self) -> None:
        """Filtra os itens exibidos na tabela."""
        itens = list(self._dados.get("itens", []))
        modo = self.cmb_filtro.currentData()
        if modo == "alerta":
            itens = [item for item in itens if item.get("alertas")]
        elif modo == "alto":
            itens = [item for item in itens if item.get("risco") == "Alto"]

        self._itens_visiveis = itens
        linhas = [
            [
                item.get("categoria", ""),
                item.get("nome", ""),
                item.get("risco", ""),
                item.get("assinatura", ""),
                item.get("caminho", ""),
                (item.get("alertas") or [""])[0] if item.get("alertas") else "",
            ]
            for item in itens
        ]
        preencher_tabela(self.tabela, linhas)

    def _item_selecionado(self) -> Optional[Dict[str, Any]]:
        """Devolve o item selecionado na tabela, se houver."""
        linha = self.tabela.currentRow()
        if 0 <= linha < len(self._itens_visiveis):
            return self._itens_visiveis[linha]
        return None

    def _mostrar_detalhe(self) -> None:
        """Exibe o detalhe completo do item selecionado na área de texto."""
        item = self._item_selecionado()
        if not item:
            return
        linhas = [
            f"Categoria: {item.get('categoria', '')}",
            f"Item: {item.get('nome', '')}",
            f"Risco: {item.get('risco', '')}",
            f"Local: {item.get('local', '')}",
            f"Comando: {item.get('comando', '')}",
            f"Caminho resolvido: {item.get('caminho') or '(não identificado)'}",
            f"Arquivo existe: {'sim' if item.get('existe') else 'não'}",
            f"Tamanho: {formatar_numero(int(item.get('tamanho', 0) or 0))} bytes",
            f"SHA-256: {item.get('hash_sha256') or '(não calculado)'}",
            f"Assinatura: {item.get('assinatura', '')}",
            f"Assinante: {item.get('assinante') or '(sem assinante)'}",
            "",
            "Alertas:",
        ]
        alertas = item.get("alertas") or []
        if alertas:
            linhas.extend(f"  - {alerta}" for alerta in alertas)
        else:
            linhas.append("  Nenhum alerta para este item.")
        self.saida.setPlainText("\n".join(linhas))

    def _exportar(self, formato: str) -> None:
        """Solicita o destino e grava o relatório em JSON ou CSV."""
        if not self._dados:
            return
        if formato == "json":
            conteudo = gerar_json(self._dados)
            sugestao = "varredura_persistencia.json"
            filtro = "Arquivo JSON (*.json);;Todos os arquivos (*.*)"
        else:
            conteudo = gerar_csv(self._dados)
            sugestao = "varredura_persistencia.csv"
            filtro = "Arquivo CSV (*.csv);;Todos os arquivos (*.*)"

        if salvar_texto(self, conteudo, sugestao, filtro):
            self._log.append_log("SUCESSO", f"Relatório exportado em formato {formato.upper()}.")

    def _abrir_regedit(self) -> None:
        """Abre o Editor do Registro na chave Run do usuário atual."""
        try:
            abrir_regedit(r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run")
            self._log.append_log("INFO", "Editor do Registro aberto na chave Run do usuário.")
        except Exception as exc:
            mostrar_erro(self, "Não foi possível abrir o Regedit", exc)

    def _abrir_startup(self) -> None:
        """Abre no Explorer a pasta Startup do usuário atual."""
        pasta = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        try:
            if not pasta.exists():
                raise FileNotFoundError(f"Pasta Startup não encontrada: {pasta}")
            abrir_no_explorer(pasta)
            self._log.append_log("INFO", f"Pasta Startup aberta: {pasta}")
        except Exception as exc:
            mostrar_erro(self, "Não foi possível abrir a pasta Startup", exc)

    def _abrir_pasta_item(self) -> None:
        """Abre no Explorer a pasta do executável do item selecionado."""
        item = self._item_selecionado()
        if not item:
            self.lbl_status.setText("Selecione um item na tabela para abrir a pasta.")
            return
        caminho = str(item.get("caminho", "") or "")
        if not caminho:
            self.lbl_status.setText("O item selecionado não possui caminho resolvido.")
            return
        pasta = Path(caminho).parent
        try:
            abrir_no_explorer(pasta)
            self._log.append_log("INFO", f"Pasta aberta: {pasta}")
        except Exception as exc:
            mostrar_erro(self, "Não foi possível abrir a pasta", exc)

"""Histórico de dispositivos USB do Windows, somente leitura.

A coleta combina duas fontes nativas:

* ``HKLM\\SYSTEM\\CurrentControlSet\\Enum\\USBSTOR`` e ``...\\Enum\\USB`` para
  fabricante, produto, número de série, nome amigável e propriedades de data do
  dispositivo;
* ``C:\\Windows\\INF\\setupapi.dev.log`` para eventos de instalação e conexão com
  carimbo de data e hora.

A leitura do Registro funciona sem Administrador na maioria das instalações.
Chaves protegidas podem negar acesso e são reportadas como aviso, sem inventar
dispositivos ou datas.
"""
from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.tools._helpers import dependencia_disponivel, formatar_numero
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    botao_copiar,
    criar_aviso,
    criar_saida_texto,
    criar_tabela,
    executar_assincrono,
    mostrar_erro,
    preencher_tabela,
)

_log = get_logger("forensics.usb_history")

_GUID_PROPRIEDADES_DISPOSITIVO = "{83da6326-97a6-4088-9453-a1923f573b29}"

# Identificadores de propriedades de data documentados para dispositivos.
_PROPRIEDADES_DATA = {
    "0064": "data de instalação",
    "0065": "primeira instalação",
    "0066": "última chegada",
    "0067": "última remoção",
}


@dataclass
class DispositivoUSB:
    """Dispositivo USB identificado por uma fonte de evidência."""

    origem: str
    instancia: str
    fornecedor: str = ""
    produto: str = ""
    serial: str = ""
    nome: str = ""
    servico: str = ""
    classe: str = ""
    primeira_instalacao: str = ""
    ultima_conexao: str = ""
    evidencia: str = ""


@dataclass
class RegistroSetupApi:
    """Evento extraído do log de instalação de dispositivos."""

    instancia: str
    evento: str
    data: str


@dataclass
class ResultadoUSB:
    """Resultado consolidado da coleta de histórico USB."""

    dispositivos: List[DispositivoUSB] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)


def _winreg():
    """Importa winreg apenas quando necessário."""
    import winreg  # importação tardia

    return winreg


def _filetime_para_iso(valor: int) -> str:
    """Converte FILETIME em data ISO local."""
    if not valor:
        return ""
    try:
        segundos = (int(valor) - 116444736000000000) / 10_000_000
        return datetime.fromtimestamp(segundos, tz=timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _formatar_data_texto(texto: str) -> str:
    """Normaliza datas do setupapi.dev.log para ISO local."""
    texto = str(texto or "").strip()
    if not texto:
        return ""
    for formato in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(texto, formato).astimezone().isoformat(
                timespec="seconds"
            )
        except ValueError:
            continue
    return texto


def _ler_valores(handle: Any) -> Dict[str, Any]:
    """Lê todos os valores de uma chave do Registro."""
    winreg = _winreg()
    valores: Dict[str, Any] = {}
    indice = 0
    while True:
        try:
            nome, dado, _tipo = winreg.EnumValue(handle, indice)
        except OSError:
            break
        valores[str(nome)] = dado
        indice += 1
        if indice > 2000:
            break
    return valores


def _ler_subchaves(handle: Any) -> List[str]:
    """Lista as subchaves imediatas de uma chave do Registro."""
    winreg = _winreg()
    nomes: List[str] = []
    indice = 0
    while True:
        try:
            nomes.append(winreg.EnumKey(handle, indice))
        except OSError:
            break
        indice += 1
        if indice > 2000:
            break
    return nomes


def _abrir_chave(caminho: str) -> Any:
    """Abre uma chave de HKLM para leitura, sem qualquer permissão de escrita."""
    winreg = _winreg()
    return winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        caminho,
        0,
        winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
    )


def _texto(valor: Any) -> str:
    """Converte valores do Registro em texto legível."""
    if valor is None:
        return ""
    if isinstance(valor, bytes):
        if len(valor) % 2 == 0:
            try:
                decodificado = valor.decode("utf-16le", errors="ignore").strip("\x00")
                if decodificado:
                    return decodificado
            except UnicodeDecodeError:
                pass
        return valor.hex(" ")
    if isinstance(valor, (list, tuple)):
        return "; ".join(str(item) for item in valor if item)
    return str(valor)


def _separar_fabricante_produto(classe: str) -> Tuple[str, str]:
    """Extrai fabricante e produto do nome de classe do Enum."""
    achado = re.search(r"Ven_([^&]+)&Prod_([^&]+)", classe, re.IGNORECASE)
    if not achado:
        achado = re.search(r"VID_([^&]+)&PID_([^&]+)", classe, re.IGNORECASE)
    if not achado:
        return "", ""
    fornecedor = achado.group(1).replace("_", " ").strip()
    produto = achado.group(2).replace("_", " ").strip()
    return fornecedor, produto


def _propriedades_data(handle_instancia: Any) -> Dict[str, str]:
    """Lê as propriedades de data do dispositivo, quando presentes."""
    winreg = _winreg()
    datas: Dict[str, str] = {}
    try:
        propriedades = winreg.OpenKey(
            handle_instancia,
            rf"Properties\{_GUID_PROPRIEDADES_DISPOSITIVO}",
            0,
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
        )
    except OSError:
        return datas

    try:
        for identificador in _PROPRIEDADES_DATA:
            try:
                dado, tipo = winreg.QueryValueEx(propriedades, identificador)
            except OSError:
                continue
            if tipo == getattr(winreg, "REG_BINARY", 3) and isinstance(dado, bytes):
                if len(dado) >= 8:
                    datas[identificador] = _filetime_para_iso(
                        int.from_bytes(dado[:8], "little")
                    )
            elif isinstance(dado, str):
                datas[identificador] = _formatar_data_texto(dado)
    finally:
        try:
            winreg.CloseKey(propriedades)
        except OSError:
            pass
    return datas


def _ler_ramo_enum(ramo: str, origem: str) -> Tuple[List[DispositivoUSB], List[str]]:
    """Percorre um ramo do Enum (USBSTOR ou USB) e monta os dispositivos."""
    winreg = _winreg()
    dispositivos: List[DispositivoUSB] = []
    avisos: List[str] = []
    caminho_raiz = rf"SYSTEM\CurrentControlSet\Enum\{ramo}"
    try:
        raiz = _abrir_chave(caminho_raiz)
    except OSError as exc:
        avisos.append(
            f"Não foi possível abrir {caminho_raiz}: {exc}. "
            "A leitura do histórico USB normalmente funciona sem Administrador, "
            "mas algumas chaves podem exigir elevação."
        )
        return dispositivos, avisos

    try:
        classes = _ler_subchaves(raiz)
        for classe in classes:
            try:
                handle_classe = winreg.OpenKey(
                    raiz,
                    classe,
                    0,
                    winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
                )
            except OSError:
                continue
            try:
                instancias = _ler_subchaves(handle_classe)
                fornecedor, produto = _separar_fabricante_produto(classe)
                for serial in instancias:
                    try:
                        handle_instancia = winreg.OpenKey(
                            handle_classe,
                            serial,
                            0,
                            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
                        )
                    except OSError:
                        continue
                    try:
                        valores = _ler_valores(handle_instancia)
                        datas = _propriedades_data(handle_instancia)
                        nome = _texto(valores.get("FriendlyName")) or _texto(
                            valores.get("DeviceDesc")
                        )
                        dispositivo = DispositivoUSB(
                            origem=origem,
                            instancia=f"{ramo}\\{classe}\\{serial}",
                            fornecedor=fornecedor,
                            produto=produto,
                            serial=serial,
                            nome=nome,
                            servico=_texto(valores.get("Service")),
                            classe=_texto(valores.get("Class")),
                            primeira_instalacao=datas.get("0065")
                            or datas.get("0064", ""),
                            ultima_conexao=datas.get("0066", ""),
                            evidencia=(
                                f"Enum\\{ramo}; propriedades de data: "
                                + ", ".join(
                                    f"{chave}={valor}"
                                    for chave, valor in sorted(datas.items())
                                )
                                if datas
                                else f"Enum\\{ramo}; sem propriedades de data"
                            ),
                        )
                        dispositivos.append(dispositivo)
                    finally:
                        try:
                            winreg.CloseKey(handle_instancia)
                        except OSError:
                            pass
            finally:
                try:
                    winreg.CloseKey(handle_classe)
                except OSError:
                    pass
    finally:
        try:
            winreg.CloseKey(raiz)
        except OSError:
            pass
    return dispositivos, avisos


def ler_usbstor() -> Tuple[List[DispositivoUSB], List[str]]:
    """Lê o ramo USBSTOR, que registra dispositivos de armazenamento USB."""
    return _ler_ramo_enum("USBSTOR", "USBSTOR")


def ler_usb() -> Tuple[List[DispositivoUSB], List[str]]:
    """Lê o ramo USB, que registra dispositivos USB em geral."""
    return _ler_ramo_enum("USB", "USB")


def _caminho_setupapi_padrao() -> Path:
    """Caminho padrão do log de instalação de dispositivos."""
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "INF" / "setupapi.dev.log"


def ler_setupapi(caminho: Path | str | None = None) -> Tuple[List[RegistroSetupApi], List[str]]:
    """Extrai eventos de instalação USB do setupapi.dev.log, somente leitura."""
    arquivo = Path(caminho) if caminho else _caminho_setupapi_padrao()
    registros: List[RegistroSetupApi] = []
    avisos: List[str] = []
    if not arquivo.exists():
        return registros, [f"Log não encontrado: {arquivo}"]

    try:
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return registros, [f"Falha ao ler {arquivo}: {exc}"]

    # Cada seção começa com uma linha ">>> [evento]" seguida de ">>> Section start data".
    padrao = re.compile(
        r">>>\s+\[([^\]]+)\][ \t]*\r?\n>>>\s+Section start\s+"
        r"([0-9]{4}/[0-9]{2}/[0-9]{2}\s+[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    for achado in padrao.finditer(texto):
        evento = achado.group(1).strip()
        if not re.search(r"(?i)(USBSTOR|USB\\|Device Install|Disk&Ven)", evento):
            continue
        instancia = evento
        if " - " in evento:
            instancia = evento.split(" - ", 1)[1].strip()
        registros.append(
            RegistroSetupApi(
                instancia=instancia,
                evento=evento,
                data=_formatar_data_texto(achado.group(2)),
            )
        )
        if len(registros) >= 5000:
            break

    if not registros:
        avisos.append(
            "Nenhum evento USB foi encontrado no setupapi.dev.log. "
            "O log pode ter sido rotacionado ou não conter instalações USB."
        )
    return registros, avisos


def _correlacionar(
    dispositivos: List[DispositivoUSB],
    eventos: List[RegistroSetupApi],
) -> None:
    """Enriquece os dispositivos com a data mais recente do setupapi."""
    por_instancia: Dict[str, List[RegistroSetupApi]] = {}
    for evento in eventos:
        por_instancia.setdefault(evento.instancia.lower(), []).append(evento)

    for dispositivo in dispositivos:
        chave = dispositivo.instancia.lower()
        candidatos = por_instancia.get(chave, [])
        if not candidatos:
            # O log pode usar apenas o serial ou o nome da classe; tenta por sufixo.
            for instancia_log, lista in por_instancia.items():
                if dispositivo.serial and dispositivo.serial.lower() in instancia_log:
                    candidatos.extend(lista)
        if not candidatos:
            continue
        datas = sorted(
            (evento.data for evento in candidatos if evento.data),
            reverse=True,
        )
        if datas and (not dispositivo.ultima_conexao or datas[0] > dispositivo.ultima_conexao):
            dispositivo.ultima_conexao = datas[0]
            dispositivo.evidencia += "; setupapi.dev.log"


def coletar_historico(
    incluir_usbstor: bool = True,
    incluir_usb: bool = True,
    incluir_setupapi: bool = True,
    caminho_setupapi: Path | str | None = None,
    ctx: Optional[TaskContext] = None,
) -> ResultadoUSB:
    """Coleta o histórico USB combinando Registro e setupapi.dev.log."""
    if not dependencia_disponivel("winreg"):
        raise OSError("A coleta de histórico USB está disponível apenas no Windows.")

    resultado = ResultadoUSB()
    if incluir_usbstor:
        if ctx is not None:
            ctx.log("INFO", "Lendo HKLM\\SYSTEM\\CurrentControlSet\\Enum\\USBSTOR.")
        dispositivos, avisos = ler_usbstor()
        resultado.dispositivos.extend(dispositivos)
        resultado.avisos.extend(avisos)
    if incluir_usb:
        if ctx is not None:
            ctx.log("INFO", "Lendo HKLM\\SYSTEM\\CurrentControlSet\\Enum\\USB.")
        dispositivos, avisos = ler_usb()
        resultado.dispositivos.extend(dispositivos)
        resultado.avisos.extend(avisos)

    if incluir_setupapi:
        if ctx is not None:
            ctx.log("INFO", "Lendo setupapi.dev.log.")
        eventos, avisos = ler_setupapi(caminho_setupapi)
        resultado.avisos.extend(avisos)
        _correlacionar(resultado.dispositivos, eventos)
        conhecidos = {d.instancia.lower() for d in resultado.dispositivos}
        extras: set[str] = set()
        for evento in eventos:
            chave = evento.instancia.lower()
            if chave in conhecidos or chave in extras:
                continue
            extras.add(chave)
            resultado.dispositivos.append(
                DispositivoUSB(
                    origem="Setupapi",
                    instancia=evento.instancia,
                    nome=evento.evento,
                    ultima_conexao=evento.data,
                    evidencia="setupapi.dev.log",
                )
            )

    resultado.dispositivos.sort(
        key=lambda item: (item.ultima_conexao or "", item.instancia), reverse=True
    )
    resultado.avisos.append(
        "Nenhuma chave, valor ou log foi alterado. A coleta é somente leitura. "
        "Datas ausentes significam que a propriedade não estava presente na fonte."
    )
    return resultado


def formatar_resultado_usb(resultado: ResultadoUSB) -> str:
    """Resumo textual do histórico USB."""
    linhas = [
        "Histórico USB coletado.",
        "",
        f"Dispositivos encontrados: {formatar_numero(len(resultado.dispositivos))}",
        "",
        "Avisos:",
    ]
    linhas.extend(f"- {aviso}" for aviso in resultado.avisos)
    if resultado.dispositivos:
        linhas.extend(["", "Dispositivos:"])
        for item in resultado.dispositivos[:40]:
            linhas.append(
                f"- {item.origem} | {item.fornecedor} {item.produto} | serial {item.serial} | "
                f"última conexão {item.ultima_conexao or 'desconhecida'}"
            )
        if len(resultado.dispositivos) > 40:
            linhas.append(f"... e mais {len(resultado.dispositivos) - 40} dispositivo(s).")
    return "\n".join(linhas)


def _exportar_csv(dispositivos: List[DispositivoUSB], caminho: Path) -> None:
    """Grava o histórico em CSV UTF-8 com BOM para o Excel."""
    with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(
            [
                "Origem",
                "Instância",
                "Fabricante",
                "Produto",
                "Serial",
                "Nome",
                "Serviço",
                "Classe",
                "Primeira instalação",
                "Última conexão",
                "Evidência",
            ]
        )
        for item in dispositivos:
            escritor.writerow(
                [
                    item.origem,
                    item.instancia,
                    item.fornecedor,
                    item.produto,
                    item.serial,
                    item.nome,
                    item.servico,
                    item.classe,
                    item.primeira_instalacao,
                    item.ultima_conexao,
                    item.evidencia,
                ]
            )


@register
class UsbHistoryTool(Tool):
    """Ferramenta de histórico de dispositivos USB."""

    id = "forensics.usb_history"
    name = "Histórico de Dispositivos USB"
    category = "Forense"
    description = (
        "Coleta USBSTOR, USB e setupapi.dev.log para identificar dispositivos "
        "conectados, números de série e datas de instalação, sem privilégios elevados"
    )
    keywords = [
        "usb",
        "usbstor",
        "dispositivo",
        "histórico",
        "historico",
        "setupapi",
        "serial",
        "forense",
        "conexão",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return UsbHistoryView(self, parent)


class UsbHistoryView(PainelFerramenta):
    """Interface de coleta e exportação do histórico USB."""

    def __init__(self, tool: UsbHistoryTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[ResultadoUSB] = None
        self._montar()

    def _montar(self) -> None:
        self.adicionar_aviso(
            "Leitura somente: o Registro e o setupapi.dev.log não são modificados. "
            "A leitura do USBSTOR normalmente funciona sem Administrador; algumas "
            "chaves podem negar acesso e serão exibidas como aviso.",
        )

        cartao, layout = self.adicionar_card("Fontes de evidência")
        linha_fontes = QHBoxLayout()
        self.chk_usbstor = QCheckBox("Enum\\USBSTOR (armazenamento)")
        self.chk_usbstor.setChecked(True)
        linha_fontes.addWidget(self.chk_usbstor)
        self.chk_usb = QCheckBox("Enum\\USB (dispositivos em geral)")
        self.chk_usb.setChecked(True)
        linha_fontes.addWidget(self.chk_usb)
        self.chk_setupapi = QCheckBox("setupapi.dev.log")
        self.chk_setupapi.setChecked(True)
        linha_fontes.addWidget(self.chk_setupapi)
        layout.addLayout(linha_fontes)

        linha_log = QHBoxLayout()
        linha_log.addWidget(QLabel("Log setupapi (opcional):"))
        self.txt_setupapi = QLineEdit()
        self.txt_setupapi.setPlaceholderText(r"C:\Windows\INF\setupapi.dev.log")
        linha_log.addWidget(self.txt_setupapi, stretch=1)
        self.btn_log = QPushButton("Escolher...")
        self.btn_log.clicked.connect(self._escolher_log)
        linha_log.addWidget(self.btn_log)
        layout.addLayout(linha_log)

        linha_acoes = QHBoxLayout()
        self.lbl_status = QLabel(
            "Clique em 'Coletar Histórico' para consultar as fontes selecionadas."
        )
        self.lbl_status.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        linha_acoes.addWidget(self.lbl_status, stretch=1)
        self.btn_coletar = QPushButton("Coletar Histórico")
        self.btn_coletar.clicked.connect(self._coletar)
        linha_acoes.addWidget(self.btn_coletar)
        self.btn_exportar = QPushButton("Exportar CSV...")
        self.btn_exportar.setEnabled(False)
        self.btn_exportar.clicked.connect(self._exportar)
        linha_acoes.addWidget(self.btn_exportar)
        layout.addLayout(linha_acoes)

        cartao_resultado, layout_resultado = self.adicionar_card("Dispositivos encontrados")
        self.tabela = criar_tabela(
            [
                "Origem",
                "Instância",
                "Fabricante",
                "Produto",
                "Serial",
                "Nome",
                "Primeira instalação",
                "Última conexão",
            ],
            self,
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tabela.setMinimumHeight(240)
        layout_resultado.addWidget(self.tabela)

        self.txt_saida = criar_saida_texto(170, self)
        layout_resultado.addWidget(self.txt_saida)
        linha_botoes = QHBoxLayout()
        linha_botoes.addWidget(
            botao_copiar(lambda: self.txt_saida.toPlainText(), self, "Copiar Resultado")
        )
        linha_botoes.addStretch()
        layout_resultado.addLayout(linha_botoes)

        self.log = adicionar_log_painel(self, "Log do Histórico USB")
        self.adicionar_espaco()

    def _escolher_log(self) -> None:
        """Seleciona um setupapi.dev.log alternativo."""
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar setupapi.dev.log",
            str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "INF"),
            "Logs (*.log);;Todos os arquivos (*.*)",
        )
        if caminho:
            self.txt_setupapi.setText(caminho)

    def _coletar(self) -> None:
        """Executa a coleta em segundo plano."""
        self.btn_coletar.setEnabled(False)
        self.btn_exportar.setEnabled(False)
        self.lbl_status.setText("Coletando Registro e setupapi.dev.log...")
        caminho = self.txt_setupapi.text().strip() or None

        def tarefa(ctx: TaskContext) -> ResultadoUSB:
            return coletar_historico(
                incluir_usbstor=self.chk_usbstor.isChecked(),
                incluir_usb=self.chk_usb.isChecked(),
                incluir_setupapi=self.chk_setupapi.isChecked(),
                caminho_setupapi=caminho,
                ctx=ctx,
            )

        def concluiu(resultado: ResultadoUSB) -> None:
            self._resultado = resultado
            self.btn_coletar.setEnabled(True)
            self.btn_exportar.setEnabled(bool(resultado.dispositivos))
            self.lbl_status.setText(
                f"Coleta concluída: {formatar_numero(len(resultado.dispositivos))} dispositivo(s)."
            )
            preencher_tabela(
                self.tabela,
                [
                    [
                        item.origem,
                        item.instancia,
                        item.fornecedor,
                        item.produto,
                        item.serial,
                        item.nome,
                        item.primeira_instalacao,
                        item.ultima_conexao,
                    ]
                    for item in resultado.dispositivos
                ],
            )
            self.txt_saida.setPlainText(formatar_resultado_usb(resultado))

        def falhou(erro: Exception) -> None:
            self.btn_coletar.setEnabled(True)
            self.btn_exportar.setEnabled(bool(self._resultado and self._resultado.dispositivos))
            self.lbl_status.setText("Falha na coleta do histórico USB.")
            self.txt_saida.setPlainText(
                "A coleta não foi concluída.\n\n"
                f"{erro}\n\n"
                "Verifique se o Windows permite ler as chaves do Enum e se o log "
                "selecionado existe."
            )
            mostrar_erro(self, "Falha no histórico USB", erro)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_logar=lambda nivel, msg: self.log.append_log(nivel, msg),
        )

    def _exportar(self) -> None:
        """Exporta o resultado atual em CSV."""
        if not self._resultado or not self._resultado.dispositivos:
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar histórico USB",
            str(Path.home() / "Documents" / "historico_usb.csv"),
            "CSV (*.csv);;Todos os arquivos (*.*)",
        )
        if not destino:
            return
        try:
            _exportar_csv(self._resultado.dispositivos, Path(destino))
            self.lbl_status.setText("Histórico exportado em CSV.")
        except OSError as exc:
            mostrar_erro(self, "Falha ao exportar CSV", exc)

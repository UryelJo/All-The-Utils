"""Linha do tempo forense de artefatos do Windows, em modo somente leitura.

Fontes implementadas:

* Eventos do Windows via ``Get-WinEvent`` (System, Application e, quando
  permitido, Security);
* arquivos Prefetch, usando nome do executável e metadados do arquivo;
* Amcache, por meio de ``regipy`` quando instalado;
* RecentDocs do usuário atual, lidos com ``winreg``.

A saída é ordenada do evento mais recente para o mais antigo e pode ser
exportada em CSV ou XLSX. Nenhum artefato é modificado.
"""
from __future__ import annotations

import csv
import json
import os
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.tools._helpers import (
    DependenciaAusente,
    dependencia_disponivel,
    executar_powershell_json,
    formatar_numero,
)
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

_log = get_logger("forensics.artifact_timeline")

_FONTES = ("Eventos do Windows", "Prefetch", "Amcache", "RecentDocs")
_FILTRO_DATA = re.compile(r"/Date\((-?\d+)(?:[+-]\d+)?\)/")


@dataclass
class EventoTimeline:
    """Evento individual da linha do tempo."""

    timestamp: str
    fonte: str
    categoria: str
    titulo: str
    detalhe: str = ""
    caminho: str = ""


@dataclass
class ResultadoTimeline:
    """Resultado consolidado da linha do tempo."""

    eventos: List[EventoTimeline] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    def contagem_por_fonte(self) -> Dict[str, int]:
        """Quantidade de eventos por fonte."""
        resumo: Dict[str, int] = {}
        for evento in self.eventos:
            resumo[evento.fonte] = resumo.get(evento.fonte, 0) + 1
        return resumo


def _iso_local(instante: datetime) -> str:
    """Converte um datetime em ISO local com fuso explícito."""
    if instante.tzinfo is None:
        instante = instante.astimezone()
    return instante.astimezone().isoformat(timespec="seconds")


def _normalizar_timestamp(valor: Any) -> str:
    """Normaliza datas vindas do PowerShell, do Registro ou de arquivos."""
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return _iso_local(valor)
    texto = str(valor).strip()
    if not texto:
        return ""
    achado = _FILTRO_DATA.search(texto)
    if achado:
        try:
            return _iso_local(
                datetime.fromtimestamp(int(achado.group(1)) / 1000, tz=timezone.utc)
            )
        except (OverflowError, OSError, ValueError):
            return texto
    try:
        normalizado = texto.replace("Z", "+00:00")
        return _iso_local(datetime.fromisoformat(normalizado))
    except ValueError:
        return texto


def _filetime_para_iso(valor: int) -> str:
    """Converte FILETIME em data ISO local."""
    if not valor:
        return ""
    try:
        base = datetime(1601, 1, 1, tzinfo=timezone.utc)
        return (base + timedelta(microseconds=int(valor) // 10)).astimezone().isoformat(
            timespec="seconds"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _data_arquivo(caminho: Path) -> str:
    """Data de modificação de um arquivo em ISO local."""
    try:
        return _iso_local(datetime.fromtimestamp(caminho.stat().st_mtime, tz=timezone.utc))
    except OSError:
        return ""


def coletar_eventos_windows(
    horas: int = 24,
    limite: int = 500,
    canais: Tuple[str, ...] = ("System", "Application"),
) -> List[EventoTimeline]:
    """Consulta eventos do Windows com Get-WinEvent e devolve a linha do tempo."""
    horas = max(1, min(int(horas), 24 * 30))
    limite = max(1, min(int(limite), 5000))
    lista_canais = ",".join(f"'{canal}'" for canal in canais)
    script = (
        f"$inicio=(Get-Date).AddHours(-{horas}); "
        f"$eventos=Get-WinEvent -FilterHashtable @{{LogName=@({lista_canais}); "
        f"StartTime=$inicio}} -MaxEvents {limite} -ErrorAction SilentlyContinue; "
        "$eventos | Select-Object TimeCreated, Id, "
        "LevelDisplayName, ProviderName, LogName, Message"
    )
    dados = executar_powershell_json(script, timeout=90)
    if dados is None:
        return []
    if isinstance(dados, dict):
        dados = [dados]
    if not isinstance(dados, list):
        return []

    eventos: List[EventoTimeline] = []
    for item in dados:
        if not isinstance(item, dict):
            continue
        provedor = str(item.get("ProviderName") or "Provedor desconhecido")
        identificador = item.get("Id")
        nivel = str(item.get("LevelDisplayName") or "Informação")
        mensagem = str(item.get("Message") or "").strip()
        if len(mensagem) > 1500:
            mensagem = mensagem[:1500] + "..."
        eventos.append(
            EventoTimeline(
                timestamp=_normalizar_timestamp(item.get("TimeCreated")),
                fonte="Eventos do Windows",
                categoria=nivel,
                titulo=f"{provedor} (ID {identificador})",
                detalhe=mensagem,
                caminho=str(item.get("LogName") or ""),
            )
        )
    return eventos


def _ler_executavel_prefetch(caminho: Path) -> Tuple[str, str]:
    """Lê o nome do executável em Prefetch SCCA não comprimido.

    Arquivos comprimidos em MAM (Windows 10/11) não são descomprimidos sem uma
    biblioteca especializada; nesse caso devolve apenas o método de metadado.
    """
    try:
        with open(caminho, "rb") as arquivo:
            cabecalho = arquivo.read(0x100)
    except OSError:
        return "", "ilegível"
    if len(cabecalho) < 0x50:
        return "", "truncado"
    if cabecalho[:4] == b"SCCA":
        try:
            versao = struct.unpack_from("<I", cabecalho, 4)[0]
            nome = cabecalho[0x10:0x4C].decode("utf-16le", errors="ignore").split("\x00")[0]
            return nome, f"SCCA v{versao}"
        except (struct.error, UnicodeDecodeError):
            return "", "SCCA"
    if cabecalho[:4] == b"MAM\x04":
        return "", "MAM comprimido"
    return "", "formato desconhecido"


def coletar_prefetch(limite: int = 200) -> List[EventoTimeline]:
    """Coleta arquivos Prefetch usando os metadados disponíveis no sistema."""
    pasta = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Prefetch"
    if not pasta.exists():
        return []
    limite = max(1, min(int(limite), 5000))
    arquivos: List[Path] = []
    try:
        for arquivo in pasta.glob("*.pf"):
            try:
                arquivos.append(arquivo)
            except OSError:
                continue
    except OSError:
        return []
    arquivos.sort(key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)

    eventos: List[EventoTimeline] = []
    for caminho in arquivos[:limite]:
        executavel, formato = _ler_executavel_prefetch(caminho)
        titulo = executavel or caminho.stem
        eventos.append(
            EventoTimeline(
                timestamp=_data_arquivo(caminho),
                fonte="Prefetch",
                categoria="Execução",
                titulo=titulo,
                detalhe=(
                    f"Arquivo {caminho.name}; formato {formato}; "
                    "data obtida dos metadados do arquivo .pf"
                ),
                caminho=str(caminho),
            )
        )
    return eventos


def _valor_regipy(no: Any, nome: str) -> Any:
    """Obtém um valor de um NKRecord do regipy pelo nome."""
    try:
        for valor in list(getattr(no, "values", []) or []):
            if str(getattr(valor, "name", "")).lower() == nome.lower():
                return getattr(valor, "value", None)
    except Exception:
        pass
    return None


def _texto_regipy(valor: Any) -> str:
    """Converte um valor regipy em texto."""
    if valor is None:
        return ""
    if isinstance(valor, bytes):
        try:
            return valor.decode("utf-16le", errors="ignore").strip("\x00")
        except UnicodeDecodeError:
            return valor.hex(" ")
    return str(valor)


def coletar_amcache(limite: int = 500) -> List[EventoTimeline]:
    """Lê o Amcache.hve com regipy, quando a dependência opcional está instalada."""
    if not dependencia_disponivel("regipy"):
        raise DependenciaAusente(
            "leitura do Amcache.hve", "regipy", "regipy"
        )
    caminho = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "AppCompat" / "Programs" / "Amcache.hve"
    if not caminho.exists():
        return []

    try:
        from regipy.registry import RegistryHive  # importação tardia

        hive = RegistryHive(str(caminho))
        raiz = getattr(hive, "root", None)
        if raiz is None:
            return []
        try:
            aplicativos = hive.get_key(r"\Root\Inventory\Application")
        except Exception:
            aplicativos = None
        if aplicativos is None:
            return []
        subchaves = list(getattr(aplicativos, "subkeys", []) or [])
    except DependenciaAusente:
        raise
    except Exception as exc:
        raise RuntimeError(f"Falha ao ler o Amcache.hve com regipy: {exc}") from exc

    eventos: List[EventoTimeline] = []
    for subchave in subchaves[: max(1, int(limite))]:
        nome = _texto_regipy(_valor_regipy(subchave, "Name"))
        versao = _texto_regipy(_valor_regipy(subchave, "Version"))
        editor = _texto_regipy(_valor_regipy(subchave, "Publisher"))
        instalacao = _valor_regipy(subchave, "InstallDate")
        caminho_programa = _texto_regipy(_valor_regipy(subchave, "Path"))
        timestamp = ""
        if isinstance(instalacao, int) and instalacao > 0:
            timestamp = _filetime_para_iso(instalacao)
        elif instalacao is not None:
            timestamp = _normalizar_timestamp(instalacao)
        if not timestamp:
            modificado = getattr(getattr(subchave, "header", None), "last_modified", None)
            timestamp = _normalizar_timestamp(modificado)
        eventos.append(
            EventoTimeline(
                timestamp=timestamp,
                fonte="Amcache",
                categoria="Aplicativo instalado",
                titulo=nome or str(getattr(subchave, "name", "Aplicativo")),
                detalhe=f"Versão {versao or 'desconhecida'}; editor {editor or 'desconhecido'}",
                caminho=caminho_programa,
            )
        )
    return eventos


def _winreg():
    """Importa winreg apenas quando necessário."""
    import winreg  # importação tardia

    return winreg


def _recentdocs_chave(caminho: str, limite: int, saida: List[EventoTimeline]) -> None:
    """Lê recursivamente uma chave RecentDocs."""
    winreg = _winreg()
    try:
        chave = winreg.OpenKey(winreg.HKEY_CURRENT_USER, caminho, 0, winreg.KEY_READ)
    except OSError:
        return
    try:
        try:
            modificado = winreg.QueryInfoKey(chave)[2]
        except OSError:
            modificado = 0
        data = _filetime_para_iso(modificado)
        indice = 0
        while len(saida) < limite:
            try:
                nome_valor, dado, _tipo = winreg.EnumValue(chave, indice)
            except OSError:
                break
            indice += 1
            if nome_valor == "MRUListEx" or not isinstance(dado, bytes):
                continue
            try:
                nome = dado.decode("utf-16le", errors="ignore").split("\x00")[0]
            except UnicodeDecodeError:
                continue
            if not nome:
                continue
            saida.append(
                EventoTimeline(
                    timestamp=data,
                    fonte="RecentDocs",
                    categoria="Documento recente",
                    titulo=nome,
                    detalhe=(
                        "Data de última gravação da chave RecentDocs; "
                        f"valor {nome_valor}"
                    ),
                    caminho=caminho,
                )
            )
        indice_sub = 0
        while len(saida) < limite:
            try:
                sub = winreg.EnumKey(chave, indice_sub)
            except OSError:
                break
            indice_sub += 1
            _recentdocs_chave(f"{caminho}\\{sub}", limite, saida)
    finally:
        try:
            winreg.CloseKey(chave)
        except OSError:
            pass


def coletar_recentdocs(limite: int = 200) -> List[EventoTimeline]:
    """Lê RecentDocs do usuário atual com winreg, somente leitura."""
    if not dependencia_disponivel("winreg"):
        raise OSError("RecentDocs está disponível apenas no Windows.")
    saida: List[EventoTimeline] = []
    _recentdocs_chave(
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs",
        max(1, int(limite)),
        saida,
    )
    return saida


def construir_timeline(
    fontes: Optional[Iterable[str]] = None,
    horas: int = 24,
    limite_por_fonte: int = 500,
    ctx: Optional[TaskContext] = None,
) -> ResultadoTimeline:
    """Coleta as fontes selecionadas e devolve a linha do tempo consolidada."""
    selecionadas = list(fontes or _FONTES)
    resultado = ResultadoTimeline()

    for fonte in selecionadas:
        if ctx is not None:
            ctx.log("INFO", f"Coletando fonte: {fonte}.")
        try:
            if fonte == "Eventos do Windows":
                eventos = coletar_eventos_windows(horas=horas, limite=limite_por_fonte)
            elif fonte == "Prefetch":
                eventos = coletar_prefetch(limite=limite_por_fonte)
                resultado.avisos.append(
                    "Prefetch: arquivos comprimidos em MAM usam a data de modificação "
                    "do arquivo .pf; tempos internos de execução não são inventados."
                )
            elif fonte == "Amcache":
                eventos = coletar_amcache(limite=limite_por_fonte)
            elif fonte == "RecentDocs":
                eventos = coletar_recentdocs(limite=limite_por_fonte)
            else:
                eventos = []
                resultado.avisos.append(f"Fonte desconhecida ignorada: {fonte}")
            resultado.eventos.extend(eventos)
            if ctx is not None:
                ctx.log("INFO", f"{fonte}: {len(eventos)} evento(s).")
        except DependenciaAusente as exc:
            resultado.avisos.append(
                f"{fonte}: {exc} A fonte foi ignorada sem inventar dados."
            )
        except Exception as exc:
            resultado.avisos.append(f"{fonte}: falha na coleta ({exc}).")

    resultado.eventos.sort(key=lambda item: item.timestamp or "", reverse=True)
    if ctx is not None:
        ctx.log("INFO", f"Linha do tempo consolidada com {len(resultado.eventos)} evento(s).")
    return resultado


def _linhas_csv(eventos: List[EventoTimeline]) -> List[List[str]]:
    """Converte eventos em linhas de texto para CSV/XLSX."""
    return [
        [evento.timestamp, evento.fonte, evento.categoria, evento.titulo, evento.detalhe, evento.caminho]
        for evento in eventos
    ]


def exportar_timeline(eventos: List[EventoTimeline], caminho: Path | str) -> str:
    """Exporta a linha do tempo em CSV ou XLSX, conforme a extensão."""
    destino = Path(caminho).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    sufixo = destino.suffix.lower()
    cabecalho = ["Data e hora", "Fonte", "Categoria", "Título", "Detalhe", "Caminho"]
    linhas = _linhas_csv(eventos)

    if sufixo == ".csv":
        if dependencia_disponivel("pandas"):
            import pandas as pd  # importação tardia

            pd.DataFrame(linhas, columns=cabecalho).to_csv(
                destino, index=False, encoding="utf-8-sig", sep=";"
            )
        else:
            with open(destino, "w", encoding="utf-8-sig", newline="") as arquivo:
                escritor = csv.writer(arquivo, delimiter=";")
                escritor.writerow(cabecalho)
                escritor.writerows(linhas)
        return str(destino)

    if sufixo == ".xlsx":
        if dependencia_disponivel("pandas"):
            import pandas as pd  # importação tardia

            pd.DataFrame(linhas, columns=cabecalho).to_excel(
                destino, index=False, engine="openpyxl"
            )
            return str(destino)
        if dependencia_disponivel("openpyxl"):
            from openpyxl import Workbook  # importação tardia

            livro = Workbook()
            planilha = livro.active
            planilha.title = "Linha do Tempo"
            planilha.append(cabecalho)
            for linha in linhas:
                planilha.append(linha)
            livro.save(destino)
            return str(destino)
        raise DependenciaAusente(
            "exportação XLSX", "pandas", "pandas openpyxl"
        )

    raise ValueError("Use a extensão .csv ou .xlsx para exportar a linha do tempo.")


def formatar_resultado_timeline(resultado: ResultadoTimeline) -> str:
    """Resumo textual da linha do tempo."""
    linhas = [
        "Linha do tempo consolidada.",
        "",
        f"Total de eventos: {formatar_numero(len(resultado.eventos))}",
        "",
        "Eventos por fonte:",
    ]
    for fonte, quantidade in sorted(resultado.contagem_por_fonte().items()):
        linhas.append(f"- {fonte}: {formatar_numero(quantidade)}")
    if not resultado.eventos:
        linhas.append("- Nenhum evento coletado.")
    linhas.extend(["", "Avisos:"])
    if resultado.avisos:
        linhas.extend(f"- {aviso}" for aviso in resultado.avisos)
    else:
        linhas.append("- Nenhum aviso.")
    if resultado.eventos:
        linhas.extend(["", "Primeiros eventos:"])
        for evento in resultado.eventos[:20]:
            linhas.append(
                f"- {evento.timestamp or 'sem data'} | {evento.fonte} | "
                f"{evento.titulo}"
            )
        if len(resultado.eventos) > 20:
            linhas.append(f"... e mais {len(resultado.eventos) - 20} evento(s).")
    return "\n".join(linhas)


@register
class ArtifactTimelineTool(Tool):
    """Ferramenta de linha do tempo de artefatos forenses."""

    id = "forensics.artifact_timeline"
    name = "Linha do Tempo de Artefatos"
    category = "Forense"
    description = (
        "Consolida eventos do Windows, Prefetch, Amcache e RecentDocs em uma "
        "linha do tempo ordenada, com exportação CSV e XLSX"
    )
    keywords = [
        "linha do tempo",
        "timeline",
        "eventos",
        "prefetch",
        "amcache",
        "recentdocs",
        "forense",
        "csv",
        "xlsx",
        "incidente",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return ArtifactTimelineView(self, parent)


class ArtifactTimelineView(PainelFerramenta):
    """Interface de coleta e exportação da linha do tempo."""

    def __init__(self, tool: ArtifactTimelineTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[ResultadoTimeline] = None
        self._montar()

    def _montar(self) -> None:
        self.adicionar_aviso(
            "Leitura somente: eventos, arquivos Prefetch, Amcache e RecentDocs não "
            "são alterados. O log Security pode exigir Administrador; a fonte é "
            "ignorada com aviso quando o acesso não é permitido. Amcache requer "
            "regipy, que é opcional.",
            destaque=True,
        )

        cartao, layout = self.adicionar_card("Fontes e período")
        linha_fontes = QHBoxLayout()
        self._checks: Dict[str, QCheckBox] = {}
        for fonte in _FONTES:
            check = QCheckBox(fonte)
            check.setChecked(True)
            self._checks[fonte] = check
            linha_fontes.addWidget(check)
        layout.addLayout(linha_fontes)

        linha_parametros = QHBoxLayout()
        linha_parametros.addWidget(QLabel("Período (horas):"))
        self.spin_horas = QSpinBox()
        self.spin_horas.setRange(1, 720)
        self.spin_horas.setValue(24)
        linha_parametros.addWidget(self.spin_horas)

        linha_parametros.addWidget(QLabel("Limite por fonte:"))
        self.spin_limite = QSpinBox()
        self.spin_limite.setRange(10, 5000)
        self.spin_limite.setValue(500)
        linha_parametros.addWidget(self.spin_limite)

        self.btn_coletar = QPushButton("Coletar Linha do Tempo")
        self.btn_coletar.clicked.connect(self._coletar)
        linha_parametros.addWidget(self.btn_coletar)
        self.btn_csv = QPushButton("Exportar CSV...")
        self.btn_csv.setEnabled(False)
        self.btn_csv.clicked.connect(lambda: self._exportar(".csv"))
        linha_parametros.addWidget(self.btn_csv)
        self.btn_xlsx = QPushButton("Exportar XLSX...")
        self.btn_xlsx.setEnabled(False)
        self.btn_xlsx.clicked.connect(lambda: self._exportar(".xlsx"))
        linha_parametros.addWidget(self.btn_xlsx)
        layout.addLayout(linha_parametros)

        self.lbl_status = QLabel(
            "Selecione as fontes e clique em 'Coletar Linha do Tempo'."
        )
        self.lbl_status.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        layout.addWidget(self.lbl_status)

        cartao_resultado, layout_resultado = self.adicionar_card("Eventos da linha do tempo")
        self.tabela = criar_tabela(
            ["Data e hora", "Fonte", "Categoria", "Título", "Detalhe", "Caminho"], self
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
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

        self.log = adicionar_log_painel(self, "Log da Linha do Tempo")
        self.adicionar_espaco()

    def _fontes_selecionadas(self) -> List[str]:
        """Lista as fontes marcadas."""
        return [fonte for fonte, check in self._checks.items() if check.isChecked()]

    def _coletar(self) -> None:
        """Executa a coleta em segundo plano."""
        fontes = self._fontes_selecionadas()
        if not fontes:
            QMessageBox.information(
                self, "Selecione uma fonte", "Marque ao menos uma fonte de artefatos."
            )
            return
        self.btn_coletar.setEnabled(False)
        self.btn_csv.setEnabled(False)
        self.btn_xlsx.setEnabled(False)
        self.lbl_status.setText("Coletando linha do tempo...")
        horas = int(self.spin_horas.value())
        limite = int(self.spin_limite.value())

        def tarefa(ctx: TaskContext) -> ResultadoTimeline:
            return construir_timeline(
                fontes=fontes,
                horas=horas,
                limite_por_fonte=limite,
                ctx=ctx,
            )

        def concluiu(resultado: ResultadoTimeline) -> None:
            self._resultado = resultado
            self.btn_coletar.setEnabled(True)
            self.btn_csv.setEnabled(bool(resultado.eventos))
            self.btn_xlsx.setEnabled(bool(resultado.eventos))
            self.lbl_status.setText(
                f"Linha do tempo concluída: {formatar_numero(len(resultado.eventos))} evento(s)."
            )
            preencher_tabela(
                self.tabela,
                [
                    [
                        evento.timestamp,
                        evento.fonte,
                        evento.categoria,
                        evento.titulo,
                        evento.detalhe,
                        evento.caminho,
                    ]
                    for evento in resultado.eventos
                ],
            )
            self.txt_saida.setPlainText(formatar_resultado_timeline(resultado))

        def falhou(erro: Exception) -> None:
            self.btn_coletar.setEnabled(True)
            self.btn_csv.setEnabled(bool(self._resultado and self._resultado.eventos))
            self.btn_xlsx.setEnabled(bool(self._resultado and self._resultado.eventos))
            self.lbl_status.setText("Falha na coleta da linha do tempo.")
            mensagem = str(erro)
            if isinstance(erro, DependenciaAusente):
                mensagem += f"\n\nInstale com: pip install {erro.pacote}"
            self.txt_saida.setPlainText(
                "A coleta não foi concluída.\n\n"
                f"{mensagem}\n\n"
                "Verifique se o Windows permite consultar os eventos e os artefatos "
                "selecionados. Fontes opcionais ausentes são ignoradas com aviso."
            )
            mostrar_erro(self, "Falha na linha do tempo", erro)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_progredir=lambda atual, total, msg: self.lbl_status.setText(msg),
            ao_logar=lambda nivel, msg: self.log.append_log(nivel, msg),
        )

    def _exportar(self, extensao: str) -> None:
        """Exporta os eventos atuais para CSV ou XLSX."""
        if not self._resultado or not self._resultado.eventos:
            return
        filtro = "CSV (*.csv)" if extensao == ".csv" else "Planilha Excel (*.xlsx)"
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar linha do tempo",
            str(Path.home() / "Documents" / f"linha_do_tempo{extensao}"),
            filtro,
        )
        if not destino:
            return
        if not destino.lower().endswith(extensao):
            destino += extensao
        try:
            exportar_timeline(self._resultado.eventos, Path(destino))
            self.lbl_status.setText(f"Linha do tempo exportada: {destino}")
        except Exception as exc:
            mostrar_erro(self, "Falha ao exportar a linha do tempo", exc)

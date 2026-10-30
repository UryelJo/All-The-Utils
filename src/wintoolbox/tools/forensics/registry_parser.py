"""Leitura forense de chaves do Registro do Windows, online ou em hives offline.

No modo online, usa ``winreg`` para ler SAM, SYSTEM e SOFTWARE sem alterar
nenhum valor. No modo offline, valida o cabeçalho ``regf`` e usa ``regipy``
quando instalado. Se ``regipy`` não estiver presente, a ferramenta informa a
dependência necessária e não tenta inventar dados a partir de strings do hive.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
    formatar_bytes,
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

_log = get_logger("forensics.registry_parser")

_TIPOS = {
    0: "REG_NONE",
    1: "REG_SZ",
    2: "REG_EXPAND_SZ",
    3: "REG_BINARY",
    4: "REG_DWORD",
    5: "REG_DWORD_BIG_ENDIAN",
    6: "REG_LINK",
    7: "REG_MULTI_SZ",
    8: "REG_RESOURCE_LIST",
    9: "REG_FULL_RESOURCE_DESCRIPTOR",
    10: "REG_RESOURCE_REQUIREMENTS_LIST",
    11: "REG_QWORD",
}

_HIVES_VALIDOS = ("SAM", "SYSTEM", "SOFTWARE", "SECURITY")

_HIVES_ONLINE: Dict[str, Tuple[int, str]] = {}


@dataclass
class ValorRegistro:
    """Valor de uma chave do Registro."""

    nome: str
    tipo: str
    dados: Any


@dataclass
class ChaveRegistro:
    """Chave lida, com valores e subchaves imediatas."""

    caminho: str
    valores: List[ValorRegistro] = field(default_factory=list)
    subchaves: List[str] = field(default_factory=list)
    ultima_modificacao: str = ""


@dataclass
class ResultadoRegistro:
    """Resultado consolidado de uma análise do Registro."""

    fonte: str
    modo: str
    chaves: List[ChaveRegistro] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    @property
    def total_valores(self) -> int:
        """Quantidade de valores lidos."""
        return sum(len(chave.valores) for chave in self.chaves)


def _filetime_para_iso(valor: int) -> str:
    """Converte FILETIME (100 ns desde 1601) em data ISO local."""
    if not valor:
        return ""
    try:
        segundos = (int(valor) - 116444736000000000) / 10_000_000
        return datetime.fromtimestamp(segundos, tz=timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _winreg():
    """Importa winreg apenas quando necessário."""
    import winreg  # importação tardia

    return winreg


def _hives_online() -> Dict[str, Tuple[int, str]]:
    """Monta o mapa de hives online com as constantes reais do winreg."""
    global _HIVES_ONLINE
    if _HIVES_ONLINE:
        return _HIVES_ONLINE
    winreg = _winreg()
    _HIVES_ONLINE = {
        "SAM": (winreg.HKEY_LOCAL_MACHINE, r"SAM\SAM"),
        "SYSTEM": (winreg.HKEY_LOCAL_MACHINE, "SYSTEM"),
        "SOFTWARE": (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE"),
        "SECURITY": (winreg.HKEY_LOCAL_MACHINE, "SECURITY"),
    }
    return _HIVES_ONLINE


def _formatar_dado(tipo: int, dado: Any) -> Any:
    """Converte o dado bruto do winreg em um valor legível e fiel."""
    if tipo in (1, 2, 6):
        if isinstance(dado, bytes):
            return dado.decode("utf-16le", errors="replace").rstrip("\x00")
        return str(dado)
    if tipo == 7:
        if isinstance(dado, (list, tuple)):
            return list(dado)
        if isinstance(dado, bytes):
            return [
                parte.decode("utf-16le", errors="replace")
                for parte in dado.split(b"\x00\x00")
                if parte
            ]
        return str(dado)
    if tipo in (4, 5, 11):
        return int(dado) if isinstance(dado, int) else dado
    if tipo == 3:
        if isinstance(dado, bytes):
            if len(dado) <= 48:
                return dado.hex(" ")
            return f"{dado[:48].hex(' ')} ... ({formatar_bytes(len(dado))})"
        return str(dado)
    return dado


def _tipo_nome(tipo: int) -> str:
    """Nome legível do tipo de valor do Registro."""
    return _TIPOS.get(int(tipo), f"Tipo {tipo}")


def _ler_chave_online(
    hive: str,
    subcaminho: str,
    profundidade: int,
    limite: int,
    total: List[int],
) -> ChaveRegistro:
    """Lê uma chave e suas subchaves com winreg, limitando a profundidade."""
    winreg = _winreg()
    raiz, base = _hives_online()[hive]
    caminho_completo = f"{hive}\\{subcaminho}".rstrip("\\")
    chave = ChaveRegistro(caminho=caminho_completo)
    total[0] += 1
    try:
        handle = winreg.OpenKey(
            raiz,
            (base + ("\\" + subcaminho if subcaminho else "")),
            0,
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
        )
    except OSError as exc:
        chave.subchaves = []
        raise PermissionError(
            f"Acesso negado ou chave inexistente em {caminho_completo}: {exc}"
        ) from exc

    try:
        try:
            _subchaves, _valores, modificado = winreg.QueryInfoKey(handle)
            chave.ultima_modificacao = _filetime_para_iso(modificado)
        except OSError:
            pass

        indice = 0
        while True:
            try:
                nome, dado, tipo = winreg.EnumValue(handle, indice)
            except OSError:
                break
            chave.valores.append(
                ValorRegistro(nome=nome or "(padrão)", tipo=_tipo_nome(tipo), dados=_formatar_dado(tipo, dado))
            )
            indice += 1
            if indice > 5000:
                break

        if profundidade > 0 and total[0] < limite:
            indice = 0
            while total[0] < limite:
                try:
                    nome_sub = winreg.EnumKey(handle, indice)
                except OSError:
                    break
                chave.subchaves.append(nome_sub)
                indice += 1
                if indice > 5000:
                    break
                try:
                    filha = _ler_chave_online(
                        hive,
                        f"{subcaminho}\\{nome_sub}" if subcaminho else nome_sub,
                        profundidade - 1,
                        limite,
                        total,
                    )
                    # As filhas são anexadas pelo chamador por meio de uma lista plana.
                    chave.valores.extend([])
                    if not hasattr(chave, "_filhas"):
                        chave._filhas = []  # type: ignore[attr-defined]
                    chave._filhas.append(filha)  # type: ignore[attr-defined]
                except PermissionError:
                    continue
    finally:
        try:
            winreg.CloseKey(handle)
        except OSError:
            pass
    return chave


def _achatar_chaves(chave: ChaveRegistro) -> List[ChaveRegistro]:
    """Percorre a árvore auxiliar e devolve todas as chaves em lista plana."""
    saida = [chave]
    for filha in getattr(chave, "_filhas", []):
        saida.extend(_achatar_chaves(filha))
    return saida


def _caminhos_interesse(hive: str) -> List[Tuple[str, int]]:
    """Seleciona chaves relevantes para o resumo de cada hive online."""
    if hive == "SYSTEM":
        return [
            (r"CurrentControlSet\Control\ComputerName\ComputerName", 0),
            (r"CurrentControlSet\Control\Windows", 0),
            (r"CurrentControlSet\Control\ProductOptions", 0),
            (r"CurrentControlSet\Services", 1),
        ]
    if hive == "SOFTWARE":
        return [
            (r"Microsoft\Windows NT\CurrentVersion", 0),
            (r"Microsoft\Windows\CurrentVersion\Uninstall", 1),
        ]
    if hive == "SAM":
        return [
            (r"Domains\Account\Users\Names", 0),
            (r"Domains\Account", 0),
        ]
    if hive == "SECURITY":
        return [(r"Policy\Secrets", 0)]
    return [("", 1)]


def analisar_online(
    hive: str,
    profundidade: int = 2,
    limite: int = 500,
) -> ResultadoRegistro:
    """Lê um hive do sistema em execução usando winreg, sem escrever nada."""
    hive = str(hive).upper()
    if hive not in _HIVES_VALIDOS:
        raise ValueError(f"Hive inválido: {hive}. Use um de: {', '.join(_HIVES_VALIDOS)}.")
    if not dependencia_disponivel("winreg"):
        raise OSError("A leitura online do Registro está disponível apenas no Windows.")

    resultado = ResultadoRegistro(fonte=hive, modo="online (winreg)")
    total = [0]
    for subcaminho, profundidade_extra in _caminhos_interesse(hive):
        if total[0] >= limite:
            resultado.avisos.append("Limite de chaves atingido; a leitura foi interrompida.")
            break
        try:
            chave = _ler_chave_online(
                hive,
                subcaminho,
                min(profundidade, profundidade_extra) if profundidade_extra else 0,
                limite,
                total,
            )
            resultado.chaves.extend(_achatar_chaves(chave))
        except PermissionError as exc:
            resultado.avisos.append(str(exc))
        except FileNotFoundError as exc:
            resultado.avisos.append(str(exc))
        except OSError as exc:
            resultado.avisos.append(f"Falha ao ler {subcaminho}: {exc}")

    if not resultado.chaves:
        resultado.avisos.append(
            "Nenhuma chave pôde ser lida. Para SAM e SECURITY, execute como Administrador."
        )
    return resultado


def validar_hive_offline(caminho: Path | str) -> Dict[str, Any]:
    """Valida o cabeçalho de um hive offline e devolve metadados básicos."""
    caminho = Path(caminho).expanduser().resolve()
    if not caminho.exists():
        raise FileNotFoundError(f"Hive não encontrado: {caminho}")
    if not caminho.is_file():
        raise ValueError("O caminho do hive deve apontar para um arquivo.")
    tamanho = caminho.stat().st_size
    if tamanho < 4096:
        raise ValueError("O arquivo é pequeno demais para ser um hive do Registro.")
    with open(caminho, "rb") as arquivo:
        cabecalho = arquivo.read(64)
    if cabecalho[:4] != b"regf":
        raise ValueError(
            "Assinatura 'regf' não encontrada. Selecione um hive bruto "
            "(SYSTEM, SOFTWARE, SAM ou SECURITY), não um arquivo .reg exportado."
        )
    sequencia1, sequencia2 = struct.unpack_from("<II", cabecalho, 4)
    timestamp = struct.unpack_from("<Q", cabecalho, 12)[0]
    versao_maior, versao_menor = struct.unpack_from("<II", cabecalho, 20)
    tipo = struct.unpack_from("<I", cabecalho, 28)[0]
    return {
        "caminho": str(caminho),
        "tamanho": tamanho,
        "sequencia_primaria": sequencia1,
        "sequencia_secundaria": sequencia2,
        "ultima_gravacao": _filetime_para_iso(timestamp),
        "versao": f"{versao_maior}.{versao_menor}",
        "tipo": tipo,
    }


def _valor_regipy(valor: Any) -> ValorRegistro:
    """Converte um valor do regipy sem depender de detalhes internos da versão."""
    nome = str(getattr(valor, "name", "") or "(padrão)")
    tipo = getattr(valor, "value_type", "")
    if hasattr(tipo, "name"):
        tipo = tipo.name
    dado = getattr(valor, "value", None)
    if isinstance(dado, bytes):
        if len(dado) <= 48:
            dado = dado.hex(" ")
        else:
            dado = f"{dado[:48].hex(' ')} ... ({formatar_bytes(len(dado))})"
    return ValorRegistro(nome=nome, tipo=str(tipo), dados=dado)


def _converter_no_regipy(
    no: Any,
    caminho: str,
    profundidade: int,
    limite: int,
    total: List[int],
) -> ChaveRegistro:
    """Converte recursivamente um NKRecord do regipy em ChaveRegistro."""
    total[0] += 1
    nome = str(getattr(no, "name", "") or "")
    caminho_atual = f"{caminho}\\{nome}".strip("\\") if nome else caminho
    chave = ChaveRegistro(caminho=caminho_atual or "(raiz)")

    modificado = getattr(getattr(no, "header", None), "last_modified", None)
    if modificado is not None:
        if isinstance(modificado, datetime):
            chave.ultima_modificacao = modificado.isoformat(timespec="seconds")
        else:
            chave.ultima_modificacao = str(modificado)

    try:
        for valor in list(getattr(no, "values", []) or []):
            chave.valores.append(_valor_regipy(valor))
    except Exception:
        pass

    if profundidade > 0 and total[0] < limite:
        try:
            subchaves = list(getattr(no, "subkeys", []) or [])
        except Exception:
            subchaves = []
        for filha in subchaves:
            if total[0] >= limite:
                break
            chave.subchaves.append(str(getattr(filha, "name", "") or ""))
            try:
                if not hasattr(chave, "_filhas"):
                    chave._filhas = []  # type: ignore[attr-defined]
                chave._filhas.append(  # type: ignore[attr-defined]
                    _converter_no_regipy(filha, caminho_atual, profundidade - 1, limite, total)
                )
            except Exception:
                continue
    return chave


def analisar_hive_offline(
    caminho: Path | str,
    profundidade: int = 2,
    limite: int = 500,
) -> ResultadoRegistro:
    """Analisa um hive offline com regipy, sem montar nem alterar o arquivo."""
    metadados = validar_hive_offline(caminho)
    if not dependencia_disponivel("regipy"):
        raise DependenciaAusente(
            "leitura de hives offline (SAM, SYSTEM, SOFTWARE e SECURITY)",
            "regipy",
            "regipy",
        )

    try:
        from regipy.registry import RegistryHive  # importação tardia
    except ImportError as exc:
        raise DependenciaAusente(
            "leitura de hives offline (SAM, SYSTEM, SOFTWARE e SECURITY)",
            "regipy",
            "regipy",
        ) from exc

    resultado = ResultadoRegistro(
        fonte=Path(caminho).name,
        modo="offline (regipy)",
    )
    try:
        hive = RegistryHive(str(caminho))
        raiz = getattr(hive, "root", None)
        if raiz is None:
            raise RuntimeError("regipy não expôs a chave raiz do hive.")
        total = [0]
        chave = _converter_no_regipy(raiz, "", int(profundidade), int(limite), total)
        resultado.chaves = _achatar_chaves(chave)
    except DependenciaAusente:
        raise
    except Exception as exc:
        raise RuntimeError(
            "regipy está instalado, mas não foi possível navegar neste hive. "
            f"Detalhe: {exc}. Nenhum dado foi inventado."
        ) from exc

    resultado.avisos.append(
        f"Hive validado: {formatar_bytes(metadados['tamanho'])}, "
        f"versão {metadados['versao']}, última gravação {metadados['ultima_gravacao'] or 'desconhecida'}."
    )
    return resultado


def analisar_registro(
    hive: str,
    caminho_offline: Optional[Path | str] = None,
    profundidade: int = 2,
    limite: int = 500,
) -> ResultadoRegistro:
    """Escolhe entre leitura online (winreg) e offline (regipy)."""
    if caminho_offline:
        return analisar_hive_offline(caminho_offline, profundidade=profundidade, limite=limite)
    return analisar_online(hive, profundidade=profundidade, limite=limite)


def formatar_resultado_registro(resultado: ResultadoRegistro) -> str:
    """Resumo textual da análise do Registro."""
    linhas = [
        "Análise do Registro concluída.",
        "",
        f"Fonte: {resultado.fonte}",
        f"Modo: {resultado.modo}",
        f"Chaves lidas: {formatar_numero(len(resultado.chaves))}",
        f"Valores lidos: {formatar_numero(resultado.total_valores)}",
        "",
        "Avisos:",
    ]
    linhas.extend(f"- {aviso}" for aviso in resultado.avisos)
    if resultado.chaves:
        linhas.extend(["", "Chaves:"])
        for chave in resultado.chaves[:30]:
            linhas.append(
                f"- {chave.caminho} | {len(chave.valores)} valor(es) | "
                f"modificada em {chave.ultima_modificacao or 'data desconhecida'}"
            )
        if len(resultado.chaves) > 30:
            linhas.append(f"... e mais {len(resultado.chaves) - 30} chave(s).")
    return "\n".join(linhas)


@register
class RegistryParserTool(Tool):
    """Ferramenta de leitura de hives do Registro do Windows."""

    id = "forensics.registry_parser"
    name = "Analisador do Registro"
    category = "Forense"
    description = (
        "Lê SAM, SYSTEM e SOFTWARE em execução com winreg e hives offline "
        "com regipy, sempre em modo somente leitura"
    )
    keywords = [
        "registro",
        "registry",
        "sam",
        "system",
        "software",
        "hive",
        "forense",
        "winreg",
        "regipy",
        "persistência",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        """Cria a página da ferramenta."""
        return RegistryParserView(self, parent)


class RegistryParserView(PainelFerramenta):
    """Interface de seleção de hive e exibição de valores."""

    def __init__(self, tool: RegistryParserTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._montar()

    def _montar(self) -> None:
        self.adicionar_aviso(
            "Somente leitura: valores não são criados, alterados ou removidos. "
            "SAM e SECURITY normalmente exigem Administrador. Hives offline são "
            "lidos como cópia, sem montagem no sistema.",
            destaque=True,
        )

        cartao, layout = self.adicionar_card("Fonte do Registro")
        linha_modo = QHBoxLayout()
        linha_modo.addWidget(QLabel("Modo:"))
        self.cmb_modo = QComboBox()
        self.cmb_modo.addItems(["Sistema em execução (winreg)", "Hive offline (regipy)"])
        self.cmb_modo.currentIndexChanged.connect(self._atualizar_modo)
        linha_modo.addWidget(self.cmb_modo)

        linha_modo.addWidget(QLabel("Hive:"))
        self.cmb_hive = QComboBox()
        self.cmb_hive.addItems(list(_HIVES_VALIDOS))
        linha_modo.addWidget(self.cmb_hive)
        layout.addLayout(linha_modo)

        linha_offline = QHBoxLayout()
        linha_offline.addWidget(QLabel("Arquivo do hive:"))
        self.txt_hive = QLineEdit()
        self.txt_hive.setPlaceholderText("Ex.: C:\\Windows\\System32\\config\\SYSTEM")
        linha_offline.addWidget(self.txt_hive, stretch=1)
        self.btn_hive = QPushButton("Escolher...")
        self.btn_hive.clicked.connect(self._escolher_hive)
        linha_offline.addWidget(self.btn_hive)
        layout.addLayout(linha_offline)

        linha_parametros = QHBoxLayout()
        linha_parametros.addWidget(QLabel("Profundidade:"))
        self.spin_profundidade = QSpinBox()
        self.spin_profundidade.setRange(0, 8)
        self.spin_profundidade.setValue(2)
        linha_parametros.addWidget(self.spin_profundidade)

        linha_parametros.addWidget(QLabel("Máximo de chaves:"))
        self.spin_limite = QSpinBox()
        self.spin_limite.setRange(10, 20000)
        self.spin_limite.setValue(500)
        linha_parametros.addWidget(self.spin_limite)

        self.btn_analisar = QPushButton("Analisar Registro")
        self.btn_analisar.clicked.connect(self._analisar)
        linha_parametros.addWidget(self.btn_analisar)
        layout.addLayout(linha_parametros)

        self.lbl_status = QLabel(
            "Escolha o modo e clique em 'Analisar Registro'. Nenhuma chave será alterada."
        )
        self.lbl_status.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        layout.addWidget(self.lbl_status)

        cartao_resultado, layout_resultado = self.adicionar_card("Valores encontrados")
        self.tabela = criar_tabela(["Chave", "Valor", "Tipo", "Dados"], self)
        self.tabela.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.tabela.setMinimumHeight(220)
        layout_resultado.addWidget(self.tabela)

        self.txt_saida = criar_saida_texto(180, self)
        layout_resultado.addWidget(self.txt_saida)
        linha_botoes = QHBoxLayout()
        linha_botoes.addWidget(
            botao_copiar(lambda: self.txt_saida.toPlainText(), self, "Copiar Resultado")
        )
        linha_botoes.addStretch()
        layout_resultado.addLayout(linha_botoes)

        self.log = adicionar_log_painel(self, "Log do Analisador do Registro")
        self.adicionar_espaco()
        self._atualizar_modo()

    def _atualizar_modo(self) -> None:
        """Habilita o campo de arquivo somente no modo offline."""
        offline = self.cmb_modo.currentIndex() == 1
        self.txt_hive.setEnabled(offline)
        self.btn_hive.setEnabled(offline)
        self.cmb_hive.setEnabled(not offline)

    def _escolher_hive(self) -> None:
        """Seleciona o arquivo de um hive offline."""
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar hive do Registro",
            str(Path.home()),
            "Hives do Registro (*.hive *.dat *.regf);;Todos os arquivos (*.*)",
        )
        if caminho:
            self.txt_hive.setText(caminho)

    def _analisar(self) -> None:
        """Dispara a análise em segundo plano."""
        offline = self.cmb_modo.currentIndex() == 1
        caminho = self.txt_hive.text().strip() if offline else None
        if offline and not caminho:
            QMessageBox.information(
                self, "Informe o hive", "Selecione o arquivo do hive offline."
            )
            return
        hive = self.cmb_hive.currentText()
        profundidade = int(self.spin_profundidade.value())
        limite = int(self.spin_limite.value())

        self.btn_analisar.setEnabled(False)
        self.lbl_status.setText("Lendo o Registro em modo somente leitura...")
        self.tabela.setRowCount(0)

        def tarefa(ctx: TaskContext) -> ResultadoRegistro:
            ctx.log("INFO", f"Analisando hive {hive} ({'offline' if offline else 'online'}).")
            return analisar_registro(
                hive,
                caminho_offline=caminho,
                profundidade=profundidade,
                limite=limite,
            )

        def concluiu(resultado: ResultadoRegistro) -> None:
            self.btn_analisar.setEnabled(True)
            self.lbl_status.setText(
                f"Concluído: {formatar_numero(len(resultado.chaves))} chave(s), "
                f"{formatar_numero(resultado.total_valores)} valor(es)."
            )
            linhas: List[List[Any]] = []
            for chave in resultado.chaves:
                if not chave.valores:
                    linhas.append([chave.caminho, "", "", ""])
                for valor in chave.valores:
                    linhas.append(
                        [chave.caminho, valor.nome, valor.tipo, valor.dados]
                    )
            preencher_tabela(self.tabela, linhas)
            self.txt_saida.setPlainText(formatar_resultado_registro(resultado))

        def falhou(erro: Exception) -> None:
            self.btn_analisar.setEnabled(True)
            self.lbl_status.setText("Falha na leitura do Registro.")
            mensagem = str(erro)
            if isinstance(erro, DependenciaAusente):
                mensagem += (
                    "\n\nA leitura de hives offline requer regipy. "
                    "Instale com: pip install regipy"
                )
            self.txt_saida.setPlainText(
                "A análise não foi concluída.\n\n"
                f"{mensagem}\n\n"
                "O modo online usa winreg e não requer regipy. Para hives offline, "
                "instale a dependência indicada."
            )
            mostrar_erro(self, "Falha na análise do Registro", erro)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_logar=lambda nivel, msg: self.log.append_log(nivel, msg),
        )

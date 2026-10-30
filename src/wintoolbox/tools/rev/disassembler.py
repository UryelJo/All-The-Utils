"""Desmontagem interativa de código de máquina com Capstone.

A biblioteca `capstone` é importada apenas quando a desmontagem é solicitada; se
não estiver instalada, a interface continua abrindo e exibe a instrução de
instalação. O módulo oferece navegação por endereço, mapa de referências (xrefs)
e exportação do assembly gerado.
"""
from __future__ import annotations

import bisect
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import DependenciaAusente, dependencia_disponivel, formatar_numero
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    botao_copiar,
    criar_card,
    criar_saida_texto,
    criar_tabela,
    executar_assincrono,
    mostrar_erro,
    preencher_tabela,
)

_log = get_logger("rev.disassembler")

# (rótulo, chave interna)
ARQUITETURAS: Tuple[Tuple[str, str], ...] = (
    ("x86 (32 bits)", "x86_32"),
    ("x86-64 (64 bits)", "x86_64"),
    ("ARM (32 bits)", "arm"),
    ("ARM Thumb", "arm_thumb"),
    ("ARM64 / AArch64", "arm64"),
    ("MIPS (32 bits, big endian)", "mips"),
    ("MIPS (32 bits, little endian)", "mips_le"),
    ("PowerPC (32 bits, big endian)", "ppc"),
    ("RISC-V (64 bits)", "riscv64"),
)

LIMITE_BYTES = 64 * 1024 * 1024
LIMITE_INSTRUCOES = 200_000


def capstone_disponivel() -> bool:
    """Informa se o Capstone pode ser importado."""
    return dependencia_disponivel("capstone")


def _resolver_modo(chave: str) -> Tuple[int, int]:
    """Traduz a chave interna para as constantes do Capstone."""
    try:
        import capstone
    except ImportError as exc:
        raise DependenciaAusente("a biblioteca Capstone", "capstone", "capstone") from exc

    mapa = {
        "x86_32": (capstone.CS_ARCH_X86, capstone.CS_MODE_32),
        "x86_64": (capstone.CS_ARCH_X86, capstone.CS_MODE_64),
        "arm": (capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM),
        "arm_thumb": (capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB),
        "arm64": (capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM),
        "mips": (capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 | capstone.CS_MODE_BIG_ENDIAN),
        "mips_le": (capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 | capstone.CS_MODE_LITTLE_ENDIAN),
        "ppc": (capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN),
        "riscv64": (capstone.CS_ARCH_RISCV, capstone.CS_MODE_RISCV64),
    }
    if chave not in mapa:
        raise ValueError(f"Arquitetura não suportada: {chave}")
    return mapa[chave]


def desmontar(
    dados: bytes,
    arquitetura: str = "x86_64",
    endereco_base: int = 0x400000,
    deslocamento: int = 0,
    quantidade: int = 500,
) -> Dict[str, Any]:
    """Desmonta até ``quantidade`` instruções a partir de ``deslocamento``."""
    import capstone

    if not dados:
        raise ValueError("Nenhum byte para desmontar.")
    deslocamento = max(0, min(int(deslocamento), max(0, len(dados) - 1)))
    quantidade = max(1, min(int(quantidade), LIMITE_INSTRUCOES))
    arquitetura_id, modo = _resolver_modo(arquitetura)

    md = capstone.Cs(arquitetura_id, modo)
    md.detail = True
    md.skipdata = True

    codigo = dados[deslocamento:]
    inicio = int(endereco_base) + deslocamento
    instrucoes: List[Dict[str, Any]] = []
    for instrucao in md.disasm(codigo, inicio):
        instrucoes.append(
            {
                "endereco": int(instrucao.address),
                "endereco_hex": f"0x{instrucao.address:08X}",
                "bytes": instrucao.bytes.hex(" "),
                "mnemonico": instrucao.mnemonic,
                "operandos": instrucao.op_str,
                "tamanho": int(instrucao.size),
                "grupos": [md.group_name(grupo) for grupo in getattr(instrucao, "groups", [])],
                "eh_salto": instrucao.mnemonic.startswith(("j", "call", "loop")),
            }
        )
        if len(instrucoes) >= quantidade:
            break

    return {
        "arquitetura": arquitetura,
        "endereco_base": int(endereco_base),
        "deslocamento": deslocamento,
        "quantidade": len(instrucoes),
        "bytes_disponiveis": len(dados) - deslocamento,
        "instrucoes": instrucoes,
    }


def montar_asm(resultado: Dict[str, Any]) -> str:
    """Gera o texto do assembly desmontado."""
    linhas = [
        f"; Arquitetura: {resultado.get('arquitetura')}",
        f"; Endereço base: 0x{int(resultado.get('endereco_base', 0)):X}",
        f"; Deslocamento inicial: 0x{int(resultado.get('deslocamento', 0)):X}",
        f"; Instruções: {resultado.get('quantidade', 0)}",
        "",
    ]
    for instrucao in resultado.get("instrucoes", []):
        linhas.append(
            f"{instrucao['endereco_hex']}:  {instrucao['bytes']:<24} "
            f"{instrucao['mnemonico']} {instrucao['operandos']}".rstrip()
        )
    return "\n".join(linhas)


def calcular_xrefs(instrucoes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mapeia destinos citados nas instruções (saltos e endereços imediatos)."""
    alvos: Dict[int, List[int]] = {}
    for instrucao in instrucoes:
        endereco = int(instrucao.get("endereco", 0))
        operandos = str(instrucao.get("operandos", ""))
        for achado in re.finditer(r"0x([0-9a-fA-F]+)", operandos):
            try:
                alvo = int(achado.group(1), 16)
            except ValueError:
                continue
            if alvo <= 0 or alvo > 0xFFFFFFFFFFFF:
                continue
            alvos.setdefault(alvo, []).append(endereco)
    resultado: List[Dict[str, Any]] = []
    for alvo, origens in sorted(alvos.items()):
        resultado.append(
            {
                "alvo": alvo,
                "alvo_hex": f"0x{alvo:08X}",
                "referencias": len(origens),
                "origens": [f"0x{origem:08X}" for origem in origens[:12]],
            }
        )
    resultado.sort(key=lambda item: -item["referencias"])
    return resultado


def localizar_indice(instrucoes: List[Dict[str, Any]], endereco: int) -> int:
    """Devolve o índice da instrução com endereço igual ou imediatamente superior."""
    if not instrucoes:
        return -1
    enderecos = [int(instrucao["endereco"]) for instrucao in instrucoes]
    indice = bisect.bisect_left(enderecos, int(endereco))
    if indice >= len(enderecos):
        indice = len(enderecos) - 1
    return indice


def _parse_endereco(texto: str, padrao: int = 0) -> int:
    """Aceita ``0x400000``, ``400000h`` ou decimal."""
    limpo = str(texto or "").strip().lower().replace("_", "")
    if not limpo:
        return padrao
    try:
        if limpo.startswith("0x"):
            return int(limpo, 16)
        if limpo.endswith("h"):
            return int(limpo[:-1], 16)
        return int(limpo, 10)
    except ValueError as exc:
        raise ValueError(f"Endereço inválido: {texto}") from exc


@register
class DisassemblerTool(Tool):
    """Ferramenta de desmontagem com Capstone."""

    id = "rev.disassembler"
    name = "Desmontador de Código de Máquina"
    category = "Reverse Engineering"
    description = (
        "Desmonta o código de máquina de executáveis e binários com Capstone, "
        "permite navegar por endereço, mapear referências e exportar o assembly em texto"
    )
    keywords = [
        "desmontador", "disassembler", "capstone", "assembly", "asm", "xref",
        "instruções", "opcodes", "engenharia reversa", "binário",
    ]
    optional_deps = ["capstone"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DisassemblerView(self, parent)


class DisassemblerView(PainelFerramenta):
    """Painel interativo do desmontador."""

    def __init__(self, tool: DisassemblerTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._dados: bytes = b""
        self._resultado: Dict[str, Any] = {}
        self._executando = False
        self._captstone_ok = capstone_disponivel()

        if not self._captstone_ok:
            self.adicionar_aviso(
                "Capstone não está instalado. A interface permanece disponível, mas a "
                "desmontagem exige a biblioteca.\n\n"
                "Instale com: pip install capstone\n\n"
                "Depois de instalar, feche e abra esta ferramenta novamente.",
                destaque=True,
            )
        else:
            self.adicionar_aviso(
                "A desmontagem é estática: o binário não é executado. Endereços exibidos são "
                "virtuais e consideram o endereço base informado, não o carregamento real.",
                destaque=False,
            )

        card, layout = self.adicionar_card("Arquivo e parâmetros")
        linha = QHBoxLayout()
        self.txt_caminho = QLineEdit()
        self.txt_caminho.setPlaceholderText("Selecione o arquivo binário")
        linha.addWidget(self.txt_caminho, stretch=1)
        btn_procurar = QPushButton("Selecionar...")
        btn_procurar.clicked.connect(self._selecionar)
        linha.addWidget(btn_procurar)
        self.btn_desmontar = QPushButton("Desmontar")
        self.btn_desmontar.setProperty("class", "primary")
        self.btn_desmontar.setEnabled(self._captstone_ok)
        self.btn_desmontar.clicked.connect(self._desmontar)
        linha.addWidget(self.btn_desmontar)
        layout.addLayout(linha)

        linha_opcoes = QHBoxLayout()
        linha_opcoes.addWidget(QLabel("Arquitetura:"))
        self.cmb_arquitetura = QComboBox()
        for rotulo, chave in ARQUITETURAS:
            self.cmb_arquitetura.addItem(rotulo, chave)
        self.cmb_arquitetura.setCurrentIndex(1)
        linha_opcoes.addWidget(self.cmb_arquitetura)

        linha_opcoes.addWidget(QLabel("Endereço base:"))
        self.txt_base = QLineEdit("0x400000")
        self.txt_base.setMaximumWidth(120)
        linha_opcoes.addWidget(self.txt_base)

        linha_opcoes.addWidget(QLabel("Deslocamento:"))
        self.txt_offset = QLineEdit("0")
        self.txt_offset.setMaximumWidth(100)
        linha_opcoes.addWidget(self.txt_offset)

        linha_opcoes.addWidget(QLabel("Instruções:"))
        self.spn_quantidade = QSpinBox()
        self.spn_quantidade.setRange(1, LIMITE_INSTRUCOES)
        self.spn_quantidade.setValue(500)
        linha_opcoes.addWidget(self.spn_quantidade)
        linha_opcoes.addStretch()
        layout.addLayout(linha_opcoes)

        linha_acoes = QHBoxLayout()
        self.txt_ir_para = QLineEdit()
        self.txt_ir_para.setPlaceholderText("Endereço para navegar (ex.: 0x401000)")
        self.txt_ir_para.setMaximumWidth(240)
        linha_acoes.addWidget(self.txt_ir_para)
        self.btn_ir = QPushButton("Ir para endereço")
        self.btn_ir.clicked.connect(self._ir_para)
        linha_acoes.addWidget(self.btn_ir)
        self.btn_xrefs = QPushButton("Calcular referências")
        self.btn_xrefs.clicked.connect(self._xrefs)
        linha_acoes.addWidget(self.btn_xrefs)
        self.btn_exportar = QPushButton("Exportar ASM...")
        self.btn_exportar.clicked.connect(self._exportar)
        linha_acoes.addWidget(self.btn_exportar)
        self.btn_copiar = botao_copiar(self._texto_asm, self, "Copiar ASM")
        linha_acoes.addWidget(self.btn_copiar)
        linha_acoes.addStretch()
        layout.addLayout(linha_acoes)

        self.lbl_status = QLabel("Nenhuma desmontagem executada.")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        card_inst, layout_inst = self.adicionar_card("Instruções")
        self.tabela = criar_tabela(["Endereço", "Bytes", "Mnemônico", "Operandos"], self)
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tabela.itemSelectionChanged.connect(self._detalhar_selecao)
        layout_inst.addWidget(self.tabela)

        card_det, layout_det = self.adicionar_card("Assembly e detalhes")
        self.saida = criar_saida_texto(200, self)
        layout_det.addWidget(self.saida)
        self.detalhes = criar_saida_texto(120, self)
        layout_det.addWidget(self.detalhes)

        self.log = adicionar_log_painel(self, "Log da desmontagem")
        self.adicionar_espaco()

    # ------------------------------------------------------------------ ações
    def _texto_asm(self) -> str:
        return self.saida.toPlainText()

    def _selecionar(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar binário", "", "Todos os arquivos (*.*)"
        )
        if caminho:
            self.txt_caminho.setText(caminho)

    def _definir_execucao(self, ativa: bool) -> None:
        self._executando = ativa
        self.btn_desmontar.setEnabled(not ativa and self._captstone_ok)
        self.btn_exportar.setEnabled(not ativa)

    def _desmontar(self) -> None:
        if self._executando:
            return
        if not self._captstone_ok:
            mostrar_erro(
                self,
                "Capstone ausente",
                "A desmontagem requer a biblioteca Capstone.\n\nInstale com: pip install capstone",
            )
            return
        caminho = Path(self.txt_caminho.text().strip())
        if not caminho.is_file():
            mostrar_erro(self, "Arquivo não encontrado", "Selecione um arquivo binário válido.")
            return
        try:
            base = _parse_endereco(self.txt_base.text(), 0x400000)
            deslocamento = _parse_endereco(self.txt_offset.text(), 0)
        except ValueError as exc:
            mostrar_erro(self, "Endereço inválido", exc)
            return
        arquitetura = self.cmb_arquitetura.currentData() or "x86_64"
        quantidade = self.spn_quantidade.value()

        self._definir_execucao(True)
        self.lbl_status.setText(f"Desmontando {caminho.name}...")
        self.log.append_log("INFO", f"Desmontando {caminho} ({arquitetura}).")

        def tarefa(ctx):
            if caminho.stat().st_size > LIMITE_BYTES:
                raise ValueError(f"Arquivo acima do limite de {LIMITE_BYTES // (1024 * 1024)} MB.")
            dados = caminho.read_bytes()
            if ctx.cancelled():
                raise RuntimeError("Operação cancelada.")
            resultado = desmontar(dados, arquitetura, base, deslocamento, quantidade)
            ctx.log("INFO", f"{resultado['quantidade']} instrução(ões) decodificada(s).")
            return resultado

        def concluiu(resultado) -> None:
            self._definir_execucao(False)
            self._resultado = resultado or {}
            self._preencher()
            self.lbl_status.setText(
                f"{formatar_numero(self._resultado.get('quantidade', 0))} instrução(ões) a partir de "
                f"0x{int(self._resultado.get('endereco_base', 0)) + int(self._resultado.get('deslocamento', 0)):08X}."
            )
            self.log.append_log("INFO", "Desmontagem concluída.")

        def falhou(erro: Exception) -> None:
            self._definir_execucao(False)
            self.lbl_status.setText("Falha na desmontagem.")
            self.log.append_log("ERROR", str(erro))
            mostrar_erro(self, "Falha na desmontagem", erro)

        executar_assincrono(self, tarefa, concluiu, falhou)

    def _preencher(self) -> None:
        instrucoes = self._resultado.get("instrucoes", [])
        preencher_tabela(
            self.tabela,
            [
                [item["endereco_hex"], item["bytes"], item["mnemonico"], item["operandos"]]
                for item in instrucoes
            ],
        )
        self.saida.setPlainText(montar_asm(self._resultado))
        self.detalhes.clear()

    def _detalhar_selecao(self) -> None:
        linhas = self.tabela.selectionModel().selectedRows() if self.tabela.selectionModel() else []
        if not linhas:
            return
        indice = linhas[0].row()
        instrucoes = self._resultado.get("instrucoes", [])
        if not (0 <= indice < len(instrucoes)):
            return
        instrucao = instrucoes[indice]
        detalhe = [
            f"Endereço: {instrucao['endereco_hex']}",
            f"Bytes: {instrucao['bytes']}",
            f"Instrução: {instrucao['mnemonico']} {instrucao['operandos']}".rstrip(),
            f"Tamanho: {instrucao['tamanho']} byte(s)",
            f"Grupos: {', '.join(instrucao.get('grupos') or []) or '-'}",
        ]
        if instrucao.get("eh_salto"):
            alvos = re.findall(r"0x([0-9a-fA-F]+)", instrucao.get("operandos", ""))
            if alvos:
                detalhe.append(f"Destino do salto: 0x{int(alvos[0], 16):08X}")
        self.detalhes.setPlainText("\n".join(detalhe))

    def _ir_para(self) -> None:
        if not self._resultado.get("instrucoes"):
            mostrar_erro(self, "Sem desmontagem", "Execute uma desmontagem antes de navegar.")
            return
        try:
            endereco = _parse_endereco(self.txt_ir_para.text(), 0)
        except ValueError as exc:
            mostrar_erro(self, "Endereço inválido", exc)
            return
        if not endereco:
            mostrar_erro(self, "Endereço inválido", "Informe um endereço, por exemplo 0x401000.")
            return
        instrucoes = self._resultado["instrucoes"]
        indice = localizar_indice(instrucoes, endereco)
        self.tabela.selectRow(indice)
        self.tabela.scrollToItem(self.tabela.item(indice, 0))
        self.lbl_status.setText(
            f"Endereço mais próximo: {instrucoes[indice]['endereco_hex']} (índice {indice})."
        )

    def _xrefs(self) -> None:
        if not self._resultado.get("instrucoes"):
            mostrar_erro(self, "Sem desmontagem", "Execute uma desmontagem antes de calcular referências.")
            return
        xrefs = calcular_xrefs(self._resultado["instrucoes"])
        if not xrefs:
            self.detalhes.setPlainText("Nenhuma referência de endereço encontrada nas instruções desmontadas.")
            return
        linhas = ["Referências por destino (mais referenciados primeiro):", ""]
        for item in xrefs[:200]:
            linhas.append(
                f"{item['alvo_hex']}: {item['referencias']} referência(s) "
                f"em {', '.join(item['origens'])}"
            )
        if len(xrefs) > 200:
            linhas.append(f"... e mais {len(xrefs) - 200} destino(s).")
        self.detalhes.setPlainText("\n".join(linhas))
        self.lbl_status.setText(f"{len(xrefs)} destino(s) com referências mapeadas.")

    def _exportar(self) -> None:
        if not self._resultado.get("instrucoes"):
            mostrar_erro(self, "Nada para exportar", "Execute uma desmontagem antes de exportar.")
            return
        sugestao = f"{Path(self.txt_caminho.text().strip()).stem or 'desmontagem'}.asm"
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar assembly", sugestao, "Assembly (*.asm);;Texto (*.txt)")
        if not destino:
            return
        try:
            Path(destino).write_text(montar_asm(self._resultado), encoding="utf-8")
            self.lbl_status.setText(f"Assembly exportado para {destino}.")
            self.log.append_log("INFO", f"Assembly gravado em {destino}.")
        except OSError as exc:
            mostrar_erro(self, "Falha ao exportar", exc)

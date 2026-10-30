"""Análise estática de executáveis PE (Portable Executable).

Usa `pefile` para cabeçalhos, seções, entropia, importações, exportações e
recursos; a assinatura Authenticode é delegada ao módulo de segurança já
existente. Nenhum arquivo é executado: toda a análise é somente leitura.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import DependenciaAusente, formatar_bytes, truncar
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

_log = get_logger("rev.pe_analyzer")

_ASSINATURAS_PACKER = {
    "UPX": "UPX",
    "ASPack": "ASPack",
    "MPRESS": "MPRESS",
    "Themida": "Themida",
    "VMProtect": "VMProtect",
    ".vmp": "VMProtect",
    "Enigma": "Enigma Protector",
    "Obsidium": "Obsidium",
    "PECompact": "PECompact",
    "Petite": "Petite",
    "FSG": "FSG",
    "MEW": "MEW",
    "NeoLite": "NeoLite",
    "NSPack": "NSPack",
    "RLPack": "RLPack",
    "tElock": "tElock",
    "Yoda": "Yoda Protector",
    "EXECryptor": "EXECryptor",
}

_NOMES_SECAO_SUSPEITOS = {
    "upx0", "upx1", "upx2", "upx!", ".aspack", ".adata", ".packed", ".petite",
    ".mpress1", ".mpress2", ".nsp0", ".nsp1", ".neolite", ".themida", ".vmp0",
    ".vmp1", ".enigma1", ".enigma2", ".perplex", ".rlpack", ".boom", ".ccg",
    ".charmve", ".mask", ".mew", ".pin", ".pklst", ".taz", ".y0da", ".z0",
    ".z1", ".ec", ".scrambler", ".taggant",
}

_SECAO_VIRTUAL = 0x1
_SECAO_RAW_DATA = 0x2
_SECAO_EXECUTAVEL = 0x20000000
_SECAO_LEITURA = 0x40000000
_SECAO_GRAVAVEL = 0x80000000


def calcular_entropia(dados: bytes) -> float:
    """Calcula a entropia de Shannon (0 a 8) de um bloco de bytes."""
    if not dados:
        return 0.0
    contagem = Counter(dados)
    total = len(dados)
    entropia = 0.0
    for quantidade in contagem.values():
        probabilidade = quantidade / total
        entropia -= probabilidade * math.log2(probabilidade)
    return round(entropia, 4)


def descrever_flags(caracteristicas: int) -> str:
    """Traduz as características de uma seção em rótulos legíveis."""
    rotulos: List[str] = []
    if caracteristicas & _SECAO_EXECUTAVEL:
        rotulos.append("executável")
    if caracteristicas & _SECAO_GRAVAVEL:
        rotulos.append("gravável")
    if caracteristicas & _SECAO_LEITURA:
        rotulos.append("leitura")
    if caracteristicas & _SECAO_RAW_DATA:
        rotulos.append("dados")
    return ", ".join(rotulos) or "sem flags relevantes"


def _carregar_pe(caminho: Path):
    try:
        import pefile
    except ImportError as exc:
        raise DependenciaAusente("a biblioteca pefile", "pefile", "pefile") from exc
    try:
        return pefile.PE(str(caminho), fast_load=False)
    except pefile.PEFormatError as exc:
        raise ValueError(f"Arquivo não é um PE válido: {exc}") from exc


def _nome_secao(secao: Any) -> str:
    try:
        return secao.Name.rstrip(b"\x00").decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return "?"


def _diagnosticar_packers(
    secoes: List[Dict[str, Any]],
    entrada_secao: str,
    total_importacoes: int,
    total_dlls: int,
) -> Tuple[List[Dict[str, str]], str]:
    """Aplica heurísticas de empacotamento e devolve achados e nome provável."""
    achados: List[Dict[str, str]] = []
    nome_provavel = ""

    for secao in secoes:
        nome = str(secao["nome"]).lower()
        for assinatura, familia in _ASSINATURAS_PACKER.items():
            if assinatura.lower() in nome:
                achados.append(
                    {
                        "indicador": "Nome de seção típico de empacotador",
                        "detalhe": f"Seção {secao['nome']} sugere {familia}",
                    }
                )
                nome_provavel = nome_provavel or familia
                break
        if nome in _NOMES_SECAO_SUSPEITOS and not nome_provavel:
            achados.append(
                {
                    "indicador": "Nome de seção suspeito",
                    "detalhe": f"Seção {secao['nome']} não é padrão de compiladores conhecidos",
                }
            )

    altas = [secao for secao in secoes if secao.get("entropia", 0.0) >= 7.2]
    if altas:
        achados.append(
            {
                "indicador": "Entropia elevada",
                "detalhe": f"{len(altas)} seção(ões) com entropia >= 7,2: "
                + ", ".join(str(secao["nome"]) for secao in altas[:5]),
            }
        )
        nome_provavel = nome_provavel or "Conteúdo compactado ou cifrado"

    if secoes and entrada_secao and entrada_secao == str(secoes[-1]["nome"]):
        achados.append(
            {
                "indicador": "Ponto de entrada na última seção",
                "detalhe": f"EP em {entrada_secao}, arranjo comum em binários empacotados",
            }
        )

    if secoes and total_dlls and total_dlls <= 2 and total_importacoes <= 12:
        achados.append(
            {
                "indicador": "Tabela de importações mínima",
                "detalhe": f"{total_dlls} DLL(s) e {total_importacoes} função(ões) importada(s)",
            }
        )

    gv = [secao for secao in secoes if secao.get("gravavel") and secao.get("executavel")]
    if gv:
        achados.append(
            {
                "indicador": "Seção gravável e executável",
                "detalhe": "Presente em: " + ", ".join(str(secao["nome"]) for secao in gv[:5]),
            }
        )

    return achados, nome_provavel


def _coletar_recursos(pe: Any) -> List[Dict[str, Any]]:
    """Percorre a árvore de recursos e devolve tipo, nome, idioma e tamanho."""
    saida: List[Dict[str, Any]] = []
    raiz = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
    if raiz is None:
        return saida

    def _rotulo(entrada: Any, padrao: str) -> str:
        if getattr(entrada, "name", None) is not None:
            try:
                return str(entrada.name.string.decode("utf-8", errors="replace"))
            except Exception:  # noqa: BLE001
                return padrao
        return f"ID {getattr(entrada, 'id', 0)}"

    def _percorrer(entradas: Any, nivel: int, rotulos: List[str]) -> None:
        for entrada in entradas or []:
            if nivel >= 3:
                continue
            try:
                if hasattr(entrada, "directory"):
                    _percorrer(
                        entrada.directory.entries,
                        nivel + 1,
                        rotulos + [_rotulo(entrada, f"nível {nivel}")],
                    )
                elif hasattr(entrada, "data"):
                    estrutura = entrada.data.struct
                    saida.append(
                        {
                            "tipo": rotulos[0] if rotulos else "?",
                            "nome": rotulos[1] if len(rotulos) > 1 else "-",
                            "idioma": rotulos[2] if len(rotulos) > 2 else "-",
                            "tamanho": int(getattr(estrutura, "Size", 0)),
                        }
                    )
            except Exception:  # noqa: BLE001 - recursos malformados são comuns
                continue

    try:
        _percorrer(raiz.entries, 0, [])
    except Exception as exc:  # noqa: BLE001
        _log.debug("Falha ao percorrer recursos: %s", exc)
    return saida


def _coletar_importacoes(pe: Any) -> List[Dict[str, Any]]:
    saida: List[Dict[str, Any]] = []
    for entrada in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []) or []:
        dll = entrada.dll.decode("utf-8", errors="replace") if isinstance(entrada.dll, bytes) else str(entrada.dll)
        for simbolo in entrada.imports or []:
            nome = simbolo.name.decode("utf-8", errors="replace") if simbolo.name else ""
            saida.append(
                {
                    "dll": dll,
                    "funcao": nome or f"ordinal {simbolo.ordinal}",
                    "ordinal": simbolo.ordinal,
                    "endereco": f"0x{(simbolo.address or 0):08X}",
                }
            )
    return saida


def _coletar_exportacoes(pe: Any) -> List[Dict[str, Any]]:
    saida: List[Dict[str, Any]] = []
    diretorio = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    if diretorio is None:
        return saida
    nome_dll = diretorio.name.decode("utf-8", errors="replace") if getattr(diretorio, "name", None) else ""
    for simbolo in diretorio.symbols or []:
        nome = simbolo.name.decode("utf-8", errors="replace") if getattr(simbolo, "name", None) else ""
        saida.append(
            {
                "dll": nome_dll,
                "nome": nome or f"ordinal {simbolo.ordinal}",
                "ordinal": simbolo.ordinal,
                "endereco": f"0x{(simbolo.address or 0):08X}",
            }
        )
    return saida


def _assinatura(caminho: Path) -> Dict[str, Any]:
    """Consulta a assinatura Authenticode reutilizando o módulo de segurança."""
    try:
        from wintoolbox.tools.security.signature_check.logic import check_authenticode_signature

        return check_authenticode_signature(caminho)
    except Exception as exc:  # noqa: BLE001 - depende de PowerShell
        return {
            "status_label": f"Não verificada: {exc}",
            "is_valid": None,
            "signer": "-",
            "issuer": "-",
            "valid_until": "-",
        }


def analisar_pe(caminho: Path, verificar_assinatura: bool = True) -> Dict[str, Any]:
    """Produz o dossiê estático de um executável PE."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    pe = _carregar_pe(caminho)
    try:
        import pefile

        maquina = int(pe.FILE_HEADER.Machine)
        arquitetura = {
            0x014C: "x86 (32 bits)",
            0x8664: "x86-64 (64 bits)",
            0x01C0: "ARM",
            0x01C4: "ARMv7 (Thumb)",
            0xAA64: "ARM64",
            0x0200: "IA-64",
        }.get(maquina, pefile.MACHINE_TYPE.get(maquina, f"desconhecida (0x{maquina:04X})"))

        caracteristicas = int(pe.FILE_HEADER.Characteristics)
        tipo = "DLL" if caracteristicas & 0x2000 else "Executável"
        if caracteristicas & 0x1000:
            tipo += " (driver de sistema)"

        carimbo = int(pe.FILE_HEADER.TimeDateStamp)
        try:
            data_compilacao = datetime.fromtimestamp(carimbo, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            data_compilacao = f"timestamp inválido ({carimbo})"

        entrada_rva = int(pe.OPTIONAL_HEADER.AddressOfEntryPoint)
        entrada_secao = "?"
        try:
            secao_ep = pe.get_section_by_rva(entrada_rva)
            if secao_ep is not None:
                entrada_secao = _nome_secao(secao_ep)
        except Exception:  # noqa: BLE001
            pass

        secoes: List[Dict[str, Any]] = []
        for secao in pe.sections or []:
            caracteristicas_secao = int(secao.Characteristics)
            entropia = round(float(secao.get_entropy()), 4)
            secoes.append(
                {
                    "nome": _nome_secao(secao),
                    "endereco_virtual": f"0x{int(secao.VirtualAddress):08X}",
                    "tamanho_virtual": int(secao.Misc_VirtualSize),
                    "tamanho_bruto": int(secao.SizeOfRawData),
                    "entropia": entropia,
                    "flags": descrever_flags(caracteristicas_secao),
                    "executavel": bool(caracteristicas_secao & _SECAO_EXECUTAVEL),
                    "gravavel": bool(caracteristicas_secao & _SECAO_GRAVAVEL),
                }
            )

        importacoes = _coletar_importacoes(pe)
        exportacoes = _coletar_exportacoes(pe)
        recursos = _coletar_recursos(pe)
        dlls = sorted({item["dll"] for item in importacoes})
        indicadores, packer = _diagnosticar_packers(
            secoes, entrada_secao, len(importacoes), len(dlls)
        )

        try:
            imphash = pe.get_imphash()
        except Exception:  # noqa: BLE001
            imphash = ""
        try:
            overlay = pe.get_overlay_data_start_offset()
        except Exception:  # noqa: BLE001
            overlay = None
        try:
            rich = pe.parse_rich_header()
        except Exception:  # noqa: BLE001
            rich = None

        dados: Dict[str, Any] = {
            "arquivo": caminho.name,
            "caminho": str(caminho),
            "tamanho_bytes": caminho.stat().st_size,
            "tamanho_legivel": formatar_bytes(caminho.stat().st_size),
            "sha256": "",
            "tipo": tipo,
            "arquitetura": arquitetura,
            "compilado_em": data_compilacao,
            "entrypoint": f"0x{entrada_rva:08X}",
            "entrypoint_secao": entrada_secao,
            "image_base": f"0x{int(pe.OPTIONAL_HEADER.ImageBase):X}",
            "tamanho_imagem": int(pe.OPTIONAL_HEADER.SizeOfImage),
            "subsistema": int(pe.OPTIONAL_HEADER.Subsystem),
            "dll_characteristics": f"0x{int(pe.OPTIONAL_HEADER.DllCharacteristics):04X}",
            "linker": f"{pe.OPTIONAL_HEADER.MajorLinkerVersion}.{pe.OPTIONAL_HEADER.MinorLinkerVersion}",
            "checksum": f"0x{int(pe.OPTIONAL_HEADER.CheckSum):08X}",
            "imphash": imphash,
            "overlay_offset": overlay,
            "rich_header": bool(rich),
            "secoes": secoes,
            "importacoes": importacoes,
            "dlls": dlls,
            "exportacoes": exportacoes,
            "recursos": recursos,
            "indicadores": indicadores,
            "packer_provavel": packer,
            "assinatura": {},
        }
        try:
            from wintoolbox.tools._helpers import hash_arquivo

            dados["sha256"] = hash_arquivo(caminho, "sha256")
        except Exception:  # noqa: BLE001
            pass
        if verificar_assinatura:
            dados["assinatura"] = _assinatura(caminho)
        return dados
    finally:
        try:
            pe.close()
        except Exception:  # noqa: BLE001
            pass


def resumo_texto(dados: Dict[str, Any]) -> str:
    """Laudo resumido em pt-BR a partir do dossiê do PE."""
    assinatura = dados.get("assinatura") or {}
    linhas = [
        f"Arquivo: {dados.get('arquivo')}",
        f"Tipo: {dados.get('tipo')} | Arquitetura: {dados.get('arquitetura')}",
        f"Tamanho: {dados.get('tamanho_legivel')}",
        f"Compilado em: {dados.get('compilado_em')}",
        f"Ponto de entrada: {dados.get('entrypoint')} (seção {dados.get('entrypoint_secao')})",
        f"Image base: {dados.get('image_base')} | Tamanho da imagem: {dados.get('tamanho_imagem')}",
        f"Linker: {dados.get('linker')} | Checksum: {dados.get('checksum')}",
        f"Imphash: {dados.get('imphash') or '-'}",
        f"SHA-256: {dados.get('sha256') or '-'}",
        f"Overlay: {'presente em 0x%X' % dados['overlay_offset'] if dados.get('overlay_offset') else 'ausente'}",
        "",
        f"Seções: {len(dados.get('secoes', []))}",
        f"Importações: {len(dados.get('importacoes', []))} função(ões) de {len(dados.get('dlls', []))} DLL(s)",
        f"Exportações: {len(dados.get('exportacoes', []))}",
        f"Recursos: {len(dados.get('recursos', []))}",
        "",
        f"Empacotador provável: {dados.get('packer_provavel') or 'não identificado'}",
        f"Assinatura: {assinatura.get('status_label') or 'não verificada'}",
    ]
    if assinatura.get("signer"):
        linhas.append(f"Signatário: {assinatura.get('signer')}")
    if assinatura.get("valid_until") and assinatura.get("valid_until") != "-":
        linhas.append(f"Certificado válido até: {assinatura.get('valid_until')}")
    indicadores = dados.get("indicadores", [])
    if indicadores:
        linhas.append("")
        linhas.append("Indicadores de atenção:")
        for item in indicadores:
            linhas.append(f"  {item['indicador']}: {item['detalhe']}")
    return "\n".join(linhas)


def exportar_json(dados: Dict[str, Any], destino: Path) -> Path:
    """Grava o dossiê em JSON."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


@register
class PeAnalyzerTool(Tool):
    """Ferramenta de análise estática de executáveis PE."""

    id = "rev.pe_analyzer"
    name = "Analisador de Executáveis PE"
    category = "Reverse Engineering"
    description = (
        "Inspeciona cabeçalhos, seções, entropia, importações, exportações, recursos e "
        "assinatura Authenticode de arquivos PE, apontando indícios de empacotamento"
    )
    keywords = [
        "pe", "pefile", "executável", "dll", "entropia", "importações", "exports",
        "packer", "assinatura", "authenticode", "engenharia reversa", "análise estática",
    ]
    optional_deps = ["pefile"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PeAnalyzerView(self, parent)


class PeAnalyzerView(PainelFerramenta):
    """Painel interativo da análise de PE."""

    def __init__(self, tool: PeAnalyzerTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._dados: Dict[str, Any] = {}
        self._executando = False

        self.adicionar_aviso(
            "A análise é somente leitura e não executa o arquivo. A verificação de assinatura "
            "depende do PowerShell (Get-AuthenticodeSignature) e pode ficar indisponível fora do Windows.",
            destaque=False,
        )

        card, layout = self.adicionar_card("Arquivo alvo")
        linha = QHBoxLayout()
        self.txt_caminho = QLineEdit()
        self.txt_caminho.setPlaceholderText("Selecione um .exe, .dll, .sys ou .ocx")
        self.txt_caminho.returnPressed.connect(self._analisar)
        linha.addWidget(self.txt_caminho, stretch=1)
        btn_procurar = QPushButton("Selecionar...")
        btn_procurar.clicked.connect(self._selecionar)
        linha.addWidget(btn_procurar)
        self.btn_analisar = QPushButton("Analisar PE")
        self.btn_analisar.setProperty("class", "primary")
        self.btn_analisar.clicked.connect(self._analisar)
        linha.addWidget(self.btn_analisar)
        layout.addLayout(linha)

        linha_acoes = QHBoxLayout()
        self.btn_exportar = QPushButton("Exportar JSON...")
        self.btn_exportar.clicked.connect(self._exportar)
        linha_acoes.addWidget(self.btn_exportar)
        self.btn_copiar = botao_copiar(self._texto_resumo, self, "Copiar laudo")
        linha_acoes.addWidget(self.btn_copiar)
        self.lbl_status = QLabel("Nenhuma análise executada.")
        self.lbl_status.setWordWrap(True)
        linha_acoes.addWidget(self.lbl_status, stretch=1)
        layout.addLayout(linha_acoes)

        card_secoes, layout_secoes = self.adicionar_card("Seções e entropia")
        self.tabela_secoes = criar_tabela(
            ["Seção", "Endereço virtual", "Tam. virtual", "Tam. bruto", "Entropia", "Flags"], self
        )
        self.tabela_secoes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela_secoes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabela_secoes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabela_secoes.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tabela_secoes.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tabela_secoes.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        layout_secoes.addWidget(self.tabela_secoes)

        card_ind, layout_ind = self.adicionar_card("Indicadores de atenção")
        self.tabela_indicadores = criar_tabela(["Indicador", "Detalhe"], self)
        self.tabela_indicadores.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela_indicadores.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout_ind.addWidget(self.tabela_indicadores)

        card_imp, layout_imp = self.adicionar_card("Importações")
        self.tabela_importacoes = criar_tabela(["DLL", "Função", "Ordinal", "Endereço"], self)
        self.tabela_importacoes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabela_importacoes.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabela_importacoes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabela_importacoes.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout_imp.addWidget(self.tabela_importacoes)

        card_exp, layout_exp = self.adicionar_card("Exportações")
        self.tabela_exportacoes = criar_tabela(["Nome", "Ordinal", "Endereço"], self)
        self.tabela_exportacoes.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela_exportacoes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabela_exportacoes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout_exp.addWidget(self.tabela_exportacoes)

        card_rec, layout_rec = self.adicionar_card("Recursos")
        self.tabela_recursos = criar_tabela(["Tipo", "Nome", "Idioma", "Tamanho"], self)
        for coluna in range(3):
            self.tabela_recursos.horizontalHeader().setSectionResizeMode(coluna, QHeaderView.ResizeToContents)
        self.tabela_recursos.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        layout_rec.addWidget(self.tabela_recursos)

        card_resumo, layout_resumo = self.adicionar_card("Laudo")
        self.saida = criar_saida_texto(260, self)
        layout_resumo.addWidget(self.saida)

        self.log = adicionar_log_painel(self, "Log da análise")
        self.adicionar_espaco()

    def _texto_resumo(self) -> str:
        return self.saida.toPlainText()

    def _selecionar(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar executável",
            "",
            "Executáveis (*.exe *.dll *.sys *.ocx *.scr *.cpl);;Todos os arquivos (*.*)",
        )
        if caminho:
            self.txt_caminho.setText(caminho)

    def _definir_execucao(self, ativa: bool) -> None:
        self._executando = ativa
        for botao in (self.btn_analisar, self.btn_exportar):
            botao.setEnabled(not ativa)

    def _analisar(self) -> None:
        if self._executando:
            return
        texto = self.txt_caminho.text().strip()
        if not texto:
            mostrar_erro(self, "Arquivo não informado", "Selecione um arquivo PE para analisar.")
            return
        caminho = Path(texto)
        if not caminho.is_file():
            mostrar_erro(self, "Arquivo não encontrado", f"O caminho informado não existe: {caminho}")
            return

        self._definir_execucao(True)
        self.lbl_status.setText(f"Analisando {caminho.name}...")
        self.saida.clear()
        self.log.append_log("INFO", f"Analisando {caminho}.")

        def tarefa(ctx):
            ctx.log("INFO", "Lendo cabeçalhos e seções.")
            dados = analisar_pe(caminho, verificar_assinatura=True)
            ctx.log(
                "INFO",
                f"{len(dados.get('secoes', []))} seção(ões), "
                f"{len(dados.get('importacoes', []))} importação(ões).",
            )
            return dados

        def concluiu(dados) -> None:
            self._definir_execucao(False)
            self._dados = dados or {}
            self._preencher()
            self.lbl_status.setText(
                f"{self._dados.get('arquivo', caminho.name)}: {self._dados.get('tipo')} "
                f"{self._dados.get('arquitetura')}."
            )
            self.log.append_log("INFO", "Análise concluída.")

        def falhou(erro: Exception) -> None:
            self._definir_execucao(False)
            self.lbl_status.setText("Falha na análise.")
            self.log.append_log("ERROR", str(erro))
            mostrar_erro(self, "Falha ao analisar o PE", erro)

        executar_assincrono(self, tarefa, concluiu, falhou)

    def _preencher(self) -> None:
        dados = self._dados
        preencher_tabela(
            self.tabela_secoes,
            [
                [
                    secao.get("nome", ""),
                    secao.get("endereco_virtual", ""),
                    secao.get("tamanho_virtual", 0),
                    secao.get("tamanho_bruto", 0),
                    secao.get("entropia", 0.0),
                    secao.get("flags", ""),
                ]
                for secao in dados.get("secoes", [])
            ],
        )
        preencher_tabela(
            self.tabela_indicadores,
            [[item.get("indicador", ""), item.get("detalhe", "")] for item in dados.get("indicadores", [])],
        )
        preencher_tabela(
            self.tabela_importacoes,
            [
                [item.get("dll", ""), item.get("funcao", ""), item.get("ordinal", ""), item.get("endereco", "")]
                for item in dados.get("importacoes", [])[:3000]
            ],
        )
        preencher_tabela(
            self.tabela_exportacoes,
            [
                [item.get("nome", ""), item.get("ordinal", ""), item.get("endereco", "")]
                for item in dados.get("exportacoes", [])
            ],
        )
        preencher_tabela(
            self.tabela_recursos,
            [
                [item.get("tipo", ""), item.get("nome", ""), item.get("idioma", ""), item.get("tamanho", 0)]
                for item in dados.get("recursos", [])[:2000]
            ],
        )
        self.saida.setPlainText(resumo_texto(dados))

    def _exportar(self) -> None:
        if not self._dados:
            mostrar_erro(self, "Nada para exportar", "Execute uma análise antes de exportar.")
            return
        sugestao = f"pe_{Path(self._dados.get('arquivo', 'analise')).stem}.json"
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar laudo", sugestao, "JSON (*.json)")
        if not destino:
            return
        try:
            final = exportar_json(self._dados, Path(destino))
            self.lbl_status.setText(f"Laudo exportado para {final}.")
            self.log.append_log("INFO", f"Laudo gravado em {final}.")
        except OSError as exc:
            mostrar_erro(self, "Falha ao exportar", exc)

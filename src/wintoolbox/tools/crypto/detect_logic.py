"""Núcleo puro de detecção de esteganografia LSB (sem Qt).

Reúne três famílias de testes clássicos de esteganalise, todos implementados
com Pillow e numpy:

* **Qui-quadrado de Westfeld**: compara as frequências dos pares de valores
  (``2i``, ``2i+1``). Quando os bits menos significativos são aleatorizados, os
  pares tendem a se equalizar e a probabilidade de embutimento sobe.
* **Análise RS de Fridrich**: aplica inversões no LSB de grupos de quatro
  amostras e compara a variação do grupo. A diferença entre as contagens
  "regulares" e "singulares" nos dois sentidos permite estimar a taxa de
  embutimento sem precisar da imagem original.
* **Pares de amostra**: mede a distribuição de paridade dos pares vizinhos.
  Quanto mais uniforme, mais aleatórios estão os bits menos significativos.

Além dos três testes, o módulo reconhece a assinatura ``WTBXSTEG`` da
ferramenta de esteganografia do próprio WinToolbox, o que dá um veredito
definitivo quando a carga foi criada aqui.
"""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from wintoolbox.tools.crypto import stegano_logic

LADO_MAXIMO_PADRAO = 1400
NIVEIS = ("assinatura", "alto", "moderado", "baixo")
ROTULOS_NIVEL = {
    "assinatura": "Assinatura WTBXSTEG detectada",
    "alto": "Suspeita alta",
    "moderado": "Suspeita moderada",
    "baixo": "Sem indícios relevantes",
}
DESCRICAO_METODOS = (
    "Qui-quadrado: razão estatística/graus e probabilidade de Westfeld; a razão "
    "tende a 1 com LSBs aleatórios. "
    "RS: taxa estimada de embutimento (0 a 1). "
    "Pares de amostra: índice de aleatoriedade da paridade dos pares vizinhos (0 a 1)."
)


# ---------------------------------------------------------------------------
# Funções especiais (sem scipy)
# ---------------------------------------------------------------------------
def _gama_serie(a: float, x: float) -> float:
    """Série de P(a, x), a função gama incompleta inferior regularizada."""
    if x <= 0.0:
        return 0.0
    termo = 1.0 / a
    soma = termo
    ap = a
    for _ in range(1000):
        ap += 1.0
        termo *= x / ap
        soma += termo
        if abs(termo) < abs(soma) * 1e-15:
            break
    return soma * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gama_fracao_continuada(a: float, x: float) -> float:
    """Fração continuada de Q(a, x), a função gama incompleta superior regularizada."""
    infinito = 1e300
    b = x + 1.0 - a
    c = 1.0 / infinito
    d = 1.0 / b if b != 0.0 else 1.0 / 1e-300
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def _gama_superior_regularizada(a: float, x: float) -> float:
    """Q(a, x) = 1 - P(a, x), sem depender de scipy."""
    if x <= 0.0:
        return 1.0
    if x < a + 1.0:
        return max(0.0, min(1.0, 1.0 - _gama_serie(a, x)))
    return max(0.0, min(1.0, _gama_fracao_continuada(a, x)))


def probabilidade_qui_quadrado(estatistica: float, graus_liberdade: int) -> float:
    """Probabilidade de embutimento de Westfeld (cauda superior da qui-quadrado)."""
    if graus_liberdade <= 0:
        return 0.0
    valor = _gama_superior_regularizada(graus_liberdade / 2.0, max(0.0, estatistica) / 2.0)
    return max(0.0, min(1.0, valor))


# ---------------------------------------------------------------------------
# Testes por canal
# ---------------------------------------------------------------------------
def qui_quadrado_canal(canal: Any) -> Dict[str, Any]:
    """Teste de Westfeld sobre um canal de 8 bits."""
    import numpy as np

    valores = np.asarray(canal, dtype=np.uint8).reshape(-1)
    if valores.size == 0:
        return {
            "estatistica": 0.0,
            "graus_liberdade": 0,
            "probabilidade": 0.0,
            "pares_avaliados": 0,
            "razao": 0.0,
        }
    histograma = np.bincount(valores, minlength=256).astype(np.float64)
    pares_a = histograma[0::2]
    pares_b = histograma[1::2]
    somas = pares_a + pares_b
    validos = somas > 0
    if not np.any(validos):
        return {
            "estatistica": 0.0,
            "graus_liberdade": 0,
            "probabilidade": 0.0,
            "pares_avaliados": 0,
            "razao": 0.0,
        }
    diferencas = pares_a[validos] - pares_b[validos]
    somas_validas = somas[validos]
    estatistica = float(np.sum((diferencas * diferencas) / somas_validas))
    graus = int(np.count_nonzero(validos))
    probabilidade = probabilidade_qui_quadrado(estatistica, graus)
    # A razão estatística/graus é mais informativa que o valor-p: sob LSB
    # aleatorizado ela se aproxima de 1; em imagens suaves fica muito acima.
    razao = estatistica / graus if graus else 0.0
    return {
        "estatistica": estatistica,
        "graus_liberdade": graus,
        "probabilidade": probabilidade,
        "pares_avaliados": graus,
        "razao": razao,
    }


def _inverter_lsb(valores: Any, sentido: int) -> Any:
    """Aplica F1 (sentido 1) ou F-1 (sentido -1) no LSB dos valores."""
    import numpy as np

    pares = valores % 2 == 0
    if sentido > 0:
        deslocamento = np.where(pares, 1, -1)
    else:
        deslocamento = np.where(pares, -1, 1)
    return np.clip(valores + deslocamento, 0, 255)


def _discriminante(grupos: Any) -> Any:
    import numpy as np

    return np.abs(np.diff(grupos, axis=1)).sum(axis=1)


def rs_analise(canal: Any, mascara: Sequence[int] = (0, 1, 1, 0)) -> Dict[str, Any]:
    """Análise RS de Fridrich com máscara de 4 posições.

    A taxa é estimada pela relação entre as diferenças regular-singular nos dois
    sentidos de inversão. Valores próximos de 0 indicam LSBs originais; valores
    próximos de 1 indicam LSBs aleatorizados.
    """
    import numpy as np

    matriz = np.asarray(canal, dtype=np.uint8)
    if matriz.ndim != 2 or matriz.size == 0:
        return {"regular": 0, "singular": 0, "regular_neg": 0, "singular_neg": 0, "taxa": 0.0, "grupos": 0}

    altura, largura = matriz.shape
    blocos: List[Any] = []
    if largura >= 4:
        colunas = largura // 4
        blocos.append(matriz[:, : colunas * 4].reshape(altura, colunas, 4))
    if altura >= 4:
        linhas = altura // 4
        bloco_vertical = matriz[: linhas * 4, :].reshape(linhas, 4, largura)
        blocos.append(bloco_vertical.transpose(0, 2, 1))
    if not blocos:
        return {"regular": 0, "singular": 0, "regular_neg": 0, "singular_neg": 0, "taxa": 0.0, "grupos": 0}

    grupos = np.concatenate([bloco.reshape(-1, 4) for bloco in blocos]).astype(np.int16)
    mascara_arr = np.asarray(mascara, dtype=bool)
    if mascara_arr.size != 4:
        mascara_arr = np.array([0, 1, 1, 0], dtype=bool)
    ativos = np.repeat(mascara_arr.reshape(1, 4), grupos.shape[0], axis=0)

    base = _discriminante(grupos)
    invertido_1 = grupos.copy()
    invertido_1[ativos] = _inverter_lsb(invertido_1[ativos], 1)
    invertido_menos_1 = grupos.copy()
    invertido_menos_1[ativos] = _inverter_lsb(invertido_menos_1[ativos], -1)

    variacao_1 = _discriminante(invertido_1)
    variacao_menos_1 = _discriminante(invertido_menos_1)

    regular = int(np.count_nonzero(variacao_1 > base))
    singular = int(np.count_nonzero(variacao_1 < base))
    regular_neg = int(np.count_nonzero(variacao_menos_1 > base))
    singular_neg = int(np.count_nonzero(variacao_menos_1 < base))

    d0 = regular - singular
    d1 = regular_neg - singular_neg
    denominador = d0 + d1
    if denominador == 0:
        taxa = 0.0
    else:
        taxa = (d1 - d0) / denominador
    taxa = max(0.0, min(1.0, taxa))
    return {
        "regular": regular,
        "singular": singular,
        "regular_neg": regular_neg,
        "singular_neg": singular_neg,
        "grupos": int(grupos.shape[0]),
        "taxa": taxa,
    }


def pares_amostra(canal: Any) -> Dict[str, Any]:
    """Análise de pares de amostra pela distribuição de paridade de vizinhos.

    Conta os pares horizontais e verticais nas quatro classes de paridade e
    devolve a homogeneidade observada e o índice normalizado de aleatoriedade.
    Em pares de uma imagem natural os vizinhos costumam ter a mesma paridade;
    com LSBs aleatórios a paridade se uniformiza.
    """
    import numpy as np

    matriz = np.asarray(canal, dtype=np.uint8)
    if matriz.ndim != 2:
        return {"pares": 0, "indice": 0.0, "homogeneidade": 0.0, "classes": (0, 0, 0, 0)}
    pares_u = []
    pares_v = []
    if matriz.shape[1] >= 2:
        pares_u.append(matriz[:, :-1].reshape(-1))
        pares_v.append(matriz[:, 1:].reshape(-1))
    if matriz.shape[0] >= 2:
        pares_u.append(matriz[:-1, :].reshape(-1))
        pares_v.append(matriz[1:, :].reshape(-1))
    if not pares_u:
        return {"pares": 0, "indice": 0.0, "homogeneidade": 0.0, "classes": (0, 0, 0, 0)}

    u = np.concatenate(pares_u).astype(np.int32)
    v = np.concatenate(pares_v).astype(np.int32)
    u_par = (u & 1) == 0
    v_par = (v & 1) == 0
    ee = int(np.count_nonzero(u_par & v_par))
    oo = int(np.count_nonzero(~u_par & ~v_par))
    eo = int(np.count_nonzero(u_par & ~v_par))
    oe = int(np.count_nonzero(~u_par & v_par))
    total = ee + oo + eo + oe
    if total == 0:
        return {"pares": 0, "indice": 0.0, "homogeneidade": 0.0, "classes": (0, 0, 0, 0)}

    entropia = 0.0
    for contagem in (ee, oo, eo, oe):
        if contagem > 0:
            p = contagem / total
            entropia -= p * math.log2(p)
    homogeneidade = (ee + oo) / total
    # Em pares vizinhos de uma imagem natural os dois elementos costumam ter a
    # mesma paridade (homogeneidade acima de 0,5). Com LSBs aleatórios a
    # paridade se uniformiza e a homogeneidade cai para 0,5. O índice abaixo
    # normaliza essa queda para a faixa 0 a 1.
    indice = max(0.0, min(1.0, 2.0 * (1.0 - homogeneidade)))
    return {
        "pares": total,
        "indice": indice,
        "entropia": min(1.0, entropia / 2.0),
        "homogeneidade": homogeneidade,
        "classes": (ee, oo, eo, oe),
    }


# ---------------------------------------------------------------------------
# Orquestração e laudo
# ---------------------------------------------------------------------------
def carregar_canais(caminho: Path, lado_maximo: int = LADO_MAXIMO_PADRAO) -> Dict[str, Any]:
    """Carrega a imagem em RGB, reduzindo o lado maior para manter a análise rápida."""
    from PIL import Image
    import numpy as np

    caminho = Path(caminho)
    with Image.open(caminho) as imagem:
        formato = (imagem.format or "").upper()
        largura, altura = imagem.size
        if formato not in ("PNG", "BMP"):
            raise ValueError(
                f"Formato {formato or 'desconhecido'} não analisado. "
                "A detecção LSB desta ferramenta cobre PNG e BMP."
            )
        if lado_maximo and max(largura, altura) > lado_maximo:
            imagem.thumbnail((lado_maximo, lado_maximo), Image.Resampling.LANCZOS)
        reduzida = imagem.convert("RGB")
        matriz = np.array(reduzida, dtype=np.uint8)
        largura_analisada, altura_analisada = reduzida.size
    canais = {
        "R": matriz[:, :, 0],
        "G": matriz[:, :, 1],
        "B": matriz[:, :, 2],
    }
    return {
        "formato": formato,
        "largura": largura,
        "altura": altura,
        "largura_analisada": largura_analisada,
        "altura_analisada": altura_analisada,
        "canais": canais,
    }


def analisar_arquivo(
    caminho: Path,
    lado_maximo: int = LADO_MAXIMO_PADRAO,
    incluir_rs: bool = True,
) -> Dict[str, Any]:
    """Executa os três testes em uma imagem e monta o resultado estruturado."""
    caminho = Path(caminho)
    dados = carregar_canais(caminho, lado_maximo)
    por_canal: List[Dict[str, Any]] = []
    for nome, matriz in dados["canais"].items():
        resultado_chi = qui_quadrado_canal(matriz)
        resultado_rs = rs_analise(matriz) if incluir_rs else {"taxa": 0.0, "grupos": 0}
        resultado_spa = pares_amostra(matriz)
        por_canal.append(
            {
                "canal": nome,
                "qui_estatistica": resultado_chi["estatistica"],
                "qui_graus": resultado_chi["graus_liberdade"],
                "qui_razao": resultado_chi["razao"],
                "probabilidade": resultado_chi["probabilidade"],
                "rs_taxa": resultado_rs["taxa"],
                "rs_grupos": resultado_rs.get("grupos", 0),
                "spa_indice": resultado_spa["indice"],
                "spa_homogeneidade": resultado_spa["homogeneidade"],
            }
        )

    assinatura = stegano_logic.ler_cabecalho_de_arquivo(caminho)
    probabilidade = max(item["probabilidade"] for item in por_canal) if por_canal else 0.0
    razao_qui = max(item["qui_razao"] for item in por_canal) if por_canal else 0.0
    rs_taxa = max(item["rs_taxa"] for item in por_canal) if por_canal else 0.0
    spa_indice = (
        sum(item["spa_indice"] for item in por_canal) / len(por_canal) if por_canal else 0.0
    )

    if assinatura is not None:
        nivel = "assinatura"
    elif rs_taxa >= 0.60:
        nivel = "alto"
    elif rs_taxa >= 0.22 or (rs_taxa >= 0.15 and razao_qui <= 1.3):
        nivel = "moderado"
    else:
        nivel = "baixo"

    resultado: Dict[str, Any] = {
        "caminho": str(caminho),
        "nome": caminho.name,
        "formato": dados["formato"],
        "largura": dados["largura"],
        "altura": dados["altura"],
        "largura_analisada": dados["largura_analisada"],
        "altura_analisada": dados["altura_analisada"],
        "canais": por_canal,
        "probabilidade": probabilidade,
        "razao_qui": razao_qui,
        "rs_taxa": rs_taxa,
        "spa_indice": spa_indice,
        "assinatura": assinatura,
        "nivel": nivel,
        "rotulo": ROTULOS_NIVEL[nivel],
        "momento": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }
    resultado["laudo"] = gerar_laudo(resultado)
    return resultado


def _formatar_numero(valor: float, casas: int = 3) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def gerar_laudo(resultado: Dict[str, Any]) -> str:
    """Gera o laudo textual em pt-BR de um resultado de análise."""
    linhas: List[str] = []
    linhas.append("=" * 72)
    linhas.append("LAUDO DE ANÁLISE DE ESTEGANOGRAFIA LSB")
    linhas.append("=" * 72)
    linhas.append(f"Arquivo analisado : {resultado['caminho']}")
    linhas.append(f"Formato           : {resultado['formato']}")
    linhas.append(
        f"Dimensões         : {resultado['largura']} x {resultado['altura']} pixels"
    )
    if (
        resultado.get("largura_analisada") != resultado.get("largura")
        or resultado.get("altura_analisada") != resultado.get("altura")
    ):
        linhas.append(
            "Amostra analisada : "
            f"{resultado['largura_analisada']} x {resultado['altura_analisada']} pixels (redução técnica)"
        )
    linhas.append(f"Data da análise   : {resultado['momento']}")
    linhas.append("")
    linhas.append("1. Verificação da assinatura WTBXSTEG")
    assinatura = resultado.get("assinatura")
    if assinatura:
        linhas.append("   Resultado: assinatura encontrada no cabeçalho LSB.")
        linhas.append(f"   Tamanho declarado da carga: {assinatura['tamanho']} bytes")
        linhas.append(f"   Profundidade declarada    : {assinatura['profundidade']} bit(s) por canal")
        linhas.append(
            "   Proteção por senha        : " + ("sim" if assinatura["protegido"] else "não")
        )
        linhas.append(f"   Carga textual declarada   : {'sim' if assinatura['texto'] else 'não'}")
        linhas.append(f"   SHA-256 declarado         : {assinatura['sha256']}")
        linhas.append(
            "   Coerência do cabeçalho    : " + ("consistente" if assinatura["coerente"] else "inconsistente")
        )
    else:
        linhas.append("   Resultado: nenhuma assinatura WTBXSTEG encontrada.")
    linhas.append("")
    linhas.append("2. Testes estatísticos por canal")
    linhas.append(
        "   Canal | Qui-quadrado (razão) | Qui-quadrado (prob.) | RS (taxa) | Pares de amostra (índice)"
    )
    for item in resultado["canais"]:
        linhas.append(
            f"   {item['canal']}     | {_formatar_numero(item['qui_razao'])}"
            f"               | {_formatar_numero(item['probabilidade'])}"
            f"               | {_formatar_numero(item['rs_taxa'])}"
            f"    | {_formatar_numero(item['spa_indice'])}"
        )
    linhas.append("")
    linhas.append("3. Consolidado")
    linhas.append(f"   Razão máxima do qui-quadrado        : {_formatar_numero(resultado['razao_qui'])}")
    linhas.append(f"   Probabilidade máxima (qui-quadrado) : {_formatar_numero(resultado['probabilidade'])}")
    linhas.append(f"   Taxa estimada máxima (RS)           : {_formatar_numero(resultado['rs_taxa'])}")
    linhas.append(f"   Índice médio de pares de amostra    : {_formatar_numero(resultado['spa_indice'])}")
    linhas.append(f"   Classificação final                 : {resultado['rotulo']}")
    linhas.append("")
    linhas.append("4. Interpretação")
    if resultado["nivel"] == "assinatura":
        linhas.append(
            "   O arquivo contém uma carga criada pela ferramenta de esteganografia do"
        )
        linhas.append(
            "   WinToolbox. Use a ferramenta crypto.stegano no modo de extração para"
        )
        linhas.append("   recuperar o conteúdo; se solicitado, informe a senha.")
    elif resultado["nivel"] == "alto":
        linhas.append(
            "   Os três indicadores apontam para bits menos significativos alterados de"
        )
        linhas.append(
            "   forma compatível com embutimento de dados. Recomenda-se examinar o arquivo"
        )
        linhas.append("   com a ferramenta de extração e comparar com a origem conhecida.")
    elif resultado["nivel"] == "moderado":
        linhas.append(
            "   Há indícios parciais de alteração dos LSBs. Imagens com muito ruído,"
        )
        linhas.append(
            "   texturas finas ou pós-processamento intenso podem produzir o mesmo efeito;"
        )
        linhas.append("   confirme com uma cópia autêntica do arquivo sempre que possível.")
    else:
        linhas.append(
            "   Não foram encontrados indícios estatísticos relevantes de embutimento LSB."
        )
    linhas.append("")
    linhas.append("5. Métodos e limitações")
    linhas.append(f"   {DESCRICAO_METODOS}")
    linhas.append(
        "   A razão do qui-quadrado (estatística dividida pelos graus de liberdade)"
    )
    linhas.append(
        "   tende a 1 quando os LSBs são aleatórios e fica bem acima disso em imagens"
    )
    linhas.append(
        "   suaves; por isso ela pesa mais que o valor-p na classificação final."
    )
    linhas.append(
        "   O índice de pares de amostra alto isoladamente não confirma embutimento:"
    )
    linhas.append(
        "   imagens com textura fina ou ruído já apresentam paridade uniforme. A"
    )
    linhas.append(
        "   confirmação vem da taxa RS, que é insensível a esse efeito."
    )
    linhas.append(
        "   Os testes são estatísticos: não provam a ausência de dados, apenas indicam"
    )
    linhas.append(
        "   a probabilidade de os LSBs terem sido aleatorizados."
    )
    linhas.append("=" * 72)
    return "\n".join(linhas)


def analisar_lote(
    caminhos: Sequence[Path],
    lado_maximo: int = LADO_MAXIMO_PADRAO,
    incluir_rs: bool = True,
    progresso: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """Analisa vários arquivos e devolve os resultados individuais e o laudo consolidado."""
    resultados: List[Dict[str, Any]] = []
    total = len(caminhos)
    for indice, caminho in enumerate(caminhos, start=1):
        if progresso is not None:
            progresso(indice - 1, total, f"Analisando {Path(caminho).name}...")
        try:
            resultados.append(analisar_arquivo(caminho, lado_maximo, incluir_rs))
        except Exception as exc:  # cada arquivo falha isoladamente
            resultados.append(
                {
                    "caminho": str(caminho),
                    "nome": Path(caminho).name,
                    "erro": str(exc),
                    "nivel": "erro",
                    "rotulo": "Falha na análise",
                    "canais": [],
                    "probabilidade": 0.0,
                    "rs_taxa": 0.0,
                    "spa_indice": 0.0,
                    "assinatura": None,
                    "laudo": f"Falha ao analisar {caminho}:\n{exc}",
                }
            )
        if progresso is not None:
            progresso(indice, total, f"Concluído: {Path(caminho).name}")

    validos = [item for item in resultados if item.get("nivel") != "erro"]
    resumo = {
        "total": total,
        "analisados": len(validos),
        "assinatura": sum(1 for item in validos if item["nivel"] == "assinatura"),
        "alto": sum(1 for item in validos if item["nivel"] == "alto"),
        "moderado": sum(1 for item in validos if item["nivel"] == "moderado"),
        "baixo": sum(1 for item in validos if item["nivel"] == "baixo"),
        "erros": total - len(validos),
    }
    cabecalho = [
        "LAUDO CONSOLIDADO DE ANÁLISE DE ESTEGANOGRAFIA LSB",
        f"Arquivos analisados: {resumo['analisados']} de {total}",
        f"Assinatura WTBXSTEG: {resumo['assinatura']} | Suspeita alta: {resumo['alto']} | "
        f"Moderada: {resumo['moderado']} | Sem indícios: {resumo['baixo']} | Erros: {resumo['erros']}",
        "",
    ]
    corpo = [item["laudo"] for item in resultados]
    return {
        "resultados": resultados,
        "resumo": resumo,
        "laudo": "\n".join(cabecalho) + "\n\n".join(corpo),
    }


__all__ = [
    "DESCRICAO_METODOS",
    "LADO_MAXIMO_PADRAO",
    "NIVEIS",
    "ROTULOS_NIVEL",
    "analisar_arquivo",
    "analisar_lote",
    "carregar_canais",
    "gerar_laudo",
    "pares_amostra",
    "probabilidade_qui_quadrado",
    "qui_quadrado_canal",
    "rs_analise",
]

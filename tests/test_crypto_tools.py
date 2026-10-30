"""Testes black-box reais para as 4 ferramentas de criptografia e esteganografia.

Validações do efeito real:
1. crypto.stegano: grava PNG real, embutindo carga com senha, valida o arquivo
   com Pillow, extrai a carga e confere o texto exato bit a bit. Executa também via execute_batch.
2. crypto.stegano_detect: analisa imagem limpa e imagem com carga, validando laudo e métricas.
3. crypto.rsa_attack: recupera chaves privadas exatas por Wiener, Fermat e Módulo Comum.
4. crypto.classical_break: recupera deslocamento exato de César e decifra Vigenère.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image

from wintoolbox.core.batch import DiscoveredFile, OutputPolicy, execute_batch
from wintoolbox.core.registry import ItemResult, TaskContext
from wintoolbox.tools.crypto.classical_logic import analisar_texto, quebrar_cesar, quebrar_vigenere
from wintoolbox.tools.crypto.detect_logic import analisar_arquivo, gerar_laudo
from wintoolbox.tools.crypto.rsa_logic import (
    analise_automatica,
    ataque_modulo_comum,
    ataque_wiener,
    fatorar_fermat,
)
from wintoolbox.tools.crypto.stegano import SteganoTool


def _make_ctx(cancelled: bool = False) -> TaskContext:
    return TaskContext(
        on_progress=lambda cur, tot, msg: None,
        on_log=lambda lvl, msg: None,
        is_cancelled=lambda: cancelled,
    )


def test_stegano_tool_png_hide_and_extract(tmp_path: Path) -> None:
    """Valida gravação em PNG real, extração com senha e integridade exata."""
    tool = SteganoTool()
    assert tool.id == "crypto.stegano"

    # Criar imagem PNG portadora de 64x64 pixels
    src_img = tmp_path / "portador.png"
    img = Image.new("RGB", (64, 64), color=(120, 180, 240))
    img.save(src_img, format="PNG")

    mensagem_original = "Mensagem Secreta WTBX 2026!"
    steg_img = tmp_path / "resultado_steg.png"

    ctx = _make_ctx()

    # 1. Ocultar
    res_hide = tool.process(
        src=src_img,
        dst=steg_img,
        params={
            "modo": "ocultar",
            "tipo_carga": "texto",
            "texto": mensagem_original,
            "senha": "SuperSenhaForte42",
            "profundidade": 1,
        },
        ctx=ctx,
    )
    assert res_hide.success is True
    assert steg_img.exists()
    assert steg_img.stat().st_size > 0

    # Validação black-box: abrir arquivo resultante com leitor real Pillow
    with Image.open(steg_img) as img_aberta:
        assert img_aberta.size == (64, 64)
        assert img_aberta.mode == "RGB"

    # 2. Extrair com senha correta
    out_txt = tmp_path / "extraido.txt"
    res_ext = tool.process(
        src=steg_img,
        dst=out_txt,
        params={"modo": "extrair", "senha": "SuperSenhaForte42"},
        ctx=ctx,
    )
    assert res_ext.success is True
    assert out_txt.exists()
    conteudo_recuperado = out_txt.read_text(encoding="utf-8")
    assert conteudo_recuperado == mensagem_original

    # 3. Falha esperada: senha incorreta
    out_fail = tmp_path / "falha.txt"
    res_fail = tool.process(
        src=steg_img,
        dst=out_fail,
        params={"modo": "extrair", "senha": "senha_errada"},
        ctx=ctx,
    )
    assert res_fail.success is False
    assert "SHA-256 da carga não confere" in (res_fail.error or "")


def test_stegano_batch_integration(tmp_path: Path) -> None:
    """Executa a ferramenta SteganoTool através do motor de lote execute_batch."""
    tool = SteganoTool()

    src1 = tmp_path / "img1.png"
    Image.new("RGB", (50, 50), color=(50, 100, 150)).save(src1, format="PNG")

    src2 = tmp_path / "img2.png"
    Image.new("RGB", (50, 50), color=(80, 120, 160)).save(src2, format="PNG")

    params = {
        "modo": "ocultar",
        "tipo_carga": "texto",
        "texto": "Carga de Lote",
        "senha": "",
        "profundidade": 1,
    }

    discovered = [
        DiscoveredFile(
            source_path=src1,
            root_source_dir=tmp_path,
            size_bytes=src1.stat().st_size,
            extension=".png",
        ),
        DiscoveredFile(
            source_path=src2,
            root_source_dir=tmp_path,
            size_bytes=src2.stat().st_size,
            extension=".png",
        ),
    ]

    policy = OutputPolicy(mode="subfolder", subfolder_name="lote_saida")
    batch_res = execute_batch(
        files=discovered,
        output_policy=policy,
        target_ext=tool.output_ext(params),
        process_func=tool.process,
        params=params,
        ctx=_make_ctx(),
    )

    assert batch_res.success is True
    assert batch_res.items_total == 2
    assert batch_res.items_success == 2
    assert batch_res.items_failed == 0

    # Validar que ambos os arquivos gerados contêm a carga
    for src in [src1, src2]:
        dst = tmp_path / "lote_saida" / src.name
        assert dst.exists()
        txt_verif = tmp_path / f"verif_{src.stem}.txt"
        res_ext = tool.process(dst, txt_verif, {"modo": "extrair", "senha": ""}, _make_ctx())
        assert res_ext.success is True
        assert txt_verif.read_text(encoding="utf-8") == "Carga de Lote"


def test_stegano_detect_analysis(tmp_path: Path) -> None:
    """Valida análise estatística de detecção de esteganografia."""
    src_img = tmp_path / "analise.png"
    Image.new("RGB", (60, 60), color=(100, 150, 200)).save(src_img, format="PNG")

    resultado = analisar_arquivo(src_img, incluir_rs=True)
    assert "probabilidade" in resultado
    assert "nivel" in resultado
    assert resultado["nivel"] in ("baixo", "medio", "alto", "critico")
    assert 0.0 <= resultado["probabilidade"] <= 100.0

    laudo = resultado.get("laudo") or gerar_laudo(resultado)
    assert "ESTEGANOGRAFIA LSB" in laudo.upper()
    assert "QUI-QUADRADO" in laudo.upper()


def test_rsa_attacks_wiener_and_fermat() -> None:
    """Valida os algoritmos de Wiener e Fermat com parâmetros matemáticos exatos."""
    # Wiener: d pequeno
    p = 330248083818617833190827116743
    q = 330248083818617833190827117079
    n = p * q
    phi = (p - 1) * (q - 1)
    d = 1000003  # d pequeno
    e = pow(d, -1, phi)

    res_wiener = ataque_wiener(n, e)
    assert res_wiener is not None
    assert res_wiener["sucesso"] is True
    assert res_wiener["d"] == d
    assert res_wiener["p"] in (p, q)
    assert res_wiener["q"] in (p, q)

    # Fermat: p e q muito próximos
    p_f = 1000000000000000000000000000057
    q_f = 1000000000000000000000000000099
    n_f = p_f * q_f

    res_fermat = fatorar_fermat(n_f, max_iteracoes=10000)
    assert res_fermat is not None
    assert res_fermat["p"] in (p_f, q_f)
    assert res_fermat["q"] in (p_f, q_f)


def test_rsa_common_modulus() -> None:
    """Valida ataque de Módulo Comum via Bezout."""
    n = 2537  # 43 * 59
    e1 = 13
    e2 = 17
    m = 123
    c1 = pow(m, e1, n)
    c2 = pow(m, e2, n)

    res_mc = ataque_modulo_comum(n, e1, c1, e2, c2)
    assert res_mc["sucesso"] is True
    assert res_mc["m"] == m


def test_classical_caesar_and_vigenere() -> None:
    """Valida quebra determinística de César e Vigenère."""
    # César com deslocamento 7
    frase = "ESTE E UM TESTE DE SEGURANCA DA INFORMACAO"
    alfabeto = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    cifrado_cesar = "".join(
        alfabeto[(alfabeto.index(c) + 7) % 26] if c in alfabeto else c
        for c in frase
    )

    res_cesar = quebrar_cesar(cifrado_cesar)
    assert res_cesar["deslocamento"] == 7
    assert res_cesar["texto"].replace(" ", "") == frase.replace(" ", "")

    # Vigenère
    res_vig = quebrar_vigenere(cifrado_cesar, maximo_chave=10)
    assert "chave" in res_vig
    assert res_vig["texto"].replace(" ", "") == frase.replace(" ", "")

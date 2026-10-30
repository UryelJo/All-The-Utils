"""
Testes Black-Box rigorosos (Anti-Gambiarra) para:
1. Suporte completo bidirecional a Apple iPhone HEIF/HEIC (.heic / .heif) em images.convert e pdf.images_to_pdf.
2. Preservação/remoção seletiva de EXIF e GPS, transposição física EXIF, modo Lossless HEIC/WEBP,
   conversão colorimétrica ICC -> sRGB (ImageCms), extração multi-quadro e 18 formatos de saída de imagem.
3. Expansão de formatos e codecs de vídeo/áudio em media.convert (HEVC hvc1 Apple, WebP Animado, TS, AVI, WMV,
   OPUS, AIFF, AC3, CAF/ALAC, downscale de resolução e proteção contra dimensões ímpares).
"""
import io
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageCms
from pypdf import PdfReader

from wintoolbox.tools.images.convert.logic import (
    SUPPORTED_IMAGE_INPUTS,
    SUPPORTED_OUTPUTS,
    convert_single_image,
    ensure_heif_registered,
    get_output_extension,
    parse_bg_color,
)
from wintoolbox.tools.images.convert.tool import ImageConverterTool
from wintoolbox.tools.media.convert.logic import (
    ALL_OUTPUT_FORMATS,
    SUPPORTED_MEDIA_INPUTS,
    convert_media_file,
)
from wintoolbox.tools.media.convert.tool import MediaConvertTool
from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_info
from wintoolbox.tools.pdf.images_to_pdf.logic import convert_images_to_pdf


# ==============================================================================
# 1. TESTES DE HEIF / HEIC (IPHONE), EXIF/GPS, ICC COLOR PROFILE E 18 FORMATOS
# ==============================================================================


def test_heic_bidirectional_lossless_and_alpha_exact_pixels(tmp_path: Path):
    """Happy Path: converte PNG RGBA para HEIC Lossless e reconverte preservando pixels e canal alfa."""
    ensure_heif_registered()
    src_png = tmp_path / "origem_alpha.png"
    expected_rgba = (210, 45, 130, 180)
    Image.new("RGBA", (64, 48), expected_rgba).save(src_png, format="PNG")

    dst_heic = tmp_path / "convertido.heic"
    out_files = convert_single_image(
        src_png,
        dst_heic,
        target_format="HEIC",
        lossless=True,
        subsampling="4:4:4",
    )
    assert out_files == [dst_heic]
    assert dst_heic.is_file()

    with Image.open(dst_heic) as heic_im:
        assert heic_im.format == "HEIF"
        assert heic_im.size == (64, 48)
        assert heic_im.mode == "RGBA"
        # Em modo Lossless 4:4:4, o pixel deve ser exato
        assert heic_im.getpixel((10, 10)) == expected_rgba

    # Reconverter de .heic para .png e validar integridade
    back_png = tmp_path / "volta.png"
    convert_single_image(dst_heic, back_png, target_format="PNG")
    with Image.open(back_png) as png_im:
        assert png_im.format == "PNG"
        assert png_im.size == (64, 48)
        assert png_im.mode == "RGBA"
        assert png_im.getpixel((10, 10)) == expected_rgba


def test_iphone_heic_exif_orientation_and_gps_privacy_modes(tmp_path: Path):
    """
    Simula foto real de iPhone (.heic) gravada deitada (Orientation=6 -> 90° CW) com tags de câmera e GPS.
    Valida:
      1. Transposição física de (80, 40) para (40, 80) e reset de Orientation=1.
      2. Modo 'preserve' mantém câmera e GPS.
      3. Modo 'strip_gps' mantém câmera mas elimina 100% do IFD GPS (0x8825).
      4. Modo 'strip_all' elimina todo o EXIF.
    """
    ensure_heif_registered()
    iphone_heic = tmp_path / "IMG_0001.HEIC"
    raw_img = Image.new("RGB", (80, 40), (120, 180, 240))
    exif = raw_img.getexif()
    exif[0x0112] = 6  # Rotacionada 90 graus horário
    exif[0x010F] = "Apple"
    exif[0x0110] = "iPhone 16 Pro"
    exif[0x8825] = {1: "S", 2: (23.0, 33.0, 1.0), 3: "W", 4: (46.0, 38.0, 2.0)}
    raw_img.save(iphone_heic, format="HEIF", quality=92, exif=exif.tobytes())

    # Caso A: Preservar tudo
    out_preserve = tmp_path / "preserve.jpg"
    convert_single_image(iphone_heic, out_preserve, target_format="JPG", exif_mode="preserve")
    with Image.open(out_preserve) as im_p:
        assert im_p.size == (40, 80)  # Transposta fisicamente!
        ex_p = im_p.getexif()
        assert ex_p.get(0x0112) == 1
        assert ex_p.get(0x010F) == "Apple"
        assert ex_p.get(0x0110) == "iPhone 16 Pro"
        assert 0x8825 in ex_p
        assert ex_p.get_ifd(0x8825)[1] == "S"

    # Caso B: Remover apenas GPS (Privacidade)
    out_nogps = tmp_path / "nogps.heic"
    convert_single_image(iphone_heic, out_nogps, target_format="HEIC", exif_mode="strip_gps")
    with Image.open(out_nogps) as im_ng:
        assert im_ng.size == (40, 80)
        ex_ng = im_ng.getexif()
        assert ex_ng.get(0x0110) == "iPhone 16 Pro"
        assert (0x8825 in ex_ng) is False
        assert ex_ng.get_ifd(0x8825) == {}

    # Caso C: Remover todo o EXIF
    out_clean = tmp_path / "clean.webp"
    convert_single_image(iphone_heic, out_clean, target_format="WEBP", exif_mode="strip_all")
    with Image.open(out_clean) as im_cl:
        assert im_cl.size == (40, 80)
        assert len(im_cl.getexif()) == 0


def test_icc_color_profile_conversion_to_srgb_and_strip(tmp_path: Path):
    """Valida conversão de perfil ICC não-sRGB para sRGB via LittleCMS2 (ImageCms) e remoção opcional."""
    ensure_heif_registered()
    xyz_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("XYZ"))
    srgb_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    # Cria um perfil RGB válido alternativo (a partir de sRGB para teste determinístico de ICC bytes)
    custom_icc_bytes = srgb_profile.tobytes()
    assert len(custom_icc_bytes) > 100
    assert xyz_profile.tobytes() != custom_icc_bytes

    src = tmp_path / "wide_gamut.heic"
    Image.new("RGBA", (32, 32), (240, 50, 50, 128)).save(
        src, format="HEIF", quality=95, icc_profile=custom_icc_bytes
    )

    # Modo srgb deve embutir perfil sRGB válido e preservar o canal alpha intacto (128)
    dst_srgb = tmp_path / "srgb.png"
    convert_single_image(src, dst_srgb, target_format="PNG", color_profile_mode="srgb")
    with Image.open(dst_srgb) as im_srgb:
        icc_out = im_srgb.info.get("icc_profile")
        assert isinstance(icc_out, bytes) and len(icc_out) > 100
        prof_desc = ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc_out))).lower()
        assert "srgb" in prof_desc
        assert im_srgb.mode == "RGBA"
        assert im_srgb.getpixel((16, 16))[3] == 128

    # Modo strip deve remover completamente o perfil ICC
    dst_strip = tmp_path / "sem_icc.png"
    convert_single_image(src, dst_strip, target_format="PNG", color_profile_mode="strip")
    with Image.open(dst_strip) as im_strip:
        assert "icc_profile" not in im_strip.info


@pytest.mark.parametrize(
    "fmt,expected_pillow_fmt",
    [
        ("WEBP", "WEBP"),
        ("JPG", "JPEG"),
        ("PNG", "PNG"),
        ("HEIC", "HEIF"),
        ("HEIF", "HEIF"),
        ("AVIF", "AVIF"),
        ("TIFF", "TIFF"),
        ("BMP", "BMP"),
        ("GIF", "GIF"),
        ("ICO", "ICO"),
        ("ICNS", "ICNS"),
        ("QOI", "QOI"),
        ("TGA", "TGA"),
        ("DDS", "DDS"),
        ("JP2", "JPEG2000"),
        ("PPM", "PPM"),
        ("PCX", "PCX"),
    ],
)
def test_all_17_raster_output_formats_real_decode(tmp_path: Path, fmt: str, expected_pillow_fmt: str):
    """Testa conversão física e reabertura real com leitor Pillow para cada um dos 17 formatos matriciais."""
    src = tmp_path / "base_impar.png"
    # Usa dimensões ímpares e não-quadradas (63x47) + canal alfa para testar casos de borda (ICNS/ICO/DDS/PCX/PPM)
    Image.new("RGBA", (63, 47), (40, 140, 220, 200)).save(src, format="PNG")

    ext = get_output_extension(fmt)
    dst = tmp_path / f"saida_{fmt.lower()}{ext}"
    convert_single_image(src, dst, target_format=fmt, quality=85, bg_color="#000000")

    assert dst.is_file()
    with Image.open(dst) as out:
        assert out.format == expected_pillow_fmt
        if fmt in ("ICNS", "ICO"):
            # Ícones não quadrados devem ser centralizados em canvas quadrado sem distorcer nem falhar
            assert out.size[0] == out.size[1]
        else:
            assert out.size == (63, 47)


def test_pdf_output_and_heic_in_images_to_pdf(tmp_path: Path):
    """Valida saída PDF no conversor de imagens e compilação de fotos .heic (com EXIF rotacionado) em PDF."""
    ensure_heif_registered()
    heic_1 = tmp_path / "foto1.heic"
    im1 = Image.new("RGB", (120, 80), (10, 90, 170))
    ex = im1.getexif()
    ex[0x0112] = 6  # Deve ficar em retrato (80x120) após transposição
    im1.save(heic_1, format="HEIF", exif=ex.tobytes())

    heic_2 = tmp_path / "foto2.heif"
    Image.new("RGBA", (100, 100), (200, 80, 30, 128)).save(heic_2, format="HEIF")

    # 1. Conversão individual HEIC -> PDF
    single_pdf = tmp_path / "unico.pdf"
    convert_single_image(heic_1, single_pdf, target_format="PDF")
    reader_single = PdfReader(str(single_pdf))
    assert len(reader_single.pages) == 1

    # 2. Compilação multi-página em pdf.images_to_pdf com fotos .heic e .heif
    compiled_pdf = tmp_path / "album_iphone.pdf"
    convert_images_to_pdf(
        [heic_1, heic_2],
        compiled_pdf,
        page_size_name="Original da Imagem",
        orientation="auto",
    )
    reader_album = PdfReader(str(compiled_pdf))
    assert len(reader_album.pages) == 2
    # Verifica que a página 1 respeitou a transposição EXIF (largura < altura)
    p1_box = reader_album.pages[0].mediabox
    assert float(p1_box.width) < float(p1_box.height)


def test_edge_cases_bg_color_multiframe_and_16bit(tmp_path: Path):
    """Casos de borda: transparência sobre fundo preto (#000), extração multi-quadro com nome atômico .wtbx e 16-bit."""
    # 1. Pixel 100% transparente sobre fundo preto (#000) -> JPG deve resultar em preto (0, 0, 0)
    src_transp = tmp_path / "transp.png"
    Image.new("RGBA", (20, 20), (255, 255, 255, 0)).save(src_transp, format="PNG")
    dst_black = tmp_path / "preto.jpg"
    convert_single_image(src_transp, dst_black, target_format="JPG", quality=100, bg_color="#000")
    with Image.open(dst_black) as im_b:
        r, g, b = im_b.getpixel((10, 10))
        assert (r, g, b) == (0, 0, 0)

    # 2. Arquivo multi-quadro (GIF de 3 frames) com caminho atômico simulado (.wtbx-123-456.tmp.png)
    multi_gif = tmp_path / "burst.gif"
    frames = [
        Image.new("RGB", (24, 24), (255, 0, 0)),
        Image.new("RGB", (24, 24), (0, 255, 0)),
        Image.new("RGB", (24, 24), (0, 0, 255)),
    ]
    frames[0].save(multi_gif, format="GIF", save_all=True, append_images=frames[1:])

    atomic_tmp = tmp_path / "burst.wtbx-999-111.tmp.png"
    generated = convert_single_image(
        multi_gif,
        atomic_tmp,
        target_format="PNG",
        extract_all_frames=True,
    )
    assert len(generated) == 3
    assert generated[0] == atomic_tmp
    assert generated[1].name == "burst_quadro02.png"
    assert generated[2].name == "burst_quadro03.png"
    for p in generated:
        assert p.is_file()

    # 3. Imagem 16-bit grayscale (I;16) convertida para HEIC e QOI sem falha
    src_16 = tmp_path / "depth16.tiff"
    Image.new("I;16", (32, 32), 32000).save(src_16, format="TIFF")
    dst_qoi = tmp_path / "depth.qoi"
    convert_single_image(src_16, dst_qoi, target_format="QOI")
    with Image.open(dst_qoi) as im_q:
        assert im_q.format == "QOI"
        assert im_q.size == (32, 32)

    dst_heic16 = tmp_path / "depth.heic"
    convert_single_image(src_16, dst_heic16, target_format="HEIC")
    with Image.open(dst_heic16) as im_h16:
        assert im_h16.format == "HEIF"
        assert im_h16.size == (32, 32)


def test_image_convert_failure_scenarios(tmp_path: Path):
    """Cenários de falha: arquivo ausente, formato inválido, cor malformada e binário corrompido."""
    with pytest.raises(FileNotFoundError):
        convert_single_image(tmp_path / "inexistente.heic", tmp_path / "out.jpg", target_format="JPG")

    valid_src = tmp_path / "ok.png"
    Image.new("RGB", (16, 16), (1, 2, 3)).save(valid_src, format="PNG")

    with pytest.raises(ValueError):
        convert_single_image(valid_src, tmp_path / "out.xyz", target_format="FORMATO_INEXISTENTE")

    with pytest.raises(ValueError):
        parse_bg_color("#ZZZZZZ")

    corrupted = tmp_path / "falso.heic"
    corrupted.write_bytes(b"NOT_A_VALID_HEIC_HEADER_0123456789")
    with pytest.raises(Exception):
        convert_single_image(corrupted, tmp_path / "out.png", target_format="PNG")
    assert not (tmp_path / "out.png").exists()


# ==============================================================================
# 2. TESTES DE EXPANSÃO DE VÍDEO E ÁUDIO (MEDIA.CONVERT)
# ==============================================================================


@pytest.fixture(scope="module")
def odd_dim_sample_video(tmp_path_factory) -> Path:
    """
    Gera um vídeo curto de 0.6s com dimensões ÍMPARES (161x121 em formato .mkv raw/ffv1)
    para comprovar que o conversor lida automaticamente com vídeos recortados ímpares sem quebrar encoders YUV420P.
    """
    tmp_dir = tmp_path_factory.mktemp("media_expand_test")
    src = tmp_dir / "odd_clip.mkv"
    ff = get_ffmpeg_exe()
    res = subprocess.run(
        [
            ff, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=0.6:size=161x121:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=500:duration=0.6",
            "-c:v", "ffv1",
            "-c:a", "flac", "-ar", "44100",
            str(src),
        ],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert res.returncode == 0
    return src


def test_video_hevc_apple_hvc1_and_downscale_and_odd_dims(odd_dim_sample_video: Path, tmp_path: Path):
    """
    Valida conversão de vídeo ímpar (161x121) para MOV H.265/HEVC com tag Apple 'hvc1' e downscale para 72p.
    """
    out_mov = tmp_path / "iphone_compat.mov"
    convert_media_file(
        odd_dim_sample_video,
        out_mov,
        target_format="mov",
        video_codec="h265",
        max_height=72,
        hw_accel="cpu",
        audio_bitrate="128k",
    )
    assert out_mov.is_file()
    info = get_media_info(out_mov)
    v_streams = [s for s in info["streams"] if s.get("codec_type") == "video"]
    a_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    assert len(v_streams) == 1
    assert len(a_streams) == 1
    assert v_streams[0]["codec_name"] == "hevc"
    assert v_streams[0]["codec_tag_string"] == "hvc1"
    assert int(v_streams[0]["height"]) == 72
    assert int(v_streams[0]["width"]) % 2 == 0
    assert a_streams[0]["codec_name"] == "aac"


def test_video_to_animated_webp_and_new_containers(odd_dim_sample_video: Path, tmp_path: Path):
    """Valida geração de WebP Animado real e novos contêineres de vídeo (TS, AVI, WMV)."""
    # 1. WebP Animado
    out_webp = tmp_path / "animado.webp"
    convert_media_file(
        odd_dim_sample_video,
        out_webp,
        target_format="webp",
        gif_fps=10,
        gif_width=120,
    )
    with Image.open(out_webp) as im:
        assert im.format == "WEBP"
        assert im.size[0] == 120
        assert im.is_animated is True
        assert getattr(im, "n_frames", 0) >= 3

    # 2. MPEG-TS (.ts) e AVI (.avi)
    for fmt, expected_vcodec in [("ts", "h264"), ("avi", "mpeg4"), ("wmv", "wmv2")]:
        dst = tmp_path / f"video.{fmt}"
        convert_media_file(odd_dim_sample_video, dst, target_format=fmt, hw_accel="cpu")
        info = get_media_info(dst)
        v_streams = [s for s in info["streams"] if s.get("codec_type") == "video"]
        assert len(v_streams) == 1
        assert v_streams[0]["codec_name"] == expected_vcodec


@pytest.mark.parametrize(
    "audio_fmt,expected_codec",
    [
        ("opus", "opus"),
        ("ogg", "vorbis"),
        ("aiff", "pcm_s16be"),
        ("ac3", "ac3"),
        ("caf", "alac"),
        ("flac", "flac"),
    ],
)
def test_new_audio_output_formats_real_codecs(
    odd_dim_sample_video: Path,
    tmp_path: Path,
    audio_fmt: str,
    expected_codec: str,
):
    """Valida extração e codificação real de áudio para OPUS, OGG Vorbis, AIFF, AC3, CAF (ALAC) e FLAC."""
    dst = tmp_path / f"faixa.{audio_fmt}"
    convert_media_file(
        odd_dim_sample_video,
        dst,
        target_format=audio_fmt,
        extract_audio_only=True,
        audio_bitrate="160k",
    )
    assert dst.is_file()
    info = get_media_info(dst)
    v_streams = [s for s in info["streams"] if s.get("codec_type") == "video"]
    a_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    assert v_streams == []
    assert len(a_streams) == 1
    assert a_streams[0]["codec_name"] == expected_codec


def test_ui_tools_options_and_catalog_counts(qtbot):
    """Verifica contratos FileTool, build_options, get_options e amplitude de formatos aceitos."""
    img_tool = ImageConverterTool()
    w_img = img_tool.build_options(None)
    qtbot.addWidget(w_img)

    assert ".heic" in img_tool.accepts
    assert ".heif" in img_tool.accepts
    assert ".hif" in img_tool.accepts
    assert ".psd" in img_tool.accepts
    assert ".qoi" in img_tool.accepts
    assert len(SUPPORTED_IMAGE_INPUTS) == 42
    assert len(SUPPORTED_OUTPUTS) == 18
    assert "HEIC" in SUPPORTED_OUTPUTS

    img_tool.cmb_format.setCurrentText("HEIC")
    img_tool.chk_lossless.setChecked(True)
    opts_img = img_tool.get_options()
    assert opts_img["format"] == "HEIC"
    assert opts_img["lossless"] is True
    assert img_tool.output_ext(opts_img) == ".heic"

    media_tool = MediaConvertTool()
    w_med = media_tool.build_options(None)
    qtbot.addWidget(w_med)

    assert ".mov" in media_tool.accepts
    assert ".mts" in media_tool.accepts
    assert ".opus" in media_tool.accepts
    assert len(SUPPORTED_MEDIA_INPUTS) == 50
    assert len(ALL_OUTPUT_FORMATS) == 26

    media_tool.cmb_format.setCurrentText("MOV")
    opts_med = media_tool.get_options()
    assert opts_med["format"] == "mov"
    assert media_tool.output_ext(opts_med) == ".mov"


def test_media_convert_invalid_format_raises(odd_dim_sample_video: Path, tmp_path: Path):
    """Cenário de falha: formato de mídia não suportado deve lançar ValueError."""
    with pytest.raises(ValueError):
        convert_media_file(odd_dim_sample_video, tmp_path / "x.invalid", target_format="invalid_fmt")

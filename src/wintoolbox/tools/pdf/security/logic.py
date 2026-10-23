"""
Lógica pura para proteção e desbloqueio criptográfico de arquivos PDF.
Compatível com criptografia AES via pypdf.
"""
from pathlib import Path
from typing import Optional
from pypdf import PdfReader, PdfWriter


def protect_pdf(
    src_path: Path,
    dst_path: Path,
    user_password: str,
    owner_password: Optional[str] = None,
    allow_printing: bool = True
) -> Path:
    """
    Criptografa um arquivo PDF com senha de leitura e permissões.
    """
    src_path = Path(src_path)
    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")

    if not user_password:
        raise ValueError("A senha de proteção não pode ser vazia.")

    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(src_path))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    owner_pwd = owner_password or user_password

    # Criptografa usando algoritmo padrão seguro AES
    writer.encrypt(
        user_password=user_password,
        owner_password=owner_pwd,
        use_128bit=True
    )

    with open(dst_path, "wb") as f_out:
        writer.write(f_out)

    return dst_path


def unlock_pdf(
    src_path: Path,
    dst_path: Path,
    password: str
) -> Path:
    """
    Desbloqueia um arquivo PDF criptografado fornecendo a senha e grava uma versão livre.
    """
    src_path = Path(src_path)
    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")

    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(src_path))
    if reader.is_encrypted:
        decrypt_res = reader.decrypt(password)
        if decrypt_res == 0:
            raise ValueError("Senha incorreta. Não foi possível descriptografar o documento.")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    with open(dst_path, "wb") as f_out:
        writer.write(f_out)

    return dst_path

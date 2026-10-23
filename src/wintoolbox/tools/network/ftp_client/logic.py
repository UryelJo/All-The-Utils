"""
Lógica unificada para Cliente FTP e SFTP simples.
Utiliza ftplib (biblioteca padrão) para conexões FTP/FTPS e paramiko para conexões SFTP.
"""
import ftplib
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

class RemoteItem:
    def __init__(self, name: str, is_dir: bool, size: int = 0, modified: str = ""):
        self.name = name
        self.is_dir = is_dir
        self.size = size
        self.modified = modified

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "is_dir": self.is_dir,
            "size": self.size,
            "modified": self.modified
        }

class FtpOrSftpClient:
    def __init__(self, host: str, port: int, user: str = "", password: str = "", protocol: str = "FTP"):
        self.host = host
        self.port = port
        self.user = user or "anonymous"
        self.password = password
        self.protocol = protocol.upper()
        self.ftp_session: Optional[ftplib.FTP] = None
        self.sftp_session: Optional[Any] = None
        self.ssh_client: Optional[Any] = None
        self.current_remote_dir = "/"

    def connect(self) -> str:
        """Estabelece a conexão remota de acordo com o protocolo."""
        if self.protocol == "SFTP":
            try:
                import paramiko
            except ImportError:
                raise RuntimeError("Biblioteca paramiko não encontrada para suporte a SFTP.")

            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                self.host,
                port=self.port or 22,
                username=self.user,
                password=self.password,
                timeout=12
            )
            self.sftp_session = self.ssh_client.open_sftp()
            self.current_remote_dir = self.sftp_session.normalize(".")
            return f"Conectado via SFTP a {self.host}:{self.port or 22}"

        # Padrão: FTP
        self.ftp_session = ftplib.FTP()
        self.ftp_session.connect(self.host, self.port or 21, timeout=12)
        self.ftp_session.login(self.user, self.password)
        self.current_remote_dir = self.ftp_session.pwd()
        return f"Conectado via FTP a {self.host}:{self.port or 21}"

    def disconnect(self):
        """Encerra a sessão remota."""
        if self.ftp_session:
            try:
                self.ftp_session.quit()
            except Exception:
                pass
            self.ftp_session = None

        if self.sftp_session:
            try:
                self.sftp_session.close()
            except Exception:
                pass
            self.sftp_session = None

        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass
            self.ssh_client = None

    def list_dir(self) -> List[RemoteItem]:
        """Lista os arquivos e diretórios na pasta remota atual."""
        items: List[RemoteItem] = []
        if self.protocol == "SFTP" and self.sftp_session:
            import stat
            for attr in self.sftp_session.listdir_attr(self.current_remote_dir):
                is_dir = stat.S_ISDIR(attr.st_mode)
                items.append(RemoteItem(
                    name=attr.filename,
                    is_dir=is_dir,
                    size=attr.st_size if not is_dir else 0,
                    modified=str(attr.st_mtime or "")
                ))
            return sorted(items, key=lambda x: (not x.is_dir, x.name.lower()))

        if self.ftp_session:
            lines: List[str] = []
            self.ftp_session.retrlines("LIST", lines.append)
            for line in lines:
                parts = line.split(maxsplit=8)
                if len(parts) >= 9:
                    perms, _, _, _, size_str, _, _, _, name = parts
                    is_dir = perms.startswith("d")
                    size = int(size_str) if size_str.isdigit() else 0
                    items.append(RemoteItem(name=name, is_dir=is_dir, size=size))
                elif len(parts) >= 4:
                    # Formato DOS / Windows FTP
                    date, time_s, dir_or_size, name = parts[0], parts[1], parts[2], " ".join(parts[3:])
                    is_dir = dir_or_size.upper() == "<DIR>"
                    size = int(dir_or_size) if not is_dir and dir_or_size.isdigit() else 0
                    items.append(RemoteItem(name=name, is_dir=is_dir, size=size, modified=f"{date} {time_s}"))
            return sorted(items, key=lambda x: (not x.is_dir, x.name.lower()))

        return []

    def change_dir(self, dir_name: str) -> str:
        """Entra em um subdiretório ou sobe de nível."""
        if self.protocol == "SFTP" and self.sftp_session:
            if dir_name == "..":
                parent = str(Path(self.current_remote_dir).parent).replace("\\", "/")
                self.current_remote_dir = parent if parent else "/"
            else:
                new_path = f"{self.current_remote_dir.rstrip('/')}/{dir_name}"
                self.sftp_session.chdir(new_path)
                self.current_remote_dir = new_path
            return self.current_remote_dir

        if self.ftp_session:
            if dir_name == "..":
                self.ftp_session.cdup()
            else:
                self.ftp_session.cwd(dir_name)
            self.current_remote_dir = self.ftp_session.pwd()
            return self.current_remote_dir

        return self.current_remote_dir

    def download_file(self, remote_filename: str, local_dest_path: str, progress_cb: Optional[Callable[[int], None]] = None):
        """Baixa um arquivo remoto com acompanhamento de progresso."""
        if self.protocol == "SFTP" and self.sftp_session:
            remote_path = f"{self.current_remote_dir.rstrip('/')}/{remote_filename}"
            def sftp_cb(transferred, total):
                if total > 0 and progress_cb:
                    progress_cb(int((transferred / total) * 100))

            self.sftp_session.get(remote_path, local_dest_path, callback=sftp_cb)
            return

        if self.ftp_session:
            try:
                total_size = self.ftp_session.size(remote_filename) or 0
            except Exception:
                total_size = 0

            downloaded = 0
            with open(local_dest_path, "wb") as f:
                def ftp_cb(data):
                    nonlocal downloaded
                    f.write(data)
                    downloaded += len(data)
                    if total_size > 0 and progress_cb:
                        progress_cb(int((downloaded / total_size) * 100))

                self.ftp_session.retrbinary(f"RETR {remote_filename}", ftp_cb, blocksize=65536)

    def upload_file(self, local_src_path: str, remote_filename: str, progress_cb: Optional[Callable[[int], None]] = None):
        """Envia um arquivo local para o diretório remoto atual."""
        total_size = os.path.getsize(local_src_path)

        if self.protocol == "SFTP" and self.sftp_session:
            remote_path = f"{self.current_remote_dir.rstrip('/')}/{remote_filename}"
            def sftp_cb(transferred, total):
                if total > 0 and progress_cb:
                    progress_cb(int((transferred / total) * 100))

            self.sftp_session.put(local_src_path, remote_path, callback=sftp_cb)
            return

        if self.ftp_session:
            uploaded = 0
            with open(local_src_path, "rb") as f:
                def ftp_cb(data):
                    nonlocal uploaded
                    uploaded += len(data)
                    if total_size > 0 and progress_cb:
                        progress_cb(int((uploaded / total_size) * 100))

                self.ftp_session.storbinary(f"STOR {remote_filename}", f, blocksize=65536, callback=ftp_cb)

    def delete_item(self, remote_name: str, is_dir: bool):
        """Exclui um arquivo ou diretório remoto."""
        if self.protocol == "SFTP" and self.sftp_session:
            path = f"{self.current_remote_dir.rstrip('/')}/{remote_name}"
            if is_dir:
                self.sftp_session.rmdir(path)
            else:
                self.sftp_session.remove(path)
            return

        if self.ftp_session:
            if is_dir:
                self.ftp_session.rmd(remote_name)
            else:
                self.ftp_session.delete(remote_name)

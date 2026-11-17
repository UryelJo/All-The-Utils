"""
Lógica pura para enumeração e backup de drivers de terceiros do Windows via pnputil.
Isolada de interface gráfica.
"""
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.shell import CONSOLE_ENCODING, CREATE_NO_WINDOW


def _normalize_driver_date(date_str: str) -> str:
    """Converte MM/DD/YYYY do pnputil para DD/MM/YYYY se aplicável."""
    s = (date_str or "").strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        mm, dd, yyyy = m.group(1), m.group(2), m.group(3)
        # Se o primeiro número for <= 12 e o segundo > 12 (ou formato padrão americano do pnputil MM/DD/YYYY)
        if int(mm) <= 12:
            return f"{dd}/{mm}/{yyyy}"
    return s


def parse_pnputil_drivers_output(output_text: str) -> List[Dict[str, Any]]:
    """Analisa a saída de 'pnputil /enum-drivers' suportando Windows em PT-BR e EN-US."""
    drivers: List[Dict[str, Any]] = []
    current_driver: Dict[str, Any] = {}

    for line in (output_text or "").splitlines():
        line_str = line.strip()
        if not line_str:
            if current_driver and "published_name" in current_driver:
                drivers.append(current_driver)
                current_driver = {}
            continue

        if ":" in line_str:
            k, v = line_str.split(":", 1)
            key = k.strip().lower()
            val = v.strip()

            if "nome publicado" in key or "published name" in key:
                if current_driver and "published_name" in current_driver:
                    drivers.append(current_driver)
                    current_driver = {}
                current_driver["published_name"] = val
            elif "nome original" in key or "original name" in key:
                current_driver["original_name"] = val
            elif "nome do provedor" in key or "provider name" in key or "provedor" in key:
                current_driver["provider"] = val
            elif "nome da classe" in key or "nome de classe" in key or "class name" in key:
                current_driver["class_name"] = val
            elif "guid da classe" in key or "class guid" in key:
                current_driver["class_guid"] = val
            elif "vers" in key or "version" in key:
                # pnputil retorna: "06/21/2006 10.0.26100.1" (data + versão na mesma linha)
                parts = val.split()
                if len(parts) >= 2 and re.match(r"^\d{2,4}[/-]\d{2}[/-]\d{2,4}$", parts[0]):
                    current_driver["date"] = _normalize_driver_date(parts[0])
                    current_driver["version"] = " ".join(parts[1:])
                else:
                    current_driver["version"] = val
            elif "data" in key or "date" in key:
                current_driver["date"] = _normalize_driver_date(val)
            elif "signat" in key or "signer" in key:
                current_driver["signer"] = val

    if current_driver and "published_name" in current_driver:
        drivers.append(current_driver)

    for d in drivers:
        d.setdefault("original_name", "-")
        d.setdefault("provider", "Desconhecido")
        d.setdefault("class_name", "Geral / Sistema")
        d.setdefault("version", "-")
        d.setdefault("date", "-")

    return drivers


def list_third_party_drivers() -> List[Dict[str, Any]]:
    """
    Lista todos os pacotes de drivers de terceiros instalados no sistema via 'pnputil /enum-drivers'.
    """
    try:
        res = subprocess.run(
            ["pnputil.exe", "/enum-drivers"],
            capture_output=True,
            text=True,
            encoding=CONSOLE_ENCODING,
            errors="replace",
            timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
        if res.returncode == 0 and res.stdout:
            return parse_pnputil_drivers_output(res.stdout)
    except Exception:
        pass

    return []


def export_drivers_to_folder(
    target_dir: Path,
    published_names: Optional[List[str]] = None,
) -> Tuple[bool, str, int]:
    """
    Exporta todos os drivers (ou apenas a lista de INFs publicada em published_names)
    para a pasta especificada via 'pnputil /export-driver'.
    Retorna (sucesso, mensagem, total_exportados).
    """
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    if published_names:
        exported = 0
        errors: List[str] = []
        for inf_name in published_names:
            inf_clean = inf_name.strip()
            if not inf_clean:
                continue
            sub_target = target / Path(inf_clean).stem
            sub_target.mkdir(parents=True, exist_ok=True)
            try:
                res = subprocess.run(
                    ["pnputil.exe", "/export-driver", inf_clean, str(sub_target)],
                    capture_output=True,
                    text=True,
                    encoding=CONSOLE_ENCODING,
                    errors="replace",
                    timeout=60,
                    creationflags=CREATE_NO_WINDOW,
                )
                if res.returncode == 0 or any(sub_target.iterdir()):
                    exported += 1
                else:
                    errors.append(f"{inf_clean}: {res.stderr or res.stdout or 'Falha'}")
            except Exception as e:
                errors.append(f"{inf_clean}: {e}")

        if exported > 0:
            return True, f"Backup concluído! {exported} pacote(s) de driver exportado(s) para '{target}'.", exported
        return False, "Falha ao exportar os drivers selecionados. Verifique permissões de Administrador.", 0

    cmd = ["pnputil.exe", "/export-driver", "*", str(target)]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding=CONSOLE_ENCODING,
            errors="replace",
            timeout=300,
            creationflags=CREATE_NO_WINDOW,
        )
        stdout = res.stdout

        match = re.search(r"(\d+)\s+pacote|(\d+)\s+driver package|(\d+)\s+exportado", stdout, re.IGNORECASE)
        count = 0
        if match:
            for g in match.groups():
                if g and g.isdigit():
                    count = int(g)
                    break

        if count == 0:
            count = len([p for p in target.iterdir() if p.is_dir()])

        if res.returncode == 0 or count > 0:
            return True, f"Backup concluído com sucesso! {count} pacotes de drivers exportados para '{target}'.", count
        else:
            return False, f"Falha na exportação: {res.stderr or stdout or 'Verifique permissões de administrador.'}", 0
    except subprocess.TimeoutExpired:
        return False, "Tempo limite excedido durante a exportação de drivers.", 0
    except Exception as e:
        return False, f"Erro ao executar pnputil: {str(e)}", 0

"""
Lógica pura para enumeração e backup de drivers de terceiros do Windows via pnputil.
Isolada de interface gráfica.
"""
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple


def list_third_party_drivers() -> List[Dict[str, Any]]:
    """
    Lista todos os pacotes de drivers de terceiros instalados no sistema via 'pnputil /enum-drivers'.
    """
    drivers: List[Dict[str, Any]] = []

    try:
        res = subprocess.run(["pnputil.exe", "/enum-drivers"], capture_output=True, text=True, timeout=20)
        if res.returncode == 0:
            current_driver: Dict[str, Any] = {}
            for line in res.stdout.splitlines():
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
                    elif "nome do provedor" in key or "provider name" in key:
                        current_driver["provider"] = val
                    elif "nome de classe" in key or "class name" in key:
                        current_driver["class_name"] = val
                    elif "vers" in key or "version" in key:
                        current_driver["version"] = val
                    elif "data" in key or "date" in key:
                        current_driver["date"] = val

            if current_driver and "published_name" in current_driver:
                drivers.append(current_driver)
    except Exception:
        pass

    return drivers


def export_drivers_to_folder(target_dir: Path) -> Tuple[bool, str, int]:
    """
    Exporta todos os drivers de terceiros instalados para a pasta especificada via 'pnputil /export-driver * <destino>'.
    Retorna (sucesso, mensagem, total_exportados).
    """
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    cmd = ["pnputil.exe", "/export-driver", "*", str(target)]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        stdout = res.stdout

        # Contabiliza pacotes exportados
        # Padrão: Pacotes de driver exportados: X ou Exported driver packages: X
        match = re.search(r"(\d+)\s+pacote|(\d+)\s+driver package|(\d+)\s+exportado", stdout, re.IGNORECASE)
        count = 0
        if match:
            for g in match.groups():
                if g and g.isdigit():
                    count = int(g)
                    break

        # Se não capturou no texto, conta as pastas criadas no diretório
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

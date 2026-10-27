"""
Ponto de entrada quando executado como módulo: python -m wintoolbox ou diretamente como script.
"""
import os
import sys

_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


def main():
    if "--self-test" in sys.argv:
        from wintoolbox.selftest import run_self_test
        sys.exit(min(run_self_test(), 125))
    if len(sys.argv) > 1 and sys.argv[1] in ("run", "--list", "-h", "--help"):
        from wintoolbox.cli import run_cli
        sys.exit(run_cli())
    else:
        from wintoolbox.app import run_gui
        run_gui()

if __name__ == "__main__":
    main()

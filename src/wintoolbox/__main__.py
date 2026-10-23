"""
Ponto de entrada quando executado como módulo: python -m wintoolbox
"""
import sys

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("run", "--list", "-h", "--help"):
        from wintoolbox.cli import run_cli
        sys.exit(run_cli())
    else:
        from wintoolbox.app import run_gui
        run_gui()

if __name__ == "__main__":
    main()

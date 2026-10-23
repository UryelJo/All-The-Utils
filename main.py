"""
WinToolbox - Caixa de Ferramentas para Windows.
Script principal de inicialização da aplicação.
"""
import os
import sys

# Garante que o diretório 'src' seja incluído no sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

if __name__ == "__main__":
    from wintoolbox.__main__ import main
    main()

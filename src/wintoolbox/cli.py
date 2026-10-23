"""
Interface de Linha de Comando (CLI Mínima) do WinToolbox.
Permite automação de ferramentas e lotes via terminal ou scripts.
"""
import sys
import argparse
from pathlib import Path

# Registra as ferramentas
import wintoolbox.tools.images.convert
import wintoolbox.tools.system.tools
import wintoolbox.tools.system.monitor
import wintoolbox.tools.network
import wintoolbox.tools.text
import wintoolbox.tools.encode
import wintoolbox.tools.data
import wintoolbox.tools.files
import wintoolbox.tools.archive

from wintoolbox.core.batch import OutputPolicy, SourceItem, discover_files, execute_batch
from wintoolbox.core.registry import FileTool, TaskContext, get_all_tools, get_tool

def run_cli(args=None):
    """Executa a interface de linha de comando."""
    parser = argparse.ArgumentParser(
        prog="wintoolbox",
        description="WinToolbox - Ferramentas de automação e conversão para Windows"
    )
    parser.add_argument("--list", action="store_true", help="Lista todas as ferramentas disponíveis")
    
    subparsers = parser.add_subparsers(dest="subcommand", help="Comando a executar")

    # Subcomando: run
    run_parser = subparsers.add_parser("run", help="Executa uma ferramenta específica")
    run_parser.add_argument("tool_id", help="ID da ferramenta (ex: images.convert)")
    run_parser.add_argument("paths", nargs="+", help="Caminhos de arquivos ou pastas de origem")
    run_parser.add_argument("--recursive", "-r", action="store_true", help="Inclui subpastas recursivamente")
    run_parser.add_argument("--format", "-f", default="WEBP", help="Formato de saída (ex: WEBP, JPG, PNG)")
    run_parser.add_argument("--quality", "-q", type=int, default=90, help="Qualidade de compressão (10-100)")
    run_parser.add_argument("--dest", "-d", type=str, default="", help="Pasta de destino personalizada")

    parsed = parser.parse_args(args)

    if parsed.list:
        print("\nFerramentas registradas no WinToolbox:")
        print("--------------------------------------------------")
        for t in get_all_tools():
            print(f"- {t.id:<20} | {t.name} ({t.category})")
            print(f"  {t.description}\n")
        return 0

    if parsed.subcommand == "run":
        tool = get_tool(parsed.tool_id)
        if not tool:
            print(f"Erro: Ferramenta com ID '{parsed.tool_id}' não encontrada.")
            return 1

        if not isinstance(tool, FileTool):
            print(f"Erro: A ferramenta '{parsed.tool_id}' não suporta execução direta de arquivos via CLI.")
            return 1

        # Monta origens
        sources = []
        for p_str in parsed.paths:
            p = Path(p_str)
            if p.exists():
                sources.append(SourceItem(path=p, is_dir=p.is_dir(), recursive=parsed.recursive))

        files = discover_files(sources, allowed_extensions=set(tool.accepts))
        if not files:
            print("Nenhum arquivo correspondente encontrado.")
            return 0

        print(f"Iniciando {tool.name} para {len(files)} arquivo(s)...")

        policy = OutputPolicy(
            mode="custom" if parsed.dest else "subfolder",
            custom_dir=Path(parsed.dest) if parsed.dest else None,
            subfolder_name="convertidos",
            conflict="rename"
        )
        params = {"format": parsed.format.upper(), "quality": parsed.quality}
        target_ext = tool.output_ext(params)

        ctx = TaskContext(
            on_progress=lambda cur, tot, msg: print(f"[{cur}/{tot}] {msg}"),
            on_log=lambda lvl, msg: print(f"[{lvl}] {msg}"),
            is_cancelled=lambda: False
        )

        res = execute_batch(
            files=files,
            output_policy=policy,
            target_ext=target_ext,
            process_func=tool.process,
            params=params,
            ctx=ctx
        )
        print(f"\nResultado: {res.message}")
        return 0 if res.success else 1

    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(run_cli())

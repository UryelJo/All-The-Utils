"""
Script de geração automática da documentação oficial do WinToolbox.
Compila os metadados das 261 ferramentas registradas em docs/README.md.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Any

DOCS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DOCS_DIR.parent

CATEGORY_ORDER = [
    "Imagens",
    "Arquivos e Pastas",
    "PDF",
    "Áudio e Vídeo",
    "Sistema",
    "Rede e Internet",
    "Desenvolvimento",
    "Dados e Estruturas",
    "Texto e Redação",
    "Calculadoras",
    "Produtividade",
    "Automação",
    "Compactação",
    "Codificação e Hash",
    "Segurança",
]

CATEGORY_META: Dict[str, Dict[str, str]] = {
    "Imagens": {
        "num": "1",
        "icon": "🖼️",
        "anchor": "1-imagens-e-midia-visual",
        "title": "Imagens e Mídia Visual",
        "desc": "Conversão, compressão otimizada, redimensionamento com Lanczos, marcas d'água de texto e logo, anotações, paletas de cores, OCR nativo do Windows e geradores de QR Code/Código de Barras.",
    },
    "Arquivos e Pastas": {
        "num": "2",
        "icon": "📁",
        "anchor": "2-arquivos-pastas-e-armazenamento",
        "title": "Arquivos, Pastas e Armazenamento",
        "desc": "Organização inteligente por tipo/data, detecção de duplicados por hash SHA-256, sincronização de diretórios, triturador seguro (DoD/Gutmann), gerenciamento de junções NTFS e analisador visual de espaço em disco.",
    },
    "PDF": {
        "num": "3",
        "icon": "📄",
        "anchor": "3-pdf-e-documentos",
        "title": "PDF e Documentos",
        "desc": "Manipulação completa de arquivos PDF: divisão, junção, compressão de imagens/streams, censura permanente (redaction), OCR pesquisável, assinaturas visuais com rubrica, carimbos, numeração e extração de tabelas.",
    },
    "Áudio e Vídeo": {
        "num": "4",
        "icon": "🎵",
        "anchor": "4-audio-video-e-multimidia",
        "title": "Áudio, Vídeo e Multimídia",
        "desc": "Processamento audiovisual acelerado via FFmpeg e IA Whisper: normalização de loudness (EBU R128), conversão em lote, transcrição offline de fala em texto, corte sem perdas (stream copy) e download de mídias.",
    },
    "Sistema": {
        "num": "5",
        "icon": "⚙️",
        "anchor": "5-sistema-operacional-e-manutencao",
        "title": "Sistema Operacional e Manutenção",
        "desc": "Diagnósticos de hardware em tempo real, reparo de componentes do Windows (SFC, DNS, Fila de Impressão), gerenciamento de inicialização, serviços, variáveis de ambiente (PATH), telemetria e atualizações com Winget.",
    },
    "Rede e Internet": {
        "num": "6",
        "icon": "🌐",
        "anchor": "6-rede-internet-e-conexoes",
        "title": "Rede, Internet e Conexões",
        "desc": "Diagnóstico completo de conectividade (Ping, MTR, DNS Benchmark), testes de velocidade (Cloudflare), scanner de portas/ARP, servidor web local com QR Code móvel e integrações com APIs públicas brasileiras (BrasilAPI).",
    },
    "Desenvolvimento": {
        "num": "7",
        "icon": "💻",
        "anchor": "7-desenvolvimento-e-programacao",
        "title": "Desenvolvimento e Programação",
        "desc": "Utilitários essenciais para programadores: cliente HTTP/REST completo, limpador de builds pesados (node_modules, target, .venv), gerador de certificados SSL locais, servidor mock, contador de linhas (CLOC) e leitor SQLite.",
    },
    "Dados e Estruturas": {
        "num": "8",
        "icon": "📊",
        "anchor": "8-dados-estruturas-e-tabelas",
        "title": "Dados, Estruturas e Tabelas",
        "desc": "Visualização em árvore e conversão multidirecional entre JSON, CSV, Excel, XML e YAML, consultas analíticas com SQL em arquivos locais, comparadores estruturais semânticos e visualizador de logs com tail.",
    },
    "Texto e Redação": {
        "num": "9",
        "icon": "✍️",
        "anchor": "9-texto-redacao-e-documentos-br",
        "title": "Texto, Redação e Documentos BR",
        "desc": "Transformações e limpeza de texto, comparador visual de diferenças com realce inline de caracteres, testador de Regex interativo, gerador de Pix oficial BR Code, decodificador de boletos e geradores de documentos BR.",
    },
    "Calculadoras": {
        "num": "10",
        "icon": "🧮",
        "anchor": "10-calculadoras-e-conversores-tecnicos",
        "title": "Calculadoras e Conversores Técnicos",
        "desc": "Simulações financeiras (juros compostos, amortização Price/SAC, investimentos), folha salarial CLT Brasil com alíquotas oficiais, calculadora de sub-redes IPv4/CIDR, programador bitwise e conversor universal de unidades.",
    },
    "Produtividade": {
        "num": "11",
        "icon": "⏱️",
        "anchor": "11-produtividade-e-organizacao-pessoal",
        "title": "Produtividade e Organização Pessoal",
        "desc": "Quadro Kanban de tarefas offline, controle financeiro pessoal com importação OFX/CSV, timer Pomodoro, histórico da área de transferência com favoritos, notas rápidas e emissor de orçamentos e recibos em PDF.",
    },
    "Automação": {
        "num": "12",
        "icon": "🤖",
        "anchor": "12-automacao-macros-e-janelas",
        "title": "Automação, Macros e Janelas",
        "desc": "Autoclicker com taxa CPS configurável, regras de organização automática de pastas, atalhos de teclado globais, gerenciador de janelas do Windows (Always on Top/Transparência) e central de execução de scripts multilinguagem.",
    },
    "Compactação": {
        "num": "13",
        "icon": "📦",
        "anchor": "13-compactacao-e-arquivos-comprimidos",
        "title": "Compactação e Arquivos Comprimidos",
        "desc": "Compactação e extração em lote para ZIP, 7Z, RAR e TAR com proteção estrita Zip Slip, criação de volumes multipartes, verificador de integridade CRC e montagem/extração nativa de imagens ISO e VHD.",
    },
    "Codificação e Hash": {
        "num": "14",
        "icon": "🔑",
        "anchor": "14-codificacao-criptografia-e-hashes",
        "title": "Codificação, Criptografia e Hashes",
        "desc": "Cálculo de hashes modernos (SHA-256, BLAKE2, MD5, CRC32), codificação Base64/URL/HTML, depuração e verificação de assinaturas JWT, gerador de chaves SSH (Ed25519/RSA) e decodificador SEFAZ de chaves de acesso NF-e.",
    },
    "Segurança": {
        "num": "15",
        "icon": "🛡️",
        "anchor": "15-seguranca-e-auditoria-defensiva",
        "title": "Segurança e Auditoria Defensiva",
        "desc": "Auditoria de segurança defensiva: verificação de senhas vazadas via Have I Been Pwned (k-anonimato seguro), consulta de reputação no VirusTotal, auditoria de cabeçalhos HTTP e validação de assinaturas Authenticode.",
    },
}


def load_tools() -> List[Dict[str, Any]]:
    """Carrega metadados de todas as ferramentas registradas no WinToolbox."""
    import sys
    import inspect
    src_dir = PROJECT_ROOT / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from wintoolbox.core.registry import get_all_tools, FileTool

    tools: List[Dict[str, Any]] = []
    for t in get_all_tools():
        try:
            source_file = inspect.getfile(type(t))
            rel_to_docs = os.path.relpath(source_file, DOCS_DIR).replace("\\", "/")
        except Exception:
            rel_to_docs = ""

        t_type = "FileTool" if isinstance(t, FileTool) else "Tool"
        tools.append({
            "id": t.id,
            "name": t.name or t.id,
            "category": t.category,
            "description": t.description,
            "type": t_type,
            "admin": getattr(t, "requires_admin", False),
            "file": rel_to_docs,
        })
    return tools


def build_readme() -> str:
    tools = load_tools()

    # Agrupa ferramentas por categoria canônica
    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for t in tools:
        by_category.setdefault(t["category"], []).append(t)

    # Ordena ferramentas dentro de cada categoria por ID
    for cat in by_category:
        by_category[cat].sort(key=lambda x: x["id"])

    total_tools = len(tools)
    total_categories = len(CATEGORY_ORDER)

    lines: List[str] = []

    # Cabeçalho Principal
    lines.append("# 🧰 WinToolbox (All the Utils) — Central de Documentação & Catálogo Geral")
    lines.append("")
    lines.append("> **Caixa de ferramentas completa, moderna e 100% offline para Windows.**")
    lines.append("> Desenvolvida em **Python + PySide6 (Qt)** com design sóbrio no padrão **Windows 11 Fluent**, motor assíncrono de processamento em lote nativo e linha de comando integrada.")
    lines.append("")
    lines.append("![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python) "
                 "![Framework](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-brightgreen?logo=qt) "
                 "![Design](https://img.shields.io/badge/Design-Windows%2011%20Fluent-informational) "
                 f"![Ferramentas](https://img.shields.io/badge/Ferramentas-{total_tools}%20Ativas-success) "
                 "![Privacidade](https://img.shields.io/badge/Privacidade-100%25%20Offline-blueviolet) "
                 "![Plataforma](https://img.shields.io/badge/Plataforma-Windows%2010%20%2F%2011-lightgrey?logo=windows)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Base de Conhecimento e Links Rápidos
    lines.append("## 🧭 Base de Conhecimento do Projeto")
    lines.append("")
    lines.append("Este diretório `docs/` constitui a espinha dorsal de governança técnica do ecossistema **WinToolbox**. Cada documento possui um papel específico e complementar:")
    lines.append("")
    lines.append("| Documento | Finalidade & Conteúdo Principal | Público-Alvo |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| 📑 **[registro_tecnico.md](registro_tecnico.md)** | **Arquitetura & Engenharia de Software**: Separação estrita Core/UI/Tools, contratos dos plugins (`FileTool` e `Tool`), motor `TaskRunner`, concorrência com `QThreadPool`, manipulação de subprocessos PowerShell/Shell e registro de fases. | Desenvolvedores e Arquitetos |")
    lines.append("| 📚 **[catalogo_ferramentas.md](catalogo_ferramentas.md)** | **Inventário Minucioso de Ferramentas**: Especificações técnicas exaustivas de todas as ferramentas, entradas aceitas, formatos de saída, flags de automação e algoritmos matemáticos/criptográficos implementados. | Usuários Técnicos e Desenvolvedores |")
    lines.append("| 💡 **[contexto_para_prompts.md](contexto_para_prompts.md)** | **Guia de Contexto & Diretrizes para Prompts**: Instruções para IAs e novos colaboradores, regras de estilo Fluent (Segoe UI, sem emojis na interface de produção), padrões de código PEP 8 e diretrizes estritas de testes black-box sem gambiarras. | Modelos de IA e Contribuidores |")
    lines.append("| 📂 **[Código-Fonte do Projeto](../src/wintoolbox/)** | **Implementação Real**: Módulos do núcleo (`core/`), componentes de interface (`ui/`) e implementações de todas as ferramentas (`tools/`). | Desenvolvedores |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Painel Geral de Métricas
    lines.append("## 📊 Painel Geral de Categorias")
    lines.append("")
    lines.append(f"O **WinToolbox** conta atualmente com **{total_tools} ferramentas integradas**, distribuídas em **{total_categories} categorias temáticas**. Todas contam com execução assíncrona, relatórios de progresso em tempo real e cancelamento seguro sem congelar a interface.")
    lines.append("")
    lines.append("| # | Categoria | Ferramentas | Foco & Capacidades Principais | Acesso Rápido |")
    lines.append("| :-: | :--- | :-: | :--- | :-: |")

    for cat in CATEGORY_ORDER:
        meta = CATEGORY_META[cat]
        cnt = len(by_category.get(cat, []))
        lines.append(f"| {meta['num']} | {meta['icon']} **{meta['title']}** | `{cnt}` | {meta['desc']} | [Visualizar ➔](#{meta['anchor']}) |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Legenda dos Tipos de Ferramenta
    lines.append("## 🏷️ Tipos de Ferramentas e Convenções")
    lines.append("")
    lines.append("Para facilitar a visualização e automação, cada utilitário é categorizado segundo seu contrato de arquitetura:")
    lines.append("")
    lines.append("- `⚡ Lote (FileTool)`: Utilitário puramente focado em processamento de arquivos e diretórios em massa. Conecta-se automaticamente ao **Motor de Lotes (Batch Engine)**, oferecendo Drag & Drop, controle de concorrência (`process` ou `thread`), seleção de estratégia de conflito (sobrescrever, renomear `(1)`, pular) e espelhamento relativo de subpastas.")
    lines.append("- `🎛️ Interativo (Tool)`: Utilitário que possui interface visual própria e dedicada (dashboards, editores visuais com abas, players, temporizadores, gráficos ou calculadoras com preview dinâmico).")
    lines.append("- `🛡️ Admin`: Ferramenta que necessita de elevação de privilégios de Administrador do Windows (UAC) para realizar modificações no sistema operacional.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Seções Detalhadas de Cada Categoria
    for cat in CATEGORY_ORDER:
        meta = CATEGORY_META[cat]
        tool_list = by_category.get(cat, [])
        lines.append(f"## <a id=\"{meta['anchor']}\"></a>{meta['num']}. {meta['icon']} {meta['title']} ({len(tool_list)} Ferramentas)")
        lines.append("")
        lines.append(f"> {meta['desc']}")
        lines.append("")
        lines.append("| Ferramenta & ID | Tipo | Descrição dos Recursos | Código-Fonte | Catálogo |")
        lines.append("| :--- | :---: | :--- | :---: | :---: |")

        # Mapeia âncoras de catalogo_ferramentas.md
        catalogo_path = DOCS_DIR / "catalogo_ferramentas.md"
        cat_anchors = {}
        if catalogo_path.exists():
            import re
            for line in catalogo_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("### "):
                    m = re.search(r"`([^`]+)`", line)
                    if m:
                        tid = m.group(1).strip()
                        # Gera slug compatível com GitHub Markdown
                        raw_title = line.lstrip("#").strip().replace("`", "")
                        slug = raw_title.lower()
                        # Remove pontuações mantendo letras, números, espaços e hífens
                        slug = re.sub(r"[^\w\s-]", "", slug)
                        slug = re.sub(r"[\s_]+", "-", slug).strip("-")
                        cat_anchors[tid] = slug

        for t in tool_list:
            t_id = t["id"]
            name = t["name"]
            desc = t["description"].replace("\n", " ").strip()
            t_type = t["type"]
            admin = t["admin"]
            file_rel = t["file"].replace("\\", "/")

            # Badges
            type_badge = "⚡ Lote" if t_type == "FileTool" else "🎛️ Interativo"
            if admin:
                type_badge += " <br> `🛡️ Admin`"

            # Source link com forward slashes
            code_link = f"[`tool.py`]({file_rel})"

            # Link para o catálogo detalhado
            if t_id in cat_anchors:
                catalog_link = f"[Detalhes ➔](catalogo_ferramentas.md#{cat_anchors[t_id]})"
            else:
                catalog_link = "[Catálogo ➔](catalogo_ferramentas.md)"

            lines.append(f"| **{name}**<br>`{t_id}` | {type_badge} | {desc} | {code_link} | {catalog_link} |")

        lines.append("")
        lines.append("---")
        lines.append("")

    # Como Executar e Produtividade
    lines.append("## 🚀 Como Executar o WinToolbox")
    lines.append("")
    lines.append("### 1. Modo Gráfico (GUI)")
    lines.append("")
    lines.append("A interface desktop oferece uma experiência rica e fluida para o dia a dia:")
    lines.append("")
    lines.append("```bash")
    lines.append("# Execução direta via terminal")
    lines.append("python main.py")
    lines.append("")
    lines.append("# Ou pelo atalho no Windows")
    lines.append("iniciar.bat")
    lines.append("```")
    lines.append("")
    lines.append("#### Recursos Visuais em Destaque:")
    lines.append("- **Paleta de Comandos (`Ctrl+K`)**: Pressione `Ctrl+K` a qualquer momento para abrir a busca instantânea global estilo VS Code. Digite termos-chave ou IDs para navegar direto para qualquer utilitário.")
    lines.append("- **Arrastar e Soltar (Drag & Drop)**: Arraste arquivos individuais ou pastas inteiras do Windows Explorer direto para a tabela das ferramentas em lote.")
    lines.append("- **Motor Assíncrono sem Travamentos**: Processamentos pesados de mídia, hashing ou compressão rodam em workers separados do `QThreadPool`. A UI nunca congela e permite pausar ou cancelar tarefas a qualquer instante.")
    lines.append("- **Console de Logs Integrado**: Acompanhe logs monoespaçados com marcação de severidade (INFO, AVISO, ERRO, SUCESSO) e cópia rápida.")
    lines.append("")
    lines.append("### 2. Modo Linha de Comando (CLI Headless)")
    lines.append("")
    lines.append("O **WinToolbox** pode ser operado sem interface gráfica para integração com scripts Batch, PowerShell ou rotinas do Agendador de Tarefas do Windows:")
    lines.append("")
    lines.append("```bash")
    lines.append("# 1. Listar todas as ferramentas registradas no sistema")
    lines.append("python main.py --list")
    lines.append("")
    lines.append("# 2. Executar uma ferramenta em lote via linha de comando")
    lines.append("# Sintaxe: python main.py run <tool_id> <caminho_entrada> [opcoes]")
    lines.append('python main.py run images.convert "D:\\Fotos_Viagem" -r -f WEBP -q 85 -d "E:\\Fotos_Otimizadas"')
    lines.append("")
    lines.append("# 3. Executar ferramentas de inspeção e hashing")
    lines.append('python main.py run encode.crypto_hash "backup.iso" --algo sha256')
    lines.append("")
    lines.append("# 4. Limpeza de arquivos temporários do sistema")
    lines.append("python main.py run system.tools --action clean_temp")
    lines.append("```")
    lines.append("")
    lines.append("### 3. Suíte de Testes Automatizados")
    lines.append("")
    lines.append("O repositório conta com rigorosa cobertura de testes automatizados com validação black-box de efeito real:")
    lines.append("")
    lines.append("```bash")
    lines.append("# Executar todos os testes")
    lines.append("pytest tests/")
    lines.append("")
    lines.append("# Executar com relatório de cobertura")
    lines.append("pytest tests/ --cov=src/wintoolbox")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Guia Aberto de Contribuição e Extensão
    lines.append("## 🛠️ Como Adicionar uma Nova Ferramenta")
    lines.append("")
    lines.append("O WinToolbox foi desenhado com arquitetura de plugins aberta e desacoplada. Para criar uma nova ferramenta, basta seguir 4 etapas:")
    lines.append("")
    lines.append("### Passo 1: Escolha a Classe Base Adequada")
    lines.append("- Herde de `FileTool` se sua ferramenta processa arquivos em massa (ex: conversores, otimizadores, renomeadores). O motor de lotes gerenciará UI, tabelas e concorrência automaticamente.")
    lines.append("- Herde de `Tool` se sua ferramenta exige uma tela customizada (ex: painéis interativos, dashboards de monitoramento, simuladores).")
    lines.append("")
    lines.append("### Passo 2: Crie a Estrutura do Módulo")
    lines.append("Crie uma subpasta dentro de `src/wintoolbox/tools/<categoria>/<nome_ferramenta>/` contendo:")
    lines.append("- `logic.py`: Lógica pura de negócio (processamento puro, independente de Qt/UI).")
    lines.append("- `tool.py`: Definição da classe que herda de `FileTool` ou `Tool`, decorada com `@register`.")
    lines.append("")
    lines.append("### Exemplo Mínimo de `FileTool`:")
    lines.append("```python")
    lines.append("from pathlib import Path")
    lines.append("from typing import Any, Dict")
    lines.append("from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register")
    lines.append("")
    lines.append("@register")
    lines.append("class MeuOtimizadorTool(FileTool):")
    lines.append('    id = "minha_categoria.meu_otimizador"')
    lines.append('    name = "Meu Otimizador"')
    lines.append('    category = "Arquivos e Pastas"')
    lines.append('    description = "Otimiza arquivos personalizados em lote com segurança."')
    lines.append('    accepts = [".txt", ".dat"]')
    lines.append('    batch_kind = "per_file"')
    lines.append('    parallel_mode = "process"  # ou \'thread\'')
    lines.append("")
    lines.append("    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:")
    lines.append("        if ctx.cancelled():")
    lines.append('            return ItemResult(success=False, source_path=src, error="Cancelado pelo usuário.")')
    lines.append("        ")
    lines.append("        # Implementação pura")
    lines.append('        conteudo = src.read_text(encoding="utf-8").strip()')
    lines.append('        dst.write_text(conteudo, encoding="utf-8")')
    lines.append("        ")
    lines.append('        return ItemResult(success=True, source_path=src, output_path=dst, message="Processado com sucesso.")')
    lines.append("```")
    lines.append("")
    lines.append("### Passo 3: Princípios de Qualidade (Diretrizes Anti-Gambiarra)")
    lines.append("1. **Validação do Efeito Real**: Se a ferramenta cria um PDF, imagem, áudio ou ZIP, o teste correspondente em `tests/` DEVE abrir o binário resultante e validar seu conteúdo interno.")
    lines.append("2. **Sem Asserções Frouxas**: Proibido usar `assert True` ou `>=` quando o valor esperado é determinístico.")
    lines.append("3. **Isolamento de Rede**: Testes unitários nunca fazem requisições reais para a internet; utilize mocks que testem cenários de falha reais (ex: 502 Bad Gateway, timeouts).")
    lines.append("4. **Tokens e Credenciais**: Chaves de API nunca devem sofrer hardcode no código-fonte. Utilize o repositório seguro global de configurações `api_tokens`.")
    lines.append("")
    lines.append("### Passo 4: Atualize a Documentação")
    lines.append("Ao finalizar a implementação, registre a nova ferramenta no [catalogo_ferramentas.md](catalogo_ferramentas.md) e execute `python docs/build_readme.py` para sincronizar este índice.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📄 Licença e Uso")
    lines.append("")
    lines.append("O **WinToolbox (All the Utils)** é um software livre sob licença aberta. Consulte o arquivo de licença no repositório para mais detalhes.")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    content = build_readme()
    readme_path = DOCS_DIR / "README.md"
    readme_path.write_text(content, encoding="utf-8")
    print(f"README.md gerado com sucesso em: {readme_path}")
    print(f"Tamanho total: {len(content)} caracteres / {len(content.splitlines())} linhas.")

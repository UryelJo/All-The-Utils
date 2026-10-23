# WinToolbox — Guia de Contexto para Novos Prompts

Este documento foi criado para servir como fonte única de verdade ao iniciar novas sessões de trabalho ou novos prompts no repositório **WinToolbox**. Copie ou consulte as diretrizes abaixo para evitar perda de contexto, inconsistências ou retrabalho.

---

## 1. Visão Geral do Projeto
O **WinToolbox** é uma caixa de ferramentas utilitárias completa e moderna para Windows desenvolvida em Python 3.12 com **PySide6 (Qt)**.
O projeto foca em utilidade prática para o dia a dia: conversão e edição em lote, diagnósticos avançados de hardware e sistema operacional, testes de rede e automações de arquivos.

### Princípios Irrevogáveis do Projeto
1. **Idioma**: Todo o código, comentários, documentação e interface de usuário devem estar exclusivamente em **Português do Brasil (pt-BR)**.
2. **Visual Limpo (Anti-IA)**:
   - Proibido o uso de emojis em botões, títulos, abas ou diálogos (`QPushButton("Converter")`, NUNCA `QPushButton("⚡ Converter 🚀")`).
   - Sem badges como "PRO", "AI Powered" ou gradientes exagerados.
   - Padrão visual alinhado ao **Windows 11 Fluent Design**: Segoe UI, bordas arredondadas suaves (4-6px), e uso da cor de destaque do sistema lida do Registro do Windows (`HKCU\Software\Microsoft\Windows\DWM\AccentColor`).
3. **Leveza e Startup Rápido (< 200ms)**:
   - Utilizar importações sob demanda (**lazy loading**) dentro de ferramentas para evitar que o carregamento inicial da aplicação fique lento.
   - Preferir módulos nativos do Python e recursos internos do PySide6 (como `QSystemTrayIcon` para notificações e bandeja) antes de introduzir bibliotecas pesadas de terceiros.
4. **Thread-Safety Estrito**:
   - NUNCA manipular widgets Qt a partir de threads secundárias.
   - Toda operação demorada de rede, disco ou subprocesso DEVE usar o `TaskRunner` (`src/wintoolbox/core/tasks.py`), que gerencia o `QThreadPool` e se comunica de forma segura através de sinais Qt (`Signal`).

---

## 2. Estrutura de Diretórios
```
WinToolbox/
├── docs/                       # Base de conhecimento e registro técnico
│   ├── README.md               # Índice da documentação
│   ├── registro_tecnico.md     # Especificação técnica e status das fases
│   ├── catalogo_ferramentas.md # Lista completa de ferramentas implementadas
│   └── contexto_para_prompts.md# Este guia de contexto
├── main.py                     # Entrypoint universal (GUI ou CLI)
├── requirements.txt            # Dependências oficiais fixadas
├── src/wintoolbox/
│   ├── core/                   # Serviços de baixo nível (batch, tasks, registry, settings...)
│   ├── ui/                     # Componentes visuais (theme, tray, main_window, widgets...)
│   └── tools/                  # Plugins de ferramentas organizados por categoria
│       ├── images/             # Manipulação de imagens
│       ├── system/             # Ferramentas e monitor do sistema
│       └── network/            # Utilitários, diagnóstico e scanners de rede
└── tests/                      # Testes automatizados (pytest e pytest-qt)
```

---

## 3. Padrão para Criação de Novas Ferramentas

### Caso A: Ferramenta que Processa Arquivos em Lote (`FileTool`)
Para ferramentas de conversão, compressão, redimensionamento ou processamento de arquivos:
```python
from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import QWidget
from wintoolbox.core.registry import FileTool, register
from wintoolbox.core.batch import BatchItemResult

@register
class MinhaFerramentaLote(FileTool):
    id = "categoria.nome_acao"
    name = "Nome Amigável da Ferramenta"
    category = "Categoria no Menu"
    description = "Descrição concisa do que a ferramenta faz."
    keywords = ["palavra1", "palavra2", "lote"]
    
    # Extensões que a ferramenta aceita na entrada
    supported_extensions = [".txt", ".json", ".csv"]
    
    # Formatos de saída disponíveis para escolha do usuário
    output_formats = ["JSON", "CSV", "TXT"]
    default_output_format = "JSON"

    def build_options_widget(self, parent: Optional[QWidget] = None) -> Optional[QWidget]:
        # Retorna widget com opções específicas (ex: checkboxes, sliders de qualidade)
        return None

    def process_file(self, src: Path, dst: Path, options: dict) -> BatchItemResult:
        # Executa a transformação do arquivo 'src' e grava em 'dst'
        # O motor do FileTool já gerencia arquivos temporários (.tmp_wtbx),
        # cancelamento, barra de progresso e gravação atômica!
        return BatchItemResult(success=True, src_path=src, dst_path=dst)
```

### Caso B: Ferramenta Interativa ou Painel (`Tool`)
Para ferramentas com telas customizadas, formulários, tabelas ou gráficos:
```python
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner

@register
class MinhaFerramentaInterativa(Tool):
    id = "categoria.nome_ferramenta"
    name = "Nome da Ferramenta"
    category = "Categoria no Menu"
    description = "Descrição clara."
    keywords = ["palavra1", "palavra2"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return MinhaView(self, parent)

class MinhaView(QWidget):
    def __init__(self, tool: MinhaFerramentaInterativa, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        lbl = QLabel(self.tool.name)
        lbl.setProperty("class", "title")
        layout.addWidget(lbl)
```

---

## 4. Comandos Essenciais para Desenvolvimento e Testes

- **Executar a Aplicação**:
  ```powershell
  $env:PYTHONPATH="src"; C:\Python312\python.exe main.py
  ```
- **Rodar a Suíte Completa de Testes**:
  ```powershell
  $env:PYTHONPATH="src"; $env:QT_QPA_PLATFORM="offscreen"; C:\Python312\python.exe -m pytest tests/
  ```
- **Listar Ferramentas via Linha de Comando**:
  ```powershell
  $env:PYTHONPATH="src"; C:\Python312\python.exe main.py --list
  ```

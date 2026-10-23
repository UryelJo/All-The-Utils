# WinToolbox - Caixa de Ferramentas para Windows

Caixa de ferramentas para Windows desenvolvida em Python com **PySide6 (Qt)**, arquitetura modular, suporte a processamento em lote nativo e interface com design sóbrio no padrão **Windows 11 Fluent**.

---

## Estrutura do Projeto

O código está estruturado em pacotes modulares dentro de `src/`, garantindo separação estrita entre lógica e interface gráfica:

```
WinToolbox/
├── main.py                     # Ponto de entrada rápido da aplicação
├── pyproject.toml              # Configurações do projeto e empacotamento
├── requirements.txt            # Dependências gerenciadas
├── iniciar.bat                 # Atalho de execução rápida
├── gerar_exe.bat               # Gerador de executável (.exe)
│
├── src/wintoolbox/
│   ├── app.py                  # Ciclo de vida da aplicação PySide6
│   ├── cli.py                  # Linha de comando para automação e lotes
│   ├── __main__.py             # Entrypoint executável (python -m wintoolbox)
│   │
│   ├── core/                   # Núcleo de serviços e motores da plataforma
│   │   ├── registry.py         # Registro dinâmico de ferramentas (Tool e FileTool)
│   │   ├── batch.py            # Motor central de processamento em lote
│   │   ├── tasks.py            # Gerenciador de threads assíncronas (TaskRunner)
│   │   ├── shell.py            # Execução de subprocessos e scripts PowerShell
│   │   ├── elevation.py        # Detecção e solicitação de elevação UAC
│   │   ├── settings.py         # Preferências do usuário (%APPDATA%/WinToolbox)
│   │   └── system_info.py      # Coleta de métricas de hardware em tempo real
│   │
│   ├── ui/                     # Interface gráfica do usuário
│   │   ├── theme.py            # Design System Fluent (Segoe UI, Dark/Light mode)
│   │   ├── main_window.py      # Janela principal com sidebar e barra de status
│   │   ├── pages/
│   │   │   └── home_page.py    # Catálogo visual agrupado por categorias
│   │   └── widgets/
│   │       ├── batch_input.py  # Tabela com Drag & Drop de arquivos e pastas
│   │       ├── output_picker.py# Seletor de destino, subpastas e conflitos
│   │       ├── action_bar.py   # Barra inferior com progresso e atalhos
│   │       ├── log_panel.py    # Console de logs monoespaçado recolhível
│   │       ├── tool_page.py    # Template automatizado para FileTools
│   │       └── command_palette.py # Busca rápida estilo VS Code com Ctrl+K
│   │
│   └── tools/                  # Catálogo de ferramentas implementadas
│       ├── images/
│       │   └── convert/        # Conversor de imagens em lote
│       └── system/
│           ├── tools/          # Ferramentas e manutenção do Windows
│           └── monitor/        # Monitor de hardware (CPU, RAM, Discos)
│
└── tests/                      # Suíte de testes automatizados (pytest e pytest-qt)
    ├── test_batch.py
    ├── test_image_convert.py
    ├── test_registry.py
    └── test_gui_smoke.py
```

---

## Funcionalidades da Fase 0 (Fundação)

1. **Conversor de Imagens em Lote (`images.convert`)**:
   - Suporte a seleção de arquivos avulsos ou pastas inteiras.
   - Opção para varredura recursiva de subpastas e espelhamento relativo da árvore de diretórios.
   - Formatos suportados: `WEBP`, `JPG/JPEG`, `PNG`, `ICO` (multi-resoluções), `BMP`, `TIFF`, `PDF`.
   - Ajuste de qualidade para compressão lossy (JPEG e WEBP).
   - Tratamento automático de canal alfa/transparência para formatos sem suporte.

2. **Ferramentas de Manutenção do Windows (`system.tools`)**:
   - Desfragmentação e Otimização de Unidade (`defrag C: /O`).
   - Limpeza de arquivos temporários (`%TEMP%`) com cálculo de espaço liberado.
   - Verificação e reparo de integridade de arquivos do sistema (`sfc /scannow`).
   - Limpeza de cache de resolução DNS (`ipconfig /flushdns`).
   - Detecção de privilégios e elevação UAC sob demanda.

3. **Monitor de Hardware em Tempo Real (`system.monitor`)**:
   - Consumo de CPU com contagem de núcleos lógicos.
   - Uso de memória RAM em GB e percentual.
   - Tabela detalhada de unidades de armazenamento com sistema de arquivos, espaço livre e barras de uso.

4. **Recursos de Plataforma**:
   - **Busca Rápida com `Ctrl+K`**: Paleta de comandos para abrir qualquer ferramenta instantaneamente.
   - **Drag & Drop**: Arraste arquivos ou pastas do Windows Explorer direto para dentro do aplicativo.
   - **Interface sem travamentos**: Todas as tarefas pesadas rodam em segundo plano via `QThreadPool` com sinais Qt thread-safe.
   - **CLI integrada**: Suporte a execução automatizada via terminal:
     ```bash
     python main.py --list
     python main.py run images.convert "D:\Fotos" -r -f WEBP -d "E:\Fotos_Convertidas"
     ```

---

## Como Executar

### Opção 1: Via atalho
Dois cliques no arquivo `iniciar.bat`.

### Opção 2: Via terminal
```bash
python main.py
```

### Rodar os Testes Automatizados
```bash
pytest tests/
```

---

## Como Gerar o Executável (.exe)

Basta dar dois cliques no arquivo `gerar_exe.bat` ou executar:
```bash
pyinstaller --noconfirm --onedir --windowed --name "WinToolbox" --paths src main.py
```
O executável final estará disponível em `dist/WinToolbox/WinToolbox.exe`.

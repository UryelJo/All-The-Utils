# WinToolbox — Registro Técnico e Base de Conhecimento do Projeto

Este diretório armazena a especificação detalhada de todas as funcionalidades, decisões de arquitetura, contratos de código e estado das fases para garantir consistência e evitar retrabalho em iterações futuras.

---

## 1. Visão Geral da Arquitetura

O projeto é construído em Python 3.12 utilizando **PySide6 (Qt)**, seguindo uma arquitetura modular baseada em plugins (`tools/`), com separação estrita entre a lógica pura e a camada de apresentação.

### Padrão de Diretórios
```
WinToolbox/
├── docs/                       # Base de conhecimento e registro técnico (este diretório)
├── main.py                     # Entrypoint universal (GUI ou CLI)
├── pyproject.toml              # Empacotamento padrão PEP 517/621
├── requirements.txt            # Dependências fixadas
├── iniciar.bat                 # Inicializador no Windows
├── gerar_exe.bat               # Compilação para .exe sem console
│
├── src/wintoolbox/
│   ├── app.py                  # Ciclo de vida da QApplication, HighDPI e temas
│   ├── cli.py                  # Linha de comando para automação
│   ├── __main__.py             # Entrypoint via python -m wintoolbox
│   │
│   ├── core/                   # Serviços de baixo nível independentes de UI
│   │   ├── registry.py         # Decorador @register e contratos Tool e FileTool
│   │   ├── batch.py            # Motor de lote: descoberta recursiva, conflitos, espelhamento
│   │   ├── tasks.py            # TaskRunner com QThreadPool e sinais Qt thread-safe
│   │   ├── shell.py            # Execução de subprocessos sem janela preta e PowerShell JSON
│   │   ├── elevation.py        # Detecção de privilégios e elevação UAC sem restart total
│   │   ├── settings.py         # Preferências JSON (%APPDATA%/WinToolbox/settings.json)
│   │   ├── history.py          # Histórico de tarefas em SQLite (%APPDATA%/WinToolbox/history.db)
│   │   ├── hotkey.py           # Atalho global Ctrl+Alt+T via RegisterHotKey (Win32)
│   │   ├── context_menu.py     # Integração com pasta 'Enviar para' (SendTo)
│   │   └── system_info.py      # Métricas de CPU, RAM e Discos via psutil
│   │
│   ├── ui/                     # Componentes de interface do usuário
│   │   ├── theme.py            # Tema Fluent Windows 11 (AccentColor nativo, Segoe UI)
│   │   ├── tray.py             # System Tray e Notificações via QSystemTrayIcon (sem libs extras)
│   │   ├── main_window.py      # Janela principal com sidebar, favoritos, recentes e drop global
│   │   ├── pages/              # Páginas do sistema (home_page, history_page, settings_page)
│   │   └── widgets/            # Widgets reutilizáveis (batch_input, output_picker, action_bar...)
│   │
│   └── tools/                  # Catálogo de ferramentas registradas
│       ├── images/             # Manipulação e conversão de imagens
│       ├── system/             # Ferramentas, manutenção e monitor do Windows
│       └── network/            # Diagnóstico, scanners, wifi, apis e utilitários de rede
│
└── tests/                      # Testes automatizados (pytest e pytest-qt)
```

---

## 2. Contratos de Ferramentas (`core/registry.py`)

Toda ferramenta herda de `BaseTool` e utiliza o decorador `@register`:

1. **`FileTool`**:
   - Usado para ferramentas que processam arquivos (imagens, documentos, dados, áudio).
   - Ganha automaticamente:
     - Tabela de entrada com suporte a pastas e checkbox recursivo.
     - Detecção de extensões e tamanhos em tempo real.
     - Seletor de saída (subpasta, mesma pasta, personalizada, espelhamento de pastas e renomeação de conflitos).
     - Barra de ação com progresso, cancelamento e botão para abrir pasta gerada.
     - Execução assíncrona com arquivo temporário (`.tmp_wtbx`) para gravação atômica.
     - Registro automático no histórico SQLite e notificações na bandeja do sistema.

2. **`Tool`**:
   - Usado para ferramentas interativas, painéis de monitoramento, formulários e utilitários de rede.
   - Implementa `build_view(parent) -> QWidget`.

---

## 3. Diretrizes de Design e Usabilidade
- **Sem cara de IA**: Proibido uso de emojis em botões/títulos, sem badges "AI/PRO", sem gradientes exagerados.
- **Identidade Windows 11 Fluent**: Bordas de 4-6px, paleta neutra sóbria, cor de destaque lida de `HKCU\Software\Microsoft\Windows\DWM\AccentColor`.
- **Lazy Loading**: Nenhuma ferramenta pesada é importada no startup. O tempo de inicialização da aplicação deve permanecer abaixo de 200 ms.
- **Thread-Safety**: Nenhuma thread em segundo plano altera widgets Qt diretamente; comunicação exclusiva via sinais Qt (`Signal`).

---

## 4. Estado das Implementações

### Fase 0 — Fundação (Concluída)
- [x] PySide6 Fluent Design System (Dark/Light).
- [x] Motor de lote com suporte a arquivos, pastas, recursão e espelhamento (`batch.py`).
- [x] TaskRunner assíncrono com QThreadPool (`tasks.py`).
- [x] Configurações persistentes com backup/restauração (`settings.py`).
- [x] Histórico de tarefas em SQLite (`history.py`).
- [x] Atalho global do Windows `Ctrl+Alt+T` (`hotkey.py`).
- [x] Bandeja do sistema e notificações nativas (`tray.py`).
- [x] Integração com menu "Enviar para" do Windows (`context_menu.py`).
- [x] Busca global com paleta de comandos `Ctrl+K` (`command_palette.py`).
- [x] Drag & drop de arquivos e pastas (tanto no widget quanto drop global na janela).
- [x] Conversor de imagens em lote (`images.convert`).
- [x] Ferramentas de manutenção do Windows (`system.tools`).
- [x] Monitor de hardware em tempo real (`system.monitor`).
- [x] CLI mínima (`main.py --list` e `main.py run`).

### Fase de Rede e Internet (Concluída - 11 Ferramentas)
- [x] Verificador de IP Local e Público com métricas de tráfego em tempo real (`network.ip_info`).
- [x] Diagnóstico de Rede: Ping, Traceroute, Nslookup, Whois, Verificador de Site e Info SSL (`network.diagnostics`).
- [x] Scanner de Portas TCP e Scanner ARP de Dispositivos na LAN (`network.scanner`).
- [x] Visualizador de Senhas Wi-Fi salvas no Windows e Gerador de QR Code Wi-Fi (`network.wifi`).
- [x] Gerenciador de DNS rápido (Google, Cloudflare, Quad9, DHCP) + Reset de Conexão (`network.dns_manager`).
- [x] Servidor Web Local e Compartilhamento com QR Code e Upload Bidirecional LAN (`network.http_server`).
- [x] Testador de API / Mini Postman com suporte a métodos HTTP, headers, body e JSON (`network.api_tester`).
- [x] Consultas Públicas: CEP (ViaCEP), CNPJ (BrasilAPI), Cotação de Moedas/Cripto em tempo real (`network.public_apis`).
- [x] Utilitários de Conexão: Wake-on-LAN (WoL), Encurtador e Expansor de Links, Download com Retomada (`network.utilities`).
- [x] Teste de Velocidade de Conexão com `speedtest-cli` e fallback de CDN (`network.speedtest`).
- [x] Cliente FTP e SFTP (SSH) simples com upload, download e navegação remota (`network.ftp_client`).

### Fase 1 — Texto, Dados e Codificação (Concluída - 11 Ferramentas)
- [x] Comparador de Textos com Diff visual lado a lado em HTML (`text.diff`).
- [x] Testador de Expressões Regulares Regex com grupos, flags e substituição (`text.regex`).
- [x] Transformações de Caixa (case), remoção de acentos e manipulador de linhas (`text.transform`).
- [x] Validador oficial e gerador de documentos brasileiros CPF e CNPJ (`text.validators_br`).
- [x] Gerador de Hash e Checksum em streaming de texto e arquivos (`encode.crypto_hash`).
- [x] Codificador e Decodificador universal Base64, URL, HTML, Hex, Unicode, ROT13 (`encode.encoders`).
- [x] Inspetor e Decodificador de tokens JWT com verificação de expiração (`encode.jwt`).
- [x] Gerador de UUID v4/v1, ULID e Senhas Seguras criptográficas em lote (`encode.generators`).
- [x] Conversor de Timestamps Epoch Unix e sincronizador de bases Bin/Oct/Dec/Hex (`encode.converter`).
- [x] Conversor universal de dados em lote JSON ↔ YAML ↔ CSV ↔ XML (`data.converter`).
- [x] Formatador e Minificador de código e estruturas JSON, XML e SQL (`data.beautifier`).


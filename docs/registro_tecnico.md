# All the Utils — Registro Técnico e Base de Conhecimento do Projeto

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
│   │   ├── system_info.py      # Métricas de CPU, RAM e Discos via psutil
│   │   ├── logging_setup.py    # Central de logs (arquivo rotativo, buffer ao vivo, níveis por biblioteca)
│   │   ├── single_instance.py  # Instância única via QLocalServer (Enviar para com o app aberto)
│   │   └── hardware.py         # Detecção de GPUs (NVIDIA/AMD/Intel), NVENC/AMF/QSV e threads
│   │
│   ├── ui/                     # Componentes de interface do usuário
│   │   ├── theme.py            # Tema Fluent Windows 11 (AccentColor nativo, Segoe UI)
│   │   ├── tray.py             # System Tray e Notificações via QSystemTrayIcon (sem libs extras)
│   │   ├── main_window.py      # Janela principal com sidebar, favoritos, recentes e drop global
│   │   ├── pages/              # Páginas do sistema (home, history, settings, debug_page)
│   │   └── widgets/            # Widgets reutilizáveis (batch_input, output_picker, action_bar...)
│   │
│   └── tools/                  # Catálogo de ferramentas registradas
│       ├── images/             # Manipulação e conversão de imagens
│       ├── system/             # Ferramentas, manutenção e monitor do Windows
│       ├── network/            # Diagnóstico, scanners, wifi, apis e utilitários de rede
│       ├── text/               # Diff, regex, transformações e validações de documentos
│       ├── encode/             # Hashes, encoders (Base64/Hex), JWT, geradores e timestamps
│       ├── data/               # Conversor de dados em lote e formatadores (JSON/XML/SQL)
│       ├── files/              # Renomeador, duplicados, disco, shredder, split/merge e processos
│       └── archive/            # Compactador e extrator de arquivos (ZIP, TAR, TAR.GZ)
│
└── tests/                      # Testes automatizados (pytest e pytest-qt)
```

### Padrão de Ferramenta Modular (UI vs Lógica Pura)
Cada ferramenta no diretório `tools/` é estruturada como um pacote dedicado com separação estrita de responsabilidades:
- `__init__.py`: Importa e expõe a classe da ferramenta registrada para auto-descoberta.
- `tool.py`: Camada de apresentação gráfica (herda de `Tool` ou `FileTool`, constrói widgets PySide6, manipula eventos de tela e conecta o `TaskRunner`).
- `logic.py`: Regras de negócio puras, funções de processamento, chamadas de sistema operacional e manipulação de I/O (totalmente desacoplado de `PySide6`, 100% testável de forma unitária e reutilizável via CLI ou scripts).

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

## 3. Gerenciador Central de Chaves de API e Tokens

Para evitar limitação de recursos que dependem de serviços de terceiros (como VirusTotal, OpenAI, Anthropic Claude, Google Gemini, GitHub, Hugging Face, OpenWeatherMap, Shodan, etc.), o sistema conta com uma central de credenciais unificada:

1. **Localização e Persistência**:
   - Armazenado no arquivo `%APPDATA%/WinToolbox/settings.json` na chave `"api_tokens": { ... }`.
   - Incluído automaticamente nas rotinas de backup e restauração (`export_settings` e `import_settings`).

2. **Como Consumir em Qualquer Ferramenta**:
   ```python
   from wintoolbox.core.settings import get_api_token

   vt_key = get_api_token("virustotal")
   if not vt_key:
       # Informa o usuário de forma amigável com orientação para configurar em Configurações
       pass
   ```

3. **Interface Gráfica (`SettingsPage`)**:
   - Localizada na aba **Configurações > Chaves de API e Tokens de Serviços**.
   - Campos com máscara de senha (`QLineEdit.Password`), botão de alternar visibilidade ("Mostrar/Ocultar") e botão de limpar.
   - Pré-configurações com rótulos amigáveis para serviços populares e botão "Adicionar Outro Serviço..." para cadastrar qualquer chave customizada informando um identificador livre.

---

## 4. Diretrizes de Design e Usabilidade
- **Sem cara de IA**: Proibido uso de emojis em botões/títulos, sem badges "AI/PRO", sem gradientes exagerados.
- **Identidade Windows 11 Fluent**: Bordas de 4-6px, paleta neutra sóbria, cor de destaque lida de `HKCU\Software\Microsoft\Windows\DWM\AccentColor`.
- **Lazy Loading**: Nenhuma ferramenta pesada é importada no startup. O tempo de inicialização da aplicação deve permanecer abaixo de 200 ms.
- **Thread-Safety**: Nenhuma thread em segundo plano altera widgets Qt diretamente; comunicação exclusiva via sinais Qt (`Signal`).

---


## 5. Estado das Implementações

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

### Fase 2 — Arquivos e Compactação (Concluída - 7 Ferramentas)
- [x] Renomeador de arquivos em lote com regras empilháveis, substituição, regex, numeração e prévia (`files.rename`).
- [x] Localizador e removedor de arquivos duplicados por tamanho, hash rápido e SHA-256 com envio seguro para a Lixeira (`files.duplicates`).
- [x] Analisador de espaço em disco e mapeamento de maiores subpastas e tipos de extensões (`files.disk_usage`).
- [x] Triturador seguro de arquivos com sobrescrita multi-passes (zeros, uns e bytes criptográficos) (`files.shredder`).
- [x] Divisor e juntador de arquivos volumosos em partes sequenciais de tamanho fixo (`files.split_merge`).
- [x] Quem Está Usando Este Arquivo? com detecção de processos bloqueadores via Windows Restart Manager API nativa (`files.lock_checker`).
- [x] Compactador e extrator de arquivos em lote com suporte a ZIP, TAR e TAR.GZ e inspeção interna (`archive.manager`).

### Fase 3 — Imagens Avançadas (Concluída - 7 Novas Ferramentas, 8 no Total)
- [x] Redimensionador e cortador de fotos e imagens em lote com interpolação Lanczos, rotação e espelhamento (`images.resize`).
- [x] Otimizador e compressor de imagens com qualidade balanceada, lossless, meta de KB e quantização PNG (`images.compress`).
- [x] Aplicador de marca d'água de texto ou logo em lote com opacidade, rotação e modo mosaico (`images.watermark`).
- [x] Filtros e ajustes de imagem em lote: brilho, contraste, saturação, nitidez, sépia, P&B e desfoque (`images.effects`).
- [x] Inspetor e removedor de metadados EXIF e GPS com anonimização e renomeação por data de captura (`images.exif`).
- [x] Gerador de ícones .ico multi-resolução para Windows e pacote completo Web Favicon + Manifest PWA (`images.favicon`).
- [x] Extrator de paleta de cores dominante com exportação para variáveis CSS, JSON e imagem PNG (`images.palette`).

### Fase 4 — PDF e Documentos (Concluída - 8 Novas Ferramentas, 100% Offline)
- [x] Divisor de PDF por páginas e juntador em lote com suporte a marcadores (`pdf.split_merge`).
- [x] Conversor de fotos e digitalizações em lote para documento PDF com ajuste de página e margens (`pdf.images_to_pdf`).
- [x] Extrator de texto e imagens embutidas em alta fidelidade (`pdf.extract`).
- [x] Compressor e otimizador de peso de PDFs via recompressão de streams e eliminação de duplicatas (`pdf.compress`).
- [x] Rotação de páginas de PDF em 90°, 180° e 270° em lote (`pdf.rotate`).
- [x] Proteção criptográfica AES com senha e desbloqueio livre permanente (`pdf.security`).
- [x] Conversor e visualizador em dois painéis de Markdown para HTML autônomo com estilos Fluent (`data.doc_converter`).
- [x] Conversor de documentos Word, Excel e PowerPoint para PDF de alta fidelidade via automação COM (`pdf.office_convert`).

### Fase 5 — Vídeo, Áudio e Mídia Local (Concluída - 8 Novas Ferramentas, 100% Offline)
- [x] Conversor de áudio/vídeo, extração de áudio, vídeo para GIF e compressão por meta de MB (`media.convert`).
- [x] Cortador e juntador rápido de áudio/vídeo sem reencodagem via stream copy (`media.trim_merge`).
- [x] Downloader de mídia multiplataforma via yt-dlp local (`media.downloader`).
- [x] Extrator em lote de frames de vídeo, intervalos e mosaicos 3x3 (`media.frame_extractor`).
- [x] Gravador de tela nativo do Windows com ffmpeg gdigrab (`media.recorder`).
- [x] Texto para fala (TTS) offline local com SAPI do Windows (`media.speech`).
- [x] Editor de metadados e tags ID3 de arquivos MP3 com capa de álbum (`media.id3_editor`).
- [x] Player de áudio e vídeo embutido com QMediaPlayer nativo (`media.player`).

---

## 6. Próximas Fases do Roadmap

### Fase 6 — Arquivos Avançados e Organização Inteligente (Concluída)
- [x] Organizador automático de pastas por extensão ou data com simulação prévia (`files.auto_organize`).
- [x] Pesquisa rápida de arquivos por nome, tamanho, data e conteúdo de texto (`files.search`).
- [x] Comparador e sincronizador de pastas com preview visual estilo diff (`files.sync`).
- [x] Criptografia e descriptografia local de arquivos com AES-256 (`files.encrypt`).
- [x] Modificador em lote de datas de criação, modificação e acesso (`files.timestamp_editor`).
- [x] Monitor de pastas em tempo real com alertas na bandeja (`files.folder_watcher`).
- [x] Assistente de backup incremental de pastas locais (`files.backup`).

### Fase 7 — Sistema, Processos e Manutenção Avançada (Concluída)
- [x] Gerenciador de processos nativo com monitor de CPU/RAM e árvore de processos (`system.process_manager`).
- [x] Gerenciador de Serviços do Windows: listar, iniciar, parar, reiniciar e tipo de boot (`system.services_manager`).
- [x] Gerenciador de inicialização do Windows (Registro + pasta Startup) (`system.startup_manager`).
- [x] Editor seguro do arquivo hosts com backup e Flush DNS (`system.hosts_editor`).
- [x] Editor de variáveis de ambiente do Usuário e Sistema com gestão do PATH (`system.env_editor`).
- [x] Visualizador de programas instalados no Windows e desinstalador (`system.uninstaller`).
- [x] Planos de energia e desligamento/reinício agendado (`system.power_manager`).
- [x] Backup de drivers de terceiros instalados via pnputil (`system.driver_backup`).
- [x] Ajustes rápidos do Windows: arquivos ocultos, extensões, modo escuro e atalhos (`system.quick_tweaks`).
- [x] Gerenciador rápido de tarefas agendadas do Windows (`system.task_scheduler`).

### Fase 8 — Ferramentas Adicionais de Imagem e Desktop (Concluída)
- [x] Montador de GIFs animados e extrator de frames (`images.gif_tools`).
- [x] Colagens e montagens de imagens em grade com preview (`images.collage`).
- [x] Conta-gotas de tela com hotkey global e lupa de zoom (`images.color_picker`).
- [x] Gerador e leitor de QR Code / código de barras (`images.qrcode`).
- [x] Captura de tela com editor de anotações (`images.screenshot`).
- [x] OCR de imagem 100% offline local com API nativa do Windows ou Tesseract (`images.ocr`).
- [x] Removedor de fundo de imagem local via rembg sob demanda (`images.remove_bg`).

### Fase 9 — Ferramentas para Desenvolvedores (Concluída - 6 Novas Ferramentas)
- [x] Gerador de dados fictícios para testes em lote (CPF, CNPJ, nomes, empresas, endereços) e Lorem Ipsum (`dev.fake_data`).
- [x] Visualizador leve de bancos SQLite locais com URI somente-leitura, DataTableView paginado e executor de consultas SQL (`dev.sqlite_viewer`).
- [x] Conversor instantâneo de cores HEX, RGB, HSL, HSV, CMYK com análise de contraste WCAG 2.1 e snippets de código dev (`dev.color_converter`).
- [x] Calculador e explicador semântico de expressões cron em português com projeção determinística de datas futuras (`dev.cron_calculator`).
- [x] Wrapper visual para PyInstaller para gerar executáveis .exe nativos com compilação assíncrona QProcess e LogPanel (`dev.pyinstaller_wrapper`).
- [x] Gerador de templates e scaffold de projetos (.gitignore por linguagem, licenças MIT/Apache/GPL, README e .editorconfig) (`dev.project_scaffold`).


### Fase 10 — Produtividade e Utilidades Pessoais (Concluída - 6 Novas Ferramentas)
- [x] Histórico da área de transferência com favoritos, busca, deduplicação e persistência em SQLite (`productivity.clipboard_history`).
- [x] Lista de tarefas / To-Do local minimalista com categorias, prioridades, datas de entrega e estatísticas (`productivity.todo`).
- [x] Timer Pomodoro de foco com máquina de estados (foco, pausa curta/longa), progresso suave e notificações nativas (`productivity.pomodoro`).
- [x] Alarmes e lembretes com repetição flexível (diária, dias úteis, semanal) e notificações no Windows (`productivity.reminders`).
- [x] Bloco de anotações rápidas com salvamento automático (debounce), fixar notas e exportação MD/TXT (`productivity.quick_notes`).
- [x] Registrador de tempo por atividade ou projeto (Time Tracker) com cronômetro, resumo e exportação CSV (`productivity.time_tracker`).


### Fase 11 — Calculadoras Especiais (Concluída - 5 Novas Ferramentas)
- [x] Conversor de unidades de medida (comprimento, massa, dados, temperatura, volume, pressão, velocidade) (`calc.unit_converter`).
- [x] Calculadora de datas, contagem e adição de dias úteis com feriados nacionais brasileiros via algoritmo de Páscoa (`calc.date_calculator`).
- [x] Calculadora financeira com juros compostos e aportes, financiamento Price/SAC e margem/markup (`calc.finance`).
- [x] Calculadora de sub-redes IPv4 / CIDR com análise de hosts, broadcast, classificação e binário (`calc.subnet_calculator`).
- [x] Relógio mundial com fusos horários de referência IANA e conversor de horas entre fusos (`calc.world_clock`).

### Fase 12 — Automação e Macros Locais (Concluída - 5 Novas Ferramentas Turbinadas)
- [x] Auto Clicker de alta velocidade configurável por tempo, botão e coordenadas fixas ou cursor com Win32 API (`automation.autoclicker`).
- [x] Gerenciador de janelas: fixar sempre no topo, transparência de 10% a 100% e snap em 6 posições da tela (`automation.window_manager`).
- [x] Executor de scripts locais (.bat, .ps1, .py, .cmd, .vbs) com biblioteca de scripts salvos e console em tempo real (`automation.script_runner`).
- [x] *Incremento de Automação*: Lançador de ambientes de trabalho (Workspaces) que abre lotes de apps, pastas e URLs com 1 clique (`automation.workspace_launcher`).
- [x] *Incremento de Automação*: Automação de pastas por regras (tipo, palavras-chave, idade, tamanho) com modo simulação (Dry Run) (`automation.folder_rules`).

### Fase 13 — Segurança e Cofre Local
- [ ] Cofre local de senhas criptografado com senha mestra AES-GCM em SQLite (`security.password_vault`).
- [ ] Autenticador de dois fatores (2FA / TOTP) local com códigos de 30s (`security.totp_manager`).


### Fase 15 — Lacunas Identificadas na Auditoria (não catalogadas nem planejadas)
Sistema e Windows:
- [x] Instalador/atualizador de programas via winget, com lista curada e "atualizar tudo" (`system.winget`).
- [x] Saúde do disco: SMART, temperatura e desgaste de SSD via `Get-PhysicalDisk`/`Get-StorageReliabilityCounter` (`system.disk_health`).
- [x] Analisador de travamentos: desligamentos inesperados (evento 41), BSODs/minidumps e erros WHEA, aprofundando os logs críticos de `system.tools` (`system.crash_analyzer`).
- [x] Pontos de restauração: listar, criar e abrir a restauração (`system.restore_points`).
- [x] Central de reparos: destravar fila de impressão (spooler), resetar componentes do Windows Update e da Microsoft Store, cache de ícones/miniaturas (`system.repair_center`; SFC/DISM já existem em `system.tools`).
- [x] Privacidade e debloat do Windows 10/11 (telemetria, anúncios, apps pré-instalados, Copilot/Recall), criando ponto de restauração antes (`system.privacy`).
- [x] Menu de contexto clássico do Windows 11 e limpeza de entradas do menu do Explorer (`system.context_menu`).
- [x] Chave do produto (OEM/BIOS) e status de ativação do Windows (`system.license_info`).

Rede:
- [x] Conexões ativas por processo, estilo TCPView (`network.connections`; usar `DataTableView`).
- [x] Monitor contínuo de latência, jitter e perda de pacotes com gráfico (`network.latency_monitor`).
- [x] Regras do Firewall do Windows: listar e bloquear aplicativo (`network.firewall`).

Arquivos:
- [x] Extração de .7z e .rar (py7zr / 7-Zip empacotado / tar nativo) no `archive.manager`, hoje com suporte completo a ZIP/TAR/7Z/RAR.
- [x] Detector e conversor de codificação de texto (ANSI/UTF-8/UTF-16, CRLF/LF) em lote (`files.encoding_converter`).
- [x] Desbloquear arquivos baixados em lote (remover Mark of the Web / Zone.Identifier) (`files.unblock`).
- [x] Mover pasta para outro disco mantendo junction (`files.junction_mover`).
- [x] Permissões NTFS: tomar posse e redefinir permissões (`files.permissions`).
- [x] Manifesto de checksums de pasta (.sha256): gerar e verificar (`files.checksum_manifest`).

PDF e Mídia:
- [x] Reordenar, girar e excluir páginas por miniaturas (`pdf.page_organizer`; renderização via pypdfium2).
- [x] Numeração de páginas, carimbo e marca d'água em PDF (`pdf.stamp`).
- [x] Markdown/HTML para PDF via QTextDocument (sem dependências) (`data.doc_converter`).
- [x] Normalização de volume (loudnorm EBU R128) em lote (`media.normalize`).
- [x] Editor de legendas SRT/VTT: converter e ajustar sincronia (`media.subtitles`).
- [x] Transcrição de áudio offline (faster-whisper / whisper com exportação para texto e legendas SRT) (`media.transcribe`).

Brasil e Segurança:
- [x] Gerador de Pix "copia e cola" e QR Code no padrão BR Code (EMV + CRC16) (`text.pix_generator`).
- [x] Feriados nacionais na calculadora de dias úteis e aba dedicada (`calc.date_calculator`).
- [x] Consultas BrasilAPI adicionais: FIPE, DDD, bancos e feriados (`network.public_apis`).
- [x] Verificador de senha vazada (Have I Been Pwned, k-anonimato) (`security.pwned_check`).
- [x] Consulta de hash no VirusTotal usando `api_tokens` (`security.virustotal`).
- [x] Verificador de assinatura digital (Authenticode) de executáveis, integrável ao `system.startup_manager` (`security.signature_check`).

### Fase 14 — Empacotamento, Distribuição e Modo Portátil
- [x] Fila central de tarefas assíncronas em segundo plano (`core/tasks.py`, `BackgroundLoader`).
- [x] Build executável PyInstaller `--onedir` com autoteste (`build.py`).
- [x] Suporte a Modo Portátil automático (sem uso de %APPDATA% se pasta local existir).
- [x] Instalador Inno Setup com integração de menu de contexto do Explorer (`installer.iss`).

### Fase 16 — Expansão do Catálogo de Utilitários de Alto Impacto (Planejada)

Esta fase consolida a expansão estratégica do All the Utils / WinToolbox, adicionando utilitários essenciais que complementam as ferramentas existentes, mantendo 100% de execução local, alto desempenho e conformidade com o ecossistema Windows 11 Fluent Design.

#### 1. Imagens e Mídia
- [x] **`images.crop_editor`** (`Tool`): Recorte interativo com proporções fixas (1:1, 16:9, 4:5, A4), rotação fina (-45° a +45°) e sobreposição de grade de terços via `QGraphicsView`.
- [x] **`images.annotate`** (`Tool`): Editor de anotações sobre capturas com setas vetoriais, retângulos, numeração sequencial de passos, caixas de texto e desfoque/pixelização de áreas sensíveis (tarjas de privacidade).
- [x] **`images.text_extractor`** (`Tool`): Capturador de texto de tela no estilo "Text Extractor" do PowerToys, com atalho global para seleção retangular e cópia instantânea do texto reconhecido via OCR WinRT nativo.
- [x] **`images.compare`** (`Tool`): Comparador visual de duas imagens com slider cortina interativo (antes/depois), mapa de diferença absoluta de pixels e modo toggle/piscante para validação de fidelidade de compressão.
- [x] **`images.svg_convert`** (`FileTool`): Conversor em lote de SVG vetorial para PNG em alta resolução e ICO para Windows, utilizando renderização nativa de alta fidelidade via `PySide6.QtSvg.QSvgRenderer`.
- [x] **`images.border_shadow`** (`FileTool`): Embelezador de screenshots e mockups em lote com cantos arredondados, sombra difusa configurável, moldura externa e fundos decorativos (gradiente ou cor sólida).
- [x] **`images.barcode`** (`Tool`): Gerador completo de códigos de barras lineares (Code 128, EAN-13, EAN-8, ITF, UPC-A) com personalização de dimensões e exportação em PNG e SVG, complementando o leitor do `images.qrcode`.
- [x] **`images.split_grid`** (`FileTool`): Divisor de imagens em grade retangular (NxM) para carrossel contínuo do Instagram e extração de sprites para jogos.

#### 2. Sistema Windows
- [x] **`system.hardware_info`** (`Tool`): Inventário aprofundado de componentes da máquina (CPU, slots e barramentos de memória RAM, placa-mãe, BIOS, GPUs, monitores conectados via EDID e portas) via CIM/WMI, com exportação de relatório técnico.
- [x] **`system.keep_awake`** (`Tool`): Inibidor de suspensão e bloqueio de tela (estilo PowerToys Awake) utilizando a API nativa `SetThreadExecutionState` do Windows, com timer de expiração configurável e ícone na bandeja.
- [x] **`system.windows_features`** (`Tool`): Gerenciador visual para habilitar/desabilitar recursos opcionais do Windows (WSL, Hyper-V, Windows Sandbox, .NET 3.5, Telnet) via DISM/PowerShell com elevação UAC transparente.
- [x] **`system.boot_analyzer`** (`Tool`): Analisador de tempo de inicialização do sistema e diagnóstico de serviços e programas que causam atraso no boot através dos logs de eventos `Microsoft-Windows-Diagnostics-Performance/Operational` (Event ID 100).
- [x] **`system.event_viewer`** (`Tool`): Visualizador amigável e performático de logs de eventos do Windows (`System`, `Application`, `Security`) com filtros por nível de severidade, origem, ID e período com exportação CSV.
- [x] **`system.devices`** (`Tool`): Painel de dispositivos do Windows com destaque para componentes com código de erro PnP, verificação de drivers e histórico completo de periféricos USB já conectados.
- [x] **`system.fonts_manager`** (`Tool`): Gerenciador de tipografia do sistema com prévia de fontes, instalação rápida sem privilégios administrativos no `%LOCALAPPDATA%\Microsoft\Windows\Fonts` e remoção segura.
- [x] **`system.wsl_manager`** (`Tool`): Painel de gerenciamento do Windows Subsystem for Linux (WSL): listar distros, status de execução, iniciar/parar com 1 clique, exportar tarball, importar e migrar VHDX para outro disco.

#### 3. Rede e Comunicação
- [x] **`network.wake_on_lan`** (`Tool`): Transmissor de pacotes mágicos UDP WOL (RFC padrão) para despertar computadores na rede local via broadcast com validação de endereço MAC.
- [x] **`network.whois`** (`Tool`): Cliente de consulta de registro de domínios via porta TCP 43 com suporte a WHOIS internacional e parse especializado do Registro.br.
- [x] **`network.bandwidth_monitor`** (`Tool`): Monitoramento em tempo real de taxas de download/upload por interface de rede com gráfico histórico contínuo e contador de sessão.
- [x] **`network.subnet_calc`** (`Tool`): Calculadora de sub-redes IPv4 / CIDR com detecção de classes, hosts úteis, broadcast e representações binárias.
- [x] **`network.dns_benchmark`** (`Tool`): Medidor de latência de resposta comparativo entre os principais servidores DNS públicos (Cloudflare, Google, Quad9, OpenDNS, DNS do provedor) com integração direta ao `network.dns_manager`.
- [ ] **`network.wifi_analyzer`** (`Tool`): Analisador de espectro Wi-Fi das redes ao alcance com BSSID, canal, largura de banda (2.4/5/6 GHz), potência do sinal (dBm) e algoritmo de recomendação do canal menos congestionado.
- [ ] **`network.socket_client`** (`Tool`): Cliente e servidor de soquetes de rede TCP e UDP (estilo netcat/socat) para diagnóstico de conectividade, envio de payloads em texto ou hexadecimal e log bidirecional.
- [ ] **`network.email_headers`** (`Tool`): Analisador forense e rastreador de cabeçalhos de e-mail (RFC 822/5322), mapeando saltos entre servidores de correio (hops), cálculo de latência de trânsito e verificação de resultados de autenticação SPF, DKIM e DMARC.
- [ ] **`network.lan_speedtest`** (`Tool`): Teste de velocidade e largura de banda ponto a ponto (peer-to-peer) entre dois computadores na mesma rede local sem depender de servidores da internet.
- [ ] **`network.shares`** (`Tool`): Gerenciador de compartilhamentos de rede SMB locais (listar, criar, revogar) e mapeador visual de unidades de rede persistentes (`net use`).
- [ ] **`network.url_tools`** (`Tool`): Utilitário de composição, decodificação e construção de links com parâmetros UTM de campanhas de marketing, com encurtador integrado.

#### 4. Texto e Redação
- [x] **`text.diff_visual`** (`Tool`): Comparador visual com realce inline de caracteres modificados, inseridos e removidos estilo GitHub diff, com visualização lado a lado ou unificada.
- [x] **`text.regex_tester`** (`Tool`): Testador e depurador de expressões regulares em tempo real com realce colorido de grupos de captura, flags e substituição dinâmica.
- [x] **`text.markdown_editor`** (`Tool`): Editor de texto Markdown com prévia sincronizada em tempo real renderizada com estilos Fluent Design, atalhos rápidos de formatação e exportação HTML.
- [x] **`text.lorem_advanced`** (`Tool`): Gerador avançado de texto de preenchimento (Lorem Ipsum, Tecnológico, Jurídico e Corporativo) em palavras, frases ou parágrafos estruturados em Markdown/HTML.
- [x] **`text.case_converter`** (`Tool`): Conversor e normalizador de caixas de texto com suporte a CamelCase, snake_case, kebab-case, PascalCase, Title Case e remoção de acentos.
- [x] **`text.stats`** (`Tool`): Analisador estatístico textual completo: contagem de caracteres, palavras, linhas, frases, tempo estimado de leitura/fala e índices de legibilidade (Flesch-Kincaid e Flesch-Brás adaptado ao português).
- [x] **`text.number_words`** (`Tool`): Conversor de valores numéricos e monetários para extenso em reais brasileiros ("R$ 1.234,50" -> "mil duzentos e trinta e quatro reais e cinquenta centavos"), ideal para recibos e documentos fiscais.
- [x] **`text.template_filler`** (`Tool`): Mala direta offline inteligente: preenchimento de modelos com sintaxe de placeholders `{{campo}}` combinados com linhas de uma planilha CSV para gerar múltiplos documentos de saída.
- [x] **`text.unicode_inspector`** (`Tool`): Detector e limpador de caracteres Unicode problemáticos: caracteres zero-width, caracteres invisíveis, homóglifos de ataque de phishing, normalização de formas canônicas NFC/NFD e substituição de aspas tipográficas.
- [x] **`text.list_ops`** (`Tool`): Processador de operações de conjuntos entre duas listas de texto (união, interseção, diferença A-B, diferença simétrica, deduplicação e ordenação natural).
- [x] **`text.name_formatter`** (`Tool`): Padronizador e capitalizador gramatical de nomes próprios em português ("JOAO DA SILVA" -> "João da Silva"), preservando partículas de ligação minúsculas ("da", "de", "do", "dos", "das", "e").
- [x] **`text.boleto_parser`** (`Tool`): Decodificador e validador de linha digitável e código de barras de boletos de cobrança bancária e concessionárias de serviços (identificação de banco emissor, valor nominal, fator de vencimento e cálculo dos dígitos verificadores módulo 10/11).

#### 5. Codificação e Hash
- [x] **`encode.base64_file`** (`Tool`): Conversor bidirecional entre arquivos físicos de qualquer extensão e Base64 / Data URI com detecção automática de MIME type por magic bytes.
- [x] **`encode.jwt_debugger`** (`Tool`): Depurador e validador de tokens JWT (RFC 7519), verificação de claims temporais (exp/nbf/iat) e validação criptográfica de assinatura HMAC (HS256/384/512).
- [x] **`encode.hash_advanced`** (`Tool`): Geração e verificação em lote de manifestos de integridade (.sha256, .md5, .sfv/CRC32), hashes criptográficos modernos (BLAKE2b, SHA3) e relatório comparativo.
- [x] **`encode.html_entities`** (`Tool`): Codificador e decodificador de entidades HTML (nomeadas, numéricas decimais e hexadecimais) com catálogo pesquisável com DataTableView.
- [x] **`encode.hmac`** (`Tool`): Gerador de códigos de autenticação de mensagem em hash (HMAC) com SHA-256, SHA-512 e MD5 a partir de chaves em texto ou hexadecimal, para validação de webhooks e assinaturas de APIs.
- [x] **`encode.keygen`** (`Tool`): Gerador de pares de chaves criptográficas assimétricas RSA (2048/4096 bits) e Ed25519 em formato OpenSSH e PEM, com visualizador de impressões digitais SHA-256 e MD5 via biblioteca `cryptography`.
- [x] **`encode.cert_inspector`** (`FileTool`): Decodificador e conversor de certificados digitais locais nos formatos PEM, CRT, CER, CSR e PFX/PKCS#12 (extração de SANs, emissor, titular, validade e algoritmo).
- [x] **`encode.nfe_key`** (`Tool`): Decodificador e validador da chave de acesso de 44 dígitos de documentos fiscais eletrônicos brasileiros (NF-e, NFC-e, CT-e, MDF-e), extraindo UF, ano/mês, CNPJ do emitente, modelo, série, número da nota e dígito verificador.
- [x] **`encode.classic_ciphers`** (`Tool`): Decodificador e codificador educativo de cifras clássicas de criptografia: Cifra de César com deslocamento configurável, Vigenère, Código Morse, Cifra Atbash e ROT13/ROT47.
- [x] **`encode.punycode_html`** (`Tool`): Conversor bidirecional de domínios internacionalizados IDN/Punycode (`xn--...`) e codificador/decodificador de entidades de caracteres HTML (nomeadas e numéricas).

#### 6. Dados e Estruturas
- [x] **`data.json_path`** (`Tool`): Avaliador de expressões JSONPath (RFC 9535) com recursão profunda `$..chave`, filtros predicados `[?(@.price < 60)]` e realce visual de resultados.
- [x] **`data.csv_to_db`** (`Tool`): Conversor em lote de arquivos CSV/TSV para bancos físicos SQLite (.db) e scripts SQL DDL/DML com inferência de tipos.
- [x] **`data.xml_json`** (`Tool`): Conversor bidirecional XML <-> JSON preservando atributos de nós (`@attr`), listas homogêneas e indentação customizada.
- [x] **`data.regex_extract`** (`Tool`): Extrator de dados em massa por regex com presets integrados (e-mails, URLs, IPs, CPFs, UUIDs) e exportação em CSV/JSON.
- [x] **`data.json_explorer`** (`Tool`): Visualizador em árvore expansível e interativo para arquivos JSON complexos, com campo de busca de chaves/valores e suporte a consultas com sintaxe JSONPath.
- [x] **`data.csv_tools`** (`FileTool`): Utilitário de manipulação de planilhas CSV em lote: divisão por linhas/colunas, fusão de múltiplos arquivos com mesmo cabeçalho, reordenação de colunas, remoção de duplicatas e conversão de delimitadores (vírgula, ponto-e-vírgula, tabulação).
- [x] **`data.sql_on_files`** (`Tool`): Carregador de arquivos tabulares (CSV, JSON, Excel) para um banco SQLite em memória (`:memory:`) com execução de consultas SQL analíticas e exportação de resultados.
- [x] **`data.struct_diff`** (`Tool`): Comparador semântico de estruturas de dados (JSON, YAML, TOML) que detecta adições, modificações e exclusões ignorando variações cosméticas de formatação e ordenação de chaves.
- [x] **`data.schema_infer`** (`Tool`): Gerador automático de esquemas e modelos de tipagem a partir de um JSON de entrada: JSON Schema, contratos Pydantic v2, Python `dataclass` e interfaces TypeScript.
- [x] **`data.excel_tools`** (`FileTool`): Utilitários para arquivos Excel (`.xlsx` via `openpyxl`): dividir abas em pastas de trabalho separadas, consolidar planilhas em uma única aba e extração de intervalos definidos.
- [x] **`data.config_convert`** (`Tool`): Conversor universal bidirecional entre formatos de arquivos de configuração: `.env`, `.ini`, `.properties`, TOML, YAML e JSON.
- [x] **`data.log_viewer`** (`Tool`): Leitor de arquivos de log volumosos com carregamento sob demanda em chunks, filtragem instantânea por regex e níveis (INFO, WARN, ERROR), realce de cores e modo monitoramento contínuo ("tail").

#### 7. Arquivos e Pastas
- [x] **`files.folder_diff`** (`Tool`): Comparador diferencial de diretórios recursivo com verificação profunda por hash SHA-256 e categorização (Idênticos, Modificados, Apenas em A, Apenas em B).
- [x] **`files.symlink_manager`** (`Tool`): Criador e auditor visual de Directory Junctions (`_winapi.CreateJunction`), Symlinks e Hardlinks com detecção de links órfãos e remoção segura sem apagar o alvo.
- [x] **`files.catalog`** (`Tool`): Indexador e catalogador de mídias externas (HDs externos, pendrives, NAS) que salva snapshots da estrutura de pastas para busca e localização de arquivos mesmo quando o dispositivo estiver desconectado.
- [x] **`files.type_detector`** (`FileTool`): Identificador do tipo real de arquivos baseado em assinaturas binárias (Magic Bytes), identificando arquivos mascarados com extensão incorreta ou corrompidos.
- [x] **`files.cleanup_finder`** (`Tool`): Localizador e higienizador em lote de diretórios vazios, arquivos com tamanho 0 byte e atalhos `.lnk` com caminhos quebrados, com modo de simulação (Dry Run).
- [x] **`files.links_manager`** (`Tool`): Gerenciador visual de ponteiros de sistema de arquivos NTFS: listagem de links simbólicos, hardlinks e junções (Junctions), detecção de alvos quebrados e criação assistida.
- [x] **`files.doc_metadata`** (`FileTool`): Inspetor e limpador de metadados em lote de documentos de escritório (Microsoft Word `.docx`, Excel `.xlsx`, PowerPoint `.pptx` e PDF), removendo autor, empresa, comentários e histórico de revisões.
- [x] **`files.tree_export`** (`Tool`): Gerador de representações de árvores de diretórios com exportação para texto puro ASCII, árvore em Markdown, tabela CSV e relatório HTML com tamanhos e metadados.
- [x] **`files.hex_viewer`** (`Tool`): Visualizador hexadecimal de arquivos binários com rolagem virtual suave para arquivos de qualquer tamanho, busca por bytes hexadecimais ou strings ASCII e navegação por offset.
- [x] **`files.robocopy_gui`** (`Tool`): Interface gráfica simplificada e amigável para o utilitário nativo Robocopy do Windows, com modos de espelhamento, retomada de cópia, limites de banda e geração de relatórios de log.
- [x] **`files.free_space_wipe`** (`Tool`): Utilitário de sanitização de segurança para sobrescrever o espaço livre de partições e discos (via automação do utilitário nativo `cipher /w` ou rotina criptográfica), prevenindo a recuperação de arquivos deletados.

#### 8. Compactação
- [x] **`archive.multi_extract`** (`Tool`): Extrator em lote de arquivos compactados (ZIP, TAR, GZ) com criação automática de subpastas e proteção estrita contra Path Traversal / Zip Slip.
- [x] **`archive.creator_advanced`** (`Tool`): Criador avançado de arquivos ZIP com seleção de algoritmos (LZMA, BZIP2, DEFLATE, STORE), nível de compressão e divisão em volumes multipartes (.001, .002).
- [x] **`archive.batch_extract`** (`FileTool`): Descompactador em lote para múltiplos arquivos compactados simultâneos (ZIP, RAR, 7Z, TAR), com criação automática de subpastas individuais, opção de deleção do arquivo de origem após sucesso e detecção inteligente de pasta raiz duplicada.
- [x] **`archive.integrity_repair`** (`Tool`): Verificador de integridade estrutural de arquivos compactados e extrator de recuperação de emergência, salvando todos os arquivos intactos contidos dentro de arquivos ZIP parcialmente danificados.
- [x] **`archive.iso_tools`** (`Tool`): Utilitário visual para montar e desmontar imagens de disco ISO e VHD/VHDX via PowerShell nativo (`Mount-DiskImage` / `Dismount-DiskImage`) e extração direta de seu conteúdo.
- [x] **`archive.comic_maker`** (`FileTool`): Conversor especializado entre pastas de imagens e arquivos de história em quadrinhos digitais CBZ (`.cbz`), com ordenação natural numérica das páginas e compressão otimizada.
- [x] **`archive.multi_volume`** (`Tool`): Criador e juntador de arquivos compactados divididos em múltiplos volumes numerados (ex: `.7z.001`, `.7z.002` ou `.part1.rar`).

#### 9. PDF e Documentos
- [x] **`pdf.metadata_editor`** (`Tool`): Editor e higienizador/anonimizador de metadados ISO 32000-1 em lote via `pypdf` com limpeza de rastros de privacidade.
- [x] **`pdf.ocr_searchable`** (`FileTool`): Conversor de PDFs escaneados ou imagens em PDFs pesquisáveis (Searchable PDF) injetando camada invisível de texto via ReportLab e `pypdf`.
- [x] **`pdf.sign_visual`** (`Tool`): Inserção visual de assinatura digitalizada (imagem PNG com fundo transparente), data e rubrica com posicionamento e redimensionamento interativo sobre páginas de PDF.
- [x] **`pdf.redact`** (`Tool`): Ferramenta de censura e tarjamento permanente (Redaction) de áreas sensíveis em páginas de PDF, removendo de fato os vetores, textos e imagens subjacentes da estrutura do documento.
- [x] **`pdf.form_filler`** (`Tool`): Leitor e preenchedor de campos interativos de formulários PDF (AcroForm), com exportação dos dados preenchidos e opção de achatamento (flatten) permanente do formulário.
- [x] **`pdf.nup_booklet`** (`FileTool`): Reorganizador de páginas para impressão: montagem de N páginas por folha (2-up, 4-up) e imposição de livreto (booklet) com ordenação para encadernação frente e verso.
- [x] **`pdf.crop_margins`** (`FileTool`): Recortador de margens vazias de documentos PDF com detecção automática da caixa delimitadora do conteúdo de texto/imagem.
- [x] **`pdf.metadata_bookmarks`** (`Tool`): Editor completo de metadados do documento (título, autor, assunto, palavras-chave) e gerenciador da árvore de sumário / marcadores de navegação (TOC Bookmarks).
- [x] **`pdf.tables_to_csv`** (`Tool`): Extrator visual de tabelas presentes em relatórios em PDF com conversão direta para arquivos CSV e planilhas do Excel via biblioteca `pdfplumber`.
- [x] **`pdf.compare`** (`Tool`): Comparador comparativo lado a lado de duas versões de um documento PDF, destacando diferenças de texto e diferenças visuais de layout renderizadas.
- [x] **`pdf.scan_cleanup`** (`FileTool`): Higienizador de digitalizações e scans: desinclinação automática (deskew), realce de contraste de texto, conversão para preto e branco puro e montagem do PDF final limpo.

#### 10. Áudio e Vídeo
- [x] **`media.subtitles`** (`Tool`): Editor e conversor bidirecional de legendas (SRT ↔ WebVTT) com ajuste fino de sincronia (Time Shift) e limpeza de tags HTML.
- [x] **`media.inspector`** (`Tool`): Relatório técnico detalhado e aprofundado no estilo MediaInfo via `ffprobe`: codecs, perfis, bitrates, faixas de áudio/legenda, metadados de câmera e capítulos, com exportação JSON/TXT.
- [x] **`media.compress_target`** (`FileTool`): Compressor inteligente de vídeo para atingir um tamanho final exato em megabytes (ex: limite de 25 MB do Discord ou WhatsApp) calculando automaticamente o bitrate de vídeo em duas passadas.
- [x] **`media.stream_manager`** (`Tool`): Gerenciador de trilhas e remux de contêineres multimídia (MKV/MP4) em alta velocidade sem recodificação: extrair, reordenar, adicionar ou remover faixas de áudio e legendas.
- [x] **`media.silence_remover`** (`FileTool`): Removedor automático de trechos de silêncio e pausas mortas em podcasts, aulas e gravações de voz utilizando o filtro nativo do FFmpeg `silenceremove`.
- [x] **`media.spectrogram`** (`Tool`): Gerador visual de forma de onda de áudio e espectrograma de frequências sonoras via FFmpeg (`showspectrumpic`) para análise acústica de faixas de som.
- [x] **`media.speed_changer`** (`FileTool`): Modificador de velocidade de reprodução de arquivos de vídeo e áudio (0.5x a 3.0x) com preservação e compensação de tom de voz (pitch) através do filtro `atempo`.
- [x] **`media.video_watermark`** (`FileTool`): Aplicador em lote de marca d'água de texto ou logotipo PNG sobre vídeos, com controle de opacidade, dimensionamento e posicionamento com aceleração por GPU.
- [x] **`media.audio_recorder`** (`Tool`): Gravador dedicado de áudio com suporte a gravação do microfone e áudio de reprodução do sistema (loopback de áudio) com visualizador de níveis sonoros VU em tempo real.
- [x] **`media.cue_splitter`** (`Tool`): Divisor de arquivos de áudio de álbum contínuo (FLAC, APE, WAV) a partir de planilhas de índice `.cue`, gerando faixas individuais nomeadas e com tags de metadados gravadas.
- [x] **`media.contact_sheet`** (`Tool`): Gerador de folhas de contato e mosaicos organizados de capturas de tela sequenciais de um vídeo com informações de duração, resolução e timecode de cada quadro.

#### 11. Desenvolvedores
- [x] **`dev.api_client`** (`Tool`): Cliente HTTP/REST interativo para desenvolvedores com suporte a GET, POST, PUT, DELETE, PATCH, headers e visualizador formatado de respostas.
- [x] **`dev.sql_formatter`** (`Tool`): Formatador e minificador SQL offline com capitalização de palavras-chave, quebras em cláusulas principais e indentação configurável.
- [x] **`dev.color_palette_generator`** (`Tool`): Gerador de paletas harmônicas (Complementar, Análoga, Triádica, Monocromática), verificação de contraste WCAG 2.1 (AA/AAA) e exportação CSS.
- [ ] **`dev.project_cleaner`** (`Tool`): Analisador e limpador em massa de pastas pesadas de compilação de código (`node_modules`, `__pycache__`, `.venv`, `bin/obj`, `target`, `dist`, `.gradle`), exibindo o espaço em disco recuperável e confirmação de limpeza.
- [ ] **`dev.line_counter`** (`Tool`): Contador de linhas de código-fonte no estilo `cloc`, discriminando linhas de código efetivo, comentários e linhas em branco por linguagem, além de catalogar marcações de `TODO` e `FIXME`.
- [ ] **`dev.selfsigned_cert`** (`Tool`): Gerador de certificados SSL/TLS autoassinados e Autoridades Certificadoras (CA) locais com suporte a múltiplos Subject Alternative Names (SAN: `localhost`, `127.0.0.1`, `*.local`) para testes de desenvolvimento via `cryptography`.
- [ ] **`dev.env_compare`** (`Tool`): Comparador entre arquivos `.env` e modelos `.env.example`, apontando chaves ausentes em ambientes de produção com mascaramento de valores sensíveis.
- [ ] **`dev.reference`** (`Tool`): Tabela de referência técnica offline contendo status HTTP, MIME types comuns, tabela ASCII/Unicode, atalhos de produtividade do Windows e códigos virtuais de teclas.
- [ ] **`dev.css_toolbox`** (`Tool`): Ferramentas visuais para desenvolvedores web: gerador de gradientes CSS, sombras multicamadas (box-shadow), cálculo da função fluida `clamp()`, conversor de medidas `px ↔ rem` e analisador de taxa de contraste WCAG.
- [ ] **`dev.minifier`** (`Tool`): Minificador e formatador local de código HTML, CSS e JavaScript sem necessidade de ferramentas baseadas em Node.js.
- [ ] **`dev.git_overview`** (`Tool`): Painel agregador de múltiplos repositórios Git locais, exibindo branches atuais, status de modificações pendentes, commits à frente da origem e limpeza de branches já integradas.
- [ ] **`dev.gitignore_license`** (`Tool`): Assistente de geração de arquivos `.gitignore` especializados por linguagem/framework e templates completos de licenças de código aberto (MIT, Apache 2.0, GPL, BSD).
- [ ] **`dev.mock_server`** (`Tool`): Servidor HTTP local para testes com capacidade de responder rotas mockadas a partir de um esquema JSON ou respostas configuradas diretamente na interface.

#### 12. Produtividade
- [x] **`productivity.pomodoro`** (`Tool`): Temporizador Pomodoro com transições de estado (foco, pausa curta, pausa longa), contagem de ciclos e visualização gráfica Fluent.
- [ ] **`productivity.finance_tracker`** (`Tool`): Controle de finanças pessoais 100% offline com categorização de despesas, gráficos analíticos e importação de extratos bancários brasileiros nos formatos OFX e CSV.
- [ ] **`productivity.recibo_orcamento`** (`Tool`): Emissor de recibos de pagamento e propostas de orçamento em formato PDF para profissionais autônomos e prestadores de serviços, com logotipo customizado e conversão de valores monetários por extenso.
- [ ] **`productivity.kanban`** (`Tool`): Quadro de organização de tarefas estilo Kanban com colunas arrastáveis personalizadas, cartões com checklists, datas de entrega e persistência em banco local.
- [ ] **`productivity.snippets`** (`Tool`): Gerenciador de atalhos e expansão de trechos de texto frequentes através de abreviações disparadas por atalhos globais do Windows via `RegisterHotKey`.
- [ ] **`productivity.flashcards`** (`Tool`): Sistema de memorização e estudo baseado no algoritmo de repetição espaçada SuperMemo (SM-2), com decks de cartões de perguntas e respostas e importação de arquivos CSV.
- [ ] **`productivity.countdown`** (`Tool`): Painel de contagem regressiva para prazos de entrega, lançamentos e aniversários, com opção de widget flutuante minimalista na área de trabalho.
- [ ] **`productivity.bookmarks`** (`Tool`): Gerenciador local de links e referências web categorizados por tags, com busca instantânea, verificador de links ativos e importação de favoritos de navegadores.
- [ ] **`productivity.journal`** (`Tool`): Diário de registros pessoais com navegação por calendário, busca textual e exportação dos registros para Markdown estruturado.
- [ ] **`productivity.ics_calendar`** (`Tool`): Visualizador e gerenciador local de eventos de calendário no formato padrão iCalendar (`.ics`).
- [ ] **`productivity.break_reminder`** (`Tool`): Assistente de ergonomia no computador para incentivo a pausas ativas regulares: descanso ocular (regra 20-20-20), alongamento físico e hidratação.

#### 13. Calculadoras
- [x] **`calc.unit_converter`** (`Tool`): Conversor universal de unidades de medida (comprimento, massa, dados digitais, volume, temperatura, velocidade e pressão) com tabela comparativa completa.
- [x] **`calc.finance`** (`Tool`): Calculadora financeira completa com juros compostos com aportes, simulação de financiamento (Price e SAC) e cálculo de margem de lucro e markup.
- [x] **`calc.programmer`** (`Tool`): Calculadora de sistemas numéricos para programadores: conversão simultânea em Hexadecimal, Decimal, Octal e Binário, chaveamento visual de bits individuais (Bit Toggles), operadores bit a bit (AND, OR, XOR, NOT, Shift) e emulação de palavras de 8, 16, 32 e 64 bits.
- [ ] **`calc.salary_br`** (`Tool`): Calculadora completa da folha de pagamento brasileira: salário líquido, deduções progressivas de INSS e IRRF, alíquota efetiva, FGTS, férias proporcionais com 1/3 e cálculo rescisório com tabelas mantidas em arquivo JSON editável.
- [ ] **`calc.health`** (`Tool`): Calculadora de parâmetros de saúde e metabolismo: Índice de Massa Corporal (IMC), Taxa Metabólica Basal (TMB), estimativa de gasto calórico diário e ingestão diária recomendada de água.
- [ ] **`calc.fuel`** (`Tool`): Comparador econômico de abastecimento Etanol vs. Gasolina (regra padrão dos 70% ou fator de eficiência real do motor) e estimador de custos de viagem com combustível e pedágios.
- [ ] **`calc.statistics`** (`Tool`): Calculadora de estatística descritiva a partir de conjuntos de dados: média aritmética/ponderada, mediana, moda, variância populacional/amostral, desvio padrão, percentis e regressão linear simples.
- [ ] **`calc.materials`** (`Tool`): Calculadora de materiais de construção e reformas: cálculo de área por m², rendimento e quantidade de latas de tinta, revestimentos cerâmicos/porcelanato com acréscimo de porcentagem de quebra/perda.
- [ ] **`calc.electrical`** (`Tool`): Calculadora elétrica residencial: consumo de aparelhos em kWh e projeção de custo na fatura de energia, Lei de Ohm e decodificador visual das faixas de cores de resistores eletrônicos.
- [ ] **`calc.transfer`** (`Tool`): Estimador de tempo de transferência e download de arquivos com base no tamanho do arquivo e velocidade de conexão (com diferenciação clara entre Mbps e MB/s).
- [ ] **`calc.split_bill`** (`Tool`): Calculadora de divisão de despesas para refeições e eventos com taxa de serviço/gorjeta e rateio de itens com consumo individualizado.
- [ ] **`calc.screen`** (`Tool`): Calculadora de densidade de pixels (PPI) de telas e monitores, proporção dimensional de aspecto (Aspect Ratio) e escala recomendada de exibição no Windows.
- [ ] **`calc.investments`** (`Tool`): Simulador comparativo de rendimento de investimentos de renda fixa brasileira (CDB, LCI/LCA, Poupança e títulos do Tesouro Direto) com aplicação da tabela regressiva de alíquotas do Imposto de Renda.

#### 14. Automação
- [x] **`automation.macro_runner`** (`Tool`): Gravador e reprodutor de macros de automação: execução em sequência de cliques do mouse, digitação de texto e atalhos de teclado com repetições e persistência JSON.
- [ ] **`automation.recipes`** (`Tool`): Mecanismo avançado de encadeamento de ferramentas do WinToolbox em "Receitas" de automação reutilizáveis (ex: "Converter Imagens" -> "Otimizar Compressão" -> "Renomear"), reutilizando os contratos padronizados `FileTool` e `get_options()`.
- [ ] **`automation.hotkeys`** (`Tool`): Central de atalhos de teclado globais configuráveis para abrir ferramentas do WinToolbox, disparar scripts locais ou lançar softwares externos.
- [ ] **`automation.device_trigger`** (`Tool`): Automação ativada por hardware: escuta eventos do Windows (via WMI/PnP) e dispara ações automáticas ao conectar pendrives, discos externos ou cartões de memória (ex: disparo de backup ou abertura de pasta).
- [ ] **`automation.process_watcher`** (`Tool`): Sentinela de processos do Windows: monitoramento de programas específicos para disparar alertas visuais ou ações quando um processo é finalizado ou quando o consumo de CPU/Memória ultrapassa um limite configurado.
- [ ] **`automation.cli_scheduler`** (`Tool`): Interface de integração entre a linha de comando do WinToolbox (`main.py run ...`) e o Agendador de Tarefas nativo do Windows para agendar rotinas headless periódicas.
- [ ] **`automation.window_rules`** (`Tool`): Gerenciador de regras automáticas para janelas de aplicativos: define tela de exibição, coordenadas fixas e estado de maximização no momento em que softwares configurados são iniciados.

> **Observação sobre APIs Externas**: Ferramentas que dependem de chaves de API pagas (como LLMs de chat, geradores de imagem generativos como DALL-E, tradutores pagos e serviços de nuvem) estão intencionalmente desacopladas do fluxo principal, priorizando funcionalidades 100% locais, gratuitas e offline. A infraestrutura para consumo de tokens em `core/settings.py` permanece disponível caso o usuário decida ativá-las futuramente.

---

## 7. Métrica de Qualidade e Testes
- **Total de Ferramentas Registradas**: 225 ferramentas operacionais em 15 categorias.
- **Padrão Arquitetural de Lógica Desacoplada**: 100% das 225 ferramentas possuem divisão estrita entre UI (`tool.py`) e regras de negócio puras (`logic.py`), com zero importações de bibliotecas gráficas na camada de lógica (validado estritamente por `tests/test_logic_architecture.py`).
- **Aceleração por Hardware (GPU) & Paralelismo**:
  - Detecção automática de GPUs instaladas (NVIDIA GeForce/RTX via `nvidia-smi` / WMI, AMD Radeon e Intel Arc/Iris).
  - Aceleração por hardware no FFmpeg via **NVIDIA NVENC** (`h264_nvenc`, `hevc_nvenc`), **AMD AMF** (`h264_amf`, `hevc_amf`) e **Intel QuickSync** (`h264_qsv`) com fallback automático resiliente para CPU (`libx264`).
  - Motor de lote concorrente (`core/batch.py`) com `ThreadPoolExecutor` dimensionado automaticamente de acordo com os núcleos da máquina (`optimal_batch_workers = min(cpu_cores, 8)`).
  - Cálculo de hashes concorrente em lote na ferramenta de localização de arquivos duplicados (`files.duplicates`).
- **Cobertura de Testes**: **Mais de 581 testes unitários e de integração** executados com 100% de aprovação no `pytest`, em conformidade estrita com as **Diretrizes de Qualidade Anti-Gambiarra** (Validação de Efeito Real Black-Box, Proibição de Asserções Frouxas e Isolamento de Rede/Ambiente).
- **Tempo de Execução dos Testes**: Suíte completa executada com sucesso e smoke test validando todas as 225 ferramentas.

---

## 8. Rebranding e Modernização da UI (Fluent 2.0 / WinUI 3)

A interface passou por uma evolução arquitetural completa inspirada no **WinUI 3 (Microsoft PowerToys / DevToys 2.0)** e **Raycast**:

1. **Design System com Tokens Semânticos (`ui/theme.py`)**:
   - Remoção de estilos escuros fixos (hardcoded) nos componentes e adoção de `ThemeTokens` dinâmicos.
   - Suporte nativo a **Modo Escuro**, **Modo Claro** e **Automático (Seguir o Windows)**, além de **Seletor de Cor de Destaque** (DWM AccentColor ou paletas predefinidas).
2. **Motor de Ícones Vetoriais Nativos (`ui/icons.py`)**:
   - Substituição total de emojis por glifos vetoriais nativos das fontes `Segoe Fluent Icons` (Windows 11) e `Segoe MDL2 Assets` (Windows 10), renderizados em High-DPI e adaptados automaticamente ao tema.
3. **Kit de Micro-Componentes Fluent (`ui/widgets/`)**:
   - `ToggleSwitch`: Interruptor deslizante animado estilo Windows 11.
   - `SettingCard`: Cartão horizontal de configurações (Ícone + Título/Descrição + Controle à direita).
   - `ToastWidget` / `show_toast`: Notificações flutuantes não-bloqueantes no canto superior direito da janela.
   - `BatchInputWidget`: Empty State com Dropzone visual tracejada, chips das extensões aceitas e remoção individual de itens por linha.
   - `CommandPaletteDialog` (`Ctrl+K`): Busca *fuzzy* tolerante a erros de digitação e acentos via `rapidfuzz`, priorizando Favoritos e Recentes.
4. **App Shell Contextual (`ui/main_window.py`)**:
   - **Sidebar Retrátil (`Ctrl+B`)**: Alterna entre o modo expandido (`280px`) e o modo compacto (`60px`).
   - **Topbar Contextual**: Botão Voltar (`Alt+Esquerda`), Breadcrumb clicável, indicador ao vivo de tarefas em execução em segundo plano, atalho de busca `Ctrl+K` e alternador rápido de tema.
5. **Tela Inicial Personalizável (`ui/pages/home_page.py` & `ui/widgets/smart_drop_dialog.py`)**:
   - **Smart Dropzone Universal**: Soltar qualquer arquivo (PDF, imagem, vídeo, áudio, planilha, compactado ou pasta) analisa as extensões e sugere todas as ferramentas compatíveis do catálogo.
   - **Mini-Monitor de Recursos**: Barras compactas em tempo real de CPU, Memória RAM e Disco Principal.
   - **Acesso Rápido**: Seções de Favoritos Fixados e Usados Recentemente, com botão de estrela direto em cada card.
   - **Catálogo com Chips de Categoria + Modos de Densidade**: Filtro por chips horizontais, alternância entre modo **Confortável** e **Compacto**, grade responsiva (2 a 4 colunas) e modal **"Personalizar Tela Inicial"** persistido em `settings.json`.


## 9. Desempenho, Diagnóstico e Distribuição

### Tabelas de dados (`ui/widgets/data_table.py`)
- **Não usar `QTableWidget` para listas do sistema.** Usar `DataTableView` + `Column`: modelo `RecordTableModel` com atualização incremental por chave (preserva seleção e rolagem), filtro/ordenação local (`RecordFilterProxy`, ordena números como números) e linhas de altura fixa.
- Consultas ao Windows rodam fora da thread da UI com `BackgroundLoader` (sem sobreposição de execuções). O filtro de texto nunca reconsulta o sistema.
- Timers de atualização usam `bind_timer_to_visibility`: as telas ficam em cache na janela principal, e um timer ligado com a tela oculta consumia CPU indefinidamente.
- Processos: `ProcessSampler` usa `NtQuerySystemInformation` (uma chamada para todos os processos, ~11 ms) em vez de psutil por processo (~1,2-2 s). Tarefas agendadas: API COM `Schedule.Service` (independente de idioma), com `schtasks` como reserva.

### Tarefas em segundo plano (`core/tasks.py`)
- `_ACTIVE_WORKERS` mantém o worker vivo até a entrega do resultado; sem isso `run_task` perdia o callback de tarefas com mais de alguns milissegundos.
- `TaskWorker` **não** herda de `QRunnable`: o pool recebe o callable (`QThreadPool.start(worker.run)`). Guardar a referência Python de um `QRunnable` com `autoDelete` gera liberação dupla intermitente (0xC0000005). Nunca usar `TaskWorker`/`QThreadPool.start` direto numa variável local: usar `run_task` ou `TaskRunner`.
- `shutdown_tasks()` é chamado em `aboutToQuit`: thread rodando durante a finalização do Python derruba o processo.
- Exceções de tarefas são registradas com traceback completo (logger `wintoolbox.tasks`).

### Central de logs (`core/logging_setup.py`) e página Depuração (`Ctrl+Shift+D`)
- Arquivo `%APPDATA%/AllTheUtils/logs/app.log` (rotativo, 5 x 2 MB) com `nível | logger | thread | arquivo:linha (função) | mensagem`; `crash.log` via faulthandler para falhas nativas.
- Captura: exceções não tratadas (inclusive threads), `warnings`, mensagens do Qt (logger `qt`), todo `QMessageBox.critical/warning` (logger `wintoolbox.ui`, com o local de quem chamou) e mensagens dos painéis de log das tarefas (logger `wintoolbox.task`).
- Nível por biblioteca em `LIBRARY_LOGGERS`, persistido em `settings.json` (`log_levels`). `--debug` ou `WINTOOLBOX_DEBUG=1` forçam DEBUG no app. yt-dlp usa o adaptador `YtDlpLogger`.
- Novas ferramentas: `from wintoolbox.core.logging_setup import get_logger` e `_log = get_logger("nome")`; evitar `except Exception: pass` sem registrar.
- A página Depuração exporta um `.zip` de diagnóstico (ambiente, logs, configurações sem `api_tokens`) para testes em outros computadores.

### Build e distribuição (`build.py`)
- Fonte única das opções do PyInstaller/Inno Setup; `gerar_exe.bat` e `gerar_instalador.bat` apenas chamam `build.py` em um ambiente isolado `.venv-build`.
- O registro importa categorias por nome (string): o build passa `PYTHONPATH=src` para o `--collect-submodules wintoolbox` funcionar. Sem isso, categorias não importadas estaticamente (PDF) ficam fora do `.exe`.
- `--self-test` (no `.exe` ou em `main.py`) monta todas as ferramentas sem exibir janelas e grava `logs/self_test.txt`; o build roda o autoteste automaticamente.
- Arquivos não-Python usados em runtime (ex: `win_ocr.ps1`) devem entrar em `DATA_FILES` do `build.py`; imports dinâmicos de bibliotecas em `--hidden-import`.

### Bibliotecas de referência (decisões da auditoria)
- PDF: `pikepdf` (compressão, recompressão de imagens) e `pypdfium2` (renderização); `pypdf` para dividir/juntar/criptografar. Evitar PyMuPDF (licença AGPL).
- OCR e voz: pacotes `winrt-*` via `core/winrt_utils.run_winrt` (thread própria: WinRT assíncrono trava em thread STA criada pelo comtypes/SAPI).
- QR/códigos de barras: `zxing-cpp` (OpenCV não é mais necessário). Imagens HEIC: `pillow-heif`; AVIF nativo no Pillow 11.3+.
- Speedtest: endpoints da Cloudflare com a biblioteca padrão (`/meta` exige cabeçalho Referer).
- Gravação de tela: `ddagrab` do ffmpeg, `gdigrab` como reserva (dimensões pares).
- XML recebido sempre via `defusedxml`; YAML com `CSafeLoader`/`CSafeDumper` quando disponíveis.
- Criptografia de arquivos: formato v2 (scrypt + AES-GCM em blocos STREAM); v1 somente leitura.
- Ferramentas de lote expõem as opções em `get_options()` (há teste garantindo isso).

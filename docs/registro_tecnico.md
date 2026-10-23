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

### Fase 9 — Ferramentas para Desenvolvedores
- [ ] Gerador de dados fictícios para testes em lote e Lorem Ipsum (`dev.fake_data`).
- [ ] Visualizador leve de bancos SQLite locais e executor de consultas SQL (`dev.sqlite_viewer`).
- [ ] Conversor instantâneo de cores HEX, RGB, HSL, HSV e CMYK (`dev.color_converter`).
- [ ] Calculador e explicador de expressões cron em português (`dev.cron_calculator`).
- [ ] Wrapper visual para PyInstaller para gerar executáveis .exe (`dev.pyinstaller_wrapper`).
- [ ] Gerador de templates e scaffold de projetos (.gitignore, README, LICENSE) (`dev.project_scaffold`).

### Fase 10 — Produtividade e Utilidades Pessoais
- [ ] Histórico da área de transferência com favoritos e busca (`productivity.clipboard_history`).
- [ ] Lista de tarefas / To-Do local minimalista em SQLite (`productivity.todo`).
- [ ] Timer Pomodoro de foco com notificações nativas (`productivity.pomodoro`).
- [ ] Alarmes e lembretes com notificação nativa do Windows (`productivity.reminders`).
- [ ] Bloco de anotações rápidas flutuante com salvamento automático (`productivity.quick_notes`).
- [ ] Registrador de tempo por atividade ou projeto (`productivity.time_tracker`).

### Fase 11 — Calculadoras Especiais
- [ ] Conversor de unidades de medida (comprimento, massa, dados, temp, etc.) (`calc.unit_converter`).
- [ ] Calculadora de datas, dias úteis e prazos (`calc.date_calculator`).
- [ ] Calculadora financeira (juros compostos, parcelas, descontos) (`calc.finance`).
- [ ] Calculadora de sub-redes IPv4 / CIDR (`calc.subnet_calculator`).
- [ ] Relógio mundial com fusos horários de referência e conversor de horas (`calc.world_clock`).

### Fase 12 — Automação e Macros Locais
- [ ] Autoclicker configurável e gravador simples de sequências (`automation.macro_recorder`).
- [ ] Gerenciador de janelas: sempre no topo, transparência e reposicionamento (`automation.window_manager`).
- [ ] Executor de scripts em lote (.bat, .ps1, .py) com console em tempo real (`automation.script_runner`).

### Fase 13 — Segurança e Cofre Local
- [ ] Cofre local de senhas criptografado com senha mestra AES-GCM em SQLite (`security.password_vault`).
- [ ] Autenticador de dois fatores (2FA / TOTP) local com códigos de 30s (`security.totp_manager`).


### Fase 15 — Lacunas Identificadas na Auditoria (não catalogadas nem planejadas)
Sistema e Windows:
- [ ] Instalador/atualizador de programas via winget, com lista curada e "atualizar tudo" (`system.winget`).
- [ ] Saúde do disco: SMART, temperatura e desgaste de SSD via `Get-PhysicalDisk`/`Get-StorageReliabilityCounter` (`system.disk_health`).
- [ ] Analisador de travamentos: desligamentos inesperados (evento 41), BSODs/minidumps e erros WHEA, aprofundando os logs críticos de `system.tools` (`system.crash_analyzer`).
- [ ] Pontos de restauração: listar, criar e abrir a restauração (`system.restore_points`).
- [ ] Central de reparos: destravar fila de impressão (spooler), resetar componentes do Windows Update e da Microsoft Store, cache de ícones/miniaturas (`system.repair_center`; SFC/DISM já existem em `system.tools`).
- [ ] Privacidade e debloat do Windows 10/11 (telemetria, anúncios, apps pré-instalados, Copilot/Recall), criando ponto de restauração antes (`system.privacy`).
- [ ] Menu de contexto clássico do Windows 11 e limpeza de entradas do menu do Explorer (`system.context_menu`).
- [ ] Chave do produto (OEM/BIOS) e status de ativação do Windows (`system.license_info`).

Rede:
- [ ] Conexões ativas por processo, estilo TCPView (`network.connections`; usar `DataTableView`).
- [ ] Monitor contínuo de latência, jitter e perda de pacotes com gráfico (`network.latency_monitor`).
- [ ] Regras do Firewall do Windows: listar e bloquear aplicativo (`network.firewall`).

Arquivos:
- [ ] Extração de .7z e .rar (py7zr / 7-Zip empacotado) no `archive.manager`, hoje limitado a ZIP/TAR.
- [ ] Detector e conversor de codificação de texto (ANSI/UTF-8/UTF-16, CRLF/LF) em lote (`files.encoding_converter`).
- [ ] Desbloquear arquivos baixados em lote (remover Mark of the Web / Zone.Identifier) (`files.unblock`).
- [ ] Mover pasta para outro disco mantendo junction (`files.junction_mover`).
- [ ] Permissões NTFS: tomar posse e redefinir permissões (`files.permissions`).
- [ ] Manifesto de checksums de pasta (.sha256): gerar e verificar (`files.checksum_manifest`).

PDF e Mídia:
- [ ] Reordenar, girar e excluir páginas por miniaturas (`pdf.page_organizer`; renderização via pypdfium2).
- [ ] Numeração de páginas, carimbo e marca d'água em PDF (`pdf.stamp`).
- [ ] Markdown/HTML para PDF via QTextDocument (sem dependências) (`data.doc_converter`).
- [ ] Normalização de volume (loudnorm) em lote (`media.normalize`).
- [ ] Editor de legendas SRT/VTT: converter e ajustar sincronia (`media.subtitles`).
- [ ] Transcrição de áudio offline (faster-whisper, opcional por tamanho) (`media.transcribe`).

Brasil e Segurança:
- [ ] Gerador de Pix "copia e cola" e QR Code no padrão BR Code (EMV + CRC16) (`text.pix_generator`).
- [ ] Feriados nacionais na calculadora de dias úteis já planejada (`calc.date_calculator`).
- [ ] Consultas BrasilAPI adicionais: FIPE, DDD, bancos e feriados (`network.public_apis`).
- [ ] Verificador de senha vazada (Have I Been Pwned, k-anonimato) (`security.pwned_check`).
- [ ] Consulta de hash no VirusTotal usando `api_tokens` (`security.virustotal`).
- [ ] Verificador de assinatura digital (Authenticode) de executáveis, integrável ao `system.startup_manager` (`security.signature_check`).

### Fase 14 — Empacotamento, Distribuição e Modo Portátil
- [x] Fila central de tarefas assíncronas em segundo plano (`core/tasks.py`, `BackgroundLoader`).
- [x] Build executável PyInstaller `--onedir` com autoteste (`build.py`).
- [ ] Suporte a Modo Portátil automático (sem uso de %APPDATA% se pasta local existir).
- [ ] Instalador Inno Setup com integração de menu de contexto do Explorer.

> **Observação sobre APIs Externas**: Ferramentas que dependem de chaves de API pagas (como LLMs de chat, geradores de imagem generativos como DALL-E, tradutores pagos e serviços de nuvem) estão intencionalmente desacopladas do fluxo principal, priorizando funcionalidades 100% locais, gratuitas e offline. A infraestrutura para consumo de tokens em `core/settings.py` permanece disponível caso o usuário decida ativá-las futuramente.

---

## 7. Métrica de Qualidade e Testes
- **Total de Ferramentas Registradas**: 79 ferramentas operacionais.
- **Padrão Arquitetural de Lógica Desacoplada**: 100% das 79 ferramentas possuem divisão estrita entre UI (`tool.py`) e regras de negócio puras (`logic.py`), com zero importações de `PySide6` na camada de lógica.
- **Aceleração por Hardware (GPU) & Paralelismo**:
  - Detecção automática de GPUs instaladas (NVIDIA GeForce/RTX via `nvidia-smi` / WMI, AMD Radeon e Intel Arc/Iris).
  - Aceleração por hardware no FFmpeg via **NVIDIA NVENC** (`h264_nvenc`, `hevc_nvenc`), **AMD AMF** (`h264_amf`, `hevc_amf`) e **Intel QuickSync** (`h264_qsv`) com fallback automático resiliente para CPU (`libx264`).
  - Motor de lote concorrente (`core/batch.py`) com `ThreadPoolExecutor` dimensionado automaticamente de acordo com os núcleos da máquina (`optimal_batch_workers = min(cpu_cores, 8)`).
  - Cálculo de hashes concorrente em lote na ferramenta de localização de arquivos duplicados (`files.duplicates`).
- **Cobertura de Testes**: 101 testes unitários e de integração executados com 100% de aprovação no `pytest` (incluindo testes de arquitetura, aceleração de hardware e cobertura das 7 ferramentas da Fase 8).
- **Tempo de Execução dos Testes**: ~22.0s.


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

# All the Utils — Catálogo Completo de Ferramentas Implementadas

Este documento mantém o inventário detalhado de todas as ferramentas disponíveis no All the Utils, seus identificadores, parâmetros e recursos, servindo de referência para desenvolvimento e futuros prompts.

---

## 1. Imagens e Mídia (`tools/images/`)

### `images.convert` — Conversão e Otimização de Imagens
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.ico`, `.heic`, `.heif`, `.avif`
- **Formatos de Saída**: WEBP, JPG, PNG, HEIC, HEIF, AVIF, TIFF, BMP, GIF, ICO, ICNS, QOI, TGA, DDS, JP2 (JPEG 2000), PPM, PCX, PDF (18 formatos)
- **Extensões de Entrada Completas (42 formatos)**: `.png`, `.apng`, `.jpg`, `.jpeg`, `.jpe`, `.jfif`, `.webp`, `.gif`, `.bmp`, `.dib`, `.tif`, `.tiff`, `.ico`, `.cur`, `.heic`, `.heif`, `.heics`, `.heifs`, `.hif`, `.avif`, `.avifs`, `.mpo`, `.psd`, `.qoi`, `.tga`, `.dds`, `.icns`, `.jp2`, `.j2k`, `.jpx`, `.jpf`, `.j2c`, `.ppm`, `.pgm`, `.pbm`, `.pnm`, `.pcx`, `.pfm`, `.sgi`, `.ras`, `.xbm`, `.xpm`
- **Recursos**:
  - Seleção de arquivos avulsos ou pastas inteiras com detecção recursiva.
  - Controle de qualidade (1-100%).
  - Manutenção de metadados EXIF opcional.
  - Redimensionamento proporcional (largura/altura máxima).
  - Suporte bidirecional nativo ao formato Apple iPhone HEIF/HEIC (`.heic`, `.heif`, `.hif`), incluindo modo **Sem Perdas (Lossless GBR bit-exact)** e amostragem de croma (`4:2:0`, `4:2:2`, `4:4:4`).
  - Gerenciamento colorimétrico ICC via LittleCMS2 (`PIL.ImageCms`): conversão automática de perfis wide-gamut (Apple Display P3 / Adobe RGB / CMYK) para **sRGB** padrão, preservação do perfil ICC original ou remoção completa (`strip`).
  - Controle de privacidade EXIF em 3 níveis: preservar EXIF completo (corrigindo orientação física via `exif_transpose`), remover apenas coordenadas **GPS** ou limpar todos os metadados.
  - Extração opcional de todos os quadros de arquivos multi-imagem (sequências `.heics`, `.avifs`, `.gif`, `.apng`, `.tiff`, `.mpo`).
  - Composição de transparência (canal alfa) sobre cor de fundo hexadecimal configurável (`#RRGGBB`) ao converter para formatos opacos (JPG, BMP, PDF, PPM, PCX).
  - Gravação atômica (`.tmp_wtbx`) e estratégia de conflito (sobrescrever, renomear numerado, pular).

### `images.resize` — Redimensionador e Cortador de Imagens
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.ico`, `.heic`, `.heif`, `.avif`
- **Recursos**:
  - 4 Modos de dimensionamento: Porcentagem (1-1000%), Largura Máxima, Altura Máxima e Caixa Exata (Largura x Altura).
  - Modos de Encaixe: Ajustar com Barras (Fit), Preencher e Cortar (Fill / Crop) e Distorcer (Stretch).
  - Filtros de Interpolação: Lanczos (alta fidelidade), Bicúbica, Bilinear e Vizinho Mais Próximo.
  - Rotação: 90° horário, 180°, 270° ou Orientação Automática EXIF (`ImageOps.exif_transpose`).
  - Espelhamento Horizontal e Vertical independentes.

### `images.compress` — Otimizador e Compressor de Imagens
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.heic`, `.heif`, `.avif`
- **Recursos**:
  - Modos de Compressão: "Qualidade Visual Balanceada" (slider 10-100%), "Otimização Sem Perdas (Lossless)" e "Meta de Tamanho Máximo em KB" (busca binária de convergência de tamanho).
  - Quantização de paleta para PNG (redução para 256 cores adaptativas).
  - Remoção opcional de metadados EXIF para economia máxima de bytes.
  - Suporte a JPEG progressivo e compressão otimizada de tabelas Huffman.

### `images.watermark` — Aplicador de Marca d'Água em Lote
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.heic`, `.heif`, `.avif`
- **Recursos**:
  - Marca de Texto: conteúdo customizado, tamanho de fonte, cor HEX com seletor visual, rotação (-90° a +90°) e suporte a fontes TrueType do sistema.
  - Marca de Imagem: seleção de logo PNG transparente com escala ajustável (% da imagem base).
  - Posição: 9 âncoras (inferior, superior, centro) ou "Mosaico Repetido (Tiled)" sobre toda a área da foto.
  - Opacidade (5% a 100%) e controle de margem/padding das bordas em pixels.

### `images.effects` — Filtros e Ajustes de Imagem
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.heic`, `.heif`, `.avif`
- **Recursos**:
  - Sliders com reset em 1 clique: Brilho (0.2x a 2.5x), Contraste (0.2x a 2.5x), Saturação (0.0x a 2.5x) e Nitidez (0.0x a 3.0x).
  - Filtros Artísticos: Preto e Branco (tons de cinza), Sépia Vintage, Inversão de Cores (negativo), Desfoque Gaussiano com raio configurável, Auto-Contraste Dinâmico, Detecção de Bordas e Realce de Detalhes.

### `images.exif` — Metadados EXIF e Privacidade
- **Tipo**: `Tool` (Interativo e Lote)
- **Recursos**:
  - **Aba Inspecionar**: Detecção de fabricante, modelo da câmera, abertura f/, exposição, ISO, distância focal, data/hora original, coordenadas GPS com link direto para o Google Maps e tabela completa de tags brutas.
  - **Aba Remoção em Lote**: Anonimização total (remoção de todos os metadados), remoção seletiva de GPS (compatível com JPEG, PNG, WEBP, TIFF, AVIF e fotos Apple iPhone `.heic`/`.heif`/`.hif`), ou renomeação automática de fotos pelo padrão `AAAA-MM-DD_HH-MM-SS` da data de captura.

### `images.favicon` — Gerador de Ícones e Favicons
- **Tipo**: `Tool`
- **Recursos**:
  - Geração de arquivo `.ico` nativo do Windows multi-resolução contendo tamanhos 16x16, 24x24, 32x32, 48x48, 64x64, 128x128 e 256x256 embutidos no mesmo arquivo.
  - Geração de pacote completo Web Favicon: `favicon.ico`, `favicon-16x16.png`, `favicon-32x32.png`, `apple-touch-icon.png`, `android-chrome-192x192.png`, `android-chrome-512x512.png`, `site.webmanifest` e snippet de código HTML pronto para copiar e colar na tag `<head>`.

### `images.palette` — Extrator de Paleta de Cores Dominantes
- **Tipo**: `Tool`
- **Recursos**:
  - Extração inteligente de 3 a 12 cores predominantes via quantização mediana do Pillow.
  - Cards com preview visual, códigos HEX, RGB, HSL e porcentagem de presença na imagem.
  - Botão de cópia rápida por cor e exportação da paleta completa como: Variáveis CSS (`:root`), JSON estruturado ou imagem contínua PNG.

### `images.gif_tools` — Montador e Extrator de GIF
- **Tipo**: `Tool` (Painel com Abas)
- **Recursos**:
  - **Aba Criar GIF Animado**: Sequenciamento de múltiplas fotos com reordenação manual, ajuste de duração por frame (ms), opções de repetição em loop (infinito ou quantidade fixa) e compilação otimizada com paleta quantizada.
  - **Aba Extrair Frames**: Decomposição automática de arquivos GIF em todos os seus quadros individuais salvos em PNG, JPEG, WEBP ou BMP.

### `images.collage` — Colagens e Montagens de Fotos
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Montagem de múltiplas fotos em grade organizada (1 a 10 colunas).
  - Controle de espaçamento entre células em pixels e seletor visual de cor de fundo com cálculo dinâmico de contraste.
  - Modos de Encaixe: "Preencher e Cortar (Quadrado uniforme)" ou "Ajustar Completo (Com bordas e proporção original)".

### `images.color_picker` — Conta-Gotas de Tela e Seletor de Cores
- **Tipo**: `Tool` (Painel Interativo em Tempo Real)
- **Recursos**:
  - Lupa de zoom 5x em tempo real com retículo de mira mostrando os pixels ao redor do cursor.
  - Captura instantânea com leitura via API nativa GDI do Windows.
  - Exibição e cópia em 1 clique em múltiplos formatos: HEX, RGB, HSL, HSV e CMYK.
  - Histórico de cores capturadas com amostras visuais interativas.

### `images.qrcode` — Gerador e Leitor de QR Code
- **Tipo**: `Tool` (Painel com Abas)
- **Recursos**:
  - **Aba Gerador**: Geração dinâmica de QR Codes a partir de textos, URLs ou chaves PIX com personalização de cores do código e de fundo, ajuste de tamanho e margens, botão "Copiar Imagem" para a área de transferência e salvamento em PNG.
  - **Aba Leitor**: Leitura e decodificação de QR Codes e códigos de barras (via `zxing-cpp`) a partir de arquivos de imagem no disco ou colados diretamente da área de transferência (Ctrl+V).

### `images.screenshot` — Captura de Tela e Anotações
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Captura em alta resolução da tela inteira com suporte a multi-monitores via Pillow ImageGrab.
  - Temporizador de atraso configurável (0 a 10 segundos).
  - Visualizador integrado com botões de cópia direta para a área de transferência e salvamento em PNG/JPEG.

### `images.ocr` — OCR de Imagem (Reconhecimento de Texto)
- **Tipo**: `Tool` (Painel Interativo 100% Offline)
- **Recursos**:
  - Reconhecimento óptico de caracteres 100% local utilizando o motor de OCR nativo do Windows (`Windows.Media.Ocr.OcrEngine`) via WinRT (pacotes `winrt-*`, direto no processo; script PowerShell como reserva) em português do Brasil e inglês, sem necessidade de internet ou serviços de nuvem.
  - Prévia da imagem carregada lado a lado com o texto extraído.
  - Contagem de caracteres e palavras, botão de cópia rápida e exportação para arquivo `.txt`.

### `images.remove_bg` — Removedor de Fundo de Imagem
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Remoção de fundo e geração de imagem com canal alpha transparente (PNG).
  - Modos de operação: Detecção automática baseada na média dos 4 cantos da imagem, Fundo Branco/Claro, Fundo Preto/Escuro ou Cor Específica (Chroma Key).
  - Sliders de tolerância de cor e suavização de bordas (feathering) para evitar serrilhado.
  - Prévia lado a lado da foto original e do resultado com fundo xadrez indicando transparência.

---


## 2. Sistema Windows e Manutenção (`tools/system/`)

### `system.tools` — Ferramentas e Manutenção do Windows
- **Tipo**: `Tool` (Interativo com Logs)
- **Abas e Funcionalidades**:
  1. **Diagnóstico do Sistema**: Verificação de Integridade SFC (`sfc /scannow`), Reparação de Imagem DISM (`dism /online /cleanup-image /restorehealth`), Limpeza de Disco DISM (`/startcomponentcleanup`).
  2. **Limpeza e Manutenção**: Limpeza profunda de arquivos temporários (`%TEMP%`, `C:\Windows\Temp`, Prefetch, logs de crash do Windows).
  3. **Diagnóstico de Disco**: Verificação de superfície CHKDSK (`chkdsk C: /scan`), Otimização e Desfragmentação TRIM (`defrag C: /O`).
  4. **Informações e Logs**: Relatório de Bateria (`powercfg /batteryreport`), Logs críticos recentes do Visualizador de Eventos (`Get-WinEvent`).
- **Recursos**: Detecção automática de elevação UAC com botão "Reiniciar como Administrador", logs em tempo real sem travar a interface.

### `system.monitor` — Monitor de Recursos em Tempo Real
- **Tipo**: `Tool` (Painel com Atualização Automática via QTimer)
- **Métricas Monitoradas**:
  - Uso de CPU (% por núcleo e frequência atual).
  - Uso de Memória RAM (% em uso, total e disponível).
  - Informações de Disco (tabela com todas as unidades físicas/lógicas, sistema de arquivos, espaço livre/usado e taxa de ocupação).
  - Tempo de atividade do sistema (Uptime desde o boot).

### `system.process_manager` — Gerenciador de Processos
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Monitor em tempo real de processos ativos com PID, Nome, Consumo de RAM (MB), % de CPU, Usuário e Status.
  - Busca instantânea por nome, PID ou usuário.
  - Ações: Finalizar Processo, Finalizar Árvore de Processos, Abrir Local do Executável no Explorer e Diálogo de Detalhes completos (linha de comando, pasta de trabalho, threads e prioridade).

### `system.services_manager` — Gerenciador de Serviços
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Listagem completa de todos os serviços do Windows com Nome, Nome de Exibição, Status com badges coloridos, Tipo de Inicialização e PID.
  - Filtro por texto e dropdown por status (Todos, Em execução, Parados).
  - Controle em 1 clique: Iniciar, Parar, Reiniciar e Alteração do Tipo de Inicialização (Automático, Manual ou Desativado) via `sc.exe` / `net.exe`.

### `system.startup_manager` — Gerenciador de Inicialização
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Listagem de programas que iniciam com o Windows a partir do Registro (`HKCU/HKLM Run`) e das pastas de Inicialização (`Startup`).
  - Adição de novos executáveis ou scripts à inicialização com suporte a escopo de Usuário ou Todos os Usuários.
  - Remoção segura de itens da inicialização e atalho para abrir o arquivo físico no Explorer.

### `system.hosts_editor` — Editor do Arquivo Hosts
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Leitura e edição estruturada do arquivo hosts do Windows (`C:\Windows\System32\drivers\etc\hosts`).
  - Tabela com Checkbox para ativar/desativar redirecionamentos sem precisar apagar a linha, Endereço IP, Domínio e Comentários.
  - Criação automática de backup com carimbo de data/hora (`hosts.bak_YYYYMMDD_HHMMSS`) antes de cada salvamento.
  - Restauração de backups anteriores e botão integrado de Flush DNS (`ipconfig /flushdns`).

### `system.env_editor` — Variáveis de Ambiente e PATH
- **Tipo**: `Tool` (Painel com Abas)
- **Recursos**:
  - Gestão de variáveis de ambiente do Usuário Atual (`HKCU`) e da Máquina / Sistema (`HKLM`).
  - **Aba Variáveis**: Criação, edição e exclusão de variáveis com broadcast nativo `WM_SETTINGCHANGE` para aplicar sem reiniciar o PC.
  - **Aba Editor Visual do PATH**: Exibe cada diretório do PATH em linhas separadas, identifica visualmente pastas órfãs/inexistentes em vermelho, reordenação (Mover para Cima/Baixo), adição de pastas e limpeza automática de caminhos inválidos.

### `system.uninstaller` — Programas Instalados e Desinstalador
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Varredura em profundidade de aplicativos instalados no Windows (Registros de 64-bit, 32-bit Wow6432Node e Usuário).
  - Exibição de Nome, Versão, Publicador, Tamanho Estimado em MB e Data de Instalação.
  - Execução do desinstalador oficial do programa ou Desinstalação Silenciosa sem prompts (Quiet Uninstall).
  - Cópia do comando de desinstalação para a área de transferência.

### `system.power_manager` — Planos de Energia e Desligamento
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Listagem dos planos de energia disponíveis no Windows (`powercfg /list`), identificação do plano ativo e troca rápida de plano.
  - Informações de status de bateria (nível %, tomada vs bateria, tempo restante).
  - Agendador de Ações do Sistema: Desligar, Reiniciar, Suspender (Sleep) ou Bloquear a Estação de Trabalho com contagem regressiva em minutos ou em horário específico do dia.
  - Cancelamento em 1 clique de qualquer desligamento agendado pendente (`shutdown /a`).

### `system.driver_backup` — Backup de Drivers do Windows
- **Tipo**: `Tool` (Painel com Execução Assíncrona)
- **Recursos**:
  - Enumeração de todos os pacotes de drivers de terceiros instalados no sistema via `pnputil /enum-drivers` (INF publicado, fabricante, classe, versão e data).
  - Exportação e backup completo de todos os pacotes de drivers para qualquer pasta selecionada com 1 clique via `pnputil /export-driver`.
  - Execução em segundo plano com acompanhamento de progresso sem travar a interface.

### `system.quick_tweaks` — Ajustes Rápidos do Windows
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Alternância imediata de opções essenciais do Windows:
    - Exibir/ocultar arquivos, pastas e unidades ocultas.
    - Exibir/ocultar extensões de tipos de arquivos conhecidos.
    - Exibir ícone "Este Computador" na Área de Trabalho.
    - Ocultar histórico de arquivos recentes no Acesso Rápido.
    - Modo escuro para Aplicativos e Modo escuro para o Sistema Operacional.
  - Botão integrado para reiniciar o Windows Explorer e atualizar a interface imediatamente.

### `system.task_scheduler` — Tarefas Agendadas do Windows
- **Tipo**: `Tool` (Painel Interativo)
- **Recursos**:
  - Consulta rápida de tarefas agendadas via `schtasks /query` com Nome, Caminho na árvore, Próxima Execução e Status.
  - Filtro para ocultar tarefas padrão da Microsoft e focar nas tarefas criadas por softwares instalados.
  - Ações imediatas: Executar Tarefa Agora (`schtasks /run`), Ativar e Desativar tarefas agendadas.

### `system.winget` — Gerenciador de Pacotes e Programas (winget)
- **Tipo**: `Tool` (Interativo e Automação de Software)
- **Recursos**:
  - Integração com o Windows Package Manager oficial (`winget.exe`).
  - Verificação de atualizações pendentes de todos os programas instalados.
  - Ação em 1 clique para "Atualizar Todos os Programas" em lote.
  - Catálogo curado de softwares populares organizados por categorias (Navegadores, Desenvolvimento, Utilitários, Comunicação, Multimídia).
  - Instalação e atualização silenciosa sem assistentes manuais.

### `system.disk_health` — Diagnóstico de Saúde de Discos e SSDs (SMART)
- **Tipo**: `Tool` (Diagnóstico de Armazenamento)
- **Recursos**:
  - Diagnóstico físico de discos HDD e SSDs NVMe/SATA via PowerShell e CIM (`Get-PhysicalDisk`, `Get-StorageReliabilityCounter`).
  - Métricas de integridade: Status de Saúde, Desgaste de SSD (Wear % e Vida Útil Restante), Temperatura atual em °C, Erros de Leitura/Gravação e Horas Ligado (Power-On Hours).
  - Identificação de Modelo, Número de Série, Tipo de Mídia e Tipo de Barramento (NVMe, SATA, USB).

### `system.crash_analyzer` — Analisador de Falhas e Telas Azuis (BSOD)
- **Tipo**: `Tool` (Diagnóstico Forense do Sistema)
- **Recursos**:
  - Varredura e correlação de eventos críticos de desligamento e pane no Visualizador de Eventos:
    - Evento 41 (Kernel-Power / Desligamento Inesperado).
    - Evento 1001 (BugCheck / Tela Azul da Morte - BSOD).
    - Eventos 18 e 19 (Erros Críticos de Hardware WHEA).
  - Tradutor semântico de códigos de erro de parada (BugCheck Code / Stop Code) para explicações claras e possíveis causas.
  - Detecção e listagem de arquivos de despejo de memória (Minidumps) em `C:\Windows\Minidump` com data e tamanho.

### `system.restore_points` — Pontos de Restauração do Windows
- **Tipo**: `Tool` (Proteção e Recuperação do Sistema)
- **Recursos**:
  - Listagem de pontos de restauração existentes no computador com Descrição, Data/Hora e Tipo de Sequência.
  - Criação instantânea de novo Ponto de Restauração com nome customizado via WMI / PowerShell (`Checkpoint-Computer`).
  - Atalho direto para iniciar o Assistente Oficial de Restauração do Sistema do Windows (`rstrui.exe`).

### `system.repair_center` — Central de Reparos Rápidos do Windows
- **Tipo**: `Tool` (Manutenção do Sistema)
- **Recursos**:
  - Reparos rápidos em 1 clique para problemas comuns do Windows:
    - **Destravar Spooler de Impressão**: Interrompe o serviço, limpa arquivos presos na pasta `PRINTERS` e reinicia o spooler.
    - **Reconstruir Cache de Ícones e Miniaturas**: Finaliza o Explorer, apaga bancos `IconCache.db` e `thumbcache_*.db` corrompidos e reabre a interface.
    - **Resetar Componentes do Windows Update**: Para serviços relacionados, renomeia as pastas `SoftwareDistribution` e `Catroot2` e reinicia os serviços.
    - **Resetar Microsoft Store**: Executa a limpeza e reset nativo do cache da loja via `wsreset.exe`.

### `system.privacy` — Otimizador de Privacidade e Telemetria
- **Tipo**: `Tool` (Ajustes de Registro e Privacidade)
- **Recursos**:
  - Controle centralizado de opções de privacidade e desativação de coletas desnecessárias no Windows 10 e 11:
    - Desativar Telemetria e Diagnósticos da Microsoft (`AllowTelemetry = 0`).
    - Desativar ID de Anúncios e Rastreamento de Usuário.
    - Desativar Sugestões e Dicas do Windows no Menu Iniciar e Configurações.
    - Desativar Integração do Windows Copilot.
    - Desativar Snapshots do Windows Recall de Inteligência Artificial.
    - Desativar Rastreamento de Execução de Aplicativos e Histórico de Atividade.
  - Opção para criar Ponto de Restauração do Sistema automaticamente antes de aplicar as alterações.

### `system.context_menu` — Restaurador do Menu de Contexto Clássico
- **Tipo**: `Tool` (Customização do Windows 11)
- **Recursos**:
  - Alternância entre o Menu de Contexto Clássico completo (estilo Windows 10 sem necessidade de clicar em "Mostrar mais opções") e o Menu Moderno do Windows 11 através da chave de registro `{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}`.
  - Botão integrado para reiniciar o `explorer.exe` e aplicar a alteração instantaneamente.

### `system.license_info` — Informações de Licença e Chave OEM da BIOS
- **Tipo**: `Tool` (Auditoria e Licenciamento)
- **Recursos**:
  - Extração direta da Chave de Produto original de fábrica (OEM Product Key) gravada na tabela MSDM da BIOS/UEFI da placa-mãe via CIM / SoftwareLicensingService.
  - Consulta do Status Oficial de Ativação do Windows via script nativo `slmgr.vbs /dli` (Edição, Canal de Licença e Estado de Licença).
  - Botão de cópia rápida da chave original do produto.

---


## 3. Rede e Internet (`tools/network/`)

### `network.ip_info` — Verificador de IP e Monitor de Rede
- **Tipo**: `Tool`
- **Recursos**:
  - Detecção de IP Público (via API ipify com timeout curto) e provedor/cidade.
  - Listagem de todas as interfaces de rede locais (IPv4, máscara, MAC, status Ativo/Inativo, velocidade de link em Mbps).
  - Monitor em tempo real de taxa de transferência (Download e Upload em KB/s e MB/s via `psutil.net_io_counters()`).

### `network.diagnostics` — Diagnóstico Completo de Conexão
- **Tipo**: `Tool`
- **Recursos**:
  - **Ping ICMP**: Estatísticas completas (pacotes enviados, recebidos, perda %, min/avg/max latência).
  - **Traceroute**: Rastreamento de rota até o destino via PowerShell/tracert nativo.
  - **DNS Lookup**: Resolução direta de nomes e registros A/AAAA/MX.
  - **Whois**: Consulta de titularidade de domínio na porta 43 via socket TCP nativo.
  - **Verificador de Site**: Checagem de disponibilidade HTTP/HTTPS com status code, tempo de resposta em ms e redirecionamento.
  - **Inspeção de Certificado SSL**: Leitura nativa de emissor, titular, data de emissão, validade e dias restantes para expiração via biblioteca `ssl`.

### `network.scanner` — Scanners de Rede (Portas e Dispositivos ARP)
- **Tipo**: `Tool`
- **Recursos**:
  - **Scanner de Portas TCP**: Varredura rápida multi-thread de portas individuais, faixas customizadas ou portas comuns (21, 22, 80, 443, 3389, 8080, etc.).
  - **Scanner de Dispositivos ARP**: Varredura de IPs na sub-rede local ativa com resolução de MAC e hostname reverso DNS.

### `network.wifi` — Senhas Wi-Fi e Gerador de QR Code
- **Tipo**: `Tool`
- **Recursos**:
  - Extração de senhas de redes Wi-Fi salvas no Windows via `netsh wlan show profile name="SSID" key=clear`.
  - Tabela com SSID, tipo de segurança e senha em texto claro com botão de cópia direta.
  - Gerador de QR Code Wi-Fi compatível com padrão móvel Android/iOS (`WIFI:S:ssid;T:WPA;P:password;;`).

### `network.dns_manager` — Gerenciador de DNS e Reset de Rede
- **Tipo**: `Tool`
- **Recursos**:
  - Troca rápida de servidores DNS em um clique para a interface de rede ativa: Cloudflare (1.1.1.1), Google (8.8.8.8), Quad9 (9.9.9.9) ou DHCP Automático.
  - Teste de latência comparativo entre os provedores de DNS.
  - Reset de Conexão em um clique: Flush DNS (`ipconfig /flushdns`), Liberação/Renovação de IP (`/release` e `/renew`), e Restauração de Catálogo Winsock e pilha TCP/IP.

### `network.http_server` — Servidor Web Local e Compartilhamento de Arquivos
- **Tipo**: `Tool`
- **Recursos**:
  - Compartilha qualquer pasta do computador na rede local em um clique via HTTP.
  - Gera QR Code na tela para celulares na mesma rede Wi-Fi abrirem instantaneamente a pasta no navegador.
  - **Transferência Bidirecional**: Interface web customizada que permite ao celular enviar (upload) fotos, vídeos e documentos diretamente para a pasta do computador sem instalar nenhum aplicativo.
  - Painel de log de acessos em tempo real com IP de quem conectou.

### `network.api_tester` — Testador de API (Mini Postman)
- **Tipo**: `Tool`
- **Recursos**:
  - Métodos HTTP: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`.
  - Editor de Headers customizados (chave/valor) e Body de requisição (JSON, texto ou formulário).
  - Exibição de Status HTTP colorido (ex: 200 OK verde, 404 vermelho), tempo total de resposta em ms e tamanho do payload.
  - Visualização de Headers de resposta e Corpo formatado com identação JSON automática.

### `network.public_apis` — Consultas Públicas (CEP, CNPJ, Cotações)
- **Tipo**: `Tool`
- **Recursos**:
  - **Consulta de CEP**: Busca dados de logradouro, bairro, cidade, estado e DDD via ViaCEP.
  - **Consulta de CNPJ**: Busca razão social, nome fantasia, status cadastral, CNAE principal, capital social e endereço via BrasilAPI.
  - **Cotações em Tempo Real**: Dólar Comercial (USD), Euro (EUR), Libra (GBP), Bitcoin (BTC) e Ethereum (ETH) com valor atual, variação percentual no dia e data da última atualização via AwesomeAPI.

### `network.utilities` — Utilitários de Conexão
- **Tipo**: `Tool`
- **Recursos**:
  - **Wake-on-LAN**: Emissão de Magic Packet de 102 bytes via UDP:9 para ligar computadores na rede local através do endereço MAC.
  - **Encurtador de Links**: Geração de URLs curtas via APIs públicas TinyURL ou is.gd em um clique.
  - **Expansor de Links (Anti-Phishing)**: Rastreamento completo da cadeia de redirecionamentos HTTP (301, 302, 307) para revelar o destino final seguro de URLs encurtadas.
  - **Download com Retomada**: Gerenciador de download com suporte a cabeçalho HTTP `Range: bytes=...`, permitindo continuar downloads interrompidos sem recomeçar do zero.

### `network.speedtest` — Teste de Velocidade de Internet
- **Tipo**: `Tool`
- **Recursos**:
  - Medição de Latência / Ping em milissegundos.
  - Medição de Taxa de Download em Mbps.
  - Medição de Taxa de Upload em Mbps.
  - Identificação de Servidor de teste, Provedor de Internet (ISP) e IP público.
  - Mede ping, jitter, download e upload (4 conexões paralelas) nos servidores da Cloudflare (`speed.cloudflare.com`), apenas com a biblioteca padrão; identifica provedor, IP e ponto de presença.

### `network.ftp_client` — Cliente FTP / SFTP Simples
- **Tipo**: `Tool`
- **Recursos**:
  - Conexão com servidores FTP (porta 21) via `ftplib` e SFTP / SSH (porta 22) via `paramiko`.
  - Navegação hierárquica por pastas e arquivos remotos com duplo clique.
  - Download de arquivos remotos para pasta local com barra de progresso.
  - Upload de arquivos locais para o servidor remoto com barra de progresso.
  - Exclusão de itens remotos com confirmação de segurança.

### `network.connections` — Monitor de Conexões de Rede por Processo
- **Tipo**: `Tool` (Monitoramento ao Vivo estilo TCPView)
- **Recursos**:
  - Monitoramento contínuo de sockets e conexões de rede em tempo real via `psutil.net_connections`.
  - Exibição de Protocolo (TCP/UDP), Endereço e Porta Local, Endereço e Porta Remota, Estado da Conexão (ESTABLISHED, LISTEN, CLOSE_WAIT, etc.), PID e Nome do Processo associado.
  - Tabela interativa com `DataTableView`, ordenação dinâmica, busca rápida por texto e filtro por estado.
  - Ação em 1 clique para finalizar processo suspeito ou indesejado diretamente da interface.

### `network.latency_monitor` — Monitor Contínuo de Latência e Jitter
- **Tipo**: `Tool` (Telemetria e Diagnóstico de Conexão)
- **Recursos**:
  - Pings contínuos com intervalo customizável contra qualquer host ou IP (ex: `1.1.1.1`, `8.8.8.8`).
  - Cálculo estatístico em tempo real:
    - Jitter médio e instantâneo conforme a especificação oficial RFC 3550.
    - Latência Mínima, Média e Máxima em milissegundos.
    - Taxa de Perda de Pacotes (% Packet Loss).
  - Histórico dos últimos 30 pacotes e visualização gráfica com indicador de status da conexão.

### `network.firewall` — Gerenciador de Regras do Firewall do Windows
- **Tipo**: `Tool` (Segurança de Rede do Windows)
- **Recursos**:
  - Consulta estruturada de regras ativas do Windows Defender Firewall via PowerShell (`Get-NetFirewallRule`).
  - Tabela com Nome de Exibição, Direção (Entrada / Saída), Ação (Permitir / Bloquear) e Status Ativado/Desativado.
  - Bloqueio Rápido de Aplicativo: seletor de arquivo `.exe` para criar regras de bloqueio de entrada e saída com 1 clique (`New-NetFirewallRule -Action Block`).

---

## 4. Texto e Redação (`tools/text/`)

### `text.diff` — Comparador de Textos (Diff Visual)
- **Tipo**: `Tool`
- **Recursos**:
  - Comparação lado a lado entre Texto Original (A) e Modificado (B).
  - Opções para ignorar espaços nas bordas e ignorar maiúsculas/minúsculas.
  - Visualização em HTML com realce de adições (+ verde) e remoções (- vermelho).
  - Contagem de linhas inseridas, removidas e inalteradas.

### `text.regex` — Testador de Expressões Regulares (Regex)
- **Tipo**: `Tool`
- **Recursos**:
  - Teste em tempo real de expressões regulares contra texto de entrada.
  - Flags: IgnoreCase (i), Multilinha (m) e Ponto inclui quebra de linha (s).
  - Tabela detalhada de correspondências com posições e grupos de captura.
  - Mecanismo de substituição com resultado imediato e guia rápido de sintaxe.

### `text.transform` — Transformações de Texto e Linhas
- **Tipo**: `Tool`
- **Recursos**:
  - Conversão de caixa: MAIÚSCULAS, minúsculas, Primeira Maiúscula, camelCase, snake_case, kebab-case, slug web.
  - Limpeza de texto: Remoção de acentos e diacríticos mantendo letras base.
  - Manipulação de linhas: Ordenação A-Z / Z-A, remoção de duplicadas, remoção de linhas vazias, inversão de ordem, numeração e prefixo/sufixo em lote.
  - Contador estatístico em tempo real: caracteres, palavras, linhas e bytes UTF-8.

### `text.validators_br` — Validador e Gerador de Documentos BR
- **Tipo**: `Tool`
- **Recursos**:
  - Validação oficial de dígitos verificadores de CPF e CNPJ (Módulo 11).
  - Formatação e desformatação rápida (com ou sem pontuação).
  - Gerador de CPF e CNPJ válidos para ambientes de homologação e testes de software.

### `text.pix_generator` — Gerador de Cobrança Pix e QR Code (BR Code)
- **Tipo**: `Tool` (Financeiro e Padrão Banco Central)
- **Recursos**:
  - Geração de código "Copia e Cola" Pix no padrão oficial EMVCo / BR Code do Banco Central do Brasil.
  - Cálculo matemático do checksum CRC16-CCITT polinomial `0x1021` (início `0xFFFF`).
  - Suporte a todos os tipos de chaves Pix: CPF, CNPJ, E-mail, Telefone celular (`+55...`) e Chave Aleatória EVP.
  - Campos adicionais: Nome do Beneficiário, Cidade, Valor em Reais (opcional) e Identificador de Transação / TxID (opcional).
### `text.diff_visual` — Comparador Visual de Texto (Diff Inline)
- **Tipo**: `Tool`
- **Recursos**:
  - Comparação linha a linha e caractere por caractere (inline diff) estilo GitHub / VS Code.
  - Modos de visualização lado a lado (Side-by-Side) e unificado (Unified).
  - Realce sintático e métricas estatísticas: linhas adicionadas, removidas, modificadas e inalteradas.

### `text.regex_tester` — Testador e Depurador de Expressões Regulares
- **Tipo**: `Tool`
- **Recursos**:
  - Teste de regex em tempo real com realce colorido de grupos de captura e posições.
  - Flags de compilação integradas: `re.IGNORECASE`, `re.MULTILINE`, `re.DOTALL`, `re.VERBOSE`.
  - Mecanismo dinâmico de substituição com referências numéricas (`\1`, `\2`) e grupos nomeados.
  - Catálogo de expressões regulares prontas para validação de dados comuns.

### `text.markdown_editor` — Editor Markdown com Prévia Fluent
- **Tipo**: `Tool`
- **Recursos**:
  - Editor de texto Markdown com prévia sincronizada em tempo real renderizada com estilos Fluent Design.
  - Barra de ferramentas com atalhos rápidos de formatação (títulos, negrito, itálico, código, tabelas, links).
  - Exportação instantânea para documento HTML estilizado e arquivo `.md`.

### `text.lorem_advanced` — Gerador Avançado de Texto de Preenchimento
- **Tipo**: `Tool`
- **Recursos**:
  - Geração de texto por palavras, frases ou parágrafos.
  - 4 universos temáticos especializados: Clássico (Cícero / De Finibus), Tecnológico (Dev/DevOps), Jurídico (Direito Civil/Penal brasileiro) e Corporativo (Startup/Business).
  - Opções de formatação estruturada: Texto puro, HTML com tags `<p>`, `<h1>`, `<ul>` e Markdown.

### `text.case_converter` — Conversor Universal de Caixa Tipográfica
- **Tipo**: `Tool`
- **Recursos**:
  - Conversão em tempo real entre 12 estilos: camelCase, PascalCase, snake_case, CONSTANT_CASE, kebab-case, Title Case, Sentence case, Train-Case, dot.case, path/case, Alternating Case e Invert Case.
  - Higienização opcional de diacríticos e acentos Unicode para ASCII puro.
  - Suporte a processamento frase a frase ou linha por linha para listas de identificadores.

### `text.stats` — Analisador Estatístico Textual e Legibilidade
- **Tipo**: `Tool`
- **Recursos**:
  - Contagem precisa de caracteres (com e sem espaços), palavras, linhas, frases e parágrafos.
  - Estimativa de tempo de leitura silenciosa e tempo de fala/oratória em ritmo natural.
  - Cálculo de densidade vocabular e palavras mais frequentes com filtro configurável de stopwords em português.
  - Índice de Legibilidade Flesch-Brás (Martins et al. 1996) e Flesch Reading Ease com classificação de faixa etária/escolaridade recomendada.
  - Exportação de relatório estatístico formatado para a área de transferência.

### `text.number_words` — Número e Moeda por Extenso (BRL)
- **Tipo**: `Tool`
- **Recursos**:
  - Conversão de números inteiros (até quatrilhões) e valores monetários em Reais (BRL) para extenso.
  - Conformidade estrita com as regras ortográficas brasileiras: singular/plural ('real'/'reais', 'centavo'/'centavos') e regra gramatical do conectivo 'de' em milhões/bilhões redondos ('dois milhões de reais').
  - Formato especial protegido para emissão de cheques e recibos (`# ... #` em caixa alta).
  - Conversão de numerais ordinais masculinos e femininos (1º -> primeiro, 2ª -> segunda).

### `text.template_filler` — Mala Direta e Preenchimento de Modelos
- **Tipo**: `Tool`
- **Recursos**:
  - Preenchimento em lote de documentos a partir de modelos com sintaxe de placeholders `{{campo}}`.
  - Modificadores de texto integrados: `{{campo | upper}}`, `{{campo | lower}}`, `{{campo | title}}`, `{{campo | capitalize}}`.
  - Importação de dados tabulares em formato CSV (detecção automática de delimitadores vírgula e ponto-e-vírgula).
  - Pré-visualização navegável registro por registro.
  - Geração em lote com salvamento de arquivos individuais nomeados dinamicamente ou arquivo consolidado único.

### `text.unicode_inspector` — Inspetor e Higienizador Unicode
- **Tipo**: `Tool`
- **Recursos**:
  - Detecção de caracteres de largura zero (Zero-Width Space, ZWNJ, ZWJ, BOM `\uFEFF`).
  - Identificação de espaços especiais Unicode (Non-Breaking Space `\u00A0`, En/Em space).
  - Detecção e neutralização de homóglifos de alfabetos mistos (cirílico/grego) utilizados em ataques de phishing.
  - Substituição de aspas tipográficas curvas por aspas ASCII retas.
  - Normalização canônica Unicode nos formatos padrão NFC, NFD, NFKC e NFKD.

### `text.list_ops` — Operações de Conjuntos entre Listas de Texto
- **Tipo**: `Tool`
- **Recursos**:
  - Operações matemáticas de conjuntos linha por linha: União ($A \cup B$), Interseção ($A \cap B$), Diferença $A - B$, Diferença $B - A$, Diferença Simétrica ($A \Delta B$) e Concatenação.
  - Opções de sensibilidade a maiúsculas/minúsculas, remoção de espaços em branco (trim) e ignorar linhas vazias.
  - Ordenação do resultado: Ordem original, alfabética A-Z/Z-A e Ordenação Natural (`item2` antes de `item10`).

### `text.name_formatter` — Formatador de Nomes Próprios e Citações ABNT
- **Tipo**: `Tool`
- **Recursos**:
  - Padronização e capitalização gramatical de nomes próprios em língua portuguesa.
  - Preservação em minúsculas de partículas conformativas e preposições ('da', 'de', 'do', 'dos', 'das', 'e', 'van', 'von', 'del').
  - Tratamento correto de nomes com apóstrofo (`D'Ávila`) e hífens (`Jean-Luc`).
  - Preservação de numerais romanos em maiúsculas (`Dom Pedro II`, `Henrique VIII`).
  - Geração automática de citações bibliográficas no padrão ABNT (`SILVA, João Carlos da`, `CABRAL NETO, Pedro Álvares`).
  - Extração de primeiro/último nome e iniciais limpas em lote, com exportação para CSV.

### `text.boleto_parser` — Decodificador e Validador de Boletos FEBRABAN
- **Tipo**: `Tool`
- **Recursos**:
  - Validação e decodificação de boletos de cobrança bancária (47 dígitos linha digitável ou 44 dígitos código de barras) e concessionárias/tributos (iniciados em 8).
  - Cálculo e conferência dos dígitos verificadores Módulo 10 e Módulo 11 conforme o padrão FEBRABAN.
  - Identificação automática do banco emissor / instituição financeira.
  - Extração do valor nominal em Reais e cálculo da data de vencimento exata a partir do fator FEBRABAN (com virada de ciclo pós-2025).
  - Conversão bidirecional entre linha digitável e código de barras contínuo de 44 dígitos com botões de cópia rápida.

---

## 5. Codificação e Hash (`tools/encode/`)

### `encode.crypto_hash` — Gerador de Hash e Checksum
- **Tipo**: `Tool`
- **Recursos**:
  - Hash instantâneo de texto: MD5, SHA-1, SHA-256, SHA-512, SHA3-256, CRC32 e HMAC.
  - Checksum de arquivos com cálculo assíncrono em streaming (suporta arquivos de vários GBs sem estourar memória).
  - Comparador automático contra hash esperado/oficial com verificação de integridade.

### `encode.encoders` — Codificador e Decodificador Universal
- **Tipo**: `Tool`
- **Recursos**:
  - Codificação e decodificação nos formatos: Base64, URL Encode, HTML Entities, Hexadecimal, Unicode Escape e Cifra ROT13.
  - Inversão de saída para entrada e cópia rápida.

### `encode.jwt` — Inspetor e Decodificador de JWT
- **Tipo**: `Tool`
- **Recursos**:
  - Decodificação de Header e Payload formatados em JSON limpo e legível.
  - Análise automática de data de expiração (`exp`), emissão (`iat`) e not-before (`nbf`).
  - Alerta visual com cores: [VÁLIDO] em verde, [EXPIRADO] em vermelho ou [SEM EXPIRAÇÃO].

### `encode.generators` — Gerador de UUID, ULID e Senhas Seguras
- **Tipo**: `Tool`
- **Recursos**:
  - Geração de UUID v4 (aleatório) e UUID v1 (baseado em tempo).
  - Geração de ULID (Universal Unique Lexicographically Sortable Identifier).
  - Gerador de Senhas Seguras com entropia criptográfica e escolha de tamanho (6-128 caracteres) e conjuntos de caracteres (A-Z, a-z, 0-9, símbolos).
  - Geração em quantidade (1 a 500 itens de uma só vez).

### `encode.converter` — Conversor de Timestamps e Bases Numéricas
- **Tipo**: `Tool`
- **Recursos**:
  - Conversão bidirecional de Timestamp Unix Epoch (segundos/ms) ↔ Data e Hora Local, UTC e formato ISO 8601.
### `encode.base64_file` — Conversor de Arquivos para Base64 / Data URI
- **Tipo**: `Tool`
- **Recursos**:
  - Conversão bidirecional entre arquivos binários de qualquer extensão e representação Base64 / Data URI.
  - Detecção automática de MIME types através de assinaturas binárias (Magic Bytes).
  - Prévia de imagens decodificadas e botão para salvar arquivo reconstruído em disco.

### `encode.jwt_debugger` — Depurador e Validador Avançado de JWT
- **Tipo**: `Tool`
- **Recursos**:
  - Decodificação e inspeção profunda de tokens JWT (RFC 7519).
  - Verificação matemática e temporal de claims (`exp`, `nbf`, `iat`) com indicação de validade.
  - Validação criptográfica de assinaturas HMAC-SHA (HS256, HS384, HS512) com chave secreta fornecida.

### `encode.hash_advanced` — Hashes Modernos e Verificador de Manifestos
- **Tipo**: `Tool`
- **Recursos**:
  - Geração e verificação em lote de manifestos de integridade (.sha256, .md5, .sfv/CRC32).
  - Algoritmos criptográficos de última geração: BLAKE2b, BLAKE2s, SHA3-256, SHA3-512 e SHA-512/256.
  - Relatório comparativo de integridade de arquivos com status visual de arquivos íntegros, modificados ou corrompidos.

### `encode.html_entities` — Catálogo e Codificador de Entidades HTML
- **Tipo**: `Tool`
- **Recursos**:
  - Tabela pesquisável com centenas de entidades HTML oficiais (nomeadas, decimais e hexadecimais).
  - Codificação e decodificação seletiva apenas de caracteres reservados ou de todos os caracteres não-ASCII.

### `encode.hmac` — Gerador e Validador de HMAC
- **Tipo**: `Tool`
- **Recursos**:
  - Cálculo de assinaturas HMAC com suporte a SHA-256, SHA-512, SHA-384, MD5 e SHA-1.
  - Suporte a chaves secretas em texto puro (UTF-8) ou decodificadas de hexadecimal.
  - Verificação de assinaturas (ex: webhooks do GitHub, Stripe, Mercado Pago) em tempo constante (`compare_digest`) prevenindo *timing attacks*.
  - Gerador integrado de chaves secretas criptograficamente seguras.

### `encode.keygen` — Gerador de Pares de Chaves SSH e Criptográficas
- **Tipo**: `Tool`
- **Recursos**:
  - Geração de pares de chaves assimétricas nos algoritmos: Ed25519 (recomendado), RSA (2048 e 4096 bits) e ECDSA (P-256).
  - Exportação de chave pública no formato OpenSSH (`authorized_keys`) com comentários personalizados e PEM.
  - Exportação de chave privada no formato OpenSSH e PEM PKCS#8 com proteção opcional por senha (AES-256).
  - Cálculo e exibição de impressões digitais (fingerprints) nos formatos SHA-256 (Base64) e MD5 (Hex colons).

### `encode.cert_inspector` — Inspetor e Conversor de Certificados Digitais
- **Tipo**: `FileTool` (Processamento em Lote)
- **Extensões Suportadas**: `.crt`, `.cer`, `.pem`, `.pfx`, `.p12`, `.der`
- **Recursos**:
  - Decodificação detalhada de certificados X.509 em formato PEM, DER ou pacotes PKCS#12 (com suporte a senha).
  - Extração de titular (Common Name, Organização), emissor (CA), período de validade (status de expiração e dias restantes), número de série, algoritmo de assinatura, tipo/tamanho da chave pública e Subject Alternative Names (SANs).
  - Cálculo de Thumbprints (SHA-256 e SHA-1).
  - Modo conversão automática para formato padronizado `.pem`.

### `encode.nfe_key` — Decodificador e Validador de Chave NF-e
- **Tipo**: `Tool`
- **Recursos**:
  - Validação e decodificação da chave de acesso de 44 dígitos de documentos fiscais (NF-e mod 55, NFC-e mod 65, CT-e mod 57, MDF-e mod 58).
  - Conferência matemática rigorosa do Dígito Verificador Módulo 11 conforme o padrão oficial da SEFAZ / ENCAT.
  - Extração automática de UF do emitente, data de emissão (mês e ano), CNPJ do emitente (com máscara), modelo, série, número da nota, tipo de emissão e código numérico.

### `encode.classic_ciphers` — Cifras Clássicas da Criptografia
- **Tipo**: `Tool`
- **Recursos**:
  - Cifragem e decifragem de cifras históricas: Cifra de César, Cifra de Vigenère, Código Morse (ITU), Cifra Atbash e rotações simétricas ROT13 e ROT47.
  - Módulo Brute-Force da Cifra de César exibindo simultaneamente todos os 25 deslocamentos possíveis para quebra rápida de textos cifrados.

### `encode.punycode_html` — Conversor IDN Punycode e Entidades HTML
- **Tipo**: `Tool`
- **Recursos**:
  - Conversão bidirecional entre domínios internacionalizados com acentos e formato Punycode ASCII compatível (`xn--...`), com suporte a URLs completas.
  - Codificação de entidades de caracteres HTML em três modalidades: nomeadas (`&copy;`), decimais (`&#169;`) e hexadecimais (`&#xA9;`).
  - Decodificação de qualquer entidade HTML de volta para caracteres Unicode originais.

---

## 6. Dados e Estruturas (`tools/data/`)

### `data.converter` — Conversor de Dados em Lote
- **Tipo**: `FileTool` (Processamento em Lote com Motor Central)
- **Extensões Suportadas**: `.json`, `.yaml`, `.yml`, `.csv`, `.xml`
- **Formatos de Saída**: `JSON`, `YAML`, `CSV`, `XML`
- **Recursos**:
  - Conversão de arquivos individuais ou pastas inteiras com suporte recursivo.
  - Mapeamento bidirecional inteligente de dados estruturados (listas, dicionários, atributos).
  - Espelhamento de subpastas e estratégia atômica de gravação (`.tmp_wtbx`).

### `data.beautifier` — Formatador e Minificador (JSON/XML/SQL)
- **Tipo**: `Tool`
- **Recursos**:
  - Formatação com indentação configurável (2 ou 4 espaços) para JSON, XML e SQL.
  - Minificação e compactação sem perda de dados para JSON, XML e SQL.
  - Identificação de erros de sintaxe com avisos claros.

---

## 7. Arquivos e Pastas (`tools/files/`)

### `files.rename` — Renomeador de Arquivos em Lote
- **Tipo**: `Tool`
- **Recursos**:
  - Adição de arquivos avulsos ou pastas inteiras (com busca recursiva).
  - Regras empilháveis aplicadas em cascata:
    1. Localizar e substituir (texto literal ou Expressões Regulares Regex).
    2. Inserção de prefixo e sufixo customizados.
    3. Numeração sequencial com escolha de número inicial e preenchimento de zeros à esquerda (padding).
    4. Alteração de caixa: MAIÚSCULAS, minúsculas ou Primeira Maiúscula (Title Case).
  - Tabela com prévia dinâmica em tempo real (Nome Original, Novo Nome, Status, Caminho).
  - Diálogo de confirmação de segurança antes da gravação física.

### `files.duplicates` — Localizador de Arquivos Duplicados
- **Tipo**: `Tool`
- **Recursos**:
  - Varredura ultra rápida em 3 estágios escalonados:
    1. Filtro e agrupamento preliminar por tamanho exato em bytes (`stat().st_size`).
    2. Cálculo de hash rápido dos primeiros 4KB para descarte imediato de arquivos diferentes.
    3. Cálculo de hash completo SHA-256 apenas entre candidatos finais.
  - Seleção inteligente: botões "Marcar mais recentes", "Marcar mais antigos" ou seleção manual por caixa de seleção.
  - Exclusão segura: os arquivos marcados são movidos para a Lixeira do Windows através de `send2trash` (permitindo recuperação pelo usuário em caso de descarte acidental).

### `files.disk_usage` — Analisador de Espaço em Disco
- **Tipo**: `Tool`
- **Recursos**:
  - Mapeamento de diretórios e unidades de armazenamento via `os.scandir` otimizado.
  - Aba "Maiores Pastas e Arquivos": ranking dos maiores itens com barra de progresso visual de ocupação relativa e tamanho formatado (B, KB, MB, GB).
  - Aba "Por Tipo de Arquivo": agregação de consumo por extensão (.mp4, .zip, .iso, .exe, etc.), total de arquivos e percentual de ocupação.
  - Ação de duplo clique ou menu de contexto para abrir o arquivo ou pasta diretamente no Windows Explorer.

### `files.shredder` — Triturador Seguro de Arquivos
- **Tipo**: `Tool`
- **Recursos**:
  - Destruição irrecuperável de arquivos confidenciais.
  - Modos de sobrescrita física configuráveis:
    - 1 Passe Rápido: Sobrescrita com bytes zero (`0x00`).
    - 3 Passes Padrão DoD: Zeros (`0x00`), uns (`0xFF`) e sequência pseudoaleatória criptográfica (`secrets.token_bytes`).
    - 7 Passes Gutmann Simplificado: Sobrescrita profunda multi-passes.
  - Descarga forçada de buffers em disco (`os.fsync`) após cada passagem.
  - Truncamento do arquivo para 0 bytes e renomeação para hash anônimo na Master File Table (MFT) antes da exclusão física definitiva.
  - Confirmação de segurança explícita para evitar exclusão involuntária.

### `files.split_merge` — Divisor e Juntador de Arquivos
- **Tipo**: `Tool`
- **Recursos**:
  - **Divisão (Split)**: Divide arquivos volumosos em partes sequenciais (`.part001`, `.part002`, etc.) com tamanhos predefinidos (10 MB, 25 MB para Discord/E-mail, 50 MB, 100 MB, 700 MB para CD, 4.7 GB para DVD ou tamanho customizado em MB).
  - **Junção (Merge)**: Reconstituição byte a byte do arquivo original a partir das partes divididas com verificação de sequência e integridade total.

### `files.lock_checker` — Quem Está Usando Este Arquivo?
- **Tipo**: `Tool`
- **Recursos**:
  - Identifica programas, serviços e processos do Windows que estão bloqueando e travando a exclusão ou alteração de um arquivo.
  - Integração com a API nativa do Windows Restart Manager (`rstrtmgr.dll` via `ctypes`: `RmStartSession`, `RmRegisterResources`, `RmGetList`, `RmEndSession`) sem depender de executáveis externos como Handle ou Process Explorer.
  - Fallback complementar de varredura via `psutil` de arquivos abertos.
  - Tabela com PID, Nome do Processo e Serviço associado.
### `files.auto_organize` — Organizador Automático de Pastas
- **Tipo**: `Tool`
- **Recursos**:
  - Organização automática de pastas desordenadas (como a pasta Downloads) por Categorias (Imagens, Vídeos, Documentos, Áudios, Compactados, Código, Instaladores), por Extensão Específica (.PNG, .PDF, .MP4), por Data de Modificação (Ano/Mês) ou por Ano.
  - Suporte a busca recursiva em subpastas.
  - Modos de operação: Mover arquivos ou Copiar arquivos preservando os originais.
  - Simulação prévia obrigatória (Dry-Run): lista todos os destinos planejados e categorias em tabela antes de aplicar qualquer alteração em disco.
  - Resolução automática de conflitos de nomes no destino.

### `files.search` — Pesquisa Avançada de Arquivos e Conteúdo
- **Tipo**: `Tool`
- **Recursos**:
  - Localização rápida de arquivos no disco através de múltiplos filtros combinados.
  - Filtro por nome: suporte a curingas glob (`*.pdf`, `relatorio_*.xlsx`) e diferenciação opcional de maiúsculas/minúsculas.
  - Filtro por tamanho de arquivo: qualquer tamanho, pequeno (< 1 MB), médio (1 a 50 MB) ou grande (> 50 MB).
  - Filtro por data de modificação: últimas 24 horas, últimos 7 dias, últimos 30 dias ou último ano.
  - Busca por conteúdo de texto interno: varredura em streaming em arquivos de texto, código e dados (.txt, .py, .csv, .json, .log, .md, .xml) sem carregar arquivos gigantescos na memória.
  - Tabela com exibição do snippet da linha encontrada, ações de abrir arquivo ou abrir na pasta do Windows Explorer em um clique.

### `files.sync` — Comparador e Sincronizador de Pastas
- **Tipo**: `Tool`
- **Recursos**:
  - Comparação recursiva lado a lado entre duas pastas (Origem A e Destino B).
  - Modos de Sincronismo:
    - **Espelhamento (Mirror)**: Torna a pasta de destino idêntica à de origem, copiando arquivos novos e modificados e excluindo arquivos órfãos do destino.
    - **Atualização (Update)**: Copia apenas arquivos novos e mais recentes da origem para o destino, sem excluir nada.
    - **Bidirecional**: Sincroniza ambas as pastas com a versão mais recente de cada arquivo.
  - Opção de comparação por Hash MD5 de conteúdo para máxima precisão além de data/tamanho.
  - Tabela de prévia detalhada com status colorido (Novo, Modificado, Órfão, Idêntico) antes da execução física.

### `files.encrypt` — Criptografia Local de Arquivos (AES-256)
- **Tipo**: `Tool` (Interface em Abas)
- **Recursos**:
  - **Aba Criptografar**: Criptografia de qualquer tipo de arquivo com AES-256-GCM de padrão militar e derivação de chave scrypt (N=2^17, OWASP) e criptografia em blocos de 1 MiB (formato v2 `WTBX_AE2`, sem carregar o arquivo inteiro na memória e detectando truncamento). Arquivos do formato v1 (PBKDF2) continuam sendo abertos.
  - Opção para exclusão segura do arquivo original após a conclusão bem-sucedida da criptografia.
  - **Aba Descriptografar**: Restauração com validação de autenticidade e integridade AEAD (rejeita imediatamente senhas incorretas ou arquivos corrompidos).
  - Campos de senha protegidos com alternador de visibilidade (Mostrar/Ocultar).

### `files.timestamp_editor` — Modificador de Datas de Arquivos (Timestamp)
- **Tipo**: `Tool`
- **Recursos**:
  - Modificação em lote de atributos de data e hora de arquivos e pastas no Windows.
  - Suporte à alteração de Data de Criação (`ctime` via API Win32 `kernel32.SetFileTime`), Data de Modificação (`mtime`) e Data de Último Acesso (`atime`).
  - Três modos de ajuste:
    - Data e Hora Específica Fixa com seletor de calendário pop-up.
    - Definir para o momento atual (Agora).
    - Deslocar tempo relativamente (+/- N horas ou dias).
  - Tabela com valores antes e depois para conferência.

### `files.folder_watcher` — Monitor de Pastas em Tempo Real
- **Tipo**: `Tool`
- **Recursos**:
  - Monitoramento contínuo em tempo real de eventos em diretórios com diferencial de snapshot leve em segundo plano (consumo de CPU < 0.1%).
  - Detecção imediata de arquivos criados (verde), modificados (azul) e excluídos (vermelho).
  - Tabela histórica com carimbo de data/hora, tipo de evento, nome do arquivo e detalhes de alteração de tamanho.
  - Suporte a notificações na área de notificação do Windows (Bandeja / Tray).
  - Exportação completa do histórico de eventos em relatório no formato `.CSV`.

### `files.backup` — Assistente de Backup Incremental
- **Tipo**: `Tool`
- **Recursos**:
  - Criação de backups locais com gestão de histórico e diferencial inteligente através de manifesto JSON (`.wtx_backup_manifest.json`).
  - Dois formatos de saída:
    - **Arquivo Compactado ZIP (Snapshot)**: Empacota a pasta inteira com compressão Deflate e carimbo de data e hora no nome (`backup_PASTA_YYYY-MM-DD_HHMMSS.zip`).
    - **Pasta Incremental Espelhada**: Copia apenas os arquivos novos ou com tamanho/mtime alterados desde o último backup, economizando espaço em disco e tempo de transferência.
  - Tabela de histórico da sessão com contagem de arquivos transferidos, bytes transferidos e botão de acesso direto à pasta no Explorer.

### `files.encoding_converter` — Conversor de Codificação de Texto e Finais de Linha
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.txt`, `.csv`, `.log`, `.json`, `.xml`, `.html`, `.css`, `.js`, `.ts`, `.py`, `.sql`, `.md`, `.ini`, `.cfg`, `.yaml`, `.yml`
- **Recursos**:
  - Detecção automática de codificação de entrada com fallback inteligente.
  - Conversão em lote para: UTF-8 (padrão universal), UTF-8 com BOM, Windows-1252 / ANSI, ISO-8859-1 (Latin1), UTF-16 LE e UTF-16 BE.
  - Normalização de quebras de linha entre CRLF (padrão Windows `\r\n`) e LF (padrão Linux/macOS `\n`).
  - Gravação atômica segura via motor central de lote.

### `files.unblock` — Desbloqueador de Arquivos em Lote (Mark of the Web)
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: Todas as extensões de arquivo
- **Recursos**:
  - Remove o fluxo alternativo NTFS (`Zone.Identifier`) que o Windows anexa a arquivos baixados de navegadores, clientes de e-mail ou descompactados.
  - Elimina bloqueios e avisos de segurança ao abrir planilhas, macros do Office, arquivos compactados ou instaladores `.exe`.
  - Desbloqueio direto via API Win32 do Windows (`DeleteFileW`) de alta performance.

### `files.permissions` — Reparador de Permissões NTFS e Acesso Negado
- **Tipo**: `Tool` (Correção de Permissões e Propriedade)
- **Recursos**:
  - Resolução de erros de "Acesso Negado" ao tentar abrir, mover ou renomear arquivos e pastas herdados de outros usuários ou reinstalações do Windows.
  - **Tomar Posse (Take Ownership)**: Executa `takeown.exe` atribuindo a propriedade do arquivo ou pasta ao grupo de Administradores local.
  - **Redefinir Permissões (Reset ACL)**: Executa `icacls.exe /reset /t /c` para restaurar a herança de permissões limpas a partir da pasta pai.
  - Suporte a processamento recursivo em subpastas e arquivos filhos.

### `files.checksum_manifest` — Manifesto de Checksums de Pasta (.sha256 / .md5)
- **Tipo**: `Tool` (Interface em 2 Abas: Gerar e Verificar)
- **Recursos**:
  - **Aba Gerar Manifesto**:
    - Varre todos os arquivos de um diretório e gera um arquivo de manifesto no formato padrão GNU (`manifest.sha256` ou `manifest.md5`).
    - Algoritmos suportados: SHA-256, SHA-512 e MD5.
  - **Aba Verificar Integridade**:
    - Lê o arquivo de manifesto e valida cada arquivo no disco.
    - Classificação imediata com badges visuais: OK (verde), MODIFICADO (vermelho) ou AUSENTE (laranja).
    - Resumo estatístico com total de arquivos íntegros, alterados e faltantes.

---


## 8. Compactação e Arquivos Comprimidos (`tools/archive/`)

### `archive.manager` — Compactador e Extrator de Arquivos
- **Tipo**: `Tool`
- **Formatos Suportados**: ZIP (compressão deflate), TAR e TAR.GZ (`.tar.gz`, `.tgz`).
- **Recursos**:
  - **Aba Compactar**: Adição de arquivos e diretórios inteiros, seleção de formato e barra de progresso durante o empacotamento.
  - **Aba Inspecionar**: Listagem de todo o conteúdo interno do arquivo compactado (nome relativo, tamanho real e tamanho comprimido) sem necessidade de descompactar.
  - **Aba Extrair**: Extração completa com filtro de proteção contra traversals maliciosos de diretório (`filter='data'`) e relatório de progresso.

---

## 9. PDF e Documentos (`tools/pdf/` e `tools/data/`)

### `pdf.split_merge` — Divisor e Juntador de PDF
- **Tipo**: `Tool` (Interface em Abas)
- **Recursos**:
  - **Aba Juntar PDFs (Merge)**:
    - Adiciona múltiplos arquivos PDF à lista com reordenação arrastável (subir/descer) ou manual.
    - Opção de criar automaticamente marcadores de índice (bookmarks/outline) com o nome de cada arquivo unificado.
    - Execução assíncrona com barra de progresso e geração atômica de PDF único.
  - **Aba Dividir PDF (Split)**:
    - Exibe total de páginas e tamanho do arquivo PDF de entrada.
    - 3 Estratégias de divisão:
      - Todas as páginas individuais (1 arquivo por página).
      - Intervalos customizados (ex: `1-3, 5, 8-10`).
      - Agrupamento em blocos a cada N páginas (ex: a cada 2 ou 5 páginas).
    - Definição customizada de pasta de destino e prefixo do nome dos arquivos gerados.

### `pdf.images_to_pdf` — Imagens para PDF
- **Tipo**: `Tool`
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`
- **Recursos**:
  - Converte fotos (incluindo fotos Apple iPhone `.heic`/`.heif`/`.hif`, `.avif`, `.psd`, `.qoi`, `.tga`, `.jp2`, `.png`, `.jpg`, `.webp`, `.bmp`, `.tiff`), capturas e digitalizações em lote para um único documento PDF compilado, aplicando rotação automática EXIF e conversão de cor Display P3 para sRGB.
  - Suporte a tamanhos padrão de papel: A4 (210x297mm), Carta (Letter), Ofício (Legal) e Tamanho Original da Imagem.
  - Orientação da folha: Automática (segue proporção da foto), Retrato (Vertical) ou Paisagem (Horizontal).
  - Controle de margem interna em pontos (pt).
  - Reordenação interativa de páginas (Mover para Cima/Baixo).

### `pdf.extract` — Extrator de Texto e Imagens de PDF
- **Tipo**: `Tool`
- **Recursos**:
  - **Aba Extrair Texto**:
    - Extrai todo o texto contido no PDF página a página.
    - Opção de cabeçalhos identificadores por página (`--- Página X ---`).
    - Visualizador de texto integrado com botões "Copiar Texto" e "Salvar como .txt".
  - **Aba Extrair Imagens**:
    - Varre o documento e extrai todas as imagens embutidas em alta fidelidade.
    - Filtro de dimensão mínima em pixels para descartar ícones minúsculos e bordas decorativas.
    - Exporta como PNG ou JPG para a pasta indicada.
  - **Aba Páginas como Imagem**:
    - Renderiza páginas do PDF em PNG, JPG ou WEBP via `pypdfium2` (motor PDFium), com DPI configurável (36 a 600) e seleção de páginas (`1-3, 5, 8-`).

### `pdf.compress` — Compressor de PDF
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.pdf`
- **Recursos**:
  - Otimização e redução de peso de PDFs em lote com suporte a pastas recursivas e espelhamento de saída.
  - Motor `pikepdf` (qpdf): recompressão das imagens internas em JPEG (qualidade alta/equilibrada/mínima, limite de ~300 dpi em A4) e object streams; nunca devolve arquivo maior que o original. `pypdf` como reserva.
  - Compressão de fluxos internos de texto e vetores (Content Streams).
  - Eliminação de objetos e fontes idênticas duplicadas via `compress_identical_objects`.
  - Remoção opcional de metadados internos e histórico de edições para redução máxima de bytes.
  - Relatório de compressão indicando tamanho antes, depois e porcentagem de economia.

### `pdf.rotate` — Rotacionador de PDF
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.pdf`
- **Recursos**:
  - Gira páginas de PDFs em lote no sentido horário: 90°, 180° (inversão) ou 270° (90° anti-horário).
  - Modos de aplicação seletiva: Todas as páginas, Apenas páginas ímpares, Apenas páginas pares ou Intervalo customizado (ex: `1, 3, 5-8`).

### `pdf.security` — Segurança e Senhas de PDF
- **Tipo**: `Tool`
- **Recursos**:
  - **Aba Proteger com Senha**:
    - Criptografa o arquivo PDF com chave AES de alta segurança.
    - Define senha de leitura (User Password) com confirmação e botões de alternar visualização (Mostrar/Ocultar).
    - Opção de permissão de impressão.
  - **Aba Desbloquear / Remover Senha**:
    - Descriptografa documentos protegidos cuja senha seja conhecida, gerando uma cópia permanente livre de restrições.

### `pdf.office_convert` — Conversor de Office para PDF
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.docx`, `.doc`, `.xlsx`, `.xls`, `.pptx`, `.ppt`
- **Recursos**:
  - Conversão em lote de documentos do Word, planilhas do Excel e apresentações do PowerPoint para PDF de alta fidelidade.
  - Integração com a automação COM nativa do Microsoft Office no Windows (`win32com.client`), preservando exatamente fontes, tabelas, cabeçalhos e diagramação originais.
  - Gerenciamento seguro de instâncias headless com fechamento automático de processos e liberação de memória.

### `data.doc_converter` — Conversor de Markdown para HTML
- **Tipo**: `Tool`
- **Recursos**:
  - Editor de Markdown com pré-visualização em tempo real em dois painéis lado a lado.
  - Estilização completa alinhada ao Windows 11 Fluent Design e suporte a temas claro/escuro.
  - Suporte a tabelas, listas, citações e blocos de código com fontes monoespaçadas.
  - Botão de carregar arquivo `.md`, copiar HTML gerado ou exportar diretamente como página autônoma `.html`.

---

## 10. Áudio e Vídeo (`tools/media/`)

### `media.convert` — Conversor de Vídeo e Áudio
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas (50 formatos)**: Vídeo (`.mp4`, `.m4v`, `.mov`, `.mkv`, `.webm`, `.avi`, `.flv`, `.f4v`, `.wmv`, `.asf`, `.ts`, `.mts`, `.m2ts`, `.mpg`, `.mpeg`, `.mpe`, `.mpv`, `.m2v`, `.vob`, `.3gp`, `.3g2`, `.ogv`, `.divx`, `.dv`, `.mxf`, `.rm`, `.rmvb`) e Áudio (`.mp3`, `.wav`, `.aac`, `.flac`, `.ogg`, `.oga`, `.opus`, `.m4a`, `.m4b`, `.m4r`, `.wma`, `.aiff`, `.aif`, `.caf`, `.ac3`, `.eac3`, `.dts`, `.amr`, `.ape`, `.wv`, `.mp2`, `.weba`, `.alac`)
- **Formatos de Saída (26 formatos)**: Vídeo/Animação (`MP4`, `MKV`, `MOV`, `WEBM`, `AVI`, `WMV`, `TS`, `FLV`, `M4V`, `MPG`, `3GP`, `OGV`, `GIF`, `WEBP` animado) e Áudio (`MP3`, `M4A`, `AAC`, `OPUS`, `OGG`, `FLAC`, `WAV`, `AIFF`, `AC3`, `WMA`, `CAF`, `MP2`)
- **Codecs de Vídeo e Opções Avançadas**:
  - Seleção de Codec de Vídeo: Automático por contêiner, **H.264 (AVC)**, **H.265 / HEVC** (com tag `hvc1` compatível nativamente com Apple/QuickTime/iPhone), **AV1**, **VP9**, **Apple ProRes 422** e **Stream Copy** (remux instantâneo sem recodificação).
  - Limite opcional de resolução máxima vertical (`2160p 4K`, `1440p 2K`, `1080p`, `720p`, `480p`, `360p`) com proteção automática de dimensões pares (`trunc(iw/2)*2`) e controle de bitrate de áudio (`96k` a `320k`) e largura de GIF/WebP animado.
- **Recursos**:
  - Conversão em lote com recursão de pastas e espelhamento de estrutura de diretórios.
  - Extração exclusiva de faixa de áudio de vídeos (convertendo direto para MP3/AAC/WAV/FLAC).
  - Conversão direta de trechos de vídeo para GIF animado com controle de FPS e resolução.
  - Otimização e compressão por meta de tamanho em MB (calculando automaticamente o bitrate ideal pela duração).

### `media.trim_merge` — Cortador e Juntador de Mídia
- **Tipo**: `Tool` (Interface em Abas)
- **Recursos**:
  - **Aba Cortar Mídia (Trim)**:
    - Seleção de tempo inicial e final (formato `HH:MM:SS` ou segundos).
    - Modo Stream Copy (`-c copy`) para cortes ultra-rápidos e instantâneos sem perda de qualidade, com opção de reencodagem para precisão de frame.
  - **Aba Juntar Mídias (Concat)**:
    - Concatenação em lista de múltiplos arquivos de áudio ou vídeo na ordem desejada via demuxer concat.

### `media.downloader` — Downloader de Mídia
- **Tipo**: `Tool`
- **Recursos**:
  - Download de vídeos e áudios de centenas de sites (YouTube, TikTok, Instagram, Twitter/X, Facebook, etc.) através do `yt-dlp` local integrado ao `ffmpeg`.
  - Opção de download de vídeo em alta qualidade (Original, 1080p, 720p, 480p) ou extração automática para áudio MP3 (192 kbps).
  - Barra de progresso ao vivo com percentual de download.

### `media.frame_extractor` — Extrator de Frames de Vídeo
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.mp4`, `.m4v`, `.mov`, `.mkv`, `.webm`, `.avi`, `.flv`, `.f4v`, `.wmv`, `.asf`, `.ts`, `.mts`, `.m2ts`, `.mpg`, `.mpeg`, `.vob`, `.3gp`, `.3g2`, `.ogv`, `.mxf`
- **Recursos**:
  - Extração de quadros a cada N segundos em lote para toda uma biblioteca de vídeos.
  - Extração de quadro fixo por timestamp (`HH:MM:SS`).
  - Geração de folha de mosaico de miniaturas em grade 3x3 para visão panorâmica do vídeo.
  - Exportação em formato PNG ou JPG.

### `media.recorder` — Gravador de Tela
- **Tipo**: `Tool`
- **Recursos**:
  - Gravação de vídeo da tela via `ddagrab` do ffmpeg (Desktop Duplication API, captura pela GPU), com `gdigrab` como reserva; log do ffmpeg em `logs/ffmpeg_recorder.log`.
  - Controle de taxa de quadros (15, 30 ou 60 FPS).
  - Cronômetro de tempo de gravação em tempo real (`00:00:00`).
  - Encerramento seguro gerando arquivo MP4 finalizado sem corrupção de contêiner.

### `media.speech` — Texto para Voz (TTS Local)
- **Tipo**: `Tool`
- **Recursos**:
  - Sintetizador de voz 100% offline via `Windows.Media.SpeechSynthesis` (WinRT, vozes OneCore/naturais do Windows 10/11), com SAPI via `pyttsx3` como reserva.
  - Seleção de vozes locais instaladas no Windows, com controle de velocidade (palavras por minuto) e volume.
  - Reprodução de áudio ao vivo nos alto-falantes ou gravação direta em arquivo `.wav`.

### `media.id3_editor` — Editor de Tags ID3 (MP3)
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.mp3`
- **Recursos**:
  - Edição de metadados ID3v2: Artista, Álbum, Ano e Gênero em lote para coleções de músicas.
  - Embutimento de arte de capa do álbum (PNG ou JPG) no frame `APIC`.

### `media.player` — Player de Áudio e Vídeo
- **Tipo**: `Tool`
- **Recursos**:
  - Player embutido nativo utilizando `QMediaPlayer` e `QVideoWidget` do PySide6.
  - Controles de Play, Pause, Stop, seek por slider de progresso, relógio de tempo atual/total e ajuste de volume.

---

## 11. Ferramentas para Desenvolvedores (`tools/dev/`)

### `dev.fake_data` — Gerador de Dados Fictícios
- **Tipo**: `Tool` (Interativo e Lote)
- **Recursos**:
  - **Aba Dados Estruturados em Lote**:
    - Algoritmos matemáticos oficiais de validação para CPF (com e sem pontuação) e CNPJ (com e sem pontuação).
    - Geração de nomes completos com distribuição brasileira, e-mails realistas, telefones/celulares com DDDs regionais, endereços completos (logradouro, número, bairro, cidade, UF e CEP válido).
    - Suporte a dados técnicos: endereços IPv4, endereços MAC e identificadores UUID v4.
    - Exportação multi-formato em 1 clique: JSON formatado, CSV delimitado por ponto e vírgula, instruções SQL `INSERT INTO` e Texto delimitado por tabulação.
    - Cópia para a área de transferência ou salvamento direto em arquivo de disco.
  - **Aba Gerador Lorem Ipsum**:
    - Geração sintética de texto padrão de preenchimento em Parágrafos, Frases ou Palavras.

### `dev.sqlite_viewer` — Visualizador de Bancos SQLite
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Acesso protegido e seguro via URI somente-leitura (`file:...mode=ro`), evitando locks em bancos operacionais.
  - Painel lateral com lista de tabelas e views, contagem de registros e busca instantânea.
  - Visualização de registros com paginação e ordenação de alta performance via `DataTableView` (`RecordTableModel`).
  - **Editor de Consultas SQL**: Execução de scripts livres `SELECT`, cálculo de tempo de resposta em milissegundos e exportação de resultados para CSV ou JSON.
  - **Esquema e DDL**: Inspeção de colunas, tipos de dados, chaves primárias, restrições NOT NULL e código DDL `CREATE TABLE` original.

### `dev.color_converter` — Conversor de Cores
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Conversão matemática bidirecional e instantânea entre notações HEX (#RGB, #RGBA, #RRGGBB, #RRGGBBAA), RGB (0-255), HSL (0-360°, 0-100%), HSV (0-360°, 0-100%) e CMYK (0-100%).
  - Caixa de pré-visualização visual dinâmica com teste de contraste ao vivo sobre o fundo da cor.
  - Seletor nativo do sistema operacional via `QColorDialog`.
  - **Métricas de Acessibilidade WCAG 2.1**: Cálculo de luminância relativa e razão de contraste com fundos branco e preto, com selos de aprovação nos níveis AA e AAA.
  - **Snippets Prontos para Dev**: Geração e cópia em 1 clique de notações para CSS HEX, CSS RGB/RGBA, CSS HSL/HSLA, Tailwind CSS (`bg-[#...]`), Python, Tuplas Normalizadas (0.0-1.0), Android/Flutter (`0xFF...`) e Unity C# (`new Color(...)`).

### `dev.cron_calculator` — Calculador de Cron
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Suporte a expressões cron clássicas de 5 campos (minuto, hora, dia do mês, mês, dia da semana) e 6 campos (com segundos).
  - Presets rápidos de agendamentos comuns (a cada minuto, a cada 5/15/30 min, horário comercial de dias úteis, início do mês, etc.).
  - Tradutor semântico explicativo em Português do Brasil claro e legível.
  - Motor de cálculo temporal determinístico: simula e projeta as próximas 1 a 100 execuções cronometradas com dia da semana em português.
  - Cópia da expressão e da lista completa de datas futuras para a área de transferência.

### `dev.pyinstaller_wrapper` — Gerador de Executáveis
- **Tipo**: `Tool` (Interativo e Automação)
- **Recursos**:
  - Detecção automática da instalação e versão do PyInstaller no ambiente ativo do Python (`sys.executable`).
  - Configuração visual simplificada: script de entrada `.py`/`.pyw`, nome do executável, ícone `.ico` e diretório de saída (`dist/`).
  - Seleção de empacotamento: Arquivo Standalone Único (`--onefile`) vs Pasta de Dependências (`--onedir`).
  - Switch para ocultar a janela de console preta do terminal (`--windowed` / `--noconsole`).
  - Configuração de módulos extras (`--hidden-import`) e arquivos/pastas adicionais (`--add-data`).
  - Geração de comando CLI em tempo real, cópia em 1 clique e exportação de script batch `.bat` para automações CI/CD.
  - Compilação direta e assíncrona com `QProcess`, botão de cancelamento e saída de logs em tempo real via `LogPanelWidget`.

### `dev.project_scaffold` — Scaffold de Projetos
- **Tipo**: `Tool` (Interativo e Automação)
- **Recursos**:
  - Geração padronizada de arquivos essenciais para inicialização de repositórios modernos.
  - Templates curados de `.gitignore` para Python, Node.js / TypeScript, Rust, Go, C# / .NET, C / C++ e Flutter / Dart, incluindo exclusões de sistema operacional (.DS_Store, Thumbs.db) e IDEs (.vscode, .idea).
  - Textos completos de licenças Open Source com preenchimento automático do ano corrente e autor/organização: MIT, Apache 2.0, GNU GPL v3, BSD 3-Clause e The Unlicense.
  - Criação de `README.md` estruturado com seções de instalação, uso e licença.
  - Criação de arquivos de convenção `.editorconfig` e `.env.example`.
  - Abas de pré-visualização ao vivo do conteúdo dos arquivos e criação direta na pasta selecionada no disco.

---

## 12. Produtividade e Utilidades Pessoais (`tools/productivity/`)

### `productivity.clipboard_history` — Histórico da Área de Transferência
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Monitoramento contínuo em tempo real de textos copiados no Windows via sinal nativo da área de transferência (`dataChanged`).
  - Banco SQLite local com índices rápidos e deduplicação inteligente de entradas consecutivas.
  - Marcação de itens favoritos (preservados mesmo durante a limpeza do histórico).
  - Campo de pesquisa instantânea tolerante a acentuação.
  - Ações para cada item: copiar novamente em 1 clique (ou duplo clique), favoritar, excluir e limpeza em lote do histórico.

### `productivity.todo` — Lista de Tarefas (To-Do)
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Gerenciador minimalista e local de tarefas com persistência em SQLite.
  - Categorização dinâmica por projeto/área (Trabalho, Pessoal, Estudos, Projetos).
  - Controle de prioridades: Baixa, Média, Alta e Urgente com destaques visuais adequados.
  - Prazos de entrega com seletor de calendário e filtros rápidos (Pendentes, Todas, Concluídas).
  - Painel de progresso percentual e métricas de produtividade em tempo real.

### `productivity.pomodoro` — Timer Pomodoro de Foco
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Máquina de estados determinística com modos de Foco, Pausa Curta e Pausa Longa.
  - Relógio digital grande com fonte Cascadia Mono e barra de progresso suave.
  - Alertas automáticos ao final de cada etapa com notificação nativa do Windows na bandeja do sistema.
  - Contador de ciclos concluídos e total acumulado de minutos focados no dia.
  - Configuração customizada das durações dos intervalos e botão para pular etapas manualmente.

### `productivity.reminders` — Alarmes e Lembretes
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Agendamento de alarmes com data, horário preciso e detalhes opcionais.
  - Atalhos para agendamento rápido (+15 min, +30 min, +1 hora) em 1 clique.
  - Suporte a repetição automática: Não repetir, Diariamente, Dias úteis (Seg a Sex) e Semanalmente.
  - Verificador em segundo plano que dispara notificações nativas na área de trabalho do Windows e toasts ao atingir o horário.
  - Painel de gerenciamento com opção de pausar, reativar e excluir lembretes.

### `productivity.quick_notes` — Bloco de Notas Rápidas
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Interface em dois painéis (Splitter): lista de notas à esquerda e editor à direita.
  - Salvamento automático contínuo em tempo real com debounce para evitar perda de dados.
  - Suporte a fixar notas importantes no topo da lista.
  - Contadores ao vivo de palavras e caracteres.
  - Exportação da anotação para arquivos Markdown (`.md`) ou Texto (`.txt`).

### `productivity.time_tracker` — Registrador de Tempo (Time Tracker)
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Cronômetro ao vivo para rastreamento de tarefas por nome e projeto/categoria.
  - Resumo consolidado do tempo total investido por projeto.
  - Histórico detalhado de atividades com hora de início, fim e duração formatada (`HH:MM:SS`).
  - Entrada manual de horas para registros retroativos.
  - Exportação de relatórios completos em formato CSV para planilhas.

---

## 13. Calculadoras Especiais (`tools/calc/`)

### `calc.unit_converter` — Conversor de Unidades
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Conversão instantânea de grandezas físicas e digitais em tempo real:
    - **Comprimento**: Metro, Quilômetro, Centímetro, Milímetro, Micrômetro, Nanômetro, Polegada, Pé, Jarda, Milha e Milha Náutica.
    - **Massa e Peso**: Quilograma, Grama, Miligrama, Tonelada Métrica, Libra, Onça e Arroba Brasileira (15 kg).
    - **Dados Digitais**: Bit, Byte, Kilobyte (KB/1000), Megabyte (MB), Gigabyte (GB), Terabyte (TB), Petabyte (PB), Kibibyte (KiB/1024), Mebibyte (MiB), Gibibyte (GiB) e Tebibyte (TiB).
    - **Área**: Metro Quadrado, Quilômetro Quadrado, Centímetro Quadrado, Hectare, Acre, Pé Quadrado e Alqueire Paulista (24.200 m²).
    - **Volume**: Litro, Mililitro, Metro Cúbico, Centímetro Cúbico, Galão Americano (gal), Barril de Petróleo (bbl), Xícara e Colher de Sopa.
    - **Temperatura**: Graus Celsius (°C), Graus Fahrenheit (°F) e Kelvin (K) com fórmulas matemáticas exatas de translação e escala.
    - **Pressão**: Pascal (Pa), Kilopascal (kPa), Bar, Atmosfera Padrão (atm), PSI (lbf/in²) e mmHg (Torr).
    - **Velocidade**: Metros por segundo (m/s), Quilômetros por hora (km/h), Milhas por hora (mph), Nós marítimos (knots) e Pés por segundo (ft/s).
  - Botão de inversão rápida das unidades e cópia do resultado formatado em 1 clique.

### `calc.date_calculator` — Calculadora de Datas e Prazos
- **Tipo**: `Tool` (Interativo em 3 Abas)
- **Recursos**:
  - **Aba Diferença entre Datas**:
    - Cálculo preciso do intervalo total em dias, semanas, meses e horas.
    - Contagem detalhada de dias úteis, dias de finais de semana e feriados nacionais ocorridos no período.
    - Lista discriminada de todos os feriados nacionais compreendidos entre as datas.
  - **Aba Adicionar / Subtrair Dias Úteis**:
    - Soma ou subtração de N dias úteis a partir de uma data inicial.
    - Pula automaticamente fins de semana (sábados e domingos) e todos os feriados oficiais.
  - **Aba Feriados Nacionais Brasileiros**:
    - Motor algorítmico completo baseado no Algoritmo de Butcher (Meeus/Jones/Butcher) para determinação precisa da Páscoa e derivação de todos os feriados móveis: Carnaval (Terça-feira), Sexta-feira Santa e Corpus Christi.
    - Tabela completa de feriados fixos e móveis de qualquer ano com visualizador por calendário.

### `calc.finance` — Calculadora Financeira
- **Tipo**: `Tool` (Interativo em 3 Abas)
- **Recursos**:
  - **Aba Juros Compostos**:
    - Simulação com aporte inicial, aportes mensais recorrentes, taxa de juros anual e período em meses ou anos.
    - Conversão matemática para taxa mensal equivalente `(1 + i)^(1/12) - 1`.
    - Resumo analítico com Total Investido, Total Ganho em Juros, Saldo Bruto Final e tabela de evolução por ano.
  - **Aba Financiamento (Price e SAC)**:
    - Simulação de financiamento imobiliário e veicular.
    - **Tabela Price**: Parcelas constantes fixas com amortização crescente e juros decrescentes.
    - **Tabela SAC**: Amortização constante com parcelas decrescentes.
    - Resumo comparativo: primeira parcela, última parcela, total pago e total pago exclusivamente em juros bancários.
  - **Aba Margem e Markup**:
    - Cálculo instantâneo a partir do preço de custo e venda, determinando lucro líquido, margem sobre a venda e índice de markup sobre o custo.

### `calc.subnet_calculator` — Calculadora de Sub-redes IPv4 / CIDR
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Suporta entrada em notação CIDR (ex: `192.168.1.100/24`) ou IP + máscara de rede (ex: `10.0.0.1` + `255.255.255.0`).
  - Análise profunda:
    - Endereço de rede e endereço de broadcast.
    - Máscara decimal e máscara coringa (Wildcard Mask).
    - Primeiro host utilizável e último host utilizável.
    - Total de endereços IP e total de hosts úteis.
    - Classificação IPv4: Classe A, B, C, D (Multicast) ou E (Experimental).
    - Tipo de rede: Privada (RFC 1918), Pública, Loopback ou Link-Local (APIPA).
    - Representação binária formatada (8.8.8.8) para o IP e a máscara.

### `calc.world_clock` — Relógio Mundial e Fusos Horários
- **Tipo**: `Tool` (Interativo em 2 Abas)
- **Recursos**:
  - **Aba Relógio Mundial**:
    - Mostrador em tempo real das principais cidades de referência global: Brasília / São Paulo (UTC-3), UTC / GMT, Nova York, Los Angeles, Londres, Paris/Berlim, Moscou, Dubai, Nova Déli, Tóquio, Pequim e Sydney.
    - Exibe hora ao vivo, data, fuso horário IANA, sigla de horário de verão e offset UTC.
  - **Aba Conversor entre Fusos**:
    - Seleção de data/hora de origem, fuso de partida e fuso de destino.
    - Lista de fusos completa baseada na biblioteca IANA `zoneinfo` nativa do Python.
    - Cálculo de diferença de horas entre as regiões e horário convertido com 1 clique.

### `calc.programmer` — Calculadora do Programador e Manipulador de Bits
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Conversão bidirecional e instantânea entre 4 bases numéricas: Hexadecimal (HEX), Decimal (DEC com alternância entre Unsigned e Signed em complemento de dois), Octal (OCT) e Binário (BIN formatado em nibbles de 4 bits).
  - Suporte a 4 larguras de palavra (Word Size): 64-bit (QWORD), 32-bit (DWORD), 16-bit (WORD) e 8-bit (BYTE) com truncamento e mascaramento automático.
  - Operadores lógicos bitwise completos: AND, OR, XOR, NOT, Shift Left (`<<`), Shift Right lógico (`>>`), Shift Right aritmético (SAR com preservação de sinal), Rotação circular à esquerda (ROL) e à direita (ROR).
  - Bit Board Interativo: painel visual com até 64 bits individuais chaveáveis por clique direto (0/1), botões de cópia em 1 clique para o clipboard, botão para zerar todos os bits ou definir todos em 1s.

---

## 14. Automação e Macros Locais (`tools/automation/`)

### `automation.autoclicker` — Auto Clicker
- **Tipo**: `Tool` (Interativo e Automação)
- **Recursos**:
  - Disparo de cliques em alta velocidade automatizado via Win32 API (`mouse_event`).
  - Intervalo de disparo milimetricamente configurável em milissegundos, segundos, minutos ou horas.
  - Seleção do botão do mouse: Botão Esquerdo, Botão Direito ou Botão do Meio.
  - Tipo de clique: Clique Simples ou Duplo Clique.
  - Localização do disparo: Posição Atual do Cursor do Mouse ou Coordenadas Fixas (X, Y) na tela com botão capturador de coordenadas em tempo real.
  - Suporte a limitação por número total de cliques ou execução contínua até interrupção manual.

### `automation.window_manager` — Gerenciador de Janelas do Windows
- **Tipo**: `Tool` (Interativo)
- **Recursos**:
  - Enumeração ao vivo de todas as janelas ativas da área de trabalho com títulos e identificadores HWND.
  - **Sempre no Topo (Always on Top)**: Fixa qualquer aplicativo sobreposto às demais janelas sem precisar de utilitários externos.
  - **Transparência / Opacidade**: Controle deslizante de 10% a 100% de opacidade utilizando a flag de sistema `WS_EX_LAYERED` e `SetLayeredWindowAttributes`.
  - **Snap e Posicionamento**: Posiciona instantaneamente a janela selecionada na metade esquerda, metade direita, metade superior, metade inferior, centralizada na área útil de trabalho ou maximizada.

### `automation.script_runner` — Executor de Scripts
- **Tipo**: `Tool` (Interativo e Console)
- **Recursos**:
  - Execução e gerenciamento de scripts locais sem necessidade de abrir terminais pretos separados.
  - Suporte nativo a scripts PowerShell (`.ps1`), Batch (`.bat`), Comandos (`.cmd`), Python (`.py`, `.pyw`) e VBScript (`.vbs`).
  - Biblioteca persistente de scripts favoritos com argumentos pré-configurados e diretório de trabalho.
  - Execução assíncrona com captura de saída de texto em tempo real (STDOUT e STDERR) via painel `LogPanelWidget` com rolagem automática, botão de limpar e botão para cancelar o processo em execução.

### `automation.workspace_launcher` — Lançador de Ambientes de Trabalho (Workspaces)
- **Tipo**: `Tool` (Interativo e Automação)
- **Recursos**:
  - Lançamento de lotes de produtividade em 1 clique: abre múltiplos programas, pastas de projetos no Windows Explorer e URLs/portais no navegador padrão simultaneamente.
  - Presets iniciais inclusos (Desenvolvimento Web, Estudos e Pesquisas) e criação ilimitada de novos perfis customizados.
  - Adição simplificada de itens via seletores nativos de executáveis, pastas do sistema e caixas de URL.
  - Relatório detalhado de execução com validação de sucesso para cada item disparado.

### `automation.folder_rules` — Automação de Pastas por Regras
- **Tipo**: `Tool` (Interativo e Automação)
- **Recursos**:
  - Triagem e organização automática de arquivos em diretórios com grande acúmulo (ex: pasta de Downloads ou Desktop).
  - Condições de filtragem configuráveis:
    - Por Extensão (ex: `.pdf, .docx` ou `.png, .jpg`).
    - Por Palavras-chave no nome do arquivo (ex: `relatorio, nota, boleto`).
    - Por Idade do arquivo (mais antigo que N dias).
    - Por Tamanho (maior que N megabytes).
  - Ações suportadas: Mover para pasta de destino, Copiar ou Excluir.
  - **Modo Simulação (Dry Run)**: Avalia todos os arquivos da pasta e exibe na tabela visual exatamente o que seria feito antes de realizar qualquer alteração física no disco.
  - Execução segura com tratamento automático de arquivos de mesmo nome para evitar sobrescrita acidental.

### `automation.macro_runner` — Executor e Gravador de Macros
- **Tipo**: `Tool` (Interativo e Automação de Tarefas)
- **Recursos**:
  - Automação completa de fluxos repetitivos sem dependências externas via Win32 API (`mouse_event`, `keybd_event`, `SetCursorPos`).
  - Suporte a múltiplos tipos de ações: Cliques do Mouse (esquerdo, direito, meio, simples ou duplo com coordenadas X,Y ou no cursor atual), Digitação de Texto Unicode simulada, Atalhos de Teclado Globais (combinações com Ctrl, Alt, Shift, Win, teclas de função F1-F12, etc.), Pausas de Espera (ms) e Rolagem de Scroll do Mouse.
  - Tabela interativa com reordenação manual de passos (Mover Acima, Mover Abaixo), duplicação e remoção seletiva.
  - Repetições configuráveis (Loops de 1 a 1000) com intervalo milimétrico entre ciclos e botão de interrupção instantânea.
  - Serialização e persistência completa em arquivos padronizados `.json` com validação estrita de schema.
  - Modelos pré-configurados prontos para demonstração e uso imediato.

---

## 15. Segurança e Auditoria (`tools/security/`)

### `security.pwned_check` — Verificador de Senhas Vazadas (Have I Been Pwned)
- **Tipo**: `Tool` (Privacidade e Segurança com K-Anonimato)
- **Recursos**:
  - Consulta segura se uma senha já foi exposta em grandes vazamentos de dados públicos na internet.
  - **K-Anonimato Rigoroso**: O texto da senha NUNCA é transmitido. Apenas os 5 primeiros caracteres do hash SHA-1 são enviados à API do Have I Been Pwned; o restante do hash é comparado 100% localmente no cliente.
  - Exibição de quantas vezes a senha foi encontrada em vazamentos com badges de alerta visual em vermelho ou verde para senhas seguras.

### `security.virustotal` — Consulta de Reputação no VirusTotal (Hash Lookup)
- **Tipo**: `Tool` (Inteligência contra Ameaças)
- **Recursos**:
  - Consulta o veredito de mais de 70 motores antivírus mundiais para qualquer executável, instalador ou arquivo suspeito.
  - Consulta por cálculo de hash SHA-256 local, sem upload de arquivos privados para a nuvem.
  - Gestão de chave de API em conformidade com as regras do projeto: consome exclusivamente o token centralizado nas configurações do aplicativo (`api_tokens.virustotal`).
  - Resumo de detecção com total de motores maliciosos, suspeitos e limpos, além de link direto para o relatório completo no portal VirusTotal.

### `security.signature_check` — Verificador de Assinatura Digital (Authenticode)
- **Tipo**: `Tool` (Integridade e Autenticidade de Binários)
- **Recursos**:
  - Validação da assinatura digital Authenticode de arquivos executáveis (`.exe`) e bibliotecas (`.dll`) do Windows via PowerShell / Win32 API.
  - Identificação de Status da Assinatura: `Valid` (Válida), `NotSigned` (Não Assinado), `HashMismatch` (Adulterado) ou `NotTrusted` (Não Confiável).
  - Extração de Certificado: Nome do Signatário / Empresa Emissora, Algoritmo de Hash (ex: SHA-256) e Carimbo de Data/Hora (Timestamp).

---

## 16. Ferramentas Adicionais e Especializadas

### `files.junction_mover` — Mover Pasta Mantendo Junção NTFS (Directory Junction)
- **Tipo**: `Tool` (Interativo e Operações de Disco)
- **Identificador**: `files.junction_mover`
- **Recursos**:
  - Move pastas pesadas (como bibliotecas de jogos, máquinas virtuais, caches de IDEs ou pastas de usuários) para outro disco ou partição física sem quebrar os programas que as utilizam.
  - Criação automática de Junção NTFS transparente (`_winapi.CreateJunction` nativo do Windows), dispensando privilégios de Administrador.
  - Validação de espaço livre no disco de destino com margem de segurança.
  - Indicador de tamanho e contagem recursiva de arquivos antes da execução.
  - Processo assíncrono com barra de progresso e tratamento contra reparse points aninhados.

### `pdf.page_organizer` — Organizador Visual de Páginas PDF
- **Tipo**: `Tool` (Interativo com Miniaturas Visuais)
- **Identificador**: `pdf.page_organizer`
- **Recursos**:
  - Reordenação, rotação e exclusão visual de páginas de documentos PDF.
  - Renderização ultrarrápida de miniaturas em memória via `pypdfium2` (sem arquivos temporários no disco).
  - Botões de navegação rápida por página: mover para a esquerda (`<`), mover para a direita (`>`), girar em 90° graus e excluir/restaurar página.
  - Exportação e montagem de novo documento PDF através de `pypdf`.

### `pdf.stamp` — Carimbo, Marca d'Água e Numeração de Páginas PDF
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Identificador**: `pdf.stamp`
- **Recursos**:
  - Aplicação de carimbos diagonais translúcidos ("CONFIDENCIAL", "RASCUNHO", "CÓPIA", "APROVADO" ou texto livre) com ângulo, opacidade e cor customizáveis.
  - Numeração automática de páginas com suporte a posições (rodapé direito, rodapé centralizado, cabeçalho) e formatos flexíveis (`Página {page} de {total}`, `{page}/{total}`, `{page}`).
  - Filtragem de páginas por intervalo (ex: `1-5, 8, 11-15`) ou em todo o documento.
  - Motor de renderização vetorial preciso com `reportlab` e composição com `pypdf`.

### `media.normalize` — Normalização de Volume em Lote (EBU R128 Loudnorm)
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Identificador**: `media.normalize`
- **Recursos**:
  - Normalização da sonoridade de áudios e vídeos pelo padrão broadcast internacional EBU R128 / ITU-R BS.1770 (`loudnorm`).
  - Presets prontos para streaming: Spotify/YouTube (-14 LUFS), Apple Music (-16 LUFS), Televisão / Broadcast (-23 LUFS) ou modo Personalizado.
  - Tratamento inteligente de vídeos: preserva a trilha de vídeo original intocada (`-c:v copy`), normalizando apenas as faixas de áudio sem perda de tempo ou qualidade de imagem.
  - Suporte expandido a 50 formatos de áudio e vídeo (`.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`, `.ts`, `.mts`, `.m2ts`, `.wmv`, `.flv`, `.mpg`, `.vob`, `.3gp`, `.mxf`, `.mp3`, `.wav`, `.flac`, `.m4a`, `.aac`, `.ogg`, `.opus`, `.aiff`, `.caf`, `.ac3`, `.wma`, etc.).

### `media.subtitles` — Editor e Conversor de Legendas (SRT / WebVTT)
- **Tipo**: `Tool` (Interativo e Utilitário de Mídia)
- **Identificador**: `media.subtitles`
- **Recursos**:
  - Conversão bidirecional entre arquivos de legenda SubRip (`.srt`) e WebVTT (`.vtt`).
  - Tabela interativa com listagem de todas as falas, tempos de início, tempos de fim e texto.
  - **Ajuste de Sincronia (Time Shift)**: Adicione ou subtraia tempo em milissegundos ou use os botões rápidos (+0.5s, -0.5s, +1.0s, -1.0s) para sincronizar perfeitamente áudio e vídeo com atraso ou adiantamento.
  - Limpeza automática de marcações HTML (`<i>`, `<b>`, etc.) e normalização de quebras de linha CRLF/LF.

### `media.transcribe` — Transcrição de Áudio Offline por Inteligência Artificial
- **Tipo**: `Tool` (Interativo e IA Local)
- **Identificador**: `media.transcribe`
- **Recursos**:
  - Transcrição de áudio e extração de fala 100% offline via modelos Whisper (`faster-whisper` ou `openai-whisper`).
  - Extração automática de áudio mono 16 kHz via FFmpeg a partir de qualquer arquivo de vídeo ou áudio.
  - Seleção de modelo (Tiny, Base, Small, Medium) e seleção de idioma (português, inglês ou detecção automática).
  - Exportação direta para texto puro (`.txt`) ou arquivo de legenda sincronizado (`.srt`).
  - Interface amigável com orientação de instalação caso as dependências de IA ainda não estejam presentes no ambiente Python do usuário.

---

## 17. Atualizações e Expansões de Ferramentas Existentes

- **`archive.manager`**: Expandido com suporte nativo a descompactação e inspeção de arquivos `.7z` (via `py7zr`, `7z.exe` ou `tar.exe` bsdtar nativo do Windows) e `.rar` (via `7z.exe`, `unrar.exe` ou `bsdtar`). Suporte integrado também ao Smart Drop Router.
- **`data.doc_converter`**: Adicionada opção de exportação de Markdown e HTML diretamente para PDF formatado em página A4 através de `QTextDocument` e `QPdfWriter`, sem necessidade de bibliotecas externas pesadas.
- **`calc.date_calculator`**: Incorporado cálculo algorítmico de feriados nacionais brasileiros móveis (Páscoa, Carnaval, Sexta-feira Santa, Corpus Christi) e fixos (incluindo Consciência Negra). Adicionada 4ª aba dedicada "Feriados do Ano" com listagem completa, contagem de feriados em dias úteis e fins de semana, e botão para copiar.
- **`network.public_apis`**: Expandido com consultas completas adicionais da BrasilAPI:
  - **DDD**: Consulta de código DDD com estado (UF) e lista completa ordenada de todos os municípios atendidos.
  - **Bancos**: Consulta de todos os bancos cadastrados no Banco Central/FEBRABAN com código COMPE, razão social, nome comercial e ISPB, com filtro de busca em tempo real.
  - **Feriados Nacionais**: Consulta oficial de feriados nacionais por ano via endpoint BrasilAPI.
  - **Tabela FIPE**: Consulta do valor de mercado e histórico de veículos pelo código FIPE oficial.

---

## 18. Segurança e Auditoria Defensiva (`tools/security/`)

### `security.http_headers` — Auditor de Cabeçalhos HTTP de Segurança
- **Tipo**: `Tool` (Interativo e Auditoria Defensiva)
- **Identificador**: `security.http_headers`
- **Recursos**:
  - Auditoria e autodiagnóstico de cabeçalhos HTTP públicos para sites e aplicações web próprias.
  - Avaliação detalhada de conformidade OWASP: `Strict-Transport-Security` (HSTS com verificação de max-age, includeSubDomains e preload), `Content-Security-Policy` (CSP com alerta de diretivas permissivas como unsafe-inline/unsafe-eval), `X-Frame-Options` (prevenção de Clickjacking), `X-Content-Type-Options` (nosniff), `Referrer-Policy`, `Permissions-Policy`, e políticas cross-origin (`COOP`, `COEP`, `CORP`).
  - Detecção de vazamento de informações e versões em cabeçalhos de servidor (`Server`, `X-Powered-By`, `X-AspNet-Version`).
  - Classificação por notas de **A+** a **F** e pontuação de 0 a 100 pontos no padrão internacional de segurança web.
  - Tabela com `DataTableView` contendo cores dinâmicas de status e severidade, busca/filtro instantâneo e painel de impacto detalhado.
  - Exportação completa do relatório de conformidade em formato Markdown (`.md`) ou Texto (`.txt`).
  - Execução assíncrona segura via `TaskRunner` e aviso ético explícito na interface.

---

## 19. Dados e Estruturas (`tools/data/`)

### `data.json_explorer` — Explorador e Visualizador em Árvore de JSON
- **Tipo**: `Tool` (Interativo e Visualizador Estrutural)
- **Identificador**: `data.json_explorer`
- **Recursos**:
  - Visualização em árvore expansível (`QTreeWidget`) para arquivos JSON complexos e volumosos.
  - Identificação de tipos e contagem automática em cada nó (objetos, arrays, strings, números, booleanos, nulos).
  - Busca instantânea inteligente por chaves e valores com tolerância a acentos em português.
  - Consulta integrada por sintaxe JSONPath (RFC 9535) com realce dos nós encontrados.
  - Relatório estatístico detalhado: total de nós, chaves únicas, profundidade máxima e contagem por tipo de dado.
  - Painel de inspeção e visualização formatada do nó selecionado.

### `data.csv_tools` — Utilitário Avançado de Planilhas CSV
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `data.csv_tools`
- **Recursos**:
  - Divisão de arquivos CSV em partes menores por quantidade de linhas configurável, preservando o cabeçalho original em todas as partes geradas.
  - Conversão universal de delimitadores (vírgula, ponto-e-vírgula, tabulação/TSV e pipe) com detecção automática do delimitador de origem.
  - Remoção determinística de linhas duplicadas, com suporte a subconjuntos de colunas como chave única.
  - Fusão de múltiplos arquivos com mesmo cabeçalho em um único arquivo de saída.
  - Suporte a codificações UTF-8 e Windows-1252 (CP1252 / Excel legado).

### `data.sql_on_files` — Consultas SQL Analíticas em Arquivos (CSV e JSON)
- **Tipo**: `Tool` (Interativo e Banco de Dados em Memória)
- **Identificador**: `data.sql_on_files`
- **Recursos**:
  - Carregamento de múltiplos arquivos CSV e JSON para um banco SQLite em memória (`:memory:`).
  - Inferência automática de tipos de dados (INTEGER, REAL, TEXT) e sanitização de identificadores de tabelas e colunas.
  - Editor SQL com atalhos rápidos (`SELECT * LIMIT 50`, `COUNT(*)`) e execução de consultas de leitura e manipulação com medição de tempo em milissegundos.
  - Tabela paginada e interativa com visualização dos dados resultantes.
  - Exportação direta de resultados em formatos CSV, JSON, Markdown e tabelas HTML.

### `data.struct_diff` — Comparador Semântico de Estruturas (JSON / YAML / TOML)
- **Tipo**: `Tool` (Interativo e Comparador Semântico)
- **Identificador**: `data.struct_diff`
- **Recursos**:
  - Comparação semântica profunda entre dois documentos estruturados (JSON, YAML, TOML), identificando adições, exclusões e modificações.
  - Imunidade a variações cosméticas: ignora ordenação de chaves em dicionários, espaçamentos e estilos de indentação.
  - Caminho semântico padronizado (notação de ponto e colchetes estilo JSONPath: `$.banco.porta`, `$.tags[2]`).
  - Destaque colorido por severidade (+ verde para inclusões, - vermelho para exclusões, ~ laranja para modificações de valor ou tipo).
  - Sumário estatístico comparativo completo.

### `data.schema_infer` — Inferência de Schemas e Modelos de Tipagem
- **Tipo**: `Tool` (Interativo e Gerador de Código)
- **Identificador**: `data.schema_infer`
- **Recursos**:
  - Geração automática de modelos e esquemas formais de tipagem a partir de uma amostra de dados JSON.
  - Suporte a **JSON Schema (Draft 2020-12)** com mapeamento de propriedades e lista de campos obrigatórios (`required`).
  - Geração de classes de contratos **Pydantic v2** com `BaseModel`, `Field(alias=...)` e tipos nativos de validação.
  - Geração de código Python **`@dataclass`** com `field(default_factory=list)` e valores padrão.
  - Geração de interfaces **TypeScript** com tipagem estrita para integração com aplicações web e APIs.
  - Personalização do nome da classe raiz e cópia rápida para a área de transferência.

### `data.excel_tools` — Ferramentas de Planilhas Excel (.xlsx / .xlsm)
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `data.excel_tools`
- **Recursos**:
  - Manipulação de pastas de trabalho modernas do Microsoft Excel sem necessidade de instalação do Office, via `openpyxl`.
  - Divisão de abas em arquivos `.xlsx` independentes, preservando títulos e valores.
  - Consolidação de planilhas em lote: fusão de arquivos como abas separadas ou consolidação de linhas com mesmo cabeçalho em uma aba única.
  - Exportação em lote de todas as abas de uma planilha para arquivos CSV individuais com delimitador customizável.

### `data.config_convert` — Conversor Universal de Configurações (.env / .ini / .properties / TOML / YAML / JSON)
- **Tipo**: `Tool` (Interativo e Utilitário de Configuração)
- **Identificador**: `data.config_convert`
- **Recursos**:
  - Conversão bidirecional sem perdas entre os 6 principais formatos de configuração do ecossistema de software:
    - Variáveis de ambiente (`.env`)
    - Arquivos de configuração Windows/Linux (`.ini`)
    - Configurações Java e Spring Boot (`.properties`)
    - Formato declarativo moderno TOML (`.toml`)
    - Formato legível para humanos YAML (`.yaml`, `.yml`)
    - Notação de objetos JavaScript JSON (`.json`)
  - Suporte a achatamento (flatten) em chaves com notação de ponto (`app.database.port=5432`) ou expansão hierárquica automática (unflatten).
  - Tratamento inteligente de comentários e aspas.

### `data.log_viewer` — Visualizador e Monitor de Arquivos de Log (Tail e Severidade)
- **Tipo**: `Tool` (Interativo e Diagnóstico de Sistema)
- **Identificador**: `data.log_viewer`
- **Recursos**:
  - Leitura otimizada sob demanda de arquivos de log volumosos com leitura rápida do final do arquivo (`tail`).
  - Reconhecimento automático de níveis de severidade (FATAL, ERROR, WARN, INFO, DEBUG, TRACE) e timestamps.
  - Filtro instantâneo por severidade e pesquisa por texto simples ou expressões regulares (Regex).
  - Realce visual por cores conforme severidade das mensagens.
  - Modo "Seguir Final (Tail Automático)" com recarregamento periódico de 2 segundos para monitoramento ao vivo.
  - Atalho de 1 clique para carregar diretamente o arquivo de log da aplicação (`app.log`).

---

## 20. Arquivos e Pastas (`tools/files/`)

### `files.catalog` — Indexador e Catalogador de Mídias Externas (Snapshots Offline)
- **Tipo**: `Tool` (Interativo e Catalogação Offline)
- **Identificador**: `files.catalog`
- **Recursos**:
  - Indexação recursiva rápida de diretórios, pendrives, cartões de memória e discos externos USB.
  - Salvamento de snapshots em formato JSON compacto com metadados completos (caminho relativo, tamanho em bytes, data de modificação e tipo).
  - Busca instantânea offline por nome de arquivo em todos os catálogos previamente gerados, mesmo com o disco ou pendrive desconectado.
  - Exportação e importação de arquivos de catálogo `.json` para compartilhamento ou backup de inventário.
  - Resumo de métricas por catálogo: total de arquivos, total de pastas e tamanho acumulado em KB/MB/GB.

### `files.type_detector` — Identificador de Tipo Real de Arquivo por Assinatura Binária (Magic Bytes)
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `files.type_detector`
- **Recursos**:
  - Inspeção dos bytes de cabeçalho (*Magic Bytes*) para identificação precisa do tipo MIME e formato real do arquivo.
  - Detecção de discrepâncias entre a extensão declarada no nome e o conteúdo binário real (ex.: executável `.exe` mascarado como `.jpg` ou documento compactado zip renomeado).
  - Banco de assinaturas abrangente para imagens (PNG, JPEG, GIF, WEBP, BMP, TIFF), documentos (PDF, ZIP/Office docx/xlsx/pptx, RAR, 7Z, GZ, TAR), mídia (MP3, MP4, WAV, FLAC, OGG, AVI, MKV) e executáveis Windows PE (`MZ`).
  - Opção de correção automática em lote da extensão do arquivo para a extensão recomendada legítima.

### `files.cleanup_finder` — Localizador e Higienizador em Lote de Pastas Vazias e Atalhos Quebrados
- **Tipo**: `Tool` (Interativo e Limpeza Segura)
- **Identificador**: `files.cleanup_finder`
- **Recursos**:
  - Varredura recursiva de diretórios com detecção refinada de:
    - Pastas vazias ou pastas contendo apenas arquivos de lixo de sistema (ex.: `Thumbs.db`, `desktop.ini`).
    - Arquivos de tamanho zero byte (0 B).
    - Atalhos do Windows (`.lnk`) com alvos inexistentes ou caminhos quebrados.
  - Modo de simulação (*Dry Run*) para conferência prévia sem modificação física do disco.
  - Exibição tabular interativa com seleção individual e em massa dos itens detectados.
  - Higienização segura com remoção física pós-confirmação explícita do usuário.

### `files.links_manager` — Gerenciador Visual de Links Simbólicos, Junções e Hardlinks NTFS
- **Tipo**: `Tool` (Interativo e Ponteiros de Sistema de Arquivos)
- **Identificador**: `files.links_manager`
- **Recursos**:
  - Auditoria e listagem de ponteiros NTFS existentes em qualquer pasta informada:
    - Junções de Diretório (*Directory Junctions* / `_winapi.CreateJunction`).
    - Links Simbólicos de Arquivo e de Pasta (*Symlinks*).
    - Links Rígidos (*Hardlinks*).
  - Detecção imediata de status de integridade: aponta se o destino continua existindo ou se o link está quebrado/órfão.
  - Remoção segura de links quebrados (desconecta o ponteiro sem deletar o arquivo ou diretório de destino original).
  - Assistente para criação rápida de novas junções e links simbólicos entre diretórios.

### `files.doc_metadata` — Inspetor e Limpador de Metadados de Documentos Office e PDF
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `files.doc_metadata`
- **Recursos**:
  - Inspeção detalhada de metadados de privacidade em documentos do Microsoft Office (Word `.docx`, Excel `.xlsx`, PowerPoint `.pptx`) e arquivos PDF (`.pdf`).
  - Extração de campos sensíveis: autor, título, assunto, empresa/organização, criador de software, data de criação e data de última modificação.
  - Remoção completa de metadados em lote (*Sanitize/Clean*):
    - Documentos Office OpenXML: remoção higiênica de `docProps/core.xml` e `docProps/app.xml`.
    - Documentos PDF: limpeza estrutural do dicionário `/Info` e do stream de metadados XMP via `pypdf`.
  - Preservação estrita da integridade de todo o conteúdo textual, fórmulas e imagens do documento original.

### `files.tree_export` — Gerador e Exportador de Árvore de Diretórios
- **Tipo**: `Tool` (Interativo e Documentação de Estruturas)
- **Identificador**: `files.tree_export`
- **Recursos**:
  - Geração de representações hierárquicas de árvores de arquivos e pastas com profundidade máxima configurável.
  - Suporte a 4 formatos de exportação estruturada:
    - **Texto Puro (ASCII / Unicode)** com conectores padrão `├──`, `└──` e `│`.
    - **Markdown** formatado com blocos de código ideais para documentação e READMEs.
    - **Tabela CSV** discriminando nível, nome, tipo, caminho absoluto, tamanho e data de modificação.
    - **Relatório HTML** visual responsivo e moderno com estilos Fluent Design.
  - Opções para incluir ou ignorar arquivos ocultos e limitar a profundidade da varredura.
  - Botão de cópia rápida para a área de transferência e botão para salvar arquivo físico em disco.

### `files.hex_viewer` — Visualizador Hexadecimal e ASCII com Rolagem Virtual Paginada
- **Tipo**: `Tool` (Interativo e Análise Forense de Baixo Nível)
- **Identificador**: `files.hex_viewer`
- **Recursos**:
  - Visualização de arquivos binários de qualquer porte com paginação sob demanda por offset (512 B a 4 KB por página).
  - Tabela clássica de 3 colunas: Offset Hexadecimal, Grade de 16 bytes em Hex e Coluna de caracteres ASCII legíveis (com substituição de caracteres não-imprimíveis por `.`).
  - Sistema de busca em tempo real com suporte a padrões em formato Hexadecimal (ex.: `4D 5A` ou `89 50 4E 47`) ou texto puro ASCII.
  - Navegação precisa com salto direto para offset específico (`Ir para Offset`).
  - Cópia rápida dos bytes selecionados para a área de transferência.

### `files.robocopy_gui` — Assistente Gráfico de Sincronização e Cópia Robusta Robocopy
- **Tipo**: `Tool` (Interativo e Cópia em Lote do Windows)
- **Identificador**: `files.robocopy_gui`
- **Recursos**:
  - Interface amigável para o utilitário nativo de cópia e espelhamento de alto desempenho `robocopy.exe` do Windows.
  - Seleção dos principais modos de sincronização:
    - Espelhamento completo (`/MIR` - cria cópia idêntica e remove arquivos órfãos no destino).
    - Cópia recursiva incluindo pastas vazias (`/E`).
    - Cópia incremental apenas de arquivos mais recentes (`/XO`).
    - Modo simulação prévia (*Dry Run* / `/L` - lista sem copiar nada).
    - Modo tolerante a falhas com retomada automática (`/Z`).
  - Ajuste de threads concorrentes para transferência multi-thread acelerada (`/MT:8`).
  - Filtros avançados para exclusão de pastas (`/XD`) e arquivos/máscaras (`/XF`).
  - Visualização em tempo real do console de saída e interpretação precisa da máscara de bits de códigos de saída (exit codes 0 a 7 indicam sucesso no Robocopy).

### `files.free_space_wipe` — Sanitizador Seguro de Espaço Livre em Disco
- **Tipo**: `Tool` (Interativo e Segurança e Privacidade)
- **Identificador**: `files.free_space_wipe`
- **Recursos**:
  - Sobrescrita de clusters não alocados no disco para impedir a recuperação forense de arquivos excluídos.
  - Dois modos de operação selecionáveis:
    - **Automático Nativo do Windows (`cipher /w:caminho`)**: Executa a rotina oficial de 3 passos do Windows (preenchimento com zeros `0x00`, preenchimento com `0xFF` e números pseudorrandômicos).
    - **Rotina Local Rápida (1 Passo Seguro)**: Criação e preenchimento controlado de arquivo temporário com zeros até esgotar o espaço disponível com posterior liberação e flush de disco.
  - Exibição de estatísticas de espaço livre disponível e espaço total antes e durante o processo.
  - Alerta explícito de segurança e confirmação antes do disparo da sanitização.

---

## 21. Compactação e Arquivos Comprimidos (`tools/archive/`)

### `archive.batch_extract` — Descompactador em Lote Inteligente
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `archive.batch_extract`
- **Recursos**:
  - Descompactação paralela em lote para múltiplos arquivos de formatos variados (ZIP, TAR, GZ, TGZ, BZ2, XZ, 7Z, RAR).
  - Criação automática de subpastas individuais com o nome de cada arquivo compactado.
  - Detecção inteligente de raiz duplicada para prevenir aninhamento desnecessário (ex.: `projeto/projeto/arquivo.txt`).
  - Opção para exclusão automática do arquivo compactado de origem após extração bem-sucedida.
  - Suporte a descompressão de arquivos protegidos por senha.
  - Proteção rigorosa contra ataques de *Zip Slip* e *Path Traversal*.

### `archive.integrity_repair` — Verificador de Integridade e Recuperação de Emergência
- **Tipo**: `Tool` (Interativo e Diagnóstico Forense de Compactados)
- **Identificador**: `archive.integrity_repair`
- **Recursos**:
  - Teste minucioso de integridade e validação de CRC32 membro a membro de arquivos ZIP e TAR.
  - Diagnóstico preciso discriminando membros intactos versus membros corrompidos por falhas de gravação ou download incompleto.
  - Modo de recuperação e salvamento de emergência (*Salvage*): extrai e preserva todos os arquivos saudáveis contidos dentro de arquivos ZIP parcialmente danificados.
  - Varredura heurística de baixo nível por assinaturas de cabeçalhos locais `PK\x03\x04` para resgate de dados mesmo quando o diretório central (*Central Directory*) foi apagado ou truncado.

### `archive.iso_tools` — Ferramentas de Imagens de Disco ISO, VHD e VHDX
- **Tipo**: `Tool` (Interativo e Gerenciador de Armazenamento Virtual)
- **Identificador**: `archive.iso_tools`
- **Recursos**:
  - Montagem e desmontagem visual de imagens virtuais no Windows via PowerShell nativo (`Mount-DiskImage` / `Dismount-DiskImage`) com suporte a modo somente-leitura.
  - Identificação automática da letra da unidade virtual atribuída (ex.: `E:`) e rótulo do volume.
  - Listagem em tempo real de todas as imagens virtuais montadas no sistema, com botão de desmontagem direta com 1 clique.
  - Extração direta de imagens ISO sem necessidade de montagem de unidade de disco, utilizando o utilitário nativo `tar.exe` do Windows ou espelhamento resiliente.

### `archive.comic_maker` — Conversor de Quadrinhos Digitais CBZ
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `archive.comic_maker`
- **Recursos**:
  - Conversão bidirecional entre pastas de imagens e arquivos de quadrinhos digitais CBZ (*Comic Book Archive*).
  - Ordenação natural numérica de páginas (garante que `page_2.jpg` venha antes de `page_10.jpg`).
  - Geração automática de manifesto de metadados padronizado do setor `ComicInfo.xml` com título, número da edição e contagem de páginas.
  - Modos de compressão selecionáveis: `DEFLATE` (otimizado para menor tamanho) ou `STORE` (sem compressão para leitura instantânea).

### `archive.multi_volume` — Criador e Juntador de Volumes Múltiplos
- **Tipo**: `Tool` (Interativo e Divisão/Fusão de Volumes)
- **Identificador**: `archive.multi_volume`
- **Recursos**:
  - Divisão de arquivos volumosos em partes sequenciais com presets populares (10 MB, 25 MB Discord, 50 MB WhatsApp, 100 MB, 700 MB CD, 2 GB/4 GB limites FAT32) ou tamanho em MB personalizado.
  - Suporte aos dois padrões principais de nomenclatura de mercado:
    - Extensão numérica pura: `arquivo.zip.001`, `arquivo.zip.002`...
    - Sufixo de volume: `arquivo.part01.zip`, `arquivo.part02.zip`...
  - Detecção e agrupamento automático de todas as partes da cadeia sequencial a partir da seleção de qualquer volume.
  - Reconstrução binária determinística bit a bit do arquivo consolidado original.

---

## 22. PDF e Documentos (`tools/pdf/`)

### `pdf.sign_visual` — Assinatura Visual em PDF
- **Tipo**: `Tool` (Interativo e Inserção Gráfica)
- **Identificador**: `pdf.sign_visual`
- **Recursos**:
  - Inserção e posicionamento visual de imagens digitalizadas de assinaturas e rubricas (PNG com canal alfa/transparência) sobre documentos PDF.
  - Ajuste de coordenadas (X, Y) e dimensões em pontos (pt) com preservação de proporção.
  - Opção para adicionar carimbo de data/hora ou texto explicativo de formalização logo abaixo da rubrica.
  - Seleção de página de aplicação: primeira página, última página, todas as páginas ou página número N específica.

### `pdf.redact` — Censura e Tarjamento Permanente em PDF
- **Tipo**: `Tool` (Interativo e Anonimização Segura)
- **Identificador**: `pdf.redact`
- **Recursos**:
  - Localização automática de termos confidenciais (CPFs, nomes, salários, e-mails, senhas) via extração estruturada de layout do documento.
  - Aplicação de tarjas retangulares opacas permanentes (preto de censura oficial ou branco para ocultação) que sobrepõem e removem a visualização dos dados.
  - Suporte a busca diferenciando ou ignorando maiúsculas e minúsculas (*Case Sensitive*).
  - Relatório de conformidade com total de ocorrências tarjadas e páginas afetadas.

### `pdf.form_filler` — Preenchedor de Formulários PDF (AcroForm)
- **Tipo**: `Tool` (Interativo e Manipulação de Formulários)
- **Identificador**: `pdf.form_filler`
- **Recursos**:
  - Leitura e mapeamento de todos os campos interativos contidos no PDF (campos de texto, botões de seleção e listas suspensas).
  - Tabela interativa para preenchimento ágil de valores com visualização dos nomes e tipos dos campos.
  - Opção de achatamento (*Flatten*): transforma as anotações do formulário em conteúdo fixo da página, impedindo alterações posteriores por terceiros.
  - Exportação dos dados preenchidos para arquivos estruturados no formato JSON.

### `pdf.nup_booklet` — Reorganizador de Páginas e Livretos (N-Up / Booklet)
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `pdf.nup_booklet`
- **Recursos**:
  - Imposição N-Up para economia de papel em impressão:
    - **2-Up**: 2 páginas por folha em orientação A4 paisagem com proporção preservada.
    - **4-Up**: 4 páginas por folha em grade 2x2 em orientação A4 retrato.
  - **Imposição de Livreto (*Booklet*)**: Cálculo automático da sequência de páginas para impressão frente e verso destinada à encadernação e dobra ao meio, com preenchimento de páginas em branco até múltiplo de 4.

### `pdf.crop_margins` — Recortador de Margens de PDF
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `pdf.crop_margins`
- **Recursos**:
  - Recorte de bordas brancas e margens vazias de documentos PDF para melhor legibilidade em leitores digitais e tablets.
  - **Modo Automático**: Detecção inteligente da caixa delimitadora (*bounding box*) do conteúdo real de texto e imagens, ajustando a CropBox com margem de respiro configurável.
  - **Modo Manual**: Ajuste fino de margens fixas em pontos (esquerda, direita, superior e inferior).

### `pdf.metadata_bookmarks` — Editor de Metadados e Sumário de PDF
- **Tipo**: `Tool` (Interativo e Metadados de Documento)
- **Identificador**: `pdf.metadata_bookmarks`
- **Recursos**:
  - Edição completa de propriedades e metadados do documento PDF (Título, Autor, Assunto, Palavras-chave).
  - Gerenciador visual da árvore de marcadores de sumário (*TOC Bookmarks / Outlines*):
    - Visualização dos marcadores existentes com página de destino.
    - Adição de novos capítulos e marcadores interativos com navegação instantânea.
    - Remoção ou reordenação de marcadores obsoletos.

### `pdf.tables_to_csv` — Extrator de Tabelas de PDF (CSV / Excel)
- **Tipo**: `Tool` (Interativo e Extração Tabular)
- **Identificador**: `pdf.tables_to_csv`
- **Recursos**:
  - Detecção e extração de tabelas com layout estruturado em relatórios PDF via biblioteca `pdfplumber`.
  - Visualização prévia da tabela selecionada em grade com contagem de linhas e colunas.
  - Exportação em lote de todas as tabelas encontradas para arquivos CSV individuais.
  - Exportação unificada para pasta de trabalho do Microsoft Excel (`.xlsx`), criando uma aba separada para cada tabela extraída.

### `pdf.compare` — Comparador de Documentos PDF
- **Tipo**: `Tool` (Interativo e Comparação Diferencial)
- **Identificador**: `pdf.compare`
- **Recursos**:
  - Comparação diferencial página a página entre duas versões de um mesmo documento PDF.
  - Cálculo percentual da taxa de similaridade textual via algoritmo de sequência difflib.
  - Identificação de páginas idênticas, modificadas, adicionadas ou excluídas.
  - Visualização lado a lado dos textos das páginas e destaque das linhas alteradas.

### `pdf.scan_cleanup` — Higienizador de Scans e Digitalizações
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `pdf.scan_cleanup`
- **Recursos**:
  - Melhoria da legibilidade de documentos escaneados e fotografados:
    - Aumento adaptativo de contraste para destacar textos desbotados.
    - Aplicação de filtro de nitidez (*Sharpen*) nas bordas dos caracteres.
    - Binarização inteligente (*Thresholding*) para conversão em preto e branco puro, removendo sombras cinzas de fundo e manchas de papel.
  - Seleção de resolução de renderização (100 DPI, 150 DPI equilibrado ou 300 DPI alta resolução).

---

## 23. Áudio, Vídeo e Multimídia (`tools/media/`)

### `media.inspector` — Inspetor Técnico de Mídia (MediaInfo)
- **Tipo**: `Tool` (Interativo e Análise Técnica)
- **Identificador**: `media.inspector`
- **Recursos**:
  - Inspeção aprofundada de contêineres de vídeo e áudio via `ffprobe` nativo.
  - Exibição de metadados gerais (formato, taxa de bits global, duração, encoders e tags).
  - Tabela detalhada de streams de vídeo: codec, perfil (ex: High@L4.1), resolução, aspecto, framerate (FPS), espaço de cor e amostragem de croma (ex: yuv420p).
  - Tabela de faixas de áudio: codec, taxa de amostragem (Hz), canais, idioma e bitrate.
  - Tabela de legendas: formato (subrip, ass, mov_text), idioma e títulos de faixa.
  - Exportação de relatórios técnicos completos em formatos TXT ou JSON estruturado.

### `media.compress_target` — Compressor de Vídeo com Meta de Tamanho em MB
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `media.compress_target`
- **Recursos**:
  - Cálculo automático e preciso de bitrate de vídeo e áudio para atingir um tamanho final desejado em megabytes (ex: 25 MB para Discord ou WhatsApp).
  - Presets populares integrados (8 MB, 16 MB, 25 MB, 50 MB, 100 MB).
  - Codificação de alta eficiência com H.264/AAC e suporte a presets de velocidade do encoder.

### `media.stream_manager` — Gerenciador de Trilhas e Remux de Contêineres
- **Tipo**: `Tool` (Interativo e Remuxing sem Perdas)
- **Identificador**: `media.stream_manager`
- **Recursos**:
  - Manipulação direta de contêineres multimídia (MP4 e MKV) em alta velocidade sem recodificação (*stream copy*).
  - Seleção e exclusão de faixas indesejadas de áudio ou legendas para diminuir o tamanho do arquivo.
  - Extração individualizada de faixas para arquivos separados (.mp3, .aac, .srt).
  - Reorganização e geração do novo contêiner sem perda de qualidade visual ou sonora.

### `media.silence_remover` — Removedor Automático de Silêncios e Pausas
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `media.silence_remover`
- **Recursos**:
  - Detecção e eliminação de trechos de silêncio e pausas mortas em podcasts, videoaulas e gravações.
  - Utilização do filtro acústico `silenceremove` do FFmpeg.
  - Limiar de ruído configurável em decibéis (-30 dB a -60 dB) e duração mínima de silêncio (0.3s a 2.0s).

### `media.spectrogram` — Espectrograma e Forma de Onda de Áudio
- **Tipo**: `Tool` (Interativo e Análise Acústica)
- **Identificador**: `media.spectrogram`
- **Recursos**:
  - Geração de espectrogramas acústicos de alta fidelidade via filtro `showspectrumpic` do FFmpeg com réguas de tempo e escala de frequências.
  - Geração de gráficos visuais de amplitude de forma de onda (*Waveform*) via filtro `showwavespic`.
  - Múltiplos mapas de cores térmicos e acústicos (Magma, Viridis, Plasma, Fogo).
  - Pré-visualização na interface gráfica e exportação em imagens PNG de alta resolução.

### `media.speed_changer` — Alterar Velocidade de Mídia
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `media.speed_changer`
- **Recursos**:
  - Modificação da velocidade de reprodução de arquivos de vídeo e áudio de 0.25x a 4.0x.
  - Modo com Preservação de Tom de Voz (*Pitch Correction*) através de encadeamento dinâmico de filtros `atempo`.
  - Modo Efeito Vinil/Fita (*Tape Speed Effect*) com alteração proporcional da afinação.

### `media.video_watermark` — Marca d'Água em Vídeo
- **Tipo**: `FileTool` (Processamento em Lote)
- **Identificador**: `media.video_watermark`
- **Recursos**:
  - Inserção de logotipos PNG transparentes com canal alfa ou textos estilizados sobre vídeos em lote.
  - 7 opções de posicionamento predefinidas (Cantos, Centro, Topo, Base) com margens configuráveis.
  - Ajuste de opacidade (10% a 100%) e tamanho de fonte com escape robusto de caracteres especiais.

### `media.audio_recorder` — Gravador de Áudio Dedicado
- **Tipo**: `Tool` (Interativo e Captura de Áudio)
- **Identificador**: `media.audio_recorder`
- **Recursos**:
  - Gravação de áudio a partir de dispositivos de entrada conectados via DirectShow e FFmpeg.
  - Listagem e atualização dinâmica dos microfones e interfaces de som disponíveis no Windows.
  - Cronômetro visual em tempo real, seleção de taxa de amostragem (44.1 kHz, 48 kHz) e formatos de saída (WAV, MP3, AAC, FLAC).
  - Finalização limpa de headers via comando de interrupção atômica.

### `media.cue_splitter` — Divisor de CUE Sheet
- **Tipo**: `Tool` (Interativo e Fatiamento de Álbuns)
- **Identificador**: `media.cue_splitter`
- **Recursos**:
  - Interpretação e fatiamento de arquivos `.cue` (CUE Sheet) associados a arquivos de áudio contínuos (WAV, FLAC, APE, MP3).
  - Tabela detalhada com título, artista e tempo de início de cada faixa.
  - Localização heurística do arquivo de áudio mestre com suporte a múltiplas extensões.
  - Aplicação automática de tags de metadados ID3/Vorbis nas faixas fatiadas e padrão de nomenclatura customizável.

### `media.contact_sheet` — Folha de Contato de Vídeo (Thumbnail Grid)
- **Tipo**: `Tool` (Interativo e Mosaicos de Vídeo)
- **Identificador**: `media.contact_sheet`
- **Recursos**:
  - Extração automática de quadros uniformemente espaçados ao longo da duração do vídeo.
  - Composição de mosaicos com grade configurável (ex: 3x3, 4x4, 5x5) em alta resolução (até 4K).
  - Cabeçalho escuro com metadados técnicos (nome, tamanho, resolução, codecs, duração total).
  - Marcação de timecode individual em cada miniatura e botões para salvar ou copiar a imagem para a área de transferência.

---

## 24. Ferramentas para Desenvolvedores (`tools/dev/`)

### `dev.project_cleaner` — Limpador de Projetos de Código (Build Cleaner)
- **Tipo**: `Tool` (Interativo e Limpeza em Lote)
- **Identificador**: `dev.project_cleaner`
- **Recursos**:
  - Varredura recursiva de diretórios identificando pastas pesadas de compilação e dependências descartáveis.
  - Mapeamento de ecossistemas: Node.js (`node_modules`, `.next`, `.nuxt`), Python (`__pycache__`, `.venv`, `.pytest_cache`), Rust (`target`), .NET (`bin`, `obj`) e Java/Gradle (`.gradle`).
  - Cálculo de espaço total recuperável em disco e quantidade de arquivos.
  - Exclusão seletiva e segura em massa com suporte a arquivos somente leitura no Windows.

### `dev.line_counter` — Contador de Linhas de Código (CLOC)
- **Tipo**: `Tool` (Interativo e Métricas de Código)
- **Identificador**: `dev.line_counter`
- **Recursos**:
  - Quantificação de linhas de código efetivo (SLOC), linhas de comentários e linhas em branco discriminadas por linguagem.
  - Suporte a mais de 15 linguagens (Python, JS/TS, C/C++, C#, Java, Rust, Go, HTML, CSS, SQL, Shell, etc.).
  - Varredura e catálogo automático de anotações técnicas `TODO` e `FIXME` com arquivo e número da linha.
  - Exportação de relatórios estruturados em formato CSV.

### `dev.selfsigned_cert` — Gerador de Certificados SSL/TLS Autoassinados
- **Tipo**: `Tool` (Interativo e Criptografia X.509)
- **Identificador**: `dev.selfsigned_cert`
- **Recursos**:
  - Geração de pares de certificados X.509 autoassinados e chaves privadas criptográficas via biblioteca `cryptography`.
  - Suporte a múltiplos Subject Alternative Names (SANs) para DNS (`localhost`, `*.local`) e IPs (`127.0.0.1`, `::1`).
  - Modos de emissão: Certificado de Servidor/Cliente ou Autoridade Certificadora Raiz (Root CA).
  - Algoritmos RSA (2048 e 4096 bits) e Curvas Elípticas ECDSA (P-256 e P-384).
  - Exportação em arquivos PEM individuais (.crt e .key) ou empacotamento em arquivo PKCS#12 (.pfx/.p12) com senha.

### `dev.env_compare` — Comparador de Ambientes (.env vs .env.example)
- **Tipo**: `Tool` (Interativo e Auditoria de Configurações)
- **Identificador**: `dev.env_compare`
- **Recursos**:
  - Comparação diferencial entre modelos de variáveis de ambiente (`.env.example`) e arquivos de produção reais (`.env`).
  - Destaque visual por cores: variáveis ausentes, variáveis declaradas vazias e chaves adicionais não documentadas.
  - Mascaramento inteligente de segurança para credenciais e segredos (`SECRET`, `PASSWORD`, `KEY`, `TOKEN`).
  - Geração automática e cópia das chaves faltantes para inclusão no arquivo de destino.

### `dev.reference` — Tabelas de Referência Técnica
- **Tipo**: `Tool` (Interativo e Consulta Técnica Offline)
- **Identificador**: `dev.reference`
- **Recursos**:
  - Catálogo completo de códigos de status HTTP (1xx, 2xx, 3xx, 4xx, 5xx) com frases padrão e explicações (RFC 9110).
  - Tabela de tipos MIME comuns por extensão e categoria.
  - Tabela ASCII completa (caracteres de controle 0-31 e imprimíveis 32-127 com valores Dec, Hex e Bin).
  - Mapeamento de códigos de teclas virtuais Win32 (Virtual-Key Codes: `VK_*`).
  - Lista de atalhos globais de produtividade do Windows 10/11 com filtragem em tempo real.

### `dev.css_toolbox` — CSS Developer Toolbox
- **Tipo**: `Tool` (Interativo e Design Front-End)
- **Identificador**: `dev.css_toolbox`
- **Recursos**:
  - Gerador de tipografia fluida com a função matemática CSS `clamp(min, preferred, max)` proporcional ao viewport.
  - Conversor bidirecional de unidades `px ↔ rem` com base raiz ajustável.
  - Auditoria de acessibilidade de cores com cálculo exato de luminância e taxa de contraste WCAG 2.1 (avaliação de conformidade AA e AAA).
  - Gerador de regras de sombra `box-shadow` com offset X/Y, desfoque, propagação, cor RGBA e opção de sombra interna (*inset*).

### `dev.minifier` — Minificador e Formatador Web (HTML / CSS / JS)
- **Tipo**: `Tool` (Interativo e Otimização Web)
- **Identificador**: `dev.minifier`
- **Recursos**:
  - Minificação de código HTML, folhas de estilo CSS e scripts JavaScript 100% offline sem necessidade de Node.js.
  - Remoção de comentários, quebras e espaços desnecessários com métricas de bytes economizados e taxa percentual de redução.
  - Embelezador e formatador com indentação limpa para depuração de payloads compactados.

### `dev.git_overview` — Painel Agregador de Repositórios Git
- **Tipo**: `Tool` (Interativo e Monitoramento de Projetos)
- **Identificador**: `dev.git_overview`
- **Recursos**:
  - Varredura de diretórios de código localizando todos os repositórios Git ativos.
  - Visualização unificada de branches ativas, arquivos pendentes de commit (modificados e não rastreados).
  - Contador de commits à frente (*ahead*) e atrás (*behind*) em relação ao upstream remoto.
  - Visualização da data e mensagem do commit mais recente e atalhos para abrir a pasta no Explorer ou no Terminal.

### `dev.gitignore_license` — Gerador de .gitignore e Licenças Open Source
- **Tipo**: `Tool` (Interativo e Inicialização de Projetos)
- **Identificador**: `dev.gitignore_license`
- **Recursos**:
  - Composição de arquivos `.gitignore` multicamada combinando linguagens e frameworks (Python, Node.js, Rust, Go, .NET, Java/Gradle, SO).
  - Inclusão de regras personalizadas com seções nomeadas.
  - Gerador oficial de licenças de código aberto: MIT, Apache 2.0, GNU GPL v3.0, BSD 3-Clause e The Unlicense.
  - Preenchimento dinâmico de ano e titular dos direitos autorais com salvamento direto no disco.

### `dev.mock_server` — Servidor HTTP Mock Local
- **Tipo**: `Tool` (Interativo e Teste de APIs)
- **Identificador**: `dev.mock_server`
- **Recursos**:
  - Servidor HTTP leve embutido em segundo plano executando em `127.0.0.1` com porta configurável.
  - Cadastro de rotas com métodos REST (GET, POST, PUT, DELETE, PATCH, ALL), códigos de status HTTP e payloads JSON customizados.
  - Simulação de latência de rede ajustável por endpoint.
  - Tabela de log de requisições recebidas em tempo real exibindo horário, IP de origem, endpoint e código retornado.

---

## 25. Produtividade e Organização Pessoal (`tools/productivity/`)

### `productivity.finance_tracker` — Controle de Finanças Pessoais Offline
- **Tipo**: `Tool` (Interativo e Gestão Financeira Offline)
- **Identificador**: `productivity.finance_tracker`
- **Recursos**:
  - Importação de extratos bancários brasileiros nos formatos OFX (Open Financial Exchange) e CSV.
  - Categorização automática de despesas baseada em palavras-chave inteligentes (Alimentação, Transporte, Moradia, Saúde, Lazer, etc.).
  - Cálculo instantâneo do balanço financeiro mensal: Total de Entradas, Total de Saídas, Saldo Líquido e Distribuição por Categoria.
  - Tabela de transações com ordenação, filtros por conta e exportação de dados.

### `productivity.recibo_orcamento` — Emissor de Recibos e Orçamentos em PDF
- **Tipo**: `Tool` (Interativo e Emissão Documental)
- **Identificador**: `productivity.recibo_orcamento`
- **Recursos**:
  - Emissão de recibos comerciais de pagamento diagramados em PDF via ReportLab.
  - Conversão automatizada de valores monetários em reais para texto por extenso em português.
  - Elaboração de propostas de orçamento completas com tabela discriminada de itens, quantidades, valores unitários e cálculo automático do total geral.
  - Campos completos de identificação do prestador e tomador de serviços com CPF/CNPJ e observações de pagamento.

### `productivity.kanban` — Quadro Kanban de Tarefas
- **Tipo**: `Tool` (Interativo e Gestão Visual de Projetos)
- **Identificador**: `productivity.kanban`
- **Recursos**:
  - Organização ágil de fluxos de trabalho com colunas personalizáveis dinâmicas.
  - Cartões com checklists interativos com checkboxes, etiquetas coloridas (tags), prazos de entrega e seletor de cores de destaque.
  - Movimentação rápida de cartões entre colunas e persistência automática em JSON local.
  - Funções de importação e exportação de quadros Kanban completos em JSON.

### `productivity.snippets` — Expansor de Trechos de Texto (Snippets)
- **Tipo**: `Tool` (Interativo e Automação de Digitação)
- **Identificador**: `productivity.snippets`
- **Recursos**:
  - Cadastro e organização de atalhos e trechos frequentes de texto categorizados.
  - Expansão inteligente de variáveis e placeholders dinâmicos: `{date}`, `{time}`, `{datetime}`, `{clipboard}`, `{uuid}`.
  - Painel de pré-visualização ao vivo do texto resultante com cópia imediata para a área de transferência.
  - Backup, exportação e importação da coleção de snippets em JSON.

### `productivity.flashcards` — Cartões de Memorização (Flashcards SM-2)
- **Tipo**: `Tool` (Interativo e Repetição Espaçada)
- **Identificador**: `productivity.flashcards`
- **Recursos**:
  - Implementação exata do algoritmo clássico de repetição espaçada SuperMemo SM-2 com cálculo de fator de facilidade (EF) e intervalos ideais de revisão.
  - Gestão de múltiplos baralhos de estudo independentes.
  - Sessão interativa de revisão com frente oculta, botão de revelação e avaliação de retenção (0 a 5).
  - Importação e exportação de baralhos completos no formato universal CSV.

### `productivity.countdown` — Painel de Contagem Regressiva e Prazos
- **Tipo**: `Tool` (Interativo e Gerenciamento de Tempo)
- **Identificador**: `productivity.countdown`
- **Recursos**:
  - Painel visual de acompanhamento de prazos, aniversários, datas de lançamento e entregas críticas.
  - Relógios em tempo real com discriminação de dias, horas, minutos e segundos restantes.
  - Mini-widget flutuante minimalista sem bordas (*Always on Top*) destacável para fixação direta na área de trabalho.
  - Cores semânticas customizáveis por evento e suporte a eventos passados (tempo decorrido).

### `productivity.bookmarks` — Gerenciador Local de Links e Favoritos Web
- **Tipo**: `Tool` (Interativo e Gestão de Referências Web)
- **Identificador**: `productivity.bookmarks`
- **Recursos**:
  - Catálogo de links e referências web categorizados por múltiplas tags e anotações.
  - Verificador de status HTTP integrado para identificação de links quebrados ou inativos.
  - Importação de favoritos a partir do formato padrão Netscape Bookmark HTML de qualquer navegador (Chrome, Edge, Firefox, Safari).
  - Exportação da coleção em HTML universal ou JSON estruturado.

### `productivity.journal` — Diário Pessoal & Registros Diários
- **Tipo**: `Tool` (Interativo e Escrita Cronológica)
- **Identificador**: `productivity.journal`
- **Recursos**:
  - Navegação cronológica e visual através de calendário interativo integrado.
  - Registro de pensamentos, atas e anotações com suporte a formatação rica em Markdown.
  - Seletor de humor e estado mental por dia acompanhado de etiquetas temáticas.
  - Busca textual rápida e exportação consolidada do diário completo para documento Markdown (`.md`) estruturado.

### `productivity.ics_calendar` — Visualizador de Calendário iCalendar (.ics)
- **Tipo**: `Tool` (Interativo e Agenda Padrão RFC 5545)
- **Identificador**: `productivity.ics_calendar`
- **Recursos**:
  - Leitura, edição e criação de eventos de calendário no formato padrão iCalendar RFC 5545 (`.ics`).
  - Navegação diária e mensal com exibição de horários de início e término, locais e descrições.
  - Compatibilidade com calendários do Microsoft Outlook, Google Calendar e Apple Calendar.
  - Importação e exportação de agendas completas no padrão `.ics`.

### `productivity.break_reminder` — Assistente de Ergonomia e Pausas Ativas
- **Tipo**: `Tool` (Interativo e Saúde no Trabalho)
- **Identificador**: `productivity.break_reminder`
- **Recursos**:
  - Monitor ergonômico com 3 trilhas simultâneas de pausas saudáveis:
    1. Descanso Visual baseado na regra 20-20-20 (a cada 20 minutos, olhar para 6 metros por 20 segundos).
    2. Alongamento físico e correção postural preventiva (a cada 45-60 minutos).
    3. Hidratação regular com incentivo ao consumo de água.
  - Janelas pop-up temporizadas não-bloqueantes contendo exercícios ilustrados e dicas posturais.
  - Intervalos e notificações totalmente configuráveis e persistidos no perfil do usuário.

---

## 26. Calculadoras e Simuladores Técnicos (`tools/calc/`)

### `calc.salary_br` — Calculadora Salarial CLT (Folha de Pagamento)
- **Tipo**: `Tool` (Interativo e Cálculos Trabalhistas Brasileiros)
- **Identificador**: `calc.salary_br`
- **Recursos**:
  - Cálculo oficial da folha de pagamento CLT com deduções progressivas de INSS por faixas salariais.
  - Comparativo automático do IRRF: deduções legais (número de dependentes e pensão alimentícia) versus dedução simplificada mensal.
  - Cálculo de alíquota efetiva real descontada do trabalhador e depósito patronal de FGTS (8%).
  - Módulo de férias: terço constitucional (1/3) e opção de abono pecuniário (venda de dias).
  - Simulador de rescisão contratual com discriminação de verbas rescisórias conforme o motivo (sem justa causa com multa rescisória do FGTS, pedido de demissão, justa causa ou acordo mútuo).

### `calc.health` — Calculadora de Saúde & Metabolismo (IMC / TMB)
- **Tipo**: `Tool` (Interativo e Biometria Nutricional)
- **Identificador**: `calc.health`
- **Recursos**:
  - Cálculo de Índice de Massa Corporal (IMC) com classificação oficial conforme a Organização Mundial da Saúde (OMS) e indicação de faixa de peso ideal para a estatura.
  - Cálculo de Taxa Metabólica Basal (TMB em repouso) utilizando a equação moderna de Mifflin-St Jeor para homens e mulheres.
  - Estimativa do Gasto Energético Total Diário (TDEE) conforme o nível de atividade física e metas calóricas para emagrecimento ou hipertrofia muscular.
  - Planejamento de hidratação diária com ingestão recomendada de água em litros, mililitros e copos de 250 ml considerando tempo de treino.

### `calc.fuel` — Calculadora de Combustível (Etanol vs. Gasolina)
- **Tipo**: `Tool` (Interativo e Economia Veicular)
- **Identificador**: `calc.fuel`
- **Recursos**:
  - Comparador econômico na bomba com base na paridade padrão (regra dos 70%) ou fator de eficiência real e customizado do veículo.
  - Indicação clara e em destaque do combustível mais vantajoso e preço máximo do etanol para compensar financeiramente.
  - Estimador completo de custos de viagem com base na distância (km), consumo médio (km/l), valor do combustível e pedágios.
  - Cálculo automático de custo por quilômetro rodado e divisão justa do valor por passageiro (rateio de carona).

### `calc.statistics` — Calculadora Estatística (Descritiva & Regressão)
- **Tipo**: `Tool` (Interativo e Análise Quantitativa)
- **Identificador**: `calc.statistics`
- **Recursos**:
  - Análise descritiva univariada completa a partir de dados numéricos (separados por vírgula, espaço ou linha):
    - Medidas de tendência central: Média aritmética, Mediana e Moda.
    - Medidas de dispersão: Amplitude total, Variância amostral/populacional, Desvio padrão amostral/populacional e Erro padrão da média.
    - Análise posicional: Quartis (Q1, Q2, Q3) e Intervalo Interquartil (IQR).
  - Módulo de Regressão Linear Simples via Método dos Mínimos Quadrados:
    - Equação da reta ajustada ($y = mx + b$).
    - Coeficiente de Determinação ($R^2$), Coeficiente de Correlação de Pearson ($r$), inclinação e intercepto.

### `calc.materials` — Calculadora de Materiais de Construção & Reforma
- **Tipo**: `Tool` (Interativo e Orçamento de Obras)
- **Identificador**: `calc.materials`
- **Recursos**:
  - Módulo de Pintura: cálculo de área total por demãos, rendimento da tinta por litro e otimização comercial de embalagens (combinação inteligente de Latas de 18L, Galões de 3,6L e Quartos de 900ml com minimização de sobras).
  - Módulo de Pisos e Revestimentos: área líquida com acréscimo de margem técnica de perda por recortes (10%, 15% ou 20%), total de caixas a comprar, sacos de argamassa (20kg) e quilos de rejunte necessários.
  - Módulo de Concreto e Contrapiso: cubagem em metros cúbicos ($m^3$) e estimativa de insumos no traço convencional (sacos de cimento 50kg, areia e pedra brita).

### `calc.electrical` — Calculadora Elétrica Residencial (Consumo, Ohm & Resistores)
- **Tipo**: `Tool` (Interativo e Engenharia Elétrica Básica)
- **Identificador**: `calc.electrical`
- **Recursos**:
  - Estimativa de consumo mensal em kWh e custo projetado na fatura de energia elétrica residencial a partir de presets de aparelhos (ar-condicionado, chuveiro, PC gamer, geladeira, etc.) e tarifa local.
  - Calculadora universal da Lei de Ohm: resolução automática de quaisquer grandezas faltantes (Tensão $V$, Corrente $I$, Resistência $R$ e Potência ativa $P$) a partir de 2 variáveis conhecidas.
  - Decodificador visual de código de cores de resistores eletrônicos de 4 e 5 faixas com valor nominal em Ohms (kΩ, MΩ) e tolerância aceitável.

### `calc.transfer` — Estimador de Tempo de Download & Transferência
- **Tipo**: `Tool` (Interativo e Redes de Telecomunicação)
- **Identificador**: `calc.transfer`
- **Recursos**:
  - Conversor e esclarecedor entre Mbps (Megabits por segundo anunciados em planos de internet) e MB/s (Megabytes por segundo de taxa real de download).
  - Estimativa de tempo total de transferência para arquivos com predefinições práticas (jogos pesados, filmes 4K, ISOs, álbuns).
  - Consideração de perda de banda por overhead de pacotes de rede TCP/IP.
  - Tabela comparativa automática projetando o mesmo download em planos comuns do mercado (50 Mbps, 100 Mbps, 300 Mbps, 500 Mbps e 1 Gbps).

### `calc.split_bill` — Calculadora de Divisão de Contas (Restaurante & Eventos)
- **Tipo**: `Tool` (Interativo e Gestão Compartilhada)
- **Identificador**: `calc.split_bill`
- **Recursos**:
  - Modo Divisão Rápida: rateio igualitário de despesas com inclusão proporcional de taxa de serviço (gorjeta), couvert artístico por pessoa e descontos promocionais.
  - Modo Divisão Individualizada: cadastro de múltiplos participantes e itens de consumo com discriminação de quem consumiu cada produto (inclusive subgrupos que dividiram porções ou bebidas).
  - Geração de extrato discriminado por pessoa com a soma de itens particulares, taxa de serviço e couvert já calculados.

### `calc.screen` — Calculadora de Telas & Monitores (PPI & Proporção)
- **Tipo**: `Tool` (Interativo e Métricas de Display)
- **Identificador**: `calc.screen`
- **Recursos**:
  - Cálculo preciso de densidade de pixels por polegada (PPI - Pixels Per Inch) a partir da resolução e diagonal da tela.
  - Proporção dimensional de aspecto (Aspect Ratio) com redução matemática simplificada (16:9, 16:10, 21:9 Ultrawide, 32:9 Super Ultrawide, 3:2 Surface).
  - Cálculo das dimensões físicas reais da área útil de exibição (Largura, Altura em centímetros e Área em $cm^2$).
  - Recomendação inteligente da porcentagem de escala de interface no Windows (DPI Scaling) para ergonomia visual e nitidez ideal.

### `calc.investments` — Simulador de Investimentos Renda Fixa (CDB, LCI, Poupança, Tesouro)
- **Tipo**: `Tool` (Interativo e Planejamento Financeiro)
- **Identificador**: `calc.investments`
- **Recursos**:
  - Simulação de juros compostos com aplicação inicial e aportes mensais periódicos.
  - Comparativo simultâneo lado a lado entre Caderneta de Poupança, CDBs com rentabilidade atrelada ao CDI, LCIs/LCAs isentas de imposto e Tesouro Selic.
  - Aplicação automática e determinística da tabela regressiva oficial do Imposto de Renda sobre o rendimento (22,5% até 180 dias, 20% até 360 dias, 17,5% até 720 dias e 15% acima de 720 dias).
  - Indicação em destaque do investimento mais lucrativo no vencimento e comparativo de ganho real em relação à poupança.

---

## 27. Automação Avançada do Sistema (`tools/automation/`)

### `automation.recipes` — Receitas de Automação (Pipelines Multi-Ferramentas)
- **Tipo**: `Tool` (Interativo e Encadeamento de Tarefas)
- **Identificador**: `automation.recipes`
- **Recursos**:
  - Criação, edição e reordenação de pipelines sequenciais de processamento onde a saída de uma ferramenta torna-se a entrada da próxima.
  - Editor visual com reordenação dinâmica de etapas (Subir / Descer / Adicionar / Remover).
  - Execução em lote com barra de progresso, registro de etapas e relatório consolidado de sucesso.
  - Persistência das receitas customizadas em arquivo JSON (`~/.wintoolbox/recipes.json`).

### `automation.hotkeys` — Atalhos Globais de Teclado (Hotkeys)
- **Tipo**: `Tool` (Interativo e Acessibilidade do Sistema)
- **Identificador**: `automation.hotkeys`
- **Recursos**:
  - Definição de combinações de teclas globais do Windows (ex: `Ctrl+Alt+S`, `Win+Shift+N`, `Ctrl+Shift+P`) para disparo imediato.
  - Suporte a múltiplos tipos de ação: abertura de ferramentas específicas do WinToolbox, execução de programas externos, abertura de diretórios no Windows Explorer e navegação para URLs da web.
  - Chaveamento individual de ativação/desativação de cada atalho e teste de disparo interativo.
  - Persistência e validação sintática das teclas em formato JSON.

### `automation.device_trigger` — Automação por Dispositivos Removíveis (Gatilhos USB)
- **Tipo**: `Tool` (Interativo e Monitoramento de Hardware)
- **Identificador**: `automation.device_trigger`
- **Recursos**:
  - Monitoramento contínuo e detecção física da inserção de pendrives, HDs externos e cartões de memória (`DRIVE_REMOVABLE`).
  - Associação de regras automáticas baseadas no rótulo de volume do dispositivo (ex: pendrive específico de fotos ou backups).
  - Disparo de ações como abertura da pasta no Explorer, sincronização/cópia de arquivos para pasta de destino ou execução de scripts de backup.
  - Exibição em tempo real das unidades removíveis conectadas e simulador de inserção de dispositivo.

### `automation.process_watcher` — Sentinela de Processos (Alertas de Execução & Conclusão)
- **Tipo**: `Tool` (Interativo e Sentinela de Tarefas)
- **Identificador**: `automation.process_watcher`
- **Recursos**:
  - Monitoramento de processos executáveis em segundo plano no Windows (ex: `blender.exe`, `render.exe`, `chrome.exe`).
  - Detecção de 4 condições de disparo:
    1. Encerramento do processo (`on_exit`) — ideal para avisos sonoros ao finalizar renderizações ou compilações longas.
    2. Inicialização do processo (`on_start`).
    3. Consumo de memória RAM acima do limite em MB configurado.
    4. Consumo de CPU acima do percentual configurado.
  - Seletor rápido a partir dos processos ativos no sistema operacional.

### `automation.cli_scheduler` — Agendador de Tarefas Headless (Windows Tasks)
- **Tipo**: `Tool` (Interativo e Integração com o Sistema Operacional)
- **Identificador**: `automation.cli_scheduler`
- **Recursos**:
  - Ponte de integração nativa com o utilitário `schtasks.exe` do Windows.
  - Agendamento de rotinas sem interface gráfica (modo headless: `wintoolbox run <tool_id>`).
  - Suporte a frequências: Diária (com horário configurável), Semanal, Ao Iniciar o Computador e Ao Fazer Logon.
  - Criação, exclusão, execução forçada de teste e botão direto para abertura do console nativo do Agendador de Tarefas do Windows (`taskschd.msc`).

### `automation.window_rules` — Regras Automáticas para Janelas (Monitor & Snap)
- **Tipo**: `Tool` (Interativo e Gerenciamento de Janelas)
- **Identificador**: `automation.window_rules`
- **Recursos**:
  - Criação de regras de comportamento e alocação espacial para janelas de softwares específicos ao serem executados.
  - Seleção do monitor de exibição desejado (Monitor 1 Principal, Monitor 2 Secundário, etc.).
  - Aplicação de estados de layout automáticos: Maximizado, Metade Esquerda da Tela (Snap Left), Metade Direita da Tela (Snap Right) ou Coordenadas Fixas em pixels ($X, Y, Largura, Altura$).
  - Aplicação imediata de regras sobre as janelas abertas atualmente no sistema operacional.

## 28. Segurança Ofensiva, Forense, OSINT e Engenharia Reversa

Esta expansão adiciona 43 ferramentas organizadas nos pacotes `security`, `crypto`,
`network`, `web`, `forensics`, `osint`, `rev` e `system`. As dependências opcionais
estão em `requirements-security.txt`. Toda operação longa usa `TaskRunner` e as
bibliotecas pesadas são importadas sob demanda.

### `security.hash_identify` — Identificador de Tipo de Hash
- **Tipo**: `Tool`.
- **Recursos**: assinaturas para MD5, SHA-1/2/3, NTLM, LM, bcrypt, Argon2, scrypt, Django, WordPress/PHPass, Joomla, Drupal, RIPEMD-160, CRC32, crypt Unix e Base64 de hash; confiança, comprimento esperado, exemplo e modo Hashcat; análise em tempo real com debounce de 300 ms.

### `security.hash_cracker` — Quebrador de Hashes
- **Tipo**: `Tool`; exige confirmação do termo de uso responsável.
- **Recursos**: wordlist com fallback de 100 senhas, força bruta com charset e comprimento, detecção automática do algoritmo, MD4/NTLM nativo, benchmark, Hashcat/GPU opcional, progresso, taxa, cancelamento e painel de log.

### `security.rainbow_generator` — Gerador de Rainbow Table
- **Tipo**: `Tool`.
- **Recursos**: geração incremental em SQLite com índice primário, estimativa de combinações e tamanho, confirmação acima de 1 GB, cancelamento com preservação parcial e consulta instantânea de hash.

### `security.jwt_secret_cracker` — Quebrador de Segredo JWT
- **Tipo**: `Tool`.
- **Recursos**: leitura de HS256/HS384/HS512, validação de assinatura em tempo constante, wordlist/lista inline/força bruta, alerta de token expirado, segredo encontrado e re-assinatura de token para validação.

### `crypto.stegano` — Esteganografia em Imagem e Áudio
- **Tipo**: `FileTool`; extensões `.png`, `.bmp` e `.wav`.
- **Recursos**: LSB em pixels RGB ou amostras WAV, mensagem ou arquivo, senha com fluxo SHA-256, cabeçalho `WTBXSTEG` com tamanho, flags e integridade SHA-256, cálculo de capacidade e extração com detecção de payload.

### `crypto.stegano_detect` — Detector de Esteganografia
- **Tipo**: `Tool`.
- **Recursos**: chi-quadrado de Westfeld-Pfitzmann, RS Analysis de Fridrich, Sample Pair Analysis de Dumitrescu, score consolidado de 0 a 100, histograma de LSBs e laudo em texto com métricas brutas.

### `crypto.rsa_attack` — Ataques a RSA Fraco
- **Tipo**: `Tool` com quatro abas.
- **Recursos**: Wiener por frações continuadas, fatoração de Fermat para primos próximos, módulo comum por Bézout e broadcast de Hastad com teorema chinês dos restos; teste de decriptação quando o ciphertext é informado.

### `crypto.classical_break` — Criptoanálise de Cifras Clássicas
- **Tipo**: `Tool`.
- **Recursos**: análise de frequência contra português/inglês, quebra de César com score de bigramas, Índice de Coincidência e Kasiski para Vigenère e substituição simples por hill-climbing.

### `network.packet_sniffer` — Analisador de Tráfego de Rede
- **Tipo**: `Tool`; requer Administrador e confirmação ética; depende de Npcap/Scapy.
- **Recursos**: escolha de interface e filtro BPF, `AsyncSniffer`, tabela em tempo real, dissecação TCP/UDP/ICMP/DNS/HTTP/TLS SNI, estatísticas por protocolo e top IPs, salvamento `.pcap`.

### `network.packet_crafter` — Forjador de Pacotes
- **Tipo**: `Tool`; requer Administrador e confirmação ética.
- **Recursos**: abas ICMP, TCP, UDP e DNS; flags, payload, envio e resposta com latência; trace route manual por TTL; histórico e exportação de log/pcap.

### `network.arp_poison` — Testador de ARP Spoofing
- **Tipo**: `Tool`; requer Administrador e termo ético.
- **Recursos**: descoberta de gateway e dispositivos da LAN, envenenamento bidirecional controlado, contadores, parada imediata e restauração das tabelas ARP em `try/finally`.

### `network.dns_spoof` — Simulador de DNS Spoofing
- **Tipo**: `Tool`; confirmação ética.
- **Recursos**: regras domínio para IP, interceptação de consultas UDP/53, resposta forjada e modo somente-log para auditoria de captive portals e DNS rebinding.

### `network.deauth_test` — Testador de Robustez WiFi
- **Tipo**: `Tool`; requer Administrador, placa em modo monitor e confirmação dupla.
- **Recursos**: varredura de redes, BSSID/canal/segurança, deauth limitado a um pacote por segundo, duração configurável, relatório e observação sobre a resistência de WPA3-SAE.

### `network.mitm_proxy` — Proxy Interceptador
- **Tipo**: `Tool`; confirmação ética.
- **Recursos**: proxy local em `127.0.0.1:8080`, CA de teste, fluxo de requisições/respostas, filtros, regras de rewrite, exportação HAR e modo HTTP nativo quando mitmproxy não está instalado.

### `web.dir_bruteforce` — Descobridor de Diretórios Web
- **Tipo**: `Tool`; confirmação ética.
- **Recursos**: wordlist interna extensa, wordlist externa, códigos de sucesso configuráveis, threads limitadas, atraso, filtro por tamanho, tabela colorida e exportação CSV/JSON.

### `web.subdomain_enum` — Enumerador de Subdomínios
- **Tipo**: `Tool`; confirmação ética.
- **Recursos**: wordlist interna, resolução concorrente A/AAAA, detecção de wildcard DNS, checagem HTTP opcional, exportação CSV e fallback sem dnspython.

### `web.vuln_scanner` — Scanner de Vulnerabilidades Web
- **Tipo**: `Tool`; confirmação ética e testes não destrutivos.
- **Recursos**: extração de formulários, SQLi error-based, XSS refletido, LFI, open redirect e cabeçalhos ausentes; relatório com severidade, evidência, correção e exportação Markdown/JSON.

### `web.jwt_toolkit` — Toolkit de Teste de JWT
- **Tipo**: `Tool`; confirmação ética.
- **Recursos**: `alg: none`, confusão HMAC/RSA, `kid` com path traversal e integração com quebra de segredo; token modificado em Base64URL colorido e teste contra endpoint próprio.

### `web.csrf_poc` — Gerador de PoC CSRF
- **Tipo**: `Tool`.
- **Recursos**: três variantes (auto-submit, fetch e imagem GET), preview HTML, comentário legal, cópia e salvamento `.html`.

### `forensics.memory_dump` — Extrator de Memória de Processo
- **Tipo**: `Tool`; requer Administrador e confirmação ética.
- **Recursos**: lista de processos, `ReadProcessMemory` por região de `VirtualQueryEx`, dump `.dmp` com log de regiões e classificação de strings (URL, IP, e-mail, registro e `Authorization`).

### `forensics.file_recovery` — Recuperador de Arquivos Deletados
- **Tipo**: `Tool`; leitura estritamente somente-leitura.
- **Recursos**: MFT NTFS via pytsk3 quando disponível, carving por assinaturas JPEG/PDF/ZIP/Office/MP4, preview de imagens, destino separado da origem e `recuperados.csv`.

### `forensics.registry_parser` — Analisador de Hives do Registro
- **Tipo**: `Tool`.
- **Recursos**: SAM (RID, usuário, hashes, último logon, flags), SYSTEM (serviços, drivers, USB, shutdown), SOFTWARE (instalados, versão, timezone) e NTUSER.DAT (RecentDocs, UserAssist, TypedPaths, MRU); árvore com busca e exportação.

### `forensics.browser_extract` — Extrator de Dados de Navegadores
- **Tipo**: `Tool`; confirmação ética e leitura sobre cópias.
- **Recursos**: Chrome, Edge, Brave, Opera, Vivaldi e Firefox; histórico, downloads, cookies DPAPI/AES-GCM, senhas salvas, autofill e bookmarks; abas, filtros e exportação JSON/CSV.

### `forensics.usb_history` — Histórico de Dispositivos USB
- **Tipo**: `Tool`.
- **Recursos**: `USBSTOR` e `USB`, correlação VID/PID, `Setupapi.dev.log`, primeira instalação, última inserção/remoção, dispositivos desconhecidos e CSV.

### `forensics.lnk_analyzer` — Analisador de Atalhos `.lnk`
- **Tipo**: `FileTool`; extensão `.lnk`.
- **Recursos**: parser MS-SHLLINK nativo com LnkParse3 opcional, caminho, argumentos, diretório de trabalho, timestamps, volume serial, hostname e MAC; CSV consolidado.

### `forensics.artifact_timeline` — Linha do Tempo de Artefatos
- **Tipo**: `Tool`.
- **Recursos**: Event Logs (logon, 4688, serviços, USB), Prefetch, AmCache e RecentDocs em uma única linha do tempo com filtros por período/fonte e exportação CSV/XLSX.

### `osint.username_enum` — Enumeração de Username
- **Tipo**: `Tool`; aviso de responsabilidade e LGPD.
- **Recursos**: base interna de mais de cem sites, consultas concorrentes, marcadores de ausência por site, status Encontrado/Não encontrado/Erro, abertura no navegador e CSV/JSON.

### `osint.domain_intel` — Inteligência de Domínio
- **Tipo**: `Tool`.
- **Recursos**: WHOIS via protocolo nativo, DNS A/AAAA/MX/TXT/NS/SOA/CAA, SSL/TLS, tecnologias por headers/HTML, Google Dorks prontos e relatório Markdown.

### `osint.email_breach` — Verificador de E-mail em Vazamentos
- **Tipo**: `Tool`; aviso de privacidade e LGPD.
- **Recursos**: HIBP v3 com token via `get_api_token("hibp")`, consulta individual ou em lote, classes de dados expostos, score de risco e exportação JSON.

### `osint.metadata_extract` — Extrator de Metadados
- **Tipo**: `FileTool`; imagens, PDF, Office OpenXML e mídia.
- **Recursos**: EXIF/XMP/IPTC, autor e empresa em PDF/OOXML, ID3/MP4, GPS com link de mapa, detecção de metadados reveladores e exportação JSON/CSV.

### `rev.pe_analyzer` — Analisador de Executáveis PE
- **Tipo**: `Tool`.
- **Recursos**: machine, timestamp, entrypoint, image base, subsystem, seções com entropia e flags, imports por categoria, exports, recursos, compilador provável, packers e assinatura Authenticode.

### `rev.strings_extract` — Extrator de Strings
- **Tipo**: `FileTool`; qualquer binário.
- **Recursos**: ASCII e UTF-16LE, comprimento mínimo ajustável, classificação de URL/IP/e-mail/caminho/registro/hash/JWT/chave de API/Base64, filtros e exportação TXT/CSV/JSON.

### `rev.disassembler` — Desassemblador Multi-Arquitetura
- **Tipo**: `Tool`.
- **Recursos**: x86, x86-64, ARM, ARM64 e MIPS via Capstone, sintaxe Intel/AT&T, navegação por offset, bytes brutos, xrefs para `call`/`jmp`, assembler Keystone opcional e exportação ASM.

### `rev.js_deobfuscator` — Desofuscador JavaScript
- **Tipo**: `Tool`.
- **Recursos**: pretty-print, unescape `\xNN`/`\uNNNN`, resolução de `String.fromCharCode`, `eval` literal, renomeação `_0x...`, remoção simples de dead code, diff antes/depois e análise de risco.

### `rev.pyc_decompiler` — Decompilador de Bytecode Python
- **Tipo**: `FileTool`; extensão `.pyc`.
- **Recursos**: magic number, escolha entre decompyle3/uncompyle6/pycdc, fallback com `dis`, exportação `.py` e log de avisos.

### `system.persistence_scan` — Scanner de Persistência
- **Tipo**: `Tool`.
- **Recursos**: Run/RunOnce, serviços, tarefas agendadas, WMI subscriptions, Startup, AppInit_DLLs, Winlogon e IFEO; hash SHA-256, assinatura, alertas de path suspeito, typosquatting, JSON/CSV e atalhos para Regedit/Explorer.

### `system.rootkit_detect` — Detector de Rootkit
- **Tipo**: `Tool`; requer Administrador.
- **Recursos**: comparação psutil/NtQuerySystemInformation, portas LISTEN sem dono, drivers não assinados, integridade de `winlogon`/`lsass` e relatório somente-diagnóstico.

### `system.keylogger_detect` — Detector de Keylogger
- **Tipo**: `Tool`.
- **Recursos**: DLLs e hooks suspeitos, filtros de teclado, logs em TEMP/APPDATA, heurística de `GetAsyncKeyState` e recomendações; não instala nem remove nada.

### `system.credential_audit` — Auditoria de Credenciais Locais
- **Tipo**: `Tool`; confirmação ética e exportação apenas de metadados.
- **Recursos**: Credential Manager do perfil atual, tipos e persistência, análise de força/reutilização, revelação de plaintext somente com confirmação explícita e HIBP k-anonimato opcional.

### `system.defender_audit` — Auditoria do Windows Defender
- **Tipo**: `Tool`.
- **Recursos**: status em tempo real, versões de engine/assinaturas, datas de varredura, exclusões, regras ASR, proteção de nuvem/PUA/tamper, recomendações e relatório de conformidade.

### `system.firewall_audit` — Auditoria do Firewall
- **Tipo**: `Tool`.
- **Recursos**: três perfis, regras `Any` para `Any` em portas sensíveis, aplicações sem assinatura, portas em LISTEN sem regra explícita, status do serviço, CSV e comparação com baseline.

### `system.dns_leak_test` — Teste de Vazamento de DNS
- **Tipo**: `Tool`.
- **Recursos**: descoberta do resolver real e IP público, detecção de VPN vazando DNS, DNS de ISP, inconsistências entre resolvedores e recomendações de configuração.

### `system.webrtc_leak` — Detector de Vazamento WebRTC
- **Tipo**: `Tool`.
- **Recursos**: navegador headless com Playwright quando disponível, coleta de ICE candidates, IPs locais/públicos expostos, comparação com IP real e instruções por navegador; modo manual sem Playwright.










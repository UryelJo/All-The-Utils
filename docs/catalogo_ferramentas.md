# All the Utils — Catálogo Completo de Ferramentas Implementadas

Este documento mantém o inventário detalhado de todas as ferramentas disponíveis no All the Utils, seus identificadores, parâmetros e recursos, servindo de referência para desenvolvimento e futuros prompts.

---

## 1. Imagens e Mídia (`tools/images/`)

### `images.convert` — Conversão e Otimização de Imagens
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.ico`, `.heic`, `.heif`, `.avif`
- **Formatos de Saída**: PNG, JPEG, WEBP, BMP, TIFF, ICO
- **Recursos**:
  - Seleção de arquivos avulsos ou pastas inteiras com detecção recursiva.
  - Controle de qualidade (1-100%).
  - Manutenção de metadados EXIF opcional.
  - Redimensionamento proporcional (largura/altura máxima).
  - Remoção opcional de transparência com fundo branco sólido.
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
  - **Aba Remoção em Lote**: Anonimização total (remoção de todos os metadados), remoção seletiva de GPS, ou renomeação automática de fotos pelo padrão `AAAA-MM-DD_HH-MM-SS` da data de captura.

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
  - Renderização instantânea do QR Code na tela, botão para copiar código Copia e Cola e botão para salvar a imagem do QR Code em PNG.

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
  - Seletor de data e hora com calendário para gerar Epoch.
  - Conversor sincronizado de bases numéricas: Binário (base 2), Octal (base 8), Decimal (base 10) e Hexadecimal (base 16).

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
  - Converte fotos, capturas e digitalizações em lote para um único documento PDF compilado.
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
- **Extensões Suportadas**: `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.mp3`, `.wav`, `.aac`, `.flac`, `.ogg`, `.m4a`, `.wma`
- **Formatos de Saída**: MP4, MKV, WEBM, AVI, MOV, GIF, MP3, WAV, AAC, FLAC, OGG, M4A
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
- **Extensões Suportadas**: `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`
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
  - Suporte a múltiplos formatos de áudio e vídeo (.mp4, .mkv, .mp3, .wav, .flac, .m4a, .aac, .ogg).

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

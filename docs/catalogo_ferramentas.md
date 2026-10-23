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





# WinToolbox — Catálogo Completo de Ferramentas Implementadas

Este documento mantém o inventário detalhado de todas as ferramentas disponíveis no WinToolbox, seus identificadores, parâmetros e recursos, servindo de referência para desenvolvimento e futuros prompts.

---

## 1. Imagens e Mídia (`tools/images/`)

### `images.convert` — Conversão e Otimização de Imagens
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.ico`
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
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.ico`
- **Recursos**:
  - 4 Modos de dimensionamento: Porcentagem (1-1000%), Largura Máxima, Altura Máxima e Caixa Exata (Largura x Altura).
  - Modos de Encaixe: Ajustar com Barras (Fit), Preencher e Cortar (Fill / Crop) e Distorcer (Stretch).
  - Filtros de Interpolação: Lanczos (alta fidelidade), Bicúbica, Bilinear e Vizinho Mais Próximo.
  - Rotação: 90° horário, 180°, 270° ou Orientação Automática EXIF (`ImageOps.exif_transpose`).
  - Espelhamento Horizontal e Vertical independentes.

### `images.compress` — Otimizador e Compressor de Imagens
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`
- **Recursos**:
  - Modos de Compressão: "Qualidade Visual Balanceada" (slider 10-100%), "Otimização Sem Perdas (Lossless)" e "Meta de Tamanho Máximo em KB" (busca binária de convergência de tamanho).
  - Quantização de paleta para PNG (redução para 256 cores adaptativas).
  - Remoção opcional de metadados EXIF para economia máxima de bytes.
  - Suporte a JPEG progressivo e compressão otimizada de tabelas Huffman.

### `images.watermark` — Aplicador de Marca d'Água em Lote
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`
- **Recursos**:
  - Marca de Texto: conteúdo customizado, tamanho de fonte, cor HEX com seletor visual, rotação (-90° a +90°) e suporte a fontes TrueType do sistema.
  - Marca de Imagem: seleção de logo PNG transparente com escala ajustável (% da imagem base).
  - Posição: 9 âncoras (inferior, superior, centro) ou "Mosaico Repetido (Tiled)" sobre toda a área da foto.
  - Opacidade (5% a 100%) e controle de margem/padding das bordas em pixels.

### `images.effects` — Filtros e Ajustes de Imagem
- **Tipo**: `FileTool` (Processamento em Lote Automatizado)
- **Extensões Suportadas**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`
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
  - Utiliza `speedtest-cli` com fallback automático via CDN estável para garantir resiliência.

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
  - Botão "Encerrar Processo" com confirmação para liberar o arquivo travado.

---

## 8. Compactação e Arquivos Comprimidos (`tools/archive/`)

### `archive.manager` — Compactador e Extrator de Arquivos
- **Tipo**: `Tool`
- **Formatos Suportados**: ZIP (compressão deflate), TAR e TAR.GZ (`.tar.gz`, `.tgz`).
- **Recursos**:
  - **Aba Compactar**: Adição de arquivos e diretórios inteiros, seleção de formato e barra de progresso durante o empacotamento.
  - **Aba Inspecionar**: Listagem de todo o conteúdo interno do arquivo compactado (nome relativo, tamanho real e tamanho comprimido) sem necessidade de descompactar.
  - **Aba Extrair**: Extração completa com filtro de proteção contra traversals maliciosos de diretório (`filter='data'`) e relatório de progresso.



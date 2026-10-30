# All the Utils — Especificação Técnica: Ferramentas de Segurança, Forense, OSINT e Reverse Engineering

**Versão**: 1.0  
**Propósito**: Documento de especificação técnica para implementação autônoma por agentes de IA (Gemini, Claude, GPT) no repositório **All the Utils**.  
**Público-alvo**: Agentes de IA que irão gerar código Python seguindo o padrão arquitetural do projeto.

---

## 0. Regras Globais de Implementação (não negociáveis)

Qualquer ferramenta descrita neste documento **DEVE** obedecer às regras abaixo, extraídas do `contexto_para_prompts.md`:

1. **Idioma**: UI, comentários, docstrings e logs em **Português do Brasil (pt-BR)**. Identificadores de código (variáveis, classes, funções) em inglês ou português, conforme padrão do projeto.
2. **Proibido emojis** em strings visíveis na UI. Texto puro.
3. **Thread-safety**: nunca manipular widgets Qt fora da thread principal. Toda operação longa (rede, disco, subprocesso, criptografia) **deve** usar `TaskRunner` de `wintoolbox.core.tasks`.
4. **Lazy loading**: importar bibliotecas pesadas (`scapy`, `capstone`, `pytsk3`, `decompyle3`, `selenium`) **dentro** do método que as utiliza, nunca no topo do módulo.
5. **Tokens de API**: usar `get_api_token("nome_servico")` de `wintoolbox.core.settings`. Nunca hardcodar chaves.
6. **Registro**: toda ferramenta usa o decorator `@register` e herda de `Tool` ou `FileTool` de `wintoolbox.core.registry`.
7. **Privilégios**: ferramentas que exigem admin verificam via `ctypes.windll.shell32.IsUserAnAdmin()` no `__init__` e exibem aviso com botão "Reiniciar como Administrador" (reutilizar o padrão existente do `system.tools`).
8. **Aviso ético obrigatório**: ferramentas marcadas com ⚠️ neste documento **devem** exibir um `QMessageBox` de confirmação com termo de responsabilidade antes da primeira execução.
9. **Gravação atômica**: ferramentas `FileTool` usam o motor de lote central (`wintoolbox.core.batch`), que já gerencia `.tmp_wtbx`, cancelamento e progresso.
10. **Fallback gracioso**: se uma dependência opcional (ex: `hashcat.exe`, `tshark.exe`) não estiver instalada, a ferramenta **deve** detectar e oferecer o modo alternativo nativo em Python.

---

## 1. Dependências — Instalação em Lote

Adicionar ao `requirements.txt` (ou a um `requirements-security.txt` opcional, carregado sob demanda):

```txt
# Criptografia e hashing
pycryptodome>=3.20.0
cryptography>=42.0.0
pyjwt>=2.8.0
gmpy2>=2.1.5
sympy>=1.12

# Rede e pacotes
scapy>=2.5.0
dnspython>=2.6.0
aiohttp>=3.9.0
pyshark>=0.6.0
mitmproxy>=10.2.0

# Forense
pytsk3>=20230125
regipy>=3.1.0
python-registry>=1.3.1
LnkParse3>=1.4.0
hachoir>=3.3.0
exifread>=3.0.0
python-magic>=0.4.27

# Reverse Engineering
pefile>=2023.2.7
capstone>=5.0.1
keystone-engine>=0.9.2
decompyle3>=3.9.0

# Web / OSINT
beautifulsoup4>=4.12.0
jsbeautifier>=1.15.0

# Esteganografia
stegano>=0.11.3
soundfile>=0.12.1
numpy>=1.26.0
scipy>=1.12.0

# Utilitários
python-docx>=1.1.0
openpyxl>=3.1.2
pypdf>=4.2.0
```

Bibliotecas **já presentes** no projeto que serão reutilizadas: `Pillow`, `psutil`, `requests`, `pandas`, `sqlite3`, `hashlib`, `subprocess`, `ctypes`, `pywin32`.

---

## 2. Ferramentas — Especificação Completa

### Categoria: `security` (Ofensiva/Auditoria)

---

#### 2.1 `security.hash_identify` — Identificador Universal de Hash

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `security.hash_identify` |
| **Nome** | Identificador de Tipo de Hash |
| **Categoria** | Segurança |
| **Keywords** | `hash`, `md5`, `sha`, `bcrypt`, `identificar`, `forense` |
| **Dependências** | Nativas apenas (`re`) |

**Funcionalidades**:
- Campo de entrada de texto para o hash (aceita com ou sem prefixo `$...$`).
- Tabela heurística interna com **~30 assinaturas regex** cobrindo: MD5, SHA-1, SHA-224, SHA-256, SHA-384, SHA-512, SHA3-*, NTLM, LM, MySQL 3/4/5, bcrypt (`$2a$`, `$2b$`, `$2y$`), argon2 (`$argon2i$`, `$argon2id$`), scrypt, Django (`pbkdf2_sha256$`), Laravel (`$2y$`), WordPress (`$P$`, `$H$`), Joomla, Drupal, RIPEMD-160, CRC32, Base64 de hash.
- Para cada candidato: nome do algoritmo, comprimento esperado, nível de confiança (Alto/Médio/Baixo), exemplo de string, link pra hashcat mode (`-m 1000` etc.).
- Botão "Analisar" + campo de análise em tempo real (debounce 300ms).
- Rodapé com dica: "Se nenhum candidato bater, o hash pode estar truncado ou usar salt customizado".

**Skeleton**:
```python
@register
class HashIdentifierTool(Tool):
    id = "security.hash_identify"
    name = "Identificador de Tipo de Hash"
    category = "Segurança"
    description = "Detecta o algoritmo provável de um hash por análise de formato."
    keywords = ["hash", "md5", "sha", "bcrypt", "identificar"]

    def build_view(self, parent=None):
        return HashIdentifierView(self, parent)
```

---

#### 2.2 `security.hash_cracker` — Quebrador de Hashes com Wordlist ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `security.hash_cracker` |
| **Nome** | Quebrador de Hashes (Wordlist e Brute Force) |
| **Categoria** | Segurança |
| **Keywords** | `cracker`, `wordlist`, `bruteforce`, `hashcat`, `john` |
| **Dependências** | `hashlib`, `subprocess` (opcional: hashcat/john) |

**Aviso ético**: exibir `QMessageBox` com texto: *"Esta ferramenta deve ser usada apenas em hashes dos quais você é o proprietário legítimo ou tem autorização expressa por escrito. Uso contra sistemas de terceiros é crime previsto na Lei 12.737/2012."* Botões: "Entendo e concordo" / "Cancelar".

**Funcionalidades**:
- **Modo Wordlist**: campo de hash alvo + seleção de arquivo wordlist (`.txt`), com fallback embutido de 100 senhas mais comuns do mundo.
- **Modo Brute Force**: charset (a-z, A-Z, 0-9, símbolos) + comprimento mínimo/máximo.
- **Detecção automática** do tipo de hash (integração com `security.hash_identify`).
- **Modo GPU** (opcional): se `hashcat.exe` estiver no PATH, oferece checkbox "Usar Hashcat (GPU)"; caso contrário, usa `hashlib` nativo em CPU.
- Barra de progresso com `TaskRunner`, contador de tentativas/segundo, ETA, botão Cancelar.
- Painel de log em tempo real (`LogPanelWidget`).
- Exibe senha encontrada em destaque + botão copiar.
- Modo "benchmark": mede hashes/s da máquina sem alvo.

---

#### 2.3 `security.rainbow_generator` — Gerador de Rainbow Tables

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `security.rainbow_generator` |
| **Nome** | Gerador de Rainbow Table |
| **Categoria** | Segurança |
| **Keywords** | `rainbow`, `tabela`, `pre-computado`, `hash` |
| **Dependências** | `hashlib`, `sqlite3` |

**Funcionalidades**:
- Configuração: algoritmo (MD5/SHA1/SHA256), charset, comprimento (1-8), arquivo de saída `.db` (SQLite).
- Geração em lote com `TaskRunner`; barra de progresso com contagem total de combinações.
- Esquema SQLite: `CREATE TABLE hashes (hash TEXT PRIMARY KEY, plain TEXT); CREATE INDEX idx_hash ON hashes(hash);`
- Aba de **consulta**: insere hash e retorna plaintext via SELECT indexado (consulta instantânea).
- Estimativa de tamanho de tabela antes de gerar (aviso se > 1GB).
- Botão para cancelar e salvar parcialmente.

---

#### 2.4 `security.jwt_secret_cracker` — Quebra de Segredo JWT

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `security.jwt_secret_cracker` |
| **Nome** | Quebrador de Segredo JWT (HMAC) |
| **Categoria** | Segurança |
| **Keywords** | `jwt`, `secret`, `hmac`, `crack` |
| **Dependências** | `pyjwt`, `hashlib` |

**Funcionalidades**:
- Campo para colar JWT completo (3 partes separadas por `.`).
- Extrai algoritmo do header (`HS256`/`HS384`/`HS512`).
- Modo dicionário: arquivo de wordlist ou lista inline.
- Modo brute force: charset + comprimento.
- Para cada tentativa: `hmac.compare_digest(signature_calculada, signature_do_token)`.
- Exibe segredo encontrado + botão "Gerar novo JWT com segredo" (para validar).
- Aviso visual se o token estiver expirado (`exp`).
- Integração com `TaskRunner` para evitar travar UI.

---

### Categoria: `crypto` (Esteganografia e Criptoanálise)

---

#### 2.5 `crypto.stegano` — Esteganografia em Imagem/Áudio

| Campo | Valor |
|---|---|
| **Tipo** | `FileTool` |
| **ID** | `crypto.stegano` |
| **Nome** | Esteganografia (Ocultar e Extrair) |
| **Categoria** | Criptografia |
| **Keywords** | `stegano`, `lsb`, `ocultar`, `imagem`, `áudio` |
| **Extensões Suportadas** | `.png`, `.bmp`, `.wav` |
| **Dependências** | `stegano`, `Pillow`, `numpy`, `soundfile` |
| **Aba** | Painel com 2 abas: Ocultar / Extrair |

**Funcionalidades — Aba Ocultar**:
- Seleção de arquivo portador (imagem PNG/BMP ou áudio WAV).
- Campo de mensagem de texto **ou** seleção de arquivo a ocultar (bytes).
- Método: LSB em pixels RGB (imagem) ou LSB em samples (áudio), com opção de senha (XOR dos bits via `hashlib.sha256(senha)`).
- Mostra capacidade máxima do portador em bytes e alerta se a mensagem exceder.

**Funcionalidades — Aba Extrair**:
- Detecta automaticamente se o arquivo tem payload LSB.
- Extrai mensagem ou arquivo oculto; se protegido por senha, exige a mesma.
- Mostra tipo do conteúdo extraído (texto/arquivo) com preview.

**Skeleton**:
```python
@register
class SteganoTool(FileTool):
    id = "crypto.stegano"
    name = "Esteganografia (Ocultar e Extrair)"
    category = "Criptografia"
    description = "Oculta dados dentro de imagens/áudio via LSB e extrai payloads existentes."
    keywords = ["stegano", "lsb", "ocultar"]
    supported_extensions = [".png", ".bmp", ".wav"]
    output_formats = ["PNG", "BMP", "WAV"]
    default_output_format = "PNG"

    def build_options_widget(self, parent=None):
        return SteganoOptionsWidget(parent)

    def process_file(self, src, dst, options):
        from stegano import lsb  # lazy
        ...
```

---

#### 2.6 `crypto.stegano_detect` — Detector de Esteganografia

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `crypto.stegano_detect` |
| **Nome** | Detector de Esteganografia |
| **Categoria** | Criptografia |
| **Keywords** | `stegano`, `detector`, `chi-square`, `rs-analysis` |
| **Dependências** | `Pillow`, `numpy`, `scipy` |

**Funcionalidades**:
- Seleção de imagem; executa **3 análises**:
  1. **Chi-quadrado** (Westfeld-Pfitzmann): mede desvio da distribuição esperada de LSBs; retorna p-value.
  2. **RS Analysis** (Fridrich): estima taxa de embedding em imagens coloridas.
  3. **Sample Pair Analysis** (Dumitrescu): análise de pares adjacentes.
- Dashboard com 3 barras de probabilidade ("Baixa / Média / Alta") + score consolidado (0-100).
- Preview da imagem + histograma de LSBs.
- Exportação de laudo em `.txt` com os valores brutos das métricas.

---

#### 2.7 `crypto.rsa_attack` — Ataques a RSA Fraco

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `crypto.rsa_attack` |
| **Nome** | Ataques a RSA Fraco (CTF) |
| **Categoria** | Criptografia |
| **Keywords** | `rsa`, `wiener`, `fermat`, `ctf`, `fatoração` |
| **Dependências** | `sympy`, `gmpy2`, `pycryptodome` |
| **Aba** | Painel com 4 abas de ataque |

**Funcionalidades — Ataque 1: Wiener (d pequeno)**  
- Inputs: `n`, `e`.  
- Detecta se `d < N^0.25 / 3` via expansão em fração contínua de `e/n`.  
- Retorna `d`, `p`, `q` e testa decriptação se ciphertext fornecido.

**Funcionalidades — Ataque 2: Fatoração de Fermat (p≈q)**  
- Inputs: `n`, limite de iterações.  
- Algoritmo: `a = ceil(sqrt(n))`, `b² = a² - n`, iterar até quadrado perfeito.  
- Retorna `p`, `q`, `d`.

**Funcionalidades — Ataque 3: Módulo Comum**  
- Inputs: `(n, e1, c1)` e `(n, e2, c2)`.  
- Usa `pow(e1, -1, e2)` (Bézout) para recuperar `m` sem fatorar.

**Funcionalidades — Ataque 4: Hastad Broadcast**  
- Inputs: lista de `(n_i, c_i)` com mesmo `e=3`.  
- Teorema Chinês dos Restos via `sympy.ntheory.modular.crt`, `m = c^(1/e)` exato.

---

#### 2.8 `crypto.classical_break` — Quebra de Cifras Clássicas

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `crypto.classical_break` |
| **Nome** | Criptoanálise de Cifras Clássicas |
| **Categoria** | Criptografia |
| **Keywords** | `césar`, `vigenère`, `frequência`, `kasiski` |
| **Dependências** | Nativas (`collections`, `itertools`) |

**Funcionalidades**:
- **Análise de Frequência**: histograma das letras do texto cifrado comparado com frequência do português/inglês.
- **Quebra de César**: testa 25 deslocamentos, ranqueia por "score de português" (bigramas comuns).
- **Quebra de Vigenère**: calcula Índice de Coincidência (IC) para detectar tamanho da chave; aplica Kasiski; quebra por coluna usando frequência.
- **Substituição Simples**: hill-climbing com bigramas PT-BR.
- Score de "qualidade" para cada candidato (probabilidade de ser texto legível).
- Botão copiar resultado + botão "Testar todas as cifras".

---

### Categoria: `network` (Ofensiva/Diagnóstico)

---

#### 2.9 `network.packet_sniffer` — Sniffer de Pacotes ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `network.packet_sniffer` |
| **Nome** | Analisador de Tráfego de Rede |
| **Categoria** | Rede |
| **Keywords** | `sniffer`, `pcap`, `scapy`, `tráfego` |
| **Dependências** | `scapy`, `pyshark` (opcional) |
| **Requer Admin** | Sim (WinPcap/Npcap obrigatório) |

**Aviso ético**: confirmação explícita + aviso: *"Capturar tráfego de rede de terceiros sem autorização é crime. Use apenas em redes das quais você é o administrador ou tem autorização por escrito."*

**Funcionalidades**:
- Seleção de interface (`scapy.get_if_list()`).
- Filtro BPF customizável (`tcp port 80`, `udp`, `host 192.168.1.1`).
- Captura em tempo real com `AsyncSniffer` do scapy; exibição em `DataTableView` com colunas: Timestamp, Origem, Destino, Protocolo, Tamanho, Info.
- Dissecação de protocolos: TCP, UDP, ICMP, DNS (query/response), HTTP (requests/responses), TLS SNI.
- Botão "Parar captura" + "Salvar como .pcap" (compatível com Wireshark).
- Painel lateral de estatísticas ao vivo (contagem por protocolo, top 5 IPs).
- Aviso automático se Npcap não estiver instalado, com link de download.

---

#### 2.10 `network.packet_crafter` — Forjador de Pacotes ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `network.packet_crafter` |
| **Nome** | Forjador de Pacotes (Scapy) |
| **Categoria** | Rede |
| **Keywords** | `scapy`, `craft`, `icmp`, `tcp`, `udp` |
| **Dependências** | `scapy` |
| **Requer Admin** | Sim |

**Funcionalidades**:
- Painel com 4 abas: ICMP / TCP / UDP / DNS.
- **ICMP**: define destino, tipo (echo request/reply), payload; envia e exibe resposta.
- **TCP**: src/dst port, flags (SYN/ACK/RST/FIN/PSH/URG), seq, ack, payload.
- **UDP**: src/dst port, payload.
- **DNS**: query name, tipo (A/AAAA/MX/TXT/NS), server destino.
- Histórico de pacotes enviados com resposta e latência.
- Modo "Trace route manual" (envia ICMP com TTL incremental).
- Exportação do log de pacotes em `.txt`/`.pcap`.

---

#### 2.11 `network.arp_poison` — ARP Spoofer (MITM Testing) ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `network.arp_poison` |
| **Nome** | Testador de ARP Spoofing |
| **Categoria** | Rede |
| **Keywords** | `arp`, `mitm`, `poison`, `spoof` |
| **Dependências** | `scapy` |
| **Requer Admin** | Sim |

**Aviso ético**: termo extenso obrigatório. Só deve funcionar se o usuário confirmar.

**Funcionalidades**:
- Detecta gateway padrão automaticamente (via `scapy.getmacbyip` ou `psutil`).
- Lista dispositivos na LAN (ARP scan rápido).
- Seleção: alvo + gateway; envia `ARP(is-at=...)` bidirecional por N segundos.
- **Restauração automática** das tabelas ARP no final (crítico: `try/finally`).
- Contador de pacotes interceptados + taxa bps.
- Botão "Parar e restaurar" com efeito imediato.

---

#### 2.12 `network.dns_spoof` — DNS Spoofer ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `network.dns_spoof` |
| **Nome** | Simulador de DNS Spoofing |
| **Categoria** | Rede |
| **Keywords** | `dns`, `spoof`, `rebinding`, `captive-portal` |
| **Dependências** | `scapy`, `dnslib` |

**Funcionalidades**:
- Regras: domínio → IP forjado (tabela editável).
- Intercepta queries DNS na interface local via `scapy.sniff(filter="udp port 53")`.
- Envia resposta forjada correspondente.
- Modo "Log-only": detecta e mostra tentativas de resolução sem modificar.
- Útil para testar captive portals, proteção DNS rebinding em apps.

---

#### 2.13 `network.deauth_test` — Testador de Deauth WiFi ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `network.deauth_test` |
| **Nome** | Testador de Robustez WiFi (Deauth) |
| **Categoria** | Rede |
| **Keywords** | `wifi`, `deauth`, `wpa`, `802.11` |
| **Dependências** | `scapy`, `pywifi` |
| **Requer Admin** | Sim + placa em modo monitor |

**Aviso ético**: duplo (leia-se: termo + checkbox "Confirmo que sou dono desta rede").

**Funcionalidades**:
- Lista redes vizinhas (`pywifi.scan()`).
- Identifica BSSID, canal, tipo de segurança (WPA2/WPA3).
- Envia `RadioTap/Dot11/Deauth` para um cliente específico ou broadcast — **apenas 1 por segundo** para não saturar.
- Duração configurável (1-60 segundos).
- Relatório final: quantos deauths foram enviados, taxa de reconexão dos clientes detectada.
- Aviso: WPA3-SAE é resistente a este ataque por design (útil para validar migração).

---

#### 2.14 `network.mitm_proxy` — Proxy MITM Local ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `network.mitm_proxy` |
| **Nome** | Proxy Interceptador (MITM) |
| **Categoria** | Rede |
| **Keywords** | `mitm`, `proxy`, `intercept`, `https` |
| **Dependências** | `mitmproxy`, `cryptography` |

**Funcionalidades**:
- Sobe proxy HTTP/HTTPS em `127.0.0.1:8080`.
- Gera CA própria (`mitmproxy`) e oferece download do `.crt` (para instalar no celular/VM de teste).
- Painel em tempo real com requests/responses (método, host, path, status, tamanho).
- Filtro por host/método/status.
- Editor de request/response para replay manual.
- Exportação em `.har` (compatível com Chrome DevTools).
- Regras de **rewrite** (ex: substituir `User-Agent`, modificar body JSON por regex).

---

### Categoria: `web` (Ofensiva Web)

---

#### 2.15 `web.dir_bruteforce` — Directory Brute Forcer

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `web.dir_bruteforce` |
| **Nome** | Descobridor de Diretórios Web |
| **Categoria** | Web |
| **Keywords** | `dirb`, `gobuster`, `wordlist`, `bruteforce` |
| **Dependências** | `requests`, `concurrent.futures` |

**Funcionalidades**:
- URL alvo + wordlist (interna com ~5.000 paths comuns: `/admin`, `/backup.zip`, `/.git/config`, `/.env`, `/phpinfo.php`, `/robots.txt`, etc.).
- Wordlist customizável (upload `.txt`).
- Códigos de sucesso configuráveis (200, 301, 302, 403 por padrão).
- Threads (1-50) com `ThreadPoolExecutor`.
- Delay configurável entre requests para evitar rate-limit.
- Filtro de tamanho de resposta (ignorar páginas 404 com tamanho X).
- Follow de redirects opcional.
- Tabela em tempo real com status colorido + exportação de resultados.
- Aviso ético obrigatório (target deve ser próprio).

---

#### 2.16 `web.subdomain_enum` — Enumerador de Subdomínios

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `web.subdomain_enum` |
| **Nome** | Enumerador de Subdomínios |
| **Categoria** | Web |
| **Keywords** | `subdomain`, `dns`, `recon`, `osint` |
| **Dependências** | `dnspython`, `requests` |

**Funcionalidades**:
- Domínio alvo + wordlist interna (500 subdomínios comuns).
- Consulta paralela `dns.resolver.resolve(f"{sub}.{dominio}", "A")`.
- Detecção de wildcard DNS (testa subdomínio random e ignora IPs iguais ao wildcard).
- Marca vivos por cor (verde = A record válido; amarelo = CNAME sem A; cinza = sem resposta).
- Botão "Checar HTTP" (testa porta 80/443 e mostra status + título da página).
- Exportação CSV.

---

#### 2.17 `web.vuln_scanner` — Scanner Básico de Vulnerabilidades

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `web.vuln_scanner` |
| **Nome** | Scanner de Vulnerabilidades Web |
| **Categoria** | Web |
| **Keywords** | `sqli`, `xss`, `lfi`, `scanner` |
| **Dependências** | `requests`, `beautifulsoup4` |

**Funcionalidades**:
- URL alvo + extração de `<form>` via BeautifulSoup.
- **Testes ativos**:
  - **SQLi (error-based)**: injeta `'`, `"`, `\` em campos; detecta padrões de erro do MySQL/Postgres/MSSQL/SQLite na resposta.
  - **XSS refletido**: injeta `<script>alert(1)</script>` e variações; detecta reflexão literal.
  - **LFI**: tenta `../../etc/passwd`, `..\..\windows\win.ini`, `php://filter/convert.base64-encode/resource=index`.
  - **Open Redirect**: parâmetros `url`, `redirect`, `next`, `return` → verifica se HTTP 302 vai para domínio externo.
  - **Headers ausentes**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options (reaproveita `security.http_headers`).
- Relatório com severidade (CRÍTICA/ALTA/MÉDIA/BAIXA), evidência e sugestão de correção.
- Exportação Markdown/JSON.

---

#### 2.18 `web.jwt_toolkit` — Toolkit JWT Ofensivo

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `web.jwt_toolkit` |
| **Nome** | Toolkit de Teste de JWT |
| **Categoria** | Web |
| **Keywords** | `jwt`, `alg-none`, `kid`, `hmac-confusion` |
| **Dependências** | `pyjwt`, `cryptography` |

**Funcionalidades** (4 ataques clássicos):
1. **`alg: none`**: substitui header para `{"alg":"none"}` e remove assinatura; testa se backend aceita.
2. **HMAC↔RSA Confusion**: pega chave pública RSA como se fosse secreta HMAC; reassina com HS256.
3. **`kid` Path Traversal**: altera `kid` para `/dev/null` ou `/../../etc/passwd` (blob vazio = chave vazia).
4. **Secret Brute Force**: ver `security.jwt_secret_cracker` (integração).

- Campo de token + endpoint de teste (envia e compara com resposta original).
- Exibe o token modificado em Base64URL colorido (header.payload.signature).

---

#### 2.19 `web.csrf_poc` — Gerador de PoC CSRF

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `web.csrf_poc` |
| **Nome** | Gerador de PoC CSRF |
| **Categoria** | Web |
| **Keywords** | `csrf`, `poc`, `html`, `form` |
| **Dependências** | `jinja2` |

**Funcionalidades**:
- Inputs: URL do endpoint, método (POST/GET), pares de campo/valor do form.
- Gera 3 variantes: **auto-submit HTML**, **fetch JavaScript**, **img GET**.
- Preview renderizado no `QTextBrowser`.
- Botão "Salvar .html" e "Copiar HTML".
- Comentário no HTML: *"PoC gerado para testar a proteção CSRF do próprio sistema. Uso contra terceiros = crime."*

---

### Categoria: `forensics` (Nova)

---

#### 2.20 `forensics.memory_dump` — Dump de Memória de Processo ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `forensics.memory_dump` |
| **Nome** | Extrator de Memória de Processo |
| **Categoria** | Forense |
| **Keywords** | `memory`, `dump`, `process`, `forense` |
| **Dependências** | `ctypes`, `psutil` |
| **Requer Admin** | Sim |

**Funcionalidades**:
- Lista processos (`psutil.process_iter`) com PID, nome, path, memória.
- Seleção de processo-alvo.
- Dump via `OpenProcess(PROCESS_VM_READ)` + `ReadProcessMemory` por região de `VirtualQueryEx`.
- Salva `.dmp` + log das regiões.
- **Análise integrada**: strings extraídas do dump classificadas por padrão (URL, IP, e-mail, chave de registro, possível senha se header `Authorization:`).

---

#### 2.21 `forensics.file_recovery` — Recuperador de Arquivos Deletados

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `forensics.file_recovery` |
| **Nome** | Recuperador de Arquivos Deletados |
| **Categoria** | Forense |
| **Keywords** | `recovery`, `carving`, `mft`, `undelete` |
| **Dependências** | `pytsk3`, `python-magic` |
| **Requer Admin** | Recomendado |

**Funcionalidades**:
- Seleção de unidade/partição NTFS.
- Modo 1: **MFT Scan** via `pytsk3` — lista entradas não alocadas com nome/tamanho/data originais.
- Modo 2: **Carving** por assinatura (JPEG `FF D8 FF`, PDF `%PDF`, ZIP `PK\x03\x04`, Office, MP4) — varre clusters não alocados.
- Preview de imagens recuperadas.
- Recuperação para pasta de destino com relatório (`recuperados.csv`).
- Barra de progresso com `TaskRunner`.

---

#### 2.22 `forensics.registry_parser` — Parser de Hives do Registro

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `forensics.registry_parser` |
| **Nome** | Analisador de Hives do Registro |
| **Categoria** | Forense |
| **Keywords** | `registry`, `sam`, `hive`, `offline` |
| **Dependências** | `regipy` |

**Funcionalidades**:
- Abre arquivos `.hive` do disco offline (`SAM`, `SYSTEM`, `SOFTWARE`, `SECURITY`, `NTUSER.DAT`, `UsrClass.dat`).
- **Análise SAM**: usuários locais (RID, username, hash NTLM/LM, último logon, flags de conta, expiração de senha).
- **Análise SYSTEM**: serviços instalados, drivers, USB history (integra com `forensics.usb_history`), últimos shutdowns.
- **Análise SOFTWARE**: softwares instalados (chaves `Uninstall`), versões do Windows, timezone.
- **Análise NTUSER.DAT**: RecentDocs, UserAssist (programas executados), TypedPaths, MRU lists.
- Navegação em árvore de chaves/valores com busca.
- Exportação JSON/CSV por seção.

---

#### 2.23 `forensics.browser_extract` — Extrator de Dados de Navegadores ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `forensics.browser_extract` |
| **Nome** | Extrator de Dados de Navegadores |
| **Categoria** | Forense |
| **Keywords** | `chrome`, `firefox`, `cookies`, `history`, `password` |
| **Dependências** | `sqlite3`, `pycryptodome`, `pywin32` |

**Aviso ético**: apenas dados do próprio usuário. Confirmação obrigatória.

**Funcionalidades**:
- Detecta perfis de Chrome, Edge, Brave, Opera, Vivaldi, Firefox.
- **History**: `urls` + `visits` (title, url, last_visit_time, visit_count).
- **Downloads**: `downloads` (url, path, start_time, total_bytes).
- **Cookies**: descriptografa via DPAPI (`win32crypt.CryptUnprotectData`) + AES-GCM com chave do `Local State`.
- **Senhas salvas**: `Login Data` (Chrome) e `logins.json`+`key4.db` (Firefox), com descriptografia DPAPI.
- **Autofill**: `Web Data`.
- **Bookmarks**: parse do `Bookmarks` JSON.
- Aba por tipo de dado + filtros + busca + exportação JSON/CSV.
- Aviso: usuário precisa **fechar o navegador** para evitar lock do SQLite (ou copiar o arquivo primeiro).

---

#### 2.24 `forensics.usb_history` — Histórico de Dispositivos USB

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `forensics.usb_history` |
| **Nome** | Histórico de Dispositivos USB |
| **Categoria** | Forense |
| **Keywords** | `usb`, `historico`, `device`, `forense` |
| **Dependências** | `pywin32`, `wmi` |

**Funcionalidades**:
- Lê `HKLM\SYSTEM\CurrentControlSet\Enum\USBSTOR` (todos os dispositivos já plugados).
- Correlaciona com `HKLM\SYSTEM\CurrentControlSet\Enum\USB` (VID/PID).
- Consulta `Setupapi.dev.log` para timestamps de inserção/remoção.
- Tabela: Nome do dispositivo, Vendor, Product, Serial, First Install, Last Insert, Last Removal.
- Detecção de "dispositivos desconhecidos" (nunca completamente configurados — indicativo de tentativa de conexão).
- Exportação CSV.

---

#### 2.25 `forensics.lnk_analyzer` — Analisador de Atalhos `.lnk`

| Campo | Valor |
|---|---|
| **Tipo** | `FileTool` |
| **ID** | `forensics.lnk_analyzer` |
| **Nome** | Analisador de Atalhos .lnk |
| **Categoria** | Forense |
| **Keywords** | `lnk`, `shortcut`, `atalho`, `forense` |
| **Extensões Suportadas** | `.lnk` |
| **Dependências** | `LnkParse3` |

**Funcionalidades**:
- Parse de cada `.lnk` na pasta selecionada.
- Extração: path original, args de linha de comando, working dir, ícone, **hostname e MAC** da máquina onde foi criado, volume serial, timestamps (criação, acesso, modificação do alvo).
- Mapa de "quem criou" (hostname) → útil para detectar arquivos vindos de pendrives.
- Exportação CSV.

---

#### 2.26 `forensics.artifact_timeline` — Timeline de Artefatos

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `forensics.artifact_timeline` |
| **Nome** | Linha do Tempo de Artefatos |
| **Categoria** | Forense |
| **Keywords** | `timeline`, `eventlog`, `prefetch`, `amcache` |
| **Dependências** | `pywin32`, `pandas` |

**Funcionalidades**:
- Coleta de múltiplas fontes:
  - Event Logs (`Get-WinEvent`) — logon/logoff, processos criados (4688), serviços, USB.
  - Prefetch (`C:\Windows\Prefetch\*.pf`) — execução de programas com timestamp.
  - AmCache (`Amcache.hve`) — programas executados.
  - RecentDocs do usuário.
- Junta tudo em uma única `DataFrame` ordenada por timestamp.
- Colunas: Timestamp, Fonte, Categoria, Descrição, Detalhe.
- Filtro por período e por fonte.
- Exportação CSV/XLSX.

---

### Categoria: `osint` (Nova)

---

#### 2.27 `osint.username_enum` — Enumeração de Username

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `osint.username_enum` |
| **Nome** | Enumeração de Username em Sites |
| **Categoria** | OSINT |
| **Keywords** | `username`, `sherlock`, `enum`, `osint` |
| **Dependências** | `aiohttp` |

**Funcionalidades**:
- Input: username (ex: `johndoe`).
- Base interna com **~300 sites** (Instagram, GitHub, Reddit, Twitter/X, TikTok, Twitch, Steam, Spotify, Pinterest, sites BR como Instagram/Twitter, etc.), cada um com URL pattern e regra de detecção (status 200 + ausência de "not found" string).
- Consultas concorrentes via `aiohttp` (limite: 50 conexões simultâneas).
- Resultado em tempo real com status: Encontrado (verde) / Não encontrado (cinza) / Erro/timeout (amarelo).
- Clique em resultado abre URL no navegador.
- Exportação CSV.

---

#### 2.28 `osint.domain_intel` — Inteligência de Domínio

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `osint.domain_intel` |
| **Nome** | Inteligência Completa de Domínio |
| **Categoria** | OSINT |
| **Keywords** | `whois`, `dns`, `ssl`, `tecnologias`, `domain` |
| **Dependências** | `dnspython`, `whois`, `requests`, `ssl` |

**Funcionalidades**:
- Dashboard com 5 seções:
  1. **WHOIS**: registrante, organizador, criação/expiração, name servers, status.
  2. **DNS**: registros A, AAAA, MX, TXT (incluindo SPF/DMARC/DKIM), NS, SOA, CAA.
  3. **SSL/TLS**: emissor, titular, validade, SANs, algoritmo, dias restantes (reaproveita `network.diagnostics`).
  4. **Tecnologias**: detecta CMS (WordPress, Joomla, Drupal), frameworks JS (React, Vue, Angular), servidores (nginx, Apache), CDN (Cloudflare, Akamai), analytics via parsing de headers + HTML.
  5. **Google Dorks prontos**: `site:dominio.com filetype:pdf`, `site:dominio.com inurl:admin`, etc. com botão copiar.
- Exportação relatório Markdown completo.

---

#### 2.29 `osint.email_breach` — Verificador de E-mail em Vazamentos

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `osint.email_breach` |
| **Nome** | Verificador de E-mail em Vazamentos |
| **Categoria** | OSINT |
| **Keywords** | `breach`, `hibp`, `vazamento`, `email` |
| **Dependências** | `requests` |

**Funcionalidades**:
- Token via `get_api_token("hibp")`.
- Input: e-mail (ou lista de e-mails).
- Consulta `https://haveibeenpwned.com/api/v3/breachedaccount/{email}`.
- Resultado: lista de vazamentos com nome, data, domínio, contagem de contas afetadas, tipos de dados vazados (e-mails, senhas, CPF, cartões, IPs).
- Score de risco por e-mail (baseado em quais dados foram expostos).
- **K-Anonimato** para senhas (integração com `security.pwned_check` existente).
- Exportação JSON.

---

#### 2.30 `osint.metadata_extract` — Extrator de Metadados de Arquivos

| Campo | Valor |
|---|---|
| **Tipo** | `FileTool` |
| **ID** | `osint.metadata_extract` |
| **Nome** | Extrator de Metadados (OSINT) |
| **Categoria** | OSINT |
| **Keywords** | `metadata`, `exif`, `xmp`, `pdf`, `office` |
| **Extensões Suportadas** | `.jpg`, `.jpeg`, `.png`, `.tiff`, `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.odt`, `.mp3`, `.mp4` |
| **Dependências** | `exifread`, `hachoir`, `pypdf`, `openpyxl`, `python-docx` |

**Funcionalidades**:
- Extrai EXIF (fotos), XMP, IPTC, ICC.
- Para PDFs: autor, título, criador, datas, produtor.
- Para Office OpenXML: `docProps/core.xml` e `app.xml` (autor, empresa, revisão, datas).
- Para MP3/MP4: ID3 e container tags.
- **Exibe coordenadas GPS em mapa** (link `google.com/maps?q=lat,lng`) — expande `images.exif` existente.
- Detecção de "metadados reveladores": nome real do autor, empresa, hostname, path interno do autor.
- Exportação JSON/CSV.

---

### Categoria: `rev` (Nova)

---

#### 2.31 `rev.pe_analyzer` — Analisador de PE

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `rev.pe_analyzer` |
| **Nome** | Analisador de Executáveis PE |
| **Categoria** | Reverse Engineering |
| **Keywords** | `pe`, `exe`, `dll`, `packer`, `imports` |
| **Dependências** | `pefile`, `capstone` |

**Funcionalidades**:
- Abre `.exe`/`.dll`/`.sys`.
- **Info geral**: machine (x86/x64/ARM64), timestamp, entrypoint, image base, subsystem, características (DLL, executável, large address aware).
- **Seções**: nome, virtual size, raw size, entropia (Shannon), flags (R/W/X).
  - **Detecção de packer**: entropia > 7.0 em `.text` + seção `.packed`/`UPX` = alerta.
- **Imports**: DLLs carregadas + funções com agrupamento por categoria (rede, cripto, arquivo, registro).
- **Exports**: funções exportadas (para DLLs).
- **Recursos embutidos**: ícones, versão, manifesto.
- **Compilador original**: detecta MSVC, MinGW, Go, Rust (via strings e seções características).
- **Assinatura digital**: integra `security.signature_check`.
- **Detecção de packers**: UPX, Themida, VMProtect, Enigma, MPRESS por assinatura de bytes.
- Exportação de relatório HTML.

---

#### 2.32 `rev.strings_extract` — Extrator de Strings

| Campo | Valor |
|---|---|
| **Tipo** | `FileTool` |
| **ID** | `rev.strings_extract` |
| **Nome** | Extrator de Strings (Binários) |
| **Categoria** | Reverse Engineering |
| **Keywords** | `strings`, `ascii`, `utf16`, `binário` |
| **Extensões Suportadas** | Qualquer arquivo binário |
| **Dependências** | `re`, `python-magic` |

**Funcionalidades**:
- Extrai strings ASCII (≥4 chars) e UTF-16LE.
- Filtro de comprimento mínimo configurável (4-20).
- **Classificação automática** de cada string:
  - URLs (`https?://...`), IPs (v4 e v6), e-mails, caminhos Windows/Unix, chaves de registro (`HKLM\...`), hashes, JWT, chaves de API (padrões `sk-`, `ghp_`, `AKIA`), base64.
- Filtro por categoria + busca textual.
- Exportação TXT/CSV/JSON.

---

#### 2.33 `rev.disassembler` — Desassemblador Multi-Arquitetura

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `rev.disassembler` |
| **Nome** | Desassemblador (Capstone) |
| **Categoria** | Reverse Engineering |
| **Keywords** | `disasm`, `capstone`, `x86`, `arm` |
| **Dependências** | `capstone`, `keystone-engine` |

**Funcionalidades**:
- Arquiteturas: x86, x86-64, ARM, ARM64, MIPS.
- Syntax: Intel ou AT&T.
- Navegação por offset (input hex ou decimal).
- Exibição: endereço, bytes brutos, mnemônico, operadores.
- **Cross-reference**: clicar em um `call`/`jmp` navega para o destino.
- **Assembler inline** (via `keystone`) para editar e re-montar instruções.
- Exportação ASM.

---

#### 2.34 `rev.js_deobfuscator` — Desofuscador JavaScript

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `rev.js_deobfuscator` |
| **Nome** | Desofuscador de JavaScript |
| **Categoria** | Reverse Engineering |
| **Keywords** | `js`, `obfuscator`, `beautifier`, `deobfuscate` |
| **Dependências** | `jsbeautifier`, `pyjsparser` |

**Funcionalidades**:
- Input: JS ofuscado (colar ou arquivo).
- **Etapas configuráveis**:
  1. Pretty-print via `jsbeautifier`.
  2. Unescape de `\x41`, `\u0041`, `String.fromCharCode(...)` estático.
  3. Desfaz `eval(...)` com concatenação literal (até 5 níveis).
  4. Renomeia variáveis `_0x[a-f0-9]+` para `var_1`, `var_2`.
  5. Remove dead code (variáveis nunca lidas).
- Preview lado a lado (antes/depois) + download do resultado.
- Análise de risco: detecta strings suspeitas (b64, crypto, debugger, `window.location`).

---

#### 2.35 `rev.pyc_decompiler` — Decompilador Python

| Campo | Valor |
|---|---|
| **Tipo** | `FileTool` |
| **ID** | `rev.pyc_decompiler` |
| **Nome** | Decompilador de Bytecode Python |
| **Categoria** | Reverse Engineering |
| **Keywords** | `pyc`, `decompile`, `bytecode` |
| **Extensões Suportadas** | `.pyc` |
| **Dependências** | `decompyle3`, `uncompyle6` (fallback) |

**Funcionalidades**:
- Lê o magic number do `.pyc` para determinar a versão do Python.
- Escolhe automaticamente o decompiler: `decompyle3` (3.7-3.8), `uncompyle6` (2.7-3.8), `pycdc` externo (se disponível) para versões mais recentes.
- Fallback: exibe o bytecode com `dis` se decompilação falhar.
- Exportação `.py` + log de avisos.

---

### Categoria: `system` (Auditoria Defensiva)

---

#### 2.36 `system.persistence_scan` — Scanner de Persistência

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `system.persistence_scan` |
| **Nome** | Scanner de Mecanismos de Persistência |
| **Categoria** | Sistema |
| **Keywords** | `persistence`, `autorun`, `startup`, `malware` |
| **Dependências** | `pywin32`, `wmi`, `subprocess` |

**Funcionalidades**:
- Enumera **todos os pontos de persistência** do Windows:
  - Registry: `Run`, `RunOnce`, `RunServices`, `Policies\Explorer\Run` (HKCU + HKLM + Wow6432Node).
  - Serviços (`Get-Service` + binPath de cada um).
  - Scheduled Tasks (`Get-ScheduledTask`).
  - WMI Event Subscriptions (`Get-WmiObject -Namespace root\subscription`).
  - Startup folders (usuário + all users).
  - AppInit_DLLs, Winlogon Shell/Userinit, Image File Execution Options, IFEO Debugger.
- Cada entrada com: nome, path, hash SHA-256 do binário, assinatura digital (via `security.signature_check`), data de criação.
- **Alertas**:
  - Entradas em paths suspeitos (`%TEMP%`, `%APPDATA%`, `C:\Users\Public`).
  - Binários não assinados.
  - Nomes com typosquatting (`scvhost.exe`, `chrome_updater.exe`).
- Exportação JSON/CSV + botão "Abrir no Regedit" / "Abrir pasta no Explorer".

---

#### 2.37 `system.rootkit_detect` — Detector de Rootkit (Heurístico) ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `system.rootkit_detect` |
| **Nome** | Detector de Rootkit (Heurístico) |
| **Categoria** | Sistema |
| **Keywords** | `rootkit`, `hook`, `ssdt`, `detect` |
| **Dependências** | `psutil`, `ctypes`, `pywin32` |
| **Requer Admin** | Sim |

**Funcionalidades**:
- **Cross-check psutil vs NtQuerySystemInformation**: detecta processos ocultos (visíveis via API nativa mas não via `psutil`).
- **Portas LISTEN sem dono**: sockets abertos sem processo correspondente.
- **SSDT hooks**: compara entradas da SSDT com addresses originais do kernel (via `ntoskrnl.exe` base).
- **Drivers não assinados**: `Get-WindowsDriver` + verificação de assinatura.
- **Alterações em `winlogon.exe`/`lsass.exe`** (via integrity check).
- Relatório com itens suspeitos + link para `GMER` ou `TDSSKiller` se detectar algo grave.
- **Não remove nada** — apenas diagnostica.

---

#### 2.38 `system.keylogger_detect` — Detector de Keylogger

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `system.keylogger_detect` |
| **Nome** | Detector de Keylogger |
| **Categoria** | Sistema |
| **Keywords** | `keylogger`, `hook`, `keyboard`, `detect` |
| **Dependências** | `psutil`, `ctypes` |

**Funcionalidades**:
- Enumera hooks de teclado instalados (via `SetWindowsHookEx(WH_KEYBOARD_LL)`) — busca por processos com esse hook.
- Scaneia DLLs carregadas em processos com nomes suspeitos (`keylog`, `hook`, `spy`, `monitor`, `recorder`).
- Verifica drivers de filtro de teclado (`kbdclass`, `kbfiltr`) — alerta se houver filtros desconhecidos.
- Detecta arquivos de log de teclado em locais comuns (`%TEMP%\*.log`, `%APPDATA%\*.txt` com conteúdo de teclas).
- Detecção de processos que chamam `GetAsyncKeyState` em loop (via análise heurística de imports).
- Aviso: ferramenta **apenas diagnostica**, não instala nada.

---

#### 2.39 `system.credential_audit` — Auditoria de Credenciais Salvas ⚠️

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `system.credential_audit` |
| **Nome** | Auditoria de Credenciais Locais |
| **Categoria** | Sistema |
| **Keywords** | `credentials`, `dpapi`, `senhas`, `audit` |
| **Dependências** | `pywin32` (`win32cred`, `win32crypt`) |

**Aviso ético**: apenas credenciais do próprio perfil. Termo obrigatório.

**Funcionalidades**:
- Lê **Windows Credential Manager** (`win32cred.CredEnumerate`) do perfil atual.
- Lista: target, username, tipo (Generic/Domain/Certificate), persistência.
- **Análise de força**: extrai metadados de senhas (não mostra plaintext a menos que o usuário confirme "Sim, quero ver").
- **Detecção de senhas fracas**:
  - Reutilização entre serviços (match por hash).
  - Senhas comuns (verifica contra lista embutida de top 100).
  - Credenciais expiradas (via `win32cred.CredGet`).
- **Integração com `security.pwned_check`**: para cada senha visível, oferece verificar HIBP via K-Anonimato.
- Exportação **apenas de metadados** (sem plaintext).

---

#### 2.40 `system.defender_audit` — Auditoria do Windows Defender

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `system.defender_audit` |
| **Nome** | Auditoria do Defender |
| **Categoria** | Sistema |
| **Keywords** | `defender`, `antivirus`, `status`, `audit` |
| **Dependências** | `subprocess` (PowerShell) |

**Funcionalidades**:
- Status em tempo real via `Get-MpComputerStatus`: real-time protection, antimalware engine version, signature version/last update, quick/full scan dates.
- `Get-MpPreference`: exclusões configuradas (pastas, arquivos, processos, IPs) — **alerta se houver muitas exclusões** (possível desativação maliciosa).
- ASR rules (`Get-MpPreference | Select AttackSurfaceReductionRules_Ids` + status).
- Controle de features: cloud-delivered protection, PUA protection, tamper protection.
- **Recomendações**: ligar X, atualizar Y, revisar exclusões.
- Exportação de relatório de conformidade.

---

#### 2.41 `system.firewall_audit` — Auditoria do Firewall

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `system.firewall_audit` |
| **Nome** | Auditoria do Firewall do Windows |
| **Categoria** | Sistema |
| **Keywords** | `firewall`, `rules`, `portas`, `audit` |
| **Dependências** | `subprocess` (PowerShell) |

**Funcionalidades**:
- Status de 3 perfis (Domain/Private/Public): enabled, block inbound, notify.
- **Regras suspeitas**:
  - Regras com escopo `Any → Any` em portas sensíveis (SMB 445, RDP 3389, WinRM 5985).
  - Aplicações com allow-all sem assinatura digital.
  - Portas abertas sem regra explícita (via `Get-NetTCPConnection -State Listen`).
- Verificação de que `Windows Firewall` service está rodando.
- Exportação CSV + comparação com "baseline recomendado" (Microsoft).

---

#### 2.42 `system.dns_leak_test` — Teste de Vazamento de DNS

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `system.dns_leak_test` |
| **Nome** | Teste de Vazamento de DNS |
| **Categoria** | Sistema |
| **Keywords** | `dns`, `leak`, `vpn`, `privacidade` |
| **Dependências** | `requests`, `dnspython` |

**Funcionalidades**:
- Consulta `https://1.1.1.1/cdn-cgi/trace` (Cloudflare) e `https://www.dnsleaktest.com/`-like endpoints para descobrir o resolver DNS real usado.
- Compara com IP público do usuário (`network.ip_info` existente).
- Detecção de:
  - Resolver DNS diferente do esperado (indica VPN vazando DNS).
  - Uso de DNS do ISP (privacidade baixa) vs. Cloudflare/Google/Quad9.
  - DNS hijacking (respostas inconsistentes entre resolvers).
- Recomendação: configurar DNS via `network.dns_manager` existente.

---

#### 2.43 `system.webrtc_leak` — Detector de Vazamento WebRTC

| Campo | Valor |
|---|---|
| **Tipo** | `Tool` |
| **ID** | `system.webrtc_leak` |
| **Nome** | Detector de Vazamento WebRTC |
| **Categoria** | Sistema |
| **Keywords** | `webrtc`, `leak`, `vpn`, `ip` |
| **Dependências** | `playwright` ou `selenium` |

**Funcionalidades**:
- Lança browser headless com `playwright.chromium`.
- Executa JavaScript que cria `RTCPeerConnection` e coleta ICE candidates.
- Extrai IPs locais e públicos expostos via WebRTC.
- Compara com IP público real → alerta se houver IP local exposto (VPN não está bloqueando WebRTC).
- Instruções de correção por navegador (Chrome/Firefox/Edge).

---

## 3. Estrutura de Pastas Final

```
src/wintoolbox/tools/
├── security/           # NOVA
│   ├── __init__.py
│   ├── hash_identify.py
│   ├── hash_cracker.py
│   ├── rainbow_generator.py
│   ├── jwt_secret_cracker.py
│   ├── pwned_check.py           # já existe
│   ├── virustotal.py            # já existe
│   ├── signature_check.py       # já existe
│   ├── http_headers.py          # já existe
│   └── ...
├── crypto/             # NOVA
│   ├── stegano.py
│   ├── stegano_detect.py
│   ├── rsa_attack.py
│   └── classical_break.py
├── network/            # EXISTENTE — adicionar
│   ├── packet_sniffer.py
│   ├── packet_crafter.py
│   ├── arp_poison.py
│   ├── dns_spoof.py
│   ├── deauth_test.py
│   └── mitm_proxy.py
├── web/                # NOVA
│   ├── dir_bruteforce.py
│   ├── subdomain_enum.py
│   ├── vuln_scanner.py
│   ├── jwt_toolkit.py
│   └── csrf_poc.py
├── forensics/          # NOVA
│   ├── memory_dump.py
│   ├── file_recovery.py
│   ├── registry_parser.py
│   ├── browser_extract.py
│   ├── usb_history.py
│   ├── lnk_analyzer.py
│   └── artifact_timeline.py
├── osint/              # NOVA
│   ├── username_enum.py
│   ├── domain_intel.py
│   ├── email_breach.py
│   └── metadata_extract.py
└── rev/                # NOVA
    ├── pe_analyzer.py
    ├── strings_extract.py
    ├── disassembler.py
    ├── js_deobfuscator.py
    └── pyc_decompiler.py
```

Cada pasta precisa de `__init__.py` que importa as ferramentas para registro automático via `@register`.

---

## 4. Skeleton Universal de Implementação

Para orientar a IA, segue o padrão mínimo de código que **toda** ferramenta deste documento deve seguir:

```python
"""Módulo de [descrição curta]. Ferramenta do All the Utils."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox

from wintoolbox.core.registry import Tool, FileTool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.core.settings import get_api_token


@register
class MinhaFerramenta(Tool):  # ou FileTool
    id = "categoria.nome_ferramenta"
    name = "Nome Amigável em pt-BR"
    category = "Categoria"
    description = "Descrição clara do que faz."
    keywords = ["palavra1", "palavra2"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return MinhaView(self, parent)


class MinhaView(QWidget):
    def __init__(self, tool: MinhaFerramenta, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner(self)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel(self.tool.name)
        titulo.setProperty("class", "title")
        layout.addWidget(titulo)
        # ... widgets específicos ...

    def _confirmar_termo_etico(self) -> bool:
        """Só para ferramentas marcadas com aviso ético."""
        resp = QMessageBox.warning(
            self,
            "Aviso de Uso Responsável",
            "Esta ferramenta deve ser usada apenas em sistemas dos quais você é "
            "proprietário ou tem autorização expressa por escrito.\n\n"
            "Uso não autorizado é crime previsto na Lei 12.737/2012 (art. 154-A do CP).",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return resp == QMessageBox.Yes
```

---

## 5. Ordem de Implementação Recomendada

Para uma IA implementar sem se perder, seguir esta ordem (do mais simples ao mais complexo):

| # | Ferramenta | Complexidade | Dependências Novas |
|---|---|---|---|
| 1 | `security.hash_identify` | Baixa | Nenhuma |
| 2 | `rev.strings_extract` | Baixa | `python-magic` (opcional) |
| 3 | `system.defender_audit` | Baixa | Nenhuma (PowerShell) |
| 4 | `system.firewall_audit` | Baixa | Nenhuma (PowerShell) |
| 5 | `forensics.usb_history` | Baixa | `pywin32` (já presente) |
| 6 | `osint.username_enum` | Média | `aiohttp` |
| 7 | `security.rainbow_generator` | Média | Nenhuma |
| 8 | `crypto.classical_break` | Média | Nenhuma |
| 9 | `web.subdomain_enum` | Média | `dnspython` |
| 10 | `web.dir_bruteforce` | Média | `requests` (já presente) |
| 11 | `crypto.stegano` + `detect` | Média | `stegano`, `scipy` |
| 12 | `system.persistence_scan` | Média | `pywin32` (já presente) |
| 13 | `forensics.lnk_analyzer` | Média | `LnkParse3` |
| 14 | `security.hash_cracker` | Alta | Nenhuma (hashlib) |
| 15 | `network.packet_sniffer` | Alta | `scapy` |
| 16 | `forensics.registry_parser` | Alta | `regipy` |
| 17 | `rev.pe_analyzer` | Alta | `pefile` |
| 18 | `osint.domain_intel` | Alta | `whois`, `dnspython` |
| 19 | `web.vuln_scanner` | Alta | `bs4` (já presente) |
| 20 | `forensics.browser_extract` | Alta | `pycryptodome` |
| 21 | `forensics.memory_dump` | Muito alta | `ctypes` + admin |
| 22 | `network.arp_poison` | Muito alta | `scapy` + admin |
| 23 | `network.mitm_proxy` | Muito alta | `mitmproxy` |
| 24 | `forensics.file_recovery` | Muito alta | `pytsk3` |
| 25 | `rev.disassembler` | Muito alta | `capstone`, `keystone` |

---

## 6. Checklist de Aceitação (Definition of Done)

Uma ferramenta só é considerada "pronta" se cumprir **todos** os itens:

- [ ] Arquivo criado em `src/wintoolbox/tools/<categoria>/<nome>.py`
- [ ] Decorator `@register` aplicado
- [ ] Classe herda de `Tool` ou `FileTool`
- [ ] `id`, `name`, `category`, `description`, `keywords` preenchidos em pt-BR
- [ ] `build_view` ou `build_options_widget` + `process_file` implementados
- [ ] Operações longas usam `TaskRunner` (nunca bloqueia UI)
- [ ] Bibliotecas pesadas importadas **dentro** dos métodos (lazy)
- [ ] Tokens via `get_api_token(...)` quando aplicável
- [ ] `QMessageBox` de aviso ético nas ferramentas marcadas ⚠️
- [ ] Verificação de admin nas ferramentas que precisam
- [ ] Logs via `LogPanelWidget` quando houver processamento longo
- [ ] Tratamento de exceções com mensagem amigável (não stacktrace cru)
- [ ] Teste manual: abre, executa, fecha sem crash
- [ ] Adicionado ao `docs/catalogo_ferramentas.md`
- [ ] `python main.py --list` reconhece a ferramenta
- [ ] Nenhum emoji em strings visíveis
- [ ] Interface 100% em Português do Brasil

---

## 7. Notas Finais para Agentes de IA

1. **Não invente IDs duplicados**: antes de implementar, executar `main.py --list` e verificar colisões.
2. **Reutilize ao máximo**: `network.diagnostics` já tem ping/SSL; `security.http_headers` já audita headers; `images.exif` já lê EXIF; `encode.jwt_debugger` já decodifica JWT. **Não duplique** — estenda.
3. **Avisos éticos são parte da feature**, não burocracia. Todo `⚠️` no documento exige `QMessageBox` bloqueante antes da primeira execução na sessão.
4. **Modo read-only por padrão** em ferramentas forenses: nunca modificar artefatos analisados; sempre operar em cópias quando necessário.
5. **Exportação sempre disponível**: qualquer ferramenta que gera dados deve ter botão "Copiar" e "Salvar em arquivo".
6. **Erros previstos**: toda chamada a `scapy`, `pytsk3`, `capstone` pode falhar se a dependência não estiver instalada — capture `ImportError` e mostre mensagem "Esta ferramenta requer X. Instale com `pip install X`."
7. **Documente a limitação**: se a ferramenta não funciona em certo cenário (ex: placa WiFi sem modo monitor), avise na UI ao invés de crashar.
8. **Log em arquivo**: usar `logging` do projeto (`wintoolbox.core.logging` se existir) para registrar operações — útil para auditoria.

---

**Fim do documento.**  
**Versão**: 1.0 — pronta para consumo por agentes de IA.  
**Manutenção**: adicionar novas ferramentas ao final da seção correspondente e atualizar a tabela de prioridades no item 5.
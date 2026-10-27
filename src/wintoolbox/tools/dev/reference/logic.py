"""
Lógica pura e banco de dados offline para tabelas de referência técnica para desenvolvedores.
Inclui Status HTTP, Tipos MIME, Tabela ASCII, Virtual-Key Codes do Windows e Atalhos de Teclado.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class HttpReferenceItem:
    code: int
    phrase: str
    category: str
    description: str


@dataclass
class MimeReferenceItem:
    extension: str
    mime_type: str
    category: str
    description: str


@dataclass
class AsciiReferenceItem:
    decimal: int
    hexadecimal: str
    binary: str
    character: str
    description: str


@dataclass
class VirtualKeyItem:
    vk_name: str
    hex_code: str
    dec_code: int
    description: str


@dataclass
class ShortcutItem:
    keys: str
    scope: str
    description: str


# 1. Códigos de Status HTTP (RFC 9110)
HTTP_STATUS_LIST: List[HttpReferenceItem] = [
    HttpReferenceItem(100, "Continue", "1xx Informativo", "O cliente deve continuar o envio da requisição."),
    HttpReferenceItem(101, "Switching Protocols", "1xx Informativo", "O servidor está mudando o protocolo conforme solicitado (ex: WebSocket)."),
    HttpReferenceItem(200, "OK", "2xx Sucesso", "Requisição concluída com êxito."),
    HttpReferenceItem(201, "Created", "2xx Sucesso", "Recurso criado com sucesso (comum em requisições POST)."),
    HttpReferenceItem(202, "Accepted", "2xx Sucesso", "Requisição aceita para processamento assíncrono em fila."),
    HttpReferenceItem(204, "No Content", "2xx Sucesso", "Requisição bem-sucedida, sem corpo retornado na resposta."),
    HttpReferenceItem(206, "Partial Content", "2xx Sucesso", "Resposta com intervalo parcial de bytes (header Range)."),
    HttpReferenceItem(301, "Moved Permanently", "3xx Redirecionamento", "O recurso foi movido permanentemente para uma nova URI."),
    HttpReferenceItem(302, "Found", "3xx Redirecionamento", "Redirecionamento temporário para outra URI."),
    HttpReferenceItem(304, "Not Modified", "3xx Redirecionamento", "O recurso não mudou desde a última requisição em cache."),
    HttpReferenceItem(307, "Temporary Redirect", "3xx Redirecionamento", "Redirecionamento temporário mantendo o mesmo verbo HTTP original."),
    HttpReferenceItem(308, "Permanent Redirect", "3xx Redirecionamento", "Redirecionamento permanente mantendo o mesmo verbo HTTP original."),
    HttpReferenceItem(400, "Bad Request", "4xx Erro do Cliente", "Sintaxe da requisição malformada ou parâmetros inválidos."),
    HttpReferenceItem(401, "Unauthorized", "4xx Erro do Cliente", "Autenticação requerida (credenciais ausentes ou inválidas)."),
    HttpReferenceItem(403, "Forbidden", "4xx Erro do Cliente", "O servidor compreendeu a requisição, mas recusa-se a autorizá-la."),
    HttpReferenceItem(404, "Not Found", "4xx Erro do Cliente", "O recurso solicitado não pôde ser encontrado."),
    HttpReferenceItem(405, "Method Not Allowed", "4xx Erro do Cliente", "Método HTTP não suportado pelo endpoint."),
    HttpReferenceItem(408, "Request Timeout", "4xx Erro do Cliente", "Tempo limite de espera da requisição esgotado."),
    HttpReferenceItem(409, "Conflict", "4xx Erro do Cliente", "Conflito com o estado atual do recurso no servidor."),
    HttpReferenceItem(413, "Payload Too Large", "4xx Erro do Cliente", "O corpo da requisição excede os limites suportados pelo servidor."),
    HttpReferenceItem(415, "Unsupported Media Type", "4xx Erro do Cliente", "Formato de mídia não suportado no Content-Type."),
    HttpReferenceItem(422, "Unprocessable Entity", "4xx Erro do Cliente", "Erros de validação semântica nos dados enviados (RFC 4918)."),
    HttpReferenceItem(429, "Too Many Requests", "4xx Erro do Cliente", "Limite de taxa de requisições excedido (Rate Limit)."),
    HttpReferenceItem(500, "Internal Server Error", "5xx Erro do Servidor", "Falha interna genérica no servidor."),
    HttpReferenceItem(501, "Not Implemented", "5xx Erro do Servidor", "O servidor não suporta a funcionalidade exigida."),
    HttpReferenceItem(502, "Bad Gateway", "5xx Erro do Servidor", "Resposta inválida recebida do servidor upstream/proxy."),
    HttpReferenceItem(503, "Service Unavailable", "5xx Erro do Servidor", "Servidor sobrecarregado ou em manutenção temporária."),
    HttpReferenceItem(504, "Gateway Timeout", "5xx Erro do Servidor", "O proxy expirou o tempo aguardando a resposta do backend."),
]

# 2. Tipos MIME Comuns
MIME_TYPES_LIST: List[MimeReferenceItem] = [
    MimeReferenceItem(".json", "application/json", "Aplicação", "Estrutura de dados JavaScript Object Notation"),
    MimeReferenceItem(".xml", "application/xml", "Aplicação", "Documento eXtensible Markup Language"),
    MimeReferenceItem(".pdf", "application/pdf", "Aplicação", "Documento Adobe Portable Document Format"),
    MimeReferenceItem(".zip", "application/zip", "Aplicação", "Arquivo compactado ZIP"),
    MimeReferenceItem(".html", "text/html", "Texto", "Documento Web HyperText Markup Language"),
    MimeReferenceItem(".css", "text/css", "Texto", "Folha de estilo Cascading Style Sheets"),
    MimeReferenceItem(".js", "text/javascript", "Texto", "Código-fonte JavaScript"),
    MimeReferenceItem(".txt", "text/plain", "Texto", "Texto puro ASCII/UTF-8"),
    MimeReferenceItem(".csv", "text/csv", "Texto", "Valores separados por vírgula"),
    MimeReferenceItem(".png", "image/png", "Imagem", "Portable Network Graphics com transparência"),
    MimeReferenceItem(".jpg", "image/jpeg", "Imagem", "Joint Photographic Experts Group"),
    MimeReferenceItem(".webp", "image/webp", "Imagem", "Formato de imagem de alta eficiência WebP"),
    MimeReferenceItem(".svg", "image/svg+xml", "Imagem", "Gráfico vetorial escalável"),
    MimeReferenceItem(".ico", "image/x-icon", "Imagem", "Ícone de aplicativo e favicon"),
    MimeReferenceItem(".mp3", "audio/mpeg", "Áudio", "Áudio comprimido MPEG-1 Audio Layer III"),
    MimeReferenceItem(".wav", "audio/wav", "Áudio", "Áudio PCM Waveform sem perdas"),
    MimeReferenceItem(".flac", "audio/flac", "Áudio", "Free Lossless Audio Codec"),
    MimeReferenceItem(".mp4", "video/mp4", "Vídeo", "Vídeo contêiner MPEG-4 Parte 14"),
    MimeReferenceItem(".mkv", "video/x-matroska", "Vídeo", "Contêiner multimídia Matroska"),
    MimeReferenceItem(".webm", "video/webm", "Vídeo", "Vídeo WebM otimizado para navegadores"),
]

# 3. Tabela ASCII
def get_ascii_table() -> List[AsciiReferenceItem]:
    control_names = {
        0: "NUL (Null)", 1: "SOH (Start of Heading)", 2: "STX (Start of Text)",
        3: "ETX (End of Text)", 4: "EOT (End of Trans.)", 5: "ENQ (Enquiry)",
        6: "ACK (Acknowledge)", 7: "BEL (Bell)", 8: "BS (Backspace)",
        9: "HT (Tab horizontal)", 10: "LF (Line Feed)", 11: "VT (Tab vertical)",
        12: "FF (Form Feed)", 13: "CR (Carriage Return)", 14: "SO (Shift Out)",
        15: "SI (Shift In)", 16: "DLE (Data Link Escape)", 17: "DC1 (Dev Control 1)",
        18: "DC2 (Dev Control 2)", 19: "DC3 (Dev Control 3)", 20: "DC4 (Dev Control 4)",
        21: "NAK (Negative Ack)", 22: "SYN (Sync Idle)", 23: "ETB (End Trans Block)",
        24: "CAN (Cancel)", 25: "EM (End of Medium)", 26: "SUB (Substitute)",
        27: "ESC (Escape)", 28: "FS (File Separator)", 29: "GS (Group Separator)",
        30: "RS (Record Separator)", 31: "US (Unit Separator)", 32: "Space (Espaço)",
        127: "DEL (Delete)"
    }
    items: List[AsciiReferenceItem] = []
    for i in range(128):
        hex_str = f"0x{i:02X}"
        bin_str = f"{i:08b}"
        if i in control_names:
            char_repr = control_names[i].split()[0]
            desc = control_names[i]
        else:
            char_repr = chr(i)
            desc = f"Caractere imprimível '{chr(i)}'"
        items.append(AsciiReferenceItem(i, hex_str, bin_str, char_repr, desc))
    return items

# 4. Códigos de Teclas Virtuais do Windows (Virtual-Key Codes)
VIRTUAL_KEYS_LIST: List[VirtualKeyItem] = [
    VirtualKeyItem("VK_LBUTTON", "0x01", 1, "Botão esquerdo do mouse"),
    VirtualKeyItem("VK_RBUTTON", "0x02", 2, "Botão direito do mouse"),
    VirtualKeyItem("VK_CANCEL", "0x03", 3, "Processamento de Ctrl-Break"),
    VirtualKeyItem("VK_MBUTTON", "0x04", 4, "Botão do meio do mouse"),
    VirtualKeyItem("VK_BACK", "0x08", 8, "Tecla BACKSPACE"),
    VirtualKeyItem("VK_TAB", "0x09", 9, "Tecla TAB"),
    VirtualKeyItem("VK_CLEAR", "0x0C", 12, "Tecla CLEAR"),
    VirtualKeyItem("VK_RETURN", "0x0D", 13, "Tecla ENTER"),
    VirtualKeyItem("VK_SHIFT", "0x10", 16, "Tecla SHIFT"),
    VirtualKeyItem("VK_CONTROL", "0x11", 17, "Tecla CTRL"),
    VirtualKeyItem("VK_MENU", "0x12", 18, "Tecla ALT"),
    VirtualKeyItem("VK_PAUSE", "0x13", 19, "Tecla PAUSE"),
    VirtualKeyItem("VK_CAPITAL", "0x14", 20, "Tecla CAPS LOCK"),
    VirtualKeyItem("VK_ESCAPE", "0x1B", 27, "Tecla ESC"),
    VirtualKeyItem("VK_SPACE", "0x20", 32, "Barra de espaço"),
    VirtualKeyItem("VK_PRIOR", "0x21", 33, "Tecla PAGE UP"),
    VirtualKeyItem("VK_NEXT", "0x22", 34, "Tecla PAGE DOWN"),
    VirtualKeyItem("VK_END", "0x23", 35, "Tecla END"),
    VirtualKeyItem("VK_HOME", "0x24", 36, "Tecla HOME"),
    VirtualKeyItem("VK_LEFT", "0x25", 37, "Seta para ESQUERDA"),
    VirtualKeyItem("VK_UP", "0x26", 38, "Seta para CIMA"),
    VirtualKeyItem("VK_RIGHT", "0x27", 39, "Seta para DIREITA"),
    VirtualKeyItem("VK_DOWN", "0x28", 40, "Seta para BAIXO"),
    VirtualKeyItem("VK_SNAPSHOT", "0x2C", 44, "Tecla PRINT SCREEN"),
    VirtualKeyItem("VK_INSERT", "0x2D", 45, "Tecla INSERT"),
    VirtualKeyItem("VK_DELETE", "0x2E", 46, "Tecla DELETE"),
    VirtualKeyItem("VK_LWIN", "0x5B", 91, "Tecla Windows esquerda"),
    VirtualKeyItem("VK_RWIN", "0x5C", 92, "Tecla Windows direita"),
    VirtualKeyItem("VK_F1", "0x70", 112, "Tecla de função F1"),
    VirtualKeyItem("VK_F5", "0x74", 116, "Tecla de função F5"),
    VirtualKeyItem("VK_F11", "0x7A", 122, "Tecla de função F11 (Tela cheia)"),
    VirtualKeyItem("VK_F12", "0x7B", 123, "Tecla de função F12 (DevTools)"),
]

# 5. Atalhos de Produtividade do Windows
SHORTCUTS_LIST: List[ShortcutItem] = [
    ShortcutItem("Win + V", "Área de Transferência", "Histórico avançado da área de transferência"),
    ShortcutItem("Win + Shift + S", "Captura", "Ferramenta de recorte e captura de tela retangular/livre"),
    ShortcutItem("Win + E", "Navegação", "Abre o Explorador de Arquivos"),
    ShortcutItem("Win + D", "Desktop", "Alterna a exibição da Área de Trabalho (minimiza/restaura janelas)"),
    ShortcutItem("Win + L", "Segurança", "Bloqueia a estação de trabalho imediatamente"),
    ShortcutItem("Win + . (ponto)", "Entrada", "Abre o painel de emojis, símbolos e caracteres especiais"),
    ShortcutItem("Win + R", "Executar", "Abre o diálogo clássico Executar"),
    ShortcutItem("Win + X", "Sistema", "Menu de link rápido de administração (Terminal, Disco, Dispositivos)"),
    ShortcutItem("Ctrl + Shift + Esc", "Sistema", "Abre o Gerenciador de Tarefas do Windows diretamente"),
    ShortcutItem("Win + Setas", "Janelas", "Ajusta e fixa a janela atual (Snap Layouts)"),
    ShortcutItem("Win + Tab", "Janelas", "Visão de tarefas e alternador de Áreas de Trabalho Virtuais"),
    ShortcutItem("Win + Ctrl + D", "Desktop", "Cria uma nova Área de Trabalho Virtual"),
    ShortcutItem("Win + Ctrl + F4", "Desktop", "Fecha a Área de Trabalho Virtual atual"),
]


def search_reference(query: str, items: List) -> List:
    """Filtra qualquer lista de itens com base em uma busca por texto insensível a maiúsculas."""
    if not query.strip():
        return items

    q = query.lower().strip()
    filtered = []
    for item in items:
        # Converte todos os campos do dataclass em string para conferência
        for val in item.__dict__.values():
            if q in str(val).lower():
                filtered.append(item)
                break
    return filtered

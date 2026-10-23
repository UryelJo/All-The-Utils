"""
Lógica pura do Gerador de Dados Fictícios para Testes e Desenvolvimento.
Geração 100% offline de dados sintéticos brasileiros (CPF, CNPJ, RG, CEP, Nomes, Empresas, IPs, UUID, Lorem Ipsum).
Zero acoplamento com interface gráfica.
"""
import csv
import io
import json
import random
import uuid
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("dev.fake_data")

# Bancos de dados léxicos para dados brasileiros verossímeis
FIRST_NAMES_MALE = [
    "Lucas", "Gabriel", "Matheus", "Guilherme", "Gustavo", "Felipe", "Bruno", "Rodrigo", "Leonardo",
    "Thiago", "Eduardo", "Rafael", "Vinicius", "Daniel", "Marcelo", "Alexandre", "Caio", "Diego",
    "Arthur", "Bernardo", "Heitor", "Davi", "Lorenzo", "Samuel", "Enzo", "Pedro", "Henrique"
]

FIRST_NAMES_FEMALE = [
    "Juliana", "Mariana", "Beatriz", "Larissa", "Camila", "Leticia", "Amanda", "Jessica", "Bruna",
    "Fernanda", "Carolina", "Aline", "Gabriela", "Rafaela", "Isabela", "Natalia", "Vanessa", "Patricia",
    "Helena", "Alice", "Laura", "Sophia", "Manuela", "Valentina", "Luiza", "Heloisa", "Maria"
]

LAST_NAMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira", "Lima",
    "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho", "Almeida", "Lopes", "Soares", "Fernandes",
    "Vieira", "Barbosa", "Rocha", "Dias", "Nascimento", "Andrade", "Moreira", "Nunes", "Marques",
    "Machado", "Mendes", "Freitas", "Cardoso", "Ramos", "Gonçalves", "Santana", "Teixeira"
]

EMAIL_DOMAINS = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com.br", "empresa.com.br", "teste.dev.br"]

CITIES_BY_UF: List[Tuple[str, str, int]] = [
    ("São Paulo", "SP", 11), ("Campinas", "SP", 19), ("Santos", "SP", 13),
    ("Rio de Janeiro", "RJ", 21), ("Niterói", "RJ", 21), ("Petrópolis", "RJ", 24),
    ("Belo Horizonte", "MG", 31), ("Uberlândia", "MG", 34), ("Juiz de Fora", "MG", 32),
    ("Curitiba", "PR", 41), ("Londrina", "PR", 43), ("Maringá", "PR", 44),
    ("Porto Alegre", "RS", 51), ("Caxias do Sul", "RS", 54), ("Pelotas", "RS", 53),
    ("Florianópolis", "SC", 48), ("Joinville", "SC", 47), ("Blumenau", "SC", 47),
    ("Salvador", "BA", 71), ("Feira de Santana", "BA", 75), ("Vitória da Conquista", "BA", 77),
    ("Recife", "PE", 81), ("Olinda", "PE", 81), ("Caruaru", "PE", 81),
    ("Fortaleza", "CE", 85), ("Brasília", "DF", 61), ("Goiânia", "GO", 62),
    ("Manaus", "AM", 92), ("Belém", "PA", 91), ("Vitória", "ES", 27)
]

STREET_PREFIXES = ["Rua", "Avenida", "Alameda", "Travessa", "Praça"]
STREET_NAMES = [
    "das Flores", "Brasil", "Sete de Setembro", "XV de Novembro", "São Paulo", "Tiradentes",
    "Amazonas", "Santos Dumont", "Bela Vista", "dos Andradas", "Duque de Caxias", "Paulista",
    "Independência", "Rui Barbosa", "Getúlio Vargas", "Juscelino Kubitschek"
]
NEIGHBORHOODS = [
    "Centro", "Jardim América", "Bela Vista", "Vila Nova", "Pinheiros", "Copacabana", "Boa Viagem",
    "Moinhos de Vento", "Savassi", "Batel", "Meireles", "Asa Sul", "Barra", "Cambuí", "Gonzaga"
]

COMPANY_PREFIXES = ["Tech", "Mega", "Global", "Brasil", "Inova", "Prime", "Alpha", "Nexus", "Soluções", "Delta"]
COMPANY_SUFFIXES = ["Sistemas", "Logística", "Consultoria", "Engenharia", "Comércio", "Serviços", "Digital", "Participações"]

LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit", "sed", "do",
    "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore", "magna", "aliqua", "enim",
    "ad", "minim", "veniam", "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi", "ut",
    "aliquip", "ex", "ea", "commodo", "consequat", "duis", "aute", "irure", "in", "reprehenderit",
    "voluptate", "velit", "esse", "cillum", "fugiat", "nulla", "pariatur", "excepteur", "sint", "occaecat",
    "cupidatat", "non", "proident", "sunt", "culpa", "qui", "officia", "deserunt", "mollit", "anim"
]


def generate_cpf(formatted: bool = True) -> str:
    """Gera um CPF válido segundo o algoritmo oficial da Receita Federal."""
    digits = [random.randint(0, 9) for _ in range(9)]
    # 1º dígito verificador
    s1 = sum(v * (10 - i) for i, v in enumerate(digits))
    r1 = 11 - (s1 % 11)
    d1 = 0 if r1 >= 10 else r1
    digits.append(d1)

    # 2º dígito verificador
    s2 = sum(v * (11 - i) for i, v in enumerate(digits))
    r2 = 11 - (s2 % 11)
    d2 = 0 if r2 >= 10 else r2
    digits.append(d2)

    raw = "".join(str(d) for d in digits)
    if formatted:
        return f"{raw[:3]}.{raw[3:6]}.{raw[6:9]}-{raw[9:]}"
    return raw


def generate_cnpj(formatted: bool = True) -> str:
    """Gera um CNPJ válido com matriz 0001 segundo o algoritmo oficial."""
    digits = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(d * w for d, w in zip(digits, weights1))
    r1 = s1 % 11
    d1 = 0 if r1 < 2 else 11 - r1
    digits.append(d1)

    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(d * w for d, w in zip(digits, weights2))
    r2 = s2 % 11
    d2 = 0 if r2 < 2 else 11 - r2
    digits.append(d2)

    raw = "".join(str(d) for d in digits)
    if formatted:
        return f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:]}"
    return raw


def generate_rg(formatted: bool = True) -> str:
    """Gera um número de Registro Geral (RG) fictício."""
    raw = "".join(str(random.randint(0, 9)) for _ in range(9))
    if formatted:
        return f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}-{raw[8]}"
    return raw


def generate_person_name(gender: str = "both") -> str:
    """Gera um nome completo com 1 ou 2 sobrenomes."""
    if gender == "male":
        first = random.choice(FIRST_NAMES_MALE)
    elif gender == "female":
        first = random.choice(FIRST_NAMES_FEMALE)
    else:
        first = random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)

    n_lasts = random.choice([1, 2])
    chosen_lasts = random.sample(LAST_NAMES, n_lasts)
    return f"{first} {' '.join(chosen_lasts)}"


def generate_email(name: str) -> str:
    """Gera um e-mail limpo a partir de um nome."""
    import unicodedata
    clean = "".join(c for c in unicodedata.normalize("NFKD", name.lower()) if not unicodedata.combining(c))
    parts = clean.split()
    user = f"{parts[0]}.{parts[-1]}" if len(parts) > 1 else parts[0]
    user = "".join(c for c in user if c.isalnum() or c == ".")
    return f"{user}{random.randint(10, 99)}@{random.choice(EMAIL_DOMAINS)}"


def generate_phone(ddd: Optional[int] = None, formatted: bool = True) -> str:
    """Gera um número de celular brasileiro no formato (DD) 9XXXX-XXXX."""
    d = ddd or random.choice([11, 19, 21, 31, 41, 51, 61, 71, 81, 85])
    first_part = random.randint(1000, 9999)
    second_part = random.randint(1000, 9999)
    if formatted:
        return f"({d:02d}) 9{first_part:04d}-{second_part:04d}"
    return f"{d:02d}9{first_part:04d}{second_part:04d}"


def generate_address(formatted_cep: bool = True) -> Dict[str, str]:
    """Gera um endereço brasileiro completo coerente."""
    city, uf, ddd = random.choice(CITIES_BY_UF)
    street = f"{random.choice(STREET_PREFIXES)} {random.choice(STREET_NAMES)}"
    number = str(random.randint(10, 4999))
    neighborhood = random.choice(NEIGHBORHOODS)
    cep_raw = f"{random.randint(10000, 99999):05d}{random.randint(100, 999):03d}"
    cep = f"{cep_raw[:5]}-{cep_raw[5:]}" if formatted_cep else cep_raw
    return {
        "logradouro": street,
        "numero": number,
        "bairro": neighborhood,
        "cidade": city,
        "uf": uf,
        "cep": cep,
        "ddd": str(ddd)
    }


def generate_company() -> Dict[str, str]:
    """Gera dados de uma empresa fictícia."""
    p = random.choice(COMPANY_PREFIXES)
    s = random.choice(COMPANY_SUFFIXES)
    trade_name = f"{p} {s}"
    legal_name = f"{p} {s} Ltda."
    return {
        "razao_social": legal_name,
        "nome_fantasia": trade_name,
        "cnpj": generate_cnpj(formatted=True),
        "inscricao_estadual": "".join(str(random.randint(0, 9)) for _ in range(12))
    }


def generate_ipv4() -> str:
    """Gera um endereço IPv4 fictício."""
    return f"{random.randint(11, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def generate_mac_address() -> str:
    """Gera um endereço MAC hexadecimal."""
    return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))


def generate_lorem_ipsum(count: int = 3, unit: str = "paragraphs") -> str:
    """Gera texto Lorem Ipsum em parágrafos, frases ou palavras."""
    if unit == "words":
        words = [random.choice(LOREM_WORDS) for _ in range(max(1, count))]
        return " ".join(words)
    elif unit == "sentences":
        sentences = []
        for _ in range(max(1, count)):
            n_words = random.randint(8, 16)
            s_words = [random.choice(LOREM_WORDS) for _ in range(n_words)]
            sentences.append(" ".join(s_words).capitalize() + ".")
        return " ".join(sentences)
    else:  # paragraphs
        paragraphs = []
        for _ in range(max(1, count)):
            n_sent = random.randint(3, 6)
            sents = []
            for _ in range(n_sent):
                n_words = random.randint(8, 15)
                sents.append(" ".join(random.choice(LOREM_WORDS) for _ in range(n_words)).capitalize() + ".")
            paragraphs.append(" ".join(sents))
        return "\n\n".join(paragraphs)


AVAILABLE_FIELDS: Dict[str, str] = {
    "nome": "Nome Completo",
    "cpf": "CPF",
    "rg": "RG",
    "email": "E-mail",
    "telefone": "Telefone / Celular",
    "data_nasc": "Data de Nascimento",
    "cidade": "Cidade",
    "uf": "Estado (UF)",
    "logradouro": "Logradouro (Rua)",
    "numero": "Número",
    "bairro": "Bairro",
    "cep": "CEP",
    "empresa": "Razão Social",
    "cnpj": "CNPJ",
    "ipv4": "Endereço IP (v4)",
    "uuid": "Identificador UUID v4"
}


def generate_dataset(
    fields: Optional[List[str]] = None,
    count: int = 10,
    formatted_docs: bool = True
) -> List[Dict[str, Any]]:
    """Gera uma lista de registros fictícios com os campos selecionados."""
    if not fields:
        fields = ["nome", "cpf", "email", "telefone", "cidade", "uf"]

    records: List[Dict[str, Any]] = []
    for _ in range(max(1, min(count, 50000))):
        rec: Dict[str, Any] = {}
        # Gera entidades completas para consistência relacional
        name = generate_person_name()
        addr = generate_address(formatted_cep=formatted_docs)
        comp = generate_company()

        year = random.randint(1965, 2005)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        dob = f"{day:02d}/{month:02d}/{year}"

        for f in fields:
            if f == "nome":
                rec["nome"] = name
            elif f == "cpf":
                rec["cpf"] = generate_cpf(formatted=formatted_docs)
            elif f == "rg":
                rec["rg"] = generate_rg(formatted=formatted_docs)
            elif f == "email":
                rec["email"] = generate_email(name)
            elif f == "telefone":
                rec["telefone"] = generate_phone(ddd=int(addr["ddd"]), formatted=formatted_docs)
            elif f == "data_nasc":
                rec["data_nasc"] = dob
            elif f == "cidade":
                rec["cidade"] = addr["cidade"]
            elif f == "uf":
                rec["uf"] = addr["uf"]
            elif f == "logradouro":
                rec["logradouro"] = addr["logradouro"]
            elif f == "numero":
                rec["numero"] = addr["numero"]
            elif f == "bairro":
                rec["bairro"] = addr["bairro"]
            elif f == "cep":
                rec["cep"] = addr["cep"]
            elif f == "empresa":
                rec["empresa"] = comp["razao_social"]
            elif f == "cnpj":
                rec["cnpj"] = comp["cnpj"] if formatted_docs else comp["cnpj"].replace(".", "").replace("/", "").replace("-", "")
            elif f == "ipv4":
                rec["ipv4"] = generate_ipv4()
            elif f == "uuid":
                rec["uuid"] = str(uuid.uuid4())
            else:
                rec[f] = ""

        records.append(rec)
    return records


def export_dataset(
    data: List[Dict[str, Any]],
    format_type: str = "json",
    table_name: str = "usuarios"
) -> str:
    """Exporta o dataset gerado nos formatos JSON, CSV, SQL INSERT ou TXT."""
    fmt = format_type.lower().strip()
    if not data:
        return ""

    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)

    elif fmt == "csv":
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=list(data[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(data)
        return out.getvalue()

    elif fmt == "sql":
        cols = list(data[0].keys())
        cols_str = ", ".join(f"`{c}`" for c in cols)
        lines = []
        for row in data:
            vals = []
            for c in cols:
                v = str(row.get(c, "")).replace("'", "''")
                vals.append(f"'{v}'")
            lines.append(f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({', '.join(vals)});")
        return "\n".join(lines)

    else:  # txt / readable
        lines = []
        for i, row in enumerate(data, start=1):
            lines.append(f"--- Registro #{i} ---")
            for k, v in row.items():
                label = AVAILABLE_FIELDS.get(k, k)
                lines.append(f"{label}: {v}")
            lines.append("")
        return "\n".join(lines)

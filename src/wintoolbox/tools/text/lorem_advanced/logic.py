"""
Lógica pura para geração de textos fictícios (Dummy Text / Lorem Ipsum) temáticos.

Oferece vocabulários temáticos especializados em Português e Latim:
- Clássico (Latim de Cícero)
- Corporativo / Startup (Jargões ágeis, stakeholders, sinergia)
- Jurídico / Forense (Termos processuais, acórdão, data venia)
- Gastronomia (Culinária contemporânea e técnicas gourmet)
- Ficção Científica / Cyberpunk (Naves, matriz neural, quântico)

Permite controle exato por palavras, frases ou parágrafos em texto, HTML ou Markdown.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import random
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("text.lorem_advanced.logic")

THEME_VOCABULARY: Dict[str, Dict[str, Any]] = {
    "classico": {
        "lead": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "words": [
            "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
            "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
            "et", "dolore", "magna", "aliqua", "enim", "ad", "minim", "veniam",
            "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi", "aliquip",
            "ex", "ea", "commodo", "consequat", "duis", "aute", "irure", "in",
            "reprehenderit", "voluptate", "velit", "esse", "cillum", "fugiat", "nulla"
        ],
        "sentences": [
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.",
            "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum.",
            "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia.",
            "Curabitur pretium tincidunt lacus, nec vehicula libero lacinia a.",
            "Pellentesque habitant morbi tristique senectus et netus et malesuada fames.",
            "Integer euismod lacus luctus magna posuere dictum.",
        ]
    },
    "corporativo": {
        "lead": "Nossa proposta de valor busca potencializar a sinergia entre stakeholders e acelerar o roadmap estratégico.",
        "words": [
            "sinergia", "stakeholders", "mindset", "disrupção", "escalabilidade",
            "deliverables", "pipeline", "benchmarking", "core-business", "pain-point",
            "otimização", "paradigma", "alavancagem", "proatividade", "sprint",
            "resiliência", "compliance", "engajamento", "turnaround", "framework"
        ],
        "sentences": [
            "Nossa proposta de valor busca potencializar a sinergia entre stakeholders e acelerar o roadmap estratégico.",
            "Precisamos pivotar o modelo operacional para mitigar riscos de compliance e maximizar o ROI trimestral.",
            "A metodologia ágil implementada no squad viabilizou a entrega contínua dos key-results estabelecidos.",
            "O alinhamento horizontal das lideranças garantiu maior tração no go-to-market da solução corporativa.",
            "Mapeamos os principais pain-points da jornada do cliente para desenhar um MVP com diferenciais competitivos.",
            "A alavancagem de dados em tempo real fomenta tomadas de decisão baseadas em evidências analíticas robustas.",
            "Identificamos oportunidades de cross-selling através de um benchmarking aprofundado dos concorrentes diretos.",
        ]
    },
    "juridico": {
        "lead": "Data venia, restou cabalmente demonstrada a inexistência de nexo causal entre a conduta e o alegado prejuízo.",
        "words": [
            "jurisprudência", "acórdão", "sucumbência", "liminar", "tutela",
            "preclusão", "exordial", "tempestividade", "embargos", "prescrição",
            "decadência", "nexo", "causal", "adimplemento", "litisconsórcio",
            "honorários", "procuração", "contraditório", "deferimento", "agravo"
        ],
        "sentences": [
            "Data venia, restou cabalmente demonstrada a inexistência de nexo causal entre a conduta e o alegado prejuízo.",
            "O acórdão paradigma deste Egrégio Tribunal consolidou entendimento pacífico sobre a matéria controvertida.",
            "A concessão da tutela de urgência antecipada faz-se imperiosa diante da plausibilidade do direito invocado.",
            "Operou-se o trânsito em julgado da respeitável decisão, não remanescendo qualquer recurso cabível aos autos.",
            "As razões recursais deduzidas carecem de fundamentação idônea capaz de infirmar o provimento jurisdicional exarado.",
            "O princípio da ampla defesa e do contraditório impõe a observância irrestrita do rito procedimental legal.",
            "Requer-se a condenação da parte adversa ao pagamento das custas processuais e honorários advocatícios sucumbenciais.",
        ]
    },
    "gastronomia": {
        "lead": "Iniciamos com uma emulsão aveludada de trufas negras sobre crosta crocante de sourdough artesanal.",
        "words": [
            "emulsão", "sous-vide", "redução", "balsâmico", "brunoise",
            "crosta", "harmonização", "terroir", "defumação", "confit",
            "infusão", "aromático", "frescor", "aveludado", "texturas",
            "caramelização", "parfait", "sorbet", "carpaccio", "marinada"
        ],
        "sentences": [
            "Iniciamos com uma emulsão aveludada de trufas negras sobre crosta crocante de sourdough artesanal.",
            "O lombo cozido em sous-vide por quarenta horas desmancha harmoniosamente com a redução de vinho do Porto.",
            "Uma brunoise delicada de legumes da estação acrescenta crocância e frescor ao prato principal.",
            "Finalizamos a degustação com um parfait cítrico aromatizado com raspas de limão siciliano e flor de sal.",
            "A harmonização com vinhos biodinâmicos evidencia notas minerais e taninos elegantes no paladar.",
            "A técnica milenar de fermentação natural ressalta aromas terrosos e uma acidez perfeitamente equilibrada.",
        ]
    },
    "sci_fi": {
        "lead": "O salto hiperespacial foi calibrado enquanto as matrizes quânticas estabilizavam o reator de antimatéria.",
        "words": [
            "hiperespacial", "quântico", "antimatéria", "cibernético", "nanobots",
            "androide", "propulsão", "telepatia", "teletransporte", "distopia",
            "ciberespaço", "reator", "singularidade", "exoesqueleto", "buraco de minhoca",
            "holográfico", "sintético", "anomalia", "neural", "plasma"
        ],
        "sentences": [
            "O salto hiperespacial foi calibrado enquanto as matrizes quânticas estabilizavam o reator de antimatéria.",
            "A interface neural direta permitia ao piloto controlar os propulsores de plasma na velocidade do pensamento.",
            "Detectamos uma anomalia temporal na órbita do buraco negro supermassivo no setor periférico da galáxia.",
            "Os nanobots de regeneração celular foram ativados para reparar a carcaça de titânio do exoesqueleto.",
            "A inteligência artificial autônoma da estação orbital detectou assinaturas taquiônicas desconhecidas.",
            "Uma tempestade eletromagnética sobrecarregou os escudos de deflexão e isolou as comunicações interestelares.",
        ]
    }
}


def generate_lorem_text(
    theme: str = "corporativo",
    unit: str = "paragraphs",  # "paragraphs", "sentences", "words"
    count: int = 3,
    output_format: str = "text",  # "text", "html", "markdown"
    start_with_lead: bool = True
) -> str:
    """
    Gera texto fictício coerente baseado no tema e quantidade solicitados.
    """
    vocab_theme = THEME_VOCABULARY.get(theme.lower(), THEME_VOCABULARY["corporativo"])
    sentences_pool = vocab_theme["sentences"]
    words_pool = vocab_theme["words"]
    lead_sentence = vocab_theme["lead"]

    num = max(1, count)

    if unit == "words":
        words_list: List[str] = []
        if start_with_lead and lead_sentence:
            words_list.extend(lead_sentence.split()[:min(num, len(lead_sentence.split()))])

        while len(words_list) < num:
            words_list.append(random.choice(words_pool))

        raw_result = " ".join(words_list[:num]).capitalize() + "."
        return raw_result

    elif unit == "sentences":
        chosen_sentences: List[str] = []
        if start_with_lead and lead_sentence:
            chosen_sentences.append(lead_sentence)

        while len(chosen_sentences) < num:
            s = random.choice(sentences_pool)
            if s not in chosen_sentences:
                chosen_sentences.append(s)

        final_sentences = chosen_sentences[:num]

        if output_format == "html":
            return "".join(f"<p>{s}</p>\n" for s in final_sentences).strip()
        elif output_format == "markdown":
            return "".join(f"- {s}\n" for s in final_sentences).strip()
        else:
            return " ".join(final_sentences)

    else:
        # Paragraphs (padrão)
        paragraphs: List[str] = []
        for p_idx in range(num):
            p_sentences: List[str] = []
            if p_idx == 0 and start_with_lead and lead_sentence:
                p_sentences.append(lead_sentence)

            # Cada parágrafo tem de 3 a 5 frases
            p_size = random.randint(3, 5)
            while len(p_sentences) < p_size:
                p_sentences.append(random.choice(sentences_pool))

            paragraph_text = " ".join(p_sentences)
            paragraphs.append(paragraph_text)

        if output_format == "html":
            return "\n\n".join(f"<p>{p}</p>" for p in paragraphs)
        elif output_format == "markdown":
            return "\n\n".join(f"> {p}" for p in paragraphs)
        else:
            return "\n\n".join(paragraphs)

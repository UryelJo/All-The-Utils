"""
Lógica pura para o sistema de repetição espaçada SuperMemo (SM-2) e cartões de estudo (Flashcards).
Totalmente desacoplada de frameworks de interface gráfica.
"""
import csv
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid


@dataclass
class Flashcard:
    id: str
    deck_id: str
    front: str  # Pergunta / Termo
    back: str   # Resposta / Definição
    repetition: int = 0
    interval: int = 0  # em dias
    easiness_factor: float = 2.5
    next_review: str = field(default_factory=lambda: date.today().isoformat())


@dataclass
class Deck:
    id: str
    name: str
    description: str = ""


def calculate_sm2(card: Flashcard, quality: int, current_date: Optional[date] = None) -> Flashcard:
    """
    Executa uma iteração do algoritmo SuperMemo SM-2.
    quality: escala de 0 a 5:
      0: Esquecimento total / apagão mental
      1: Resposta incorreta, mas lembrou ao ver a resposta
      2: Resposta incorreta, mas parecia fácil
      3: Resposta correta com bastante dificuldade
      4: Resposta correta com pequena hesitação
      5: Resposta perfeita e imediata
    """
    if quality < 0:
        quality = 0
    elif quality > 5:
        quality = 5

    ref_date = current_date or date.today()

    rep = card.repetition
    interval = card.interval
    ef = card.easiness_factor

    if quality >= 3:
        if rep == 0:
            interval = 1
        elif rep == 1:
            interval = 6
        else:
            interval = int(round(interval * ef))
        rep += 1
    else:
        rep = 0
        interval = 1

    # Atualização do Fator de Facilidade (EF)
    ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ef < 1.3:
        ef = 1.3

    next_rev = ref_date + timedelta(days=interval)

    return Flashcard(
        id=card.id,
        deck_id=card.deck_id,
        front=card.front,
        back=card.back,
        repetition=rep,
        interval=interval,
        easiness_factor=round(ef, 2),
        next_review=next_rev.isoformat()
    )


def is_card_due(card: Flashcard, current_date: Optional[date] = None) -> bool:
    """Verifica se o cartão está pendente de revisão na data especificada."""
    ref_date = current_date or date.today()
    if not card.next_review:
        return True
    try:
        due = date.fromisoformat(card.next_review)
        return due <= ref_date
    except Exception:
        return True


def import_flashcards_from_csv(csv_content: str, deck_id: str, delimiter: str = ",") -> List[Flashcard]:
    """Importa cartões a partir de texto CSV (formato: frente,verso)."""
    cards: List[Flashcard] = []
    reader = csv.reader(io.StringIO(csv_content), delimiter=delimiter)
    for row in reader:
        if len(row) >= 2:
            front = row[0].strip()
            back = row[1].strip()
            if front or back:
                cards.append(Flashcard(
                    id=str(uuid.uuid4()),
                    deck_id=deck_id,
                    front=front,
                    back=back,
                    next_review=date.today().isoformat()
                ))
    return cards


def export_flashcards_to_csv(cards: List[Flashcard], delimiter: str = ",") -> str:
    """Exporta lista de cartões para formato CSV."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=delimiter)
    for c in cards:
        writer.writerow([c.front, c.back])
    return out.getvalue()


def get_default_decks_and_cards() -> Tuple[List[Deck], List[Flashcard]]:
    """Gera dados iniciais de exemplo para novos usuários."""
    d1_id = "deck_atalhos_win"
    d2_id = "deck_termos_dev"

    decks = [
        Deck(id=d1_id, name="Atalhos do Windows 11", description="Atalhos úteis para produtividade diária"),
        Deck(id=d2_id, name="Conceitos de Engenharia de Software", description="Termos e princípios essenciais de desenvolvimento"),
    ]

    cards = [
        Flashcard(id=str(uuid.uuid4()), deck_id=d1_id, front="Win + V", back="Abre o histórico da área de transferência"),
        Flashcard(id=str(uuid.uuid4()), deck_id=d1_id, front="Win + Shift + S", back="Ferramenta de captura de tela nativa"),
        Flashcard(id=str(uuid.uuid4()), deck_id=d1_id, front="Win + .", back="Abre o painel de emojis e símbolos"),
        Flashcard(id=str(uuid.uuid4()), deck_id=d2_id, front="O que significa DRY?", back="Don't Repeat Yourself - Evite duplicação de lógica"),
        Flashcard(id=str(uuid.uuid4()), deck_id=d2_id, front="O que é o princípio da Responsabilidade Única (SRP)?", back="Uma classe/módulo deve ter apenas uma única razão para mudar"),
    ]

    return decks, cards


def save_flashcards_data(decks: List[Deck], cards: List[Flashcard], path: Path) -> None:
    """Salva decks e cartões em formato JSON."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "decks": [asdict(d) for d in decks],
        "cards": [asdict(c) for c in cards]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_flashcards_data(path: Path) -> Tuple[List[Deck], List[Flashcard]]:
    """Carrega decks e cartões do disco. Cria padrão caso não exista."""
    path = Path(path).resolve()
    if not path.is_file():
        return get_default_decks_and_cards()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    decks = [Deck(id=d["id"], name=d["name"], description=d.get("description", "")) for d in data.get("decks", [])]
    cards = []
    for c in data.get("cards", []):
        cards.append(Flashcard(
            id=c.get("id", str(uuid.uuid4())),
            deck_id=c.get("deck_id", ""),
            front=c.get("front", ""),
            back=c.get("back", ""),
            repetition=c.get("repetition", 0),
            interval=c.get("interval", 0),
            easiness_factor=c.get("easiness_factor", 2.5),
            next_review=c.get("next_review", date.today().isoformat())
        ))

    return decks, cards

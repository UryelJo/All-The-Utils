"""
Testes unitários para o sistema de repetição espaçada SM-2 e Flashcards.
Diretrizes Anti-Gambiarra: Validação determinística do algoritmo SM-2 e de arquivos gerados.
"""
from datetime import date, timedelta
from pathlib import Path
from wintoolbox.tools.productivity.flashcards.logic import (
    Deck,
    Flashcard,
    calculate_sm2,
    export_flashcards_to_csv,
    import_flashcards_from_csv,
    is_card_due,
    load_flashcards_data,
    save_flashcards_data,
)


def test_sm2_algorithm():
    card = Flashcard(id="c1", deck_id="d1", front="Hello", back="Olá", repetition=0, interval=0, easiness_factor=2.5)
    today = date(2026, 10, 27)

    # Primeira resposta correta com perfeição (quality=5)
    c1 = calculate_sm2(card, quality=5, current_date=today)
    assert c1.repetition == 1
    assert c1.interval == 1
    assert c1.next_review == (today + timedelta(days=1)).isoformat()
    assert c1.easiness_factor == 2.6  # 2.5 + (0.1 - 0) = 2.6

    # Segunda resposta correta (quality=4)
    c2 = calculate_sm2(c1, quality=4, current_date=today + timedelta(days=1))
    assert c2.repetition == 2
    assert c2.interval == 6
    assert c2.next_review == (today + timedelta(days=7)).isoformat()

    # Falha na terceira repetição (quality=1) -> reinicia repetição e intervalo volta para 1
    c3 = calculate_sm2(c2, quality=1, current_date=today + timedelta(days=7))
    assert c3.repetition == 0
    assert c3.interval == 1
    assert c3.next_review == (today + timedelta(days=8)).isoformat()


def test_is_card_due():
    today = date(2026, 10, 27)
    past_card = Flashcard(id="c1", deck_id="d1", front="A", back="B", next_review="2026-10-25")
    today_card = Flashcard(id="c2", deck_id="d1", front="A", back="B", next_review="2026-10-27")
    future_card = Flashcard(id="c3", deck_id="d1", front="A", back="B", next_review="2026-10-28")

    assert is_card_due(past_card, today) is True
    assert is_card_due(today_card, today) is True
    assert is_card_due(future_card, today) is False


def test_flashcards_csv_roundtrip():
    csv_raw = "Cachorro,Dog\nGato,Cat\n"
    cards = import_flashcards_from_csv(csv_raw, deck_id="deck_test")

    assert len(cards) == 2
    assert cards[0].front == "Cachorro"
    assert cards[0].back == "Dog"
    assert cards[1].front == "Gato"
    assert cards[1].back == "Cat"

    exported = export_flashcards_to_csv(cards)
    assert "Cachorro,Dog" in exported
    assert "Gato,Cat" in exported


def test_flashcards_persistence(tmp_path: Path):
    decks = [Deck(id="d1", name="Deck Teste", description="Desc")]
    cards = [Flashcard(id="c1", deck_id="d1", front="Q1", back="A1")]
    file_path = tmp_path / "cards_teste.json"

    save_flashcards_data(decks, cards, file_path)
    assert file_path.is_file()

    loaded_decks, loaded_cards = load_flashcards_data(file_path)
    assert len(loaded_decks) == 1
    assert loaded_decks[0].name == "Deck Teste"
    assert len(loaded_cards) == 1
    assert loaded_cards[0].front == "Q1"
    assert loaded_cards[0].back == "A1"

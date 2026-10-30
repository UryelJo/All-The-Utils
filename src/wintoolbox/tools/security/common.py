"""Listas internas compartilhadas pelas ferramentas de quebra de hashes."""
from __future__ import annotations

from typing import List

# As 100 senhas mais usadas em vazamentos públicos. Servem como fallback quando
# o usuário não seleciona uma wordlist e jamais são tratadas como prova de força.
SENHAS_COMUNS: List[str] = [
    "123456", "password", "123456789", "12345678", "12345", "qwerty", "1234567",
    "111111", "123123", "abc123", "1234567890", "1234", "password1", "iloveyou",
    "000000", "12345qwert", "qwerty123", "1q2w3e4r", "admin", "letmein", "welcome",
    "monkey", "dragon", "sunshine", "princess", "football", "baseball", "master",
    "shadow", "superman", "michael", "mustang", "jennifer", "hunter", "freedom",
    "whatever", "trustno1", "computer", "maggie", "buster", "soccer", "batman",
    "pepper", "daniel", "access", "flower", "hello", "charlie", "donald", "secret",
    "qazwsx", "password123", "passw0rd", "p@ssw0rd", "admin123", "root", "toor",
    "1qaz2wsx", "zaq12wsx", "qwe123", "asdfgh", "zxcvbn", "qwertyuiop", "1q2w3e",
    "123321", "654321", "666666", "888888", "121212", "112233", "131313", "aaaaaa",
    "lovely", "andrew", "joshua", "amanda", "summer", "winter", "spring", "autumn",
    "starwars", "pokemon", "naruto", "minecraft", "matrix", "internet", "service",
    "default", "changeme", "teste", "senha", "brasil", "flamengo", "corinthians",
    "palmeiras", "saopaulo", "gremio", "vasco", "cruzeiro", "santos", "botafogo",
    "familia", "amoreterno", "deusefiel", "jesuscristo", "bemvindo", "primeiro",
]

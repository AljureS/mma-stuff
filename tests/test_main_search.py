"""Pruebas de la búsqueda local de peleadores en api/main.py (sin servidor ni Redis)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'api'))
sys.path.insert(0, str(ROOT / 'scripts'))

import main  # noqa: E402  (importar no levanta uvicorn; Redis no conecta hasta el primer comando)


@pytest.fixture
def fighter_db(monkeypatch):
    df = pd.DataFrame([
        {'name': 'Natalia Silva', 'wins': 19, 'losses': 5, 'draws': 1},
        {'name': 'Jean Silva', 'wins': 19, 'losses': 12, 'draws': 3},
        {'name': 'Jon Jones', 'wins': 28, 'losses': 1, 'draws': 0},
        {'name': "Sean O'Malley", 'wins': 18, 'losses': 3, 'draws': 0},
    ])
    monkeypatch.setattr(main, 'fighter_database', df)
    return df


def test_exact_match_wins_over_substring(fighter_db):
    assert main._search_in_database('Jean Silva')['name'] == 'Jean Silva'


def test_case_insensitive_exact_match_with_spaces(fighter_db):
    assert main._search_in_database('  jon jones ')['name'] == 'Jon Jones'


def test_unique_substring_is_accepted(fighter_db):
    assert main._search_in_database('Jones')['name'] == 'Jon Jones'


def test_ambiguous_substring_returns_none(fighter_db):
    assert main._search_in_database('Silva') is None


def test_regex_special_characters_are_literal(fighter_db):
    assert main._search_in_database('(') is None
    assert main._search_in_database("O'Malley")['name'] == "Sean O'Malley"


def test_empty_query_returns_none(fighter_db):
    assert main._search_in_database('   ') is None

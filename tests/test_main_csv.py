"""Pruebas de la escritura del CSV de peleadores en api/main.py (sin servidor ni Redis)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'api'))
sys.path.insert(0, str(ROOT / 'scripts'))

import main  # noqa: E402

COLUMNS = ['name', 'wins', 'losses', 'draws', 'height', 'reach', 'age', 'weight_class', 'ranking',
           'striking_accuracy', 'striking_defense', 'takedown_accuracy', 'takedown_defense',
           'last_updated', 'weight', 'stance', 'fight_history']


@pytest.fixture
def csv_path(tmp_path, monkeypatch):
    path = tmp_path / 'fighters.csv'
    pd.DataFrame([
        {'name': 'Jon Jones', 'wins': 27, 'losses': 1, 'draws': 0, 'height': 193.0, 'reach': 213.4, 'age': 30,
         'weight_class': 'heavyweight', 'ranking': None, 'striking_accuracy': 50.0, 'striking_defense': 55.0,
         'takedown_accuracy': 40.0, 'takedown_defense': 70.0, 'last_updated': '2025-10-15T20:44:27',
         'weight': 248.0, 'stance': 'Orthodox', 'fight_history': '[]'},
    ], columns=COLUMNS).to_csv(path, index=False)
    monkeypatch.setattr(main, 'CSV_PATH', path)
    return path


def test_update_existing_fighter_with_list_values(csv_path):
    main._update_or_add_to_csv({
        'name': 'Jon Jones', 'wins': 28, 'striking_accuracy': 58.0, 'age': 38,
        'fight_history': [{'result': 'win', 'opponent': 'Stipe Miocic'}],
    })

    df = pd.read_csv(csv_path)
    row = df[df.name == 'Jon Jones'].iloc[0]
    assert len(df) == 1
    assert (row['wins'], row['striking_accuracy'], row['age']) == (28, 58.0, 38)
    assert row['last_updated'].startswith('20')
    assert 'Stipe Miocic' in row['fight_history']
    assert not csv_path.with_name(csv_path.name + '.tmp').exists()


def test_add_new_fighter_keeps_csv_schema(csv_path):
    main._update_or_add_to_csv({
        'name': 'Raul Rosas Jr.', 'wins': 12, 'losses': 1, 'draws': 0, 'weight_class': 'bantamweight',
        'fight_history': [], 'significant_strikes_per_minute': 1.34,  # clave fuera del esquema
    })

    df = pd.read_csv(csv_path)
    assert list(df.columns) == COLUMNS + ['next_fight_date']
    assert len(df) == 2
    assert df[df.name == 'Raul Rosas Jr.'].iloc[0]['wins'] == 12


def test_update_existing_fighter_clears_next_fight_date(csv_path):
    df = pd.read_csv(csv_path)
    df['next_fight_date'] = '2026-09-26'
    df.to_csv(csv_path, index=False)

    main._update_or_add_to_csv({'name': 'Jon Jones', 'next_fight_date': None})

    row = pd.read_csv(csv_path).iloc[0]
    assert pd.isna(row['next_fight_date'])


def test_reload_reads_the_configured_path(csv_path):
    main._reload_fighter_database()
    assert list(main.fighter_database.name) == ['Jon Jones']

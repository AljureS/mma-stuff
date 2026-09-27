"""Pruebas de frescura, refresh forzado y versión del cache sin servicios externos."""

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'api'))
sys.path.insert(0, str(ROOT / 'scripts'))

import data_collection  # noqa: E402
import main  # noqa: E402


@pytest.fixture(autouse=True)
def default_freshness_config(monkeypatch):
    monkeypatch.setattr(main, 'FIGHTER_MAX_AGE_HOURS', 24.0)
    monkeypatch.setattr(main, 'FIGHTER_MIN_RECHECK_MINUTES', 30.0)


# fight_offset_days: None = sin pelea programada; -1 = ayer; 0 = hoy; nan = celda vacía del CSV.
# Las fechas se construyen DENTRO del test (no en la recolección) para que una corrida que cruce
# medianoche no cambie el significado de 'ayer'/'hoy' antes de la aserción.
@pytest.mark.parametrize(('age', 'fight_offset_days', 'expected'), [
    (timedelta(hours=2), None, True),
    (timedelta(hours=30), None, False),
    (timedelta(hours=2), -1, False),
    (timedelta(minutes=5), -1, True),
    (timedelta(hours=2), 0, True),
    (timedelta(hours=2), float('nan'), True),
    (timedelta(hours=-5), None, False),   # last_updated en el futuro (CSV de otro host/zona horaria)
    (timedelta(hours=-5), -1, False),
])
def test_freshness_by_age_and_fight_date(age, fight_offset_days, expected):
    if isinstance(fight_offset_days, int):
        fight_date = (date.today() + timedelta(days=fight_offset_days)).isoformat()
    else:
        fight_date = fight_offset_days
    fighter = {
        'name': 'Jon Jones',
        'last_updated': (datetime.now() - age).isoformat(),
        'next_fight_date': fight_date,
    }
    assert main._is_data_fresh(fighter) is expected


def test_timezone_aware_last_updated_is_normalized_to_local_naive():
    aware = (datetime.now().astimezone() - timedelta(hours=2)).astimezone(timezone.utc)
    parsed = main._parse_last_updated(aware.isoformat())
    assert parsed.tzinfo is None
    assert abs((datetime.now() - parsed) - timedelta(hours=2)) < timedelta(minutes=1)
    assert main._is_data_fresh({'name': 'Jon Jones', 'last_updated': aware.isoformat()}) is True
    # antes: datetime.now() - aware -> TypeError y GET /fighter respondía 500
    assert (datetime.now() - parsed).total_seconds() > 0


def test_nan_last_updated_is_stale():
    assert main._is_data_fresh({'last_updated': float('nan')}) is False


@pytest.fixture
def fresh_fighter_csv(tmp_path, monkeypatch):
    path = tmp_path / 'fighters.csv'
    row = {
        'name': 'Jon Jones', 'wins': 28, 'losses': 1, 'draws': 0,
        'last_updated': datetime.now().isoformat(), 'next_fight_date': None,
    }
    pd.DataFrame([row]).to_csv(path, index=False)
    monkeypatch.setattr(main, 'CSV_PATH', path)
    monkeypatch.setattr(main, 'fighter_database', pd.read_csv(path))
    return path


def test_force_refresh_scrapes_even_when_fresh(fresh_fighter_csv, monkeypatch):
    calls = []

    def scrape(self, name):
        calls.append(name)
        return {'name': 'Jon Jones', 'wins': 29, 'losses': 1, 'draws': 0,
                'next_fight_date': None}

    monkeypatch.setattr(data_collection.MMADataCollector, 'search_and_scrape_fighter', scrape)

    result = main.get_fighter_data('Jon Jones', force_refresh=True)

    assert calls == ['Jon Jones']
    assert result['wins'] == 29
    assert pd.read_csv(fresh_fighter_csv).iloc[0]['wins'] == 29


def test_fresh_data_skips_scraper(fresh_fighter_csv, monkeypatch):
    def scrape(self, name):
        pytest.fail('fresh data should not trigger scraping')

    monkeypatch.setattr(data_collection.MMADataCollector, 'search_and_scrape_fighter', scrape)

    assert main.get_fighter_data('Jon Jones')['wins'] == 28


def test_cache_key_tracks_stamps_and_order():
    original = main._normalize_cache_key(' Jon Jones ', 'Stipe Miocic', 'stamp-j', 'stamp-s')
    reversed_order = main._normalize_cache_key('STIPE MIOCIC', 'jon jones', 'stamp-s', 'stamp-j')
    refreshed = main._normalize_cache_key('Jon Jones', 'Stipe Miocic', 'new-j', 'stamp-s', include_llm_analysis=False)

    assert original == reversed_order
    assert original != refreshed


def test_cache_key_tracks_request_options_that_change_the_response():
    base = main._normalize_cache_key('Jon Jones', 'Stipe Miocic', 's1', 's2')
    title = main._normalize_cache_key('Jon Jones', 'Stipe Miocic', 's1', 's2', title_fight=True)
    no_llm = main._normalize_cache_key('Jon Jones', 'Stipe Miocic', 's1', 's2', include_llm_analysis=False)

    assert base.endswith(':title=0:llm=1')
    assert len({base, title, no_llm}) == 3


def test_predict_cache_is_checked_after_fighter_refresh(monkeypatch):
    stamps = {'Jon Jones': 'old-j', 'Stipe Miocic': 'stamp-s'}
    refresh_flags = []

    def fighter_data(name, force_refresh=False):
        refresh_flags.append((name, force_refresh))
        return {'name': name, 'wins': 28, 'losses': 1, 'last_updated': stamps[name]}

    class FakeModel:
        calls = 0

        def predict_proba(self, features):
            self.calls += 1
            return [[0.4, 0.6]]

    class FakeRedis:
        def __init__(self):
            self.values = {}
            self.read_keys = []

        def get(self, key):
            self.read_keys.append(key)
            return self.values.get(key)

        def setex(self, key, ttl, value):
            assert ttl == 3600
            self.values[key] = value

    model = FakeModel()
    cache = FakeRedis()
    monkeypatch.setattr(main, 'prediction_model', model)
    monkeypatch.setattr(main, 'redis_client', cache)
    monkeypatch.setattr(main, 'get_fighter_data', fighter_data)

    request = main.FightPredictionRequest(
        fighter_a='Jon Jones', fighter_b='Stipe Miocic', include_llm_analysis=False,
    )
    asyncio.run(main.predict_fight(request))
    stamps['Jon Jones'] = 'new-j'
    asyncio.run(main.predict_fight(request.model_copy(update={'force_refresh': True})))
    asyncio.run(main.predict_fight(request))

    assert model.calls == 2
    assert cache.read_keys == [
        main._normalize_cache_key('Jon Jones', 'Stipe Miocic', 'old-j', 'stamp-s', include_llm_analysis=False),
        main._normalize_cache_key('Jon Jones', 'Stipe Miocic', 'new-j', 'stamp-s', include_llm_analysis=False),
        main._normalize_cache_key('Jon Jones', 'Stipe Miocic', 'new-j', 'stamp-s', include_llm_analysis=False),
    ]
    assert ('Jon Jones', True) in refresh_flags
    assert ('Stipe Miocic', True) in refresh_flags

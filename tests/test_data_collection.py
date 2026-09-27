"""Pruebas offline del challenge y de los parsers de UFCStats."""

import hashlib
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from data_collection import MMADataCollector


FIXTURES = Path(__file__).parent / 'fixtures'
PROFILE_URL = 'http://ufcstats.com/fighter-details/fe2babf95de24fb1'


def html_response(filename):
    content = (FIXTURES / filename).read_bytes()
    return SimpleNamespace(text=content.decode('utf-8'), content=content, status_code=200)


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.get_calls = []
        self.post_calls = []

    def get(self, url, timeout):
        self.get_calls.append((url, timeout))
        return next(self.responses)

    def post(self, url, data, timeout):
        self.post_calls.append((url, data, timeout))
        return SimpleNamespace(status_code=204)


def collector_with_responses(*responses):
    collector = MMADataCollector()
    collector.request_delay = 0
    collector.session = FakeSession(responses)
    return collector


def test_challenge_is_solved_once_before_parsing_list():
    collector = collector_with_responses(
        html_response('ufcstats_challenge.html'),
        html_response('ufcstats_fighters_R.html'),
        html_response('ufcstats_fighter_rosas_jr.html'),
    )

    result = collector.search_and_scrape_fighter('Raul Rosas Jr.')

    assert result is not None
    assert len(collector.session.post_calls) == 1
    url, data, timeout = collector.session.post_calls[0]
    assert url == 'http://ufcstats.com/__c'
    assert data['nonce'] == '5ced8977889ef36c'
    assert hashlib.sha256(f"{data['nonce']}:{data['n']}".encode()).hexdigest().startswith('00')
    assert timeout == 15
    assert len(collector.session.get_calls) == 3
    assert collector.session.get_calls[0] == collector.session.get_calls[1]


def test_list_parser_uses_surname_and_returns_real_roster_values():
    collector = collector_with_responses(
        html_response('ufcstats_fighters_R.html'),
        html_response('ufcstats_fighter_rosas_jr.html'),
    )

    result = collector.search_and_scrape_fighter('Raul Rosas Jr.')

    assert 'char=R' in collector.session.get_calls[0][0]
    assert collector.session.get_calls[1][0] == PROFILE_URL
    assert result['name'] == 'Raul Rosas Jr.'
    assert (result['wins'], result['losses'], result['draws']) == (12, 1, 0)
    assert result['height'] == pytest.approx(175.26)
    assert result['reach'] == pytest.approx(170.18)
    assert result['weight'] == pytest.approx(135.0)
    assert result['stance'] == 'Switch'
    assert result['weight_class'] == 'bantamweight'
    assert result['striking_accuracy'] == 42.0
    assert result['takedown_defense'] == 25.0


def test_profile_parser_only_returns_csv_stats_and_age():
    collector = collector_with_responses(html_response('ufcstats_fighter_rosas_jr.html'))

    stats = collector.get_fighter_detailed_stats(PROFILE_URL)

    today = date.today()
    expected_age = today.year - 2004 - ((today.month, today.day) < (10, 8))
    assert stats['striking_accuracy'] == 42.0
    assert stats['striking_defense'] == 52.0
    assert stats['takedown_accuracy'] == 54.0
    assert stats['takedown_defense'] == 25.0
    assert stats['age'] == expected_age
    assert isinstance(stats['fight_history'], list)
    assert not {'slpm', 'significant_strikes_per_minute', 'sapm', 'td_avg',
                'height', 'weight', 'reach', 'stance'} & stats.keys()


def test_profile_get_also_solves_challenge():
    collector = collector_with_responses(
        html_response('ufcstats_challenge.html'),
        html_response('ufcstats_fighter_rosas_jr.html'),
    )

    stats = collector.get_fighter_detailed_stats(PROFILE_URL)

    assert stats['striking_accuracy'] == 42.0
    assert collector.session.get_calls == [(PROFILE_URL, 10), (PROFILE_URL, 10)]
    assert collector.session.post_calls[0][0] == 'http://ufcstats.com/__c'


@pytest.mark.parametrize('dob', ['--', 'not a date'])
def test_missing_or_invalid_dob_does_not_set_age(dob):
    profile = html_response('ufcstats_fighter_rosas_jr.html')
    profile.text = profile.text.replace('Oct 08, 2004', dob, 1)
    profile.content = profile.text.encode()
    collector = collector_with_responses(profile)

    assert 'age' not in collector.get_fighter_detailed_stats(PROFILE_URL)


@pytest.mark.parametrize(('name', 'letter'), [
    ('Raul Rosas Jr.', 'R'),
    ('Jon Jones', 'J'),
    ('Topuria', 'T'),
    ('Raul Rosas SR.', 'R'),
    ('Someone Smith III', 'S'),
])
def test_search_letter_ignores_name_suffixes(name, letter):
    assert MMADataCollector()._search_letter(name) == letter


def test_exact_match_wins_over_earlier_substring():
    roster = html_response('ufcstats_fighters_R.html')
    roster.text = roster.text.replace('>Benji</a>', '>Raul</a>', 1).replace('>Radach</a>', '>Rosas</a>', 1)
    roster.content = roster.text.encode()
    collector = collector_with_responses(roster, html_response('ufcstats_fighter_rosas_jr.html'))

    result = collector.search_and_scrape_fighter('Raul Rosas Jr.')

    assert result['name'] == 'Raul Rosas Jr.'
    assert collector.session.get_calls[1][0] == PROFILE_URL


def test_missing_fighter_returns_none_without_profile_get():
    collector = collector_with_responses(html_response('ufcstats_fighters_R.html'))

    assert collector.search_and_scrape_fighter('Nobody Rando') is None
    assert len(collector.session.get_calls) == 1
    assert collector.session.post_calls == []


def test_rate_limit_between_list_and_profile(monkeypatch):
    collector = collector_with_responses(
        html_response('ufcstats_fighters_R.html'),
        html_response('ufcstats_fighter_rosas_jr.html'),
    )
    collector.request_delay = 1.0
    delays = []
    monkeypatch.setattr('data_collection.time.sleep', delays.append)
    monkeypatch.setattr('data_collection._last_request_at', 0.0)  # el throttle es global: arrancar limpio

    assert collector.search_and_scrape_fighter('Raul Rosas Jr.') is not None
    # lista -> perfil: una espera de ~request_delay (el throttle es global y descuenta el tiempo transcurrido)
    assert len(delays) == 1
    assert delays[0] == pytest.approx(1.0, abs=0.05)


def test_rate_limit_covers_challenge_round_trip(monkeypatch):
    collector = collector_with_responses(
        html_response('ufcstats_challenge.html'),
        html_response('ufcstats_fighters_R.html'),
        html_response('ufcstats_fighter_rosas_jr.html'),
    )
    collector.request_delay = 1.0
    delays = []
    monkeypatch.setattr('data_collection.time.sleep', delays.append)
    monkeypatch.setattr('data_collection._last_request_at', 0.0)

    assert collector.search_and_scrape_fighter('Raul Rosas Jr.') is not None
    # GET challenge -> POST /__c -> GET lista -> GET perfil: 3 esperas entre 4 requests
    assert len(delays) == 3
    assert all(d == pytest.approx(1.0, abs=0.05) for d in delays)


def test_ambiguous_substring_returns_none_without_profile_get():
    collector = collector_with_responses(html_response('ufcstats_fighters_R.html'))

    # 'Rodriguez' matchea a Paul Rodriguez y Ricco Rodriguez -> ambiguo
    assert collector.search_and_scrape_fighter('Rodriguez') is None
    assert len(collector.session.get_calls) == 1


def test_unique_substring_is_accepted():
    collector = collector_with_responses(
        html_response('ufcstats_fighters_R.html'),
        html_response('ufcstats_fighter_rosas_jr.html'),
    )

    result = collector.search_and_scrape_fighter('Radach')

    assert result is not None
    assert result['name'] == 'Benji Radach'


def profile_with_unknown_stats(placeholder='--'):
    """Perfil real con las 4 métricas en '--' o '0%' (peleador sin peleas UFC registradas)."""
    soup = BeautifulSoup((FIXTURES / 'ufcstats_fighter_rosas_jr.html').read_bytes(), 'html.parser')
    for li in soup.find_all('li', class_='b-list__box-list-item'):
        title = li.find('i', class_='b-list__box-item-title')
        if title and title.get_text(strip=True).rstrip(':') in ('Str. Acc.', 'Str. Def', 'TD Acc.', 'TD Def.'):
            for node in list(li.children):
                if node is not title:
                    node.extract()
            li.append(' ' + placeholder)
    html = str(soup).encode()
    return SimpleNamespace(text=html.decode(), content=html, status_code=200)


@pytest.mark.parametrize('placeholder', ['--', '0%'])
def test_unknown_stats_are_not_stored_as_zero(placeholder):
    collector = collector_with_responses(profile_with_unknown_stats(placeholder))

    stats = collector.get_fighter_detailed_stats(PROFILE_URL)

    assert not {'striking_accuracy', 'striking_defense', 'takedown_accuracy', 'takedown_defense'} & stats.keys()
    assert stats['age'] > 0


def test_unknown_stats_fall_back_to_defaults():
    collector = collector_with_responses(html_response('ufcstats_fighters_R.html'), profile_with_unknown_stats())

    result = collector.search_and_scrape_fighter('Raul Rosas Jr.')

    assert (result['striking_accuracy'], result['striking_defense'],
            result['takedown_accuracy'], result['takedown_defense']) == (50.0, 55.0, 40.0, 70.0)


def test_single_zero_stat_is_kept():
    soup = BeautifulSoup((FIXTURES / 'ufcstats_fighter_rosas_jr.html').read_bytes(), 'html.parser')
    for li in soup.find_all('li', class_='b-list__box-list-item'):
        title = li.find('i', class_='b-list__box-item-title')
        if title and title.get_text(strip=True).rstrip(':') == 'TD Def.':
            for node in list(li.children):
                if node is not title:
                    node.extract()
            li.append(' 0%')
    html = str(soup).encode()
    collector = collector_with_responses(SimpleNamespace(text=html.decode(), content=html, status_code=200))

    stats = collector.get_fighter_detailed_stats(PROFILE_URL)

    assert stats['takedown_defense'] == 0.0
    assert stats['striking_accuracy'] == 42.0


def test_zero_stat_with_other_stats_unknown_is_kept():
    """LOW ronda 3: tres métricas en '--' y un 0% legítimo -> el cero se conserva (no son 'todas en cero')."""
    soup = BeautifulSoup((FIXTURES / 'ufcstats_fighter_rosas_jr.html').read_bytes(), 'html.parser')
    for li in soup.find_all('li', class_='b-list__box-list-item'):
        title = li.find('i', class_='b-list__box-item-title')
        label = title.get_text(strip=True).rstrip(':') if title else ''
        if label in ('Str. Acc.', 'Str. Def', 'TD Acc.', 'TD Def.'):
            for node in list(li.children):
                if node is not title:
                    node.extract()
            li.append(' 0%' if label == 'TD Def.' else ' --')
    html = str(soup).encode()
    collector = collector_with_responses(SimpleNamespace(text=html.decode(), content=html, status_code=200))

    stats = collector.get_fighter_detailed_stats(PROFILE_URL)

    assert stats == {**{k: v for k, v in stats.items() if k in ('age', 'fight_history')}, 'takedown_defense': 0.0}

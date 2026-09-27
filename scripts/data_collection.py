import hashlib
import logging
import re
import threading
import time
from datetime import date, datetime
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Rate limit compartido por TODAS las instancias (la API crea un collector por peleador,
# en threads distintos): nunca más de un request a UFCStats por `request_delay` segundos.
_throttle_lock = threading.Lock()
_last_request_at = 0.0


class MMADataCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.request_delay = 1.0

    def _throttle(self):
        """Esperar hasta que hayan pasado `request_delay` s desde el último request (global)."""
        global _last_request_at
        if self.request_delay <= 0:
            return
        with _throttle_lock:
            wait = self.request_delay - (time.monotonic() - _last_request_at)
            if wait > 0:
                time.sleep(wait)
            _last_request_at = time.monotonic()

    def _get(self, url, timeout):
        """GET con rate limit; resuelve una vez el challenge JS de UFCStats con la cookie de la sesión."""
        self._throttle()
        response = self.session.get(url, timeout=timeout)
        nonce_match = re.search(r'var nonce="([0-9a-f]+)"', response.text)
        if not nonce_match:
            return response

        zeros_match = re.search(r"target=new Array\((\d+)\+1\)\.join\('0'\)", response.text)
        if not zeros_match:
            logger.warning("UFCStats challenge has no difficulty for %s", url)
            return response

        nonce = nonce_match.group(1)
        target = '0' * int(zeros_match.group(1))
        for n in range(2_000_000):
            if hashlib.sha256(f'{nonce}:{n}'.encode()).hexdigest().startswith(target):
                break
        else:
            logger.warning("UFCStats challenge exceeded iteration limit for %s", url)
            return response

        parsed_url = urlsplit(url)
        challenge_url = f'{parsed_url.scheme}://{parsed_url.netloc}/__c'
        self._throttle()
        self.session.post(challenge_url, data={'nonce': nonce, 'n': n}, timeout=timeout)
        self._throttle()
        return self.session.get(url, timeout=timeout)

    def _search_letter(self, fighter_name):
        parts = fighter_name.split()
        while len(parts) > 1 and parts[-1].lower().rstrip('.') in {'jr', 'sr', 'ii', 'iii', 'iv'}:
            parts.pop()
        return parts[-1][0].upper() if parts else 'A'

    @staticmethod
    def _normalized_name(name):
        return ' '.join(re.sub(r'[.-]', ' ', name.lower()).split())

    def search_and_scrape_fighter(self, fighter_name: str) -> dict:
        """
        Buscar un peleador específico en UFCStats y scrapearlo

        Returns:
            dict: Datos del peleador o None si no se encuentra
        """
        logger.info("Searching for fighter: %s", fighter_name)

        try:
            last_name_letter = self._search_letter(fighter_name)
            list_url = f"http://ufcstats.com/statistics/fighters?char={last_name_letter}&page=all"
            logger.debug("Fetching fighter list: %s", list_url)
            response = self._get(list_url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')

            fighter_rows = soup.find_all('tr', class_='b-statistics__table-row')
            search_name = self._normalized_name(fighter_name)
            exact_match = None
            substring_matches = []
            for row in fighter_rows:
                cells = row.find_all('td')
                if len(cells) >= 10:
                    name_link = row.find('a', class_='b-link b-link_style_black')
                    if not name_link:
                        continue

                    first_name = cells[0].get_text(strip=True)
                    last_name = cells[1].get_text(strip=True)
                    full_name = f"{first_name} {last_name}".strip()
                    name = self._normalized_name(full_name)
                    if name == search_name:
                        if exact_match is None:
                            exact_match = (full_name, cells, name_link)
                    elif search_name and (search_name in name or name in search_name):
                        substring_matches.append((full_name, cells, name_link))

            # Sin match exacto, un substring solo vale si es único: "Rosas" en la página R da
            # Jessie Rosas y Raul Rosas Jr. -> None (la UI pide el nombre completo).
            match = exact_match
            if match is None and len(substring_matches) == 1:
                match = substring_matches[0]
            elif match is None and len(substring_matches) > 1:
                logger.warning("Ambiguous fighter name %s: %d candidates (%s)", fighter_name,
                               len(substring_matches), ', '.join(m[0] for m in substring_matches[:5]))
                return None
            if match:
                name, cells, name_link = match
                logger.info("Found fighter: %s", name)

                def safe_int(value_str, default=0):
                    try:
                        return int(float(value_str.strip()) if value_str.strip() else default)
                    except (TypeError, ValueError):
                        return default

                fighter_data = {
                    'name': name,
                    'height': self._parse_height(cells[3].get_text(strip=True)),
                    'weight': self._parse_weight(cells[4].get_text(strip=True)),
                    'reach': self._parse_reach(cells[5].get_text(strip=True)),
                    'stance': cells[6].get_text(strip=True) or 'Orthodox',
                    'wins': safe_int(cells[7].get_text(strip=True)),
                    'losses': safe_int(cells[8].get_text(strip=True)),
                    'draws': safe_int(cells[9].get_text(strip=True)),
                }

                profile_url = name_link.get('href')
                if profile_url:
                    logger.debug("Fetching detailed stats from: %s", profile_url)
                    detailed_stats = self.get_fighter_detailed_stats(profile_url)
                    fighter_data.update(detailed_stats)

                fighter_data.setdefault('age', 30)
                fighter_data['weight_class'] = self._infer_weight_class(fighter_data.get('weight', 0))
                fighter_data['ranking'] = None

                # Estadísticas con defaults
                fighter_data.setdefault('striking_accuracy', 50.0)
                fighter_data.setdefault('striking_defense', 55.0)
                fighter_data.setdefault('takedown_accuracy', 40.0)
                fighter_data.setdefault('takedown_defense', 70.0)

                logger.info("Successfully scraped: %s", fighter_data['name'])
                return fighter_data

            logger.warning("Fighter not found: %s", fighter_name)
            return None

        except Exception as e:
            logger.warning("Error scraping fighter %s: %s", fighter_name, e)
            return None
    
    def get_fighter_detailed_stats(self, profile_url):
        """Obtener estadísticas detalladas de un luchador"""
        try:
            response = self._get(profile_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            stats = {}
            for stat in soup.find_all('li', class_='b-list__box-list-item'):
                label = stat.find('i', class_='b-list__box-item-title')
                if not label:
                    continue
                label_text = label.get_text(strip=True).rstrip(':')
                full_text = stat.get_text(' ', strip=True)
                value_text = full_text[len(label.get_text(strip=True)):].strip()
                if label_text == 'DOB':
                    try:
                        birthday = datetime.strptime(value_text, '%b %d, %Y').date()
                    except ValueError:
                        continue
                    today = date.today()
                    stats['age'] = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
                else:
                    key = self._normalize_stat_name(label_text)
                    if key in {'striking_accuracy', 'striking_defense', 'takedown_accuracy', 'takedown_defense'}:
                        # '--' = sin peleas UFC registradas: no guardar 0.0, dejar que apliquen los defaults
                        if value_text.replace('%', '').strip() in ('', '--'):
                            continue
                        stats[key] = self._parse_stat_value(value_text)
            
            # Historial de peleas
            fight_history = []
            fight_rows = soup.find_all('tr', class_='b-fight-details__table-row')
            
            for fight_row in fight_rows[1:]:  # Skip header
                cells = fight_row.find_all('td')
                if len(cells) >= 7:
                    fight = {
                        'result': cells[0].get_text(strip=True),
                        'opponent': cells[1].get_text(strip=True),
                        'event': cells[2].get_text(strip=True),
                        'date': cells[3].get_text(strip=True),
                        'method': cells[4].get_text(strip=True),
                        'round': cells[5].get_text(strip=True),
                        'time': cells[6].get_text(strip=True)
                    }
                    fight_history.append(fight)
            
            # Peleador sin peleas UFC registradas: UFCStats muestra 0% en las 4 métricas (o '--').
            # Eso no es rendimiento nulo sino dato desconocido: omitirlas para que apliquen los defaults.
            stat_keys = {'striking_accuracy', 'striking_defense', 'takedown_accuracy', 'takedown_defense'}
            present = stat_keys & stats.keys()
            if len(present) == len(stat_keys) and all(stats[k] == 0.0 for k in present):
                logger.info("No UFC stats yet for %s (all 0%%): using defaults", profile_url)
                for k in present:
                    del stats[k]

            stats['fight_history'] = fight_history
            return stats
            
        except Exception as e:
            logger.warning("Error getting detailed stats from %s: %s", profile_url, e)
            return {}
    
    def _parse_height(self, height_str):
        """Convertir altura a cm"""
        if not height_str or height_str == '--':
            return None

        try:
            # Formato: 5' 11" -> cm
            if "'" in height_str:
                feet, inches = height_str.replace('"', '').split("'")
                return int(feet) * 30.48 + float(inches.strip()) * 2.54
            # Formato: 71" -> cm (solo pulgadas)
            elif '"' in height_str:
                inches = float(height_str.replace('"', '').strip())
                return inches * 2.54
        except Exception as e:
            logger.warning("Could not parse height '%s': %s", height_str, e)
        return None
    
    def _infer_weight_class(self, weight_lbs):
        """Inferir categoría de peso basado en el peso en libras"""
        if not weight_lbs or weight_lbs == 0:
            return 'unknown'

        if weight_lbs <= 125:
            return 'flyweight'
        elif weight_lbs <= 135:
            return 'bantamweight'
        elif weight_lbs <= 145:
            return 'featherweight'
        elif weight_lbs <= 155:
            return 'lightweight'
        elif weight_lbs <= 170:
            return 'welterweight'
        elif weight_lbs <= 185:
            return 'middleweight'
        elif weight_lbs <= 205:
            return 'light_heavyweight'
        else:
            return 'heavyweight'

    def _parse_weight(self, weight_str):
        """Convertir peso a kg"""
        if not weight_str or weight_str == '--':
            return None

        try:
            # Formato: "185 lbs" or "155 lbs." -> keep as lbs
            weight_lbs = float(weight_str.replace('lbs', '').replace('.', '').strip())
            return weight_lbs
        except Exception as e:
            logger.warning("Could not parse weight '%s': %s", weight_str, e)
        return None

    def _parse_reach(self, reach_str):
        """Convertir reach a cm"""
        if not reach_str or reach_str == '--':
            return None

        try:
            # Formato: 6' 0" -> cm (feet and inches)
            if "'" in reach_str:
                feet, inches = reach_str.replace('"', '').split("'")
                total_inches = int(feet) * 12 + float(inches.strip())
                return total_inches * 2.54
            # Formato: 74.0" -> cm (solo pulgadas)
            elif '"' in reach_str:
                reach_inches = float(reach_str.replace('"', '').strip())
                return reach_inches * 2.54
        except Exception as e:
            logger.warning("Could not parse reach '%s': %s", reach_str, e)
        return None
    
    def _normalize_stat_name(self, stat_name):
        """Normalizar nombres de estadísticas"""
        mapping = {
            'SLpM': 'significant_strikes_per_minute',
            'Str. Acc.': 'striking_accuracy',
            'SApM': 'significant_strikes_absorbed_per_minute',
            'Str. Def.': 'striking_defense',
            'Str. Def': 'striking_defense',
            'TD Avg.': 'takedowns_average',
            'TD Acc.': 'takedown_accuracy',
            'TD Def.': 'takedown_defense',
            'Sub. Avg.': 'submissions_average'
        }
        return mapping.get(stat_name, stat_name.lower().replace(' ', '_'))
    
    def _parse_stat_value(self, value_str):
        """Parsear valores de estadísticas"""
        try:
            # Remover % y convertir a float
            value_str = value_str.replace('%', '').strip()
            return float(value_str)
        except:
            return 0.0

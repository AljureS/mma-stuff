import requests
from bs4 import BeautifulSoup

class MMADataCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def search_and_scrape_fighter(self, fighter_name: str) -> dict:
        """
        Buscar un peleador específico en UFCStats y scrapearlo

        Returns:
            dict: Datos del peleador o None si no se encuentra
        """
        print(f"Searching for fighter: {fighter_name}")

        # Buscar en UFCStats
        search_url = "http://ufcstats.com/statistics/fighters/search"

        try:
            # UFCStats ordena por APELLIDO, intentar con última palabra del nombre
            name_parts = fighter_name.split()
            last_name_letter = name_parts[-1][0].upper() if name_parts else 'A'

            list_url = f"http://ufcstats.com/statistics/fighters?char={last_name_letter}&page=all"

            print(f"Fetching URL: {list_url} (searching by last name: {name_parts[-1] if name_parts else ''})")
            response = self.session.get(list_url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Buscar en la tabla de peleadores
            fighter_rows = soup.find_all('tr', class_='b-statistics__table-row')
            print(f"Found {len(fighter_rows)} rows in table")

            checked_count = 0
            for row in fighter_rows[1:]:  # Skip header
                cells = row.find_all('td')
                if len(cells) >= 10:
                    # En UFCStats, el nombre está en el primer <a> tag
                    name_link = row.find('a', class_='b-link b-link_style_black')
                    if not name_link:
                        continue

                    # Combinar primer y segundo nombre (UFCStats divide el nombre)
                    first_name = cells[0].get_text(strip=True)
                    last_name = cells[1].get_text(strip=True)
                    full_name = f"{first_name} {last_name}".strip()

                    checked_count += 1
                    if checked_count <= 5 or 'gamrot' in full_name.lower():
                        print(f"Checking: '{full_name}'")

                    # Búsqueda case-insensitive más estricta
                    search_lower = fighter_name.lower().replace('.', '').replace('-', ' ')
                    name_lower = full_name.lower().replace('.', '').replace('-', ' ')

                    if search_lower not in name_lower and name_lower not in search_lower:
                        continue

                    name = full_name

                    print(f"Found fighter: {name}")

                    # Debug: mostrar contenido de cells
                    print(f"DEBUG: Found {len(cells)} cells")
                    for i, cell in enumerate(cells[:10]):
                        print(f"  Cell[{i}]: {cell.get_text(strip=True)[:50]}")

                    # Extraer datos básicos con manejo seguro
                    def safe_int(value_str, default=0):
                        try:
                            return int(float(value_str.strip()) if value_str.strip() else default)
                        except:
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

                    # Obtener profile link para stats detalladas
                    profile_link = name_link
                    if profile_link:
                        profile_url = profile_link.get('href')
                        print(f"Fetching detailed stats from: {profile_url}")
                        detailed_stats = self.get_fighter_detailed_stats(profile_url)
                        fighter_data.update(detailed_stats)

                    # Calcular campos adicionales
                    fighter_data['age'] = fighter_data.get('age', 30)  # Default
                    fighter_data['weight_class'] = self._infer_weight_class(fighter_data.get('weight', 0))
                    fighter_data['ranking'] = None  # Se puede actualizar con Sherdog después

                    # Estadísticas con defaults
                    fighter_data.setdefault('striking_accuracy', 50.0)
                    fighter_data.setdefault('striking_defense', 55.0)
                    fighter_data.setdefault('takedown_accuracy', 40.0)
                    fighter_data.setdefault('takedown_defense', 70.0)

                    print(f"Successfully scraped: {fighter_data['name']}")
                    return fighter_data

            print(f"Fighter not found: {fighter_name}")
            return None

        except Exception as e:
            print(f"Error scraping fighter {fighter_name}: {e}")
            return None
    
    def get_fighter_detailed_stats(self, profile_url):
        """Obtener estadísticas detalladas de un luchador"""
        try:
            response = self.session.get(profile_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            stats = {}
            
            # Estadísticas de striking
            striking_stats = soup.find_all('div', class_='b-list__box-list-item')
            for stat in striking_stats:
                label = stat.find('i', class_='b-list__box-item-title')
                value = stat.find('i', class_='b-list__box-item-value')
                
                if label and value:
                    label_text = label.get_text(strip=True)
                    value_text = value.get_text(strip=True)
                    
                    stats[self._normalize_stat_name(label_text)] = self._parse_stat_value(value_text)
            
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
            
            stats['fight_history'] = fight_history
            return stats
            
        except Exception as e:
            print(f"Error getting detailed stats: {e}")
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
            print(f"Warning: Could not parse height '{height_str}': {e}")
            pass
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
            print(f"Warning: Could not parse weight '{weight_str}': {e}")
            pass
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
            print(f"Warning: Could not parse reach '{reach_str}': {e}")
            pass
        return None
    
    def _normalize_stat_name(self, stat_name):
        """Normalizar nombres de estadísticas"""
        mapping = {
            'SLpM': 'significant_strikes_per_minute',
            'Str. Acc.': 'striking_accuracy',
            'SApM': 'significant_strikes_absorbed_per_minute',
            'Str. Def.': 'striking_defense',
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
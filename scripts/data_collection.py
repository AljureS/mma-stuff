import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By

class MMADataCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape_ufc_stats(self, max_fighters=1000):
        """Scraping UFCStats.com - la fuente más completa"""
        base_url = "http://ufcstats.com/statistics/fighters"
        fighters_data = []
        
        print("Scraping UFC Stats...")
        
        # Obtener lista de luchadores
        for page in range(1, 50):  # Ajustar según necesidad
            url = f"{base_url}?char=&page={page}"
            
            try:
                response = self.session.get(url, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Buscar tabla de luchadores
                fighter_rows = soup.find_all('tr', class_='b-statistics__table-row')
                
                for row in fighter_rows[1:]:  # Skip header
                    cells = row.find_all('td')
                    if len(cells) >= 10:
                        fighter_data = {
                            'name': cells[0].get_text(strip=True),
                            'height': self._parse_height(cells[1].get_text(strip=True)),
                            'weight': self._parse_weight(cells[2].get_text(strip=True)),
                            'reach': self._parse_reach(cells[3].get_text(strip=True)),
                            'stance': cells[4].get_text(strip=True),
                            'wins': int(cells[5].get_text(strip=True) or 0),
                            'losses': int(cells[6].get_text(strip=True) or 0),
                            'draws': int(cells[7].get_text(strip=True) or 0),
                            'belt_status': 'champion' if 'champion' in cells[8].get_text().lower() else 'contender'
                        }
                        
                        # Obtener link del perfil para más detalles
                        profile_link = cells[0].find('a')
                        if profile_link:
                            fighter_data['profile_url'] = profile_link.get('href')
                            
                        fighters_data.append(fighter_data)
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"Error scraping page {page}: {e}")
                continue
        
        return pd.DataFrame(fighters_data)
    
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
    
    def scrape_sherdog_rankings(self):
        """Scraping rankings de Sherdog"""
        base_url = "https://www.sherdog.com/rankings"
        rankings = {}
        
        weight_classes = [
            'heavyweight', 'light-heavyweight', 'middleweight', 
            'welterweight', 'lightweight', 'featherweight', 
            'bantamweight', 'flyweight'
        ]
        
        for weight_class in weight_classes:
            try:
                url = f"{base_url}/{weight_class}"
                response = self.session.get(url)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                ranking_list = []
                ranking_items = soup.find_all('div', class_='ranking_item')
                
                for i, item in enumerate(ranking_items[:15]):  # Top 15
                    fighter_name = item.find('a', class_='fighter_name')
                    if fighter_name:
                        ranking_list.append({
                            'rank': i + 1,
                            'name': fighter_name.get_text(strip=True),
                            'weight_class': weight_class
                        })
                
                rankings[weight_class] = ranking_list
                time.sleep(1)
                
            except Exception as e:
                print(f"Error scraping {weight_class} rankings: {e}")
        
        return rankings
    
    def get_betting_odds_historical(self):
        """Obtener odds históricas (requiere API key)"""
        # Ejemplo con The Odds API
        api_key = "YOUR_API_KEY"  # Obtener de theoddsapi.com
        
        url = "https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds/history"
        
        params = {
            'apiKey': api_key,
            'regions': 'us,uk',
            'markets': 'h2h,spreads',
            'dateFormat': 'iso',
            'date': '2024-01-01T00:00:00Z'
        }
        
        try:
            response = requests.get(url, params=params)
            return response.json()
        except Exception as e:
            print(f"Error getting betting odds: {e}")
            return []
    
    def scrape_tapology_events(self):
        """Scraping eventos futuros de Tapology"""
        url = "https://www.tapology.com/fightcenter"
        
        try:
            response = self.session.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            events = []
            event_items = soup.find_all('div', class_='fcListingHeader')
            
            for event in event_items:
                event_info = {
                    'title': event.find('h3').get_text(strip=True) if event.find('h3') else '',
                    'date': event.find('span', class_='fcListingDatetime').get_text(strip=True) if event.find('span', class_='fcListingDatetime') else '',
                    'fights': []
                }
                
                # Buscar peleas en el evento
                fights_container = event.find_next('div', class_='fcListingBody')
                if fights_container:
                    fights = fights_container.find_all('div', class_='fcListingColumn')
                    
                    for fight in fights:
                        fighter_links = fight.find_all('a')
                        if len(fighter_links) >= 2:
                            event_info['fights'].append({
                                'fighter_a': fighter_links[0].get_text(strip=True),
                                'fighter_b': fighter_links[1].get_text(strip=True)
                            })
                
                events.append(event_info)
            
            return events
            
        except Exception as e:
            print(f"Error scraping Tapology events: {e}")
            return []
    
    def get_social_sentiment(self, fighter_name):
        """Obtener sentiment de redes sociales"""
        # Twitter API v2 (requiere API key)
        # Reddit API
        # YouTube API para análisis de videos
        
        # Ejemplo simplificado con Reddit
        reddit_data = self._scrape_reddit_sentiment(fighter_name)
        twitter_data = self._get_twitter_sentiment(fighter_name)
        
        return {
            'reddit_sentiment': reddit_data['sentiment'],
            'reddit_mentions': reddit_data['mentions'],
            'twitter_sentiment': twitter_data['sentiment'],
            'twitter_mentions': twitter_data['mentions'],
            'combined_sentiment': (reddit_data['sentiment'] + twitter_data['sentiment']) / 2
        }
    
    def _scrape_reddit_sentiment(self, fighter_name):
        """Scraping básico de Reddit MMA"""
        # Usar PRAW (Reddit API wrapper) en producción
        return {'sentiment': 0.5, 'mentions': 100}  # Placeholder
    
    def _get_twitter_sentiment(self, fighter_name):
        """Twitter sentiment (requiere API)"""
        return {'sentiment': 0.6, 'mentions': 200}  # Placeholder
    
    def _parse_height(self, height_str):
        """Convertir altura a cm"""
        if not height_str or height_str == '--':
            return None
        
        # Formato: 5' 11" -> cm
        try:
            if "'" in height_str:
                feet, inches = height_str.replace('"', '').split("'")
                return int(feet) * 30.48 + int(inches.strip()) * 2.54
        except:
            pass
        return None
    
    def _parse_weight(self, weight_str):
        """Convertir peso a kg"""
        if not weight_str or weight_str == '--':
            return None
        
        try:
            # Formato: "185 lbs" -> kg
            weight_lbs = float(weight_str.replace('lbs', '').strip())
            return weight_lbs * 0.453592
        except:
            pass
        return None
    
    def _parse_reach(self, reach_str):
        """Convertir reach a cm"""
        if not reach_str or reach_str == '--':
            return None
        
        try:
            # Formato: 74.0" -> cm
            reach_inches = float(reach_str.replace('"', '').strip())
            return reach_inches * 2.54
        except:
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
    
    def save_data(self, data, filename):
        """Guardar datos en formato JSON y CSV"""
        # Guardar como JSON
        with open(f"{filename}.json", 'w') as f:
            json.dump(data, f, indent=2)
        
        # Si es DataFrame, guardar como CSV
        if isinstance(data, pd.DataFrame):
            data.to_csv(f"{filename}.csv", index=False)
        
        print(f"Data saved to {filename}.json and {filename}.csv")

# Script principal para recolectar todos los datos
def main():
    collector = MMADataCollector()
    
    print("Starting MMA data collection...")
    
    # 1. Scraping fighters básicos
    print("1. Collecting UFC fighter data...")
    fighters_df = collector.scrape_ufc_stats()
    collector.save_data(fighters_df, "ufc_fighters")
    
    # 2. Obtener stats detallados para top fighters
    print("2. Getting detailed stats for top fighters...")
    detailed_stats = []
    for _, fighter in fighters_df.head(100).iterrows():  # Top 100
        if 'profile_url' in fighter and fighter['profile_url']:
            print(f"Getting stats for {fighter['name']}")
            stats = collector.get_fighter_detailed_stats(fighter['profile_url'])
            stats['name'] = fighter['name']
            detailed_stats.append(stats)
            time.sleep(2)  # Rate limiting
    
    collector.save_data(detailed_stats, "detailed_fighter_stats")
    
    # 3. Rankings actuales
    print("3. Scraping current rankings...")
    rankings = collector.scrape_sherdog_rankings()
    collector.save_data(rankings, "current_rankings")
    
    # 4. Eventos futuros
    print("4. Getting upcoming events...")
    events = collector.scrape_tapology_events()
    collector.save_data(events, "upcoming_events")
    
    print("Data collection complete!")
    
    # Estadísticas finales
    print(f"\nCollected data:")
    print(f"- {len(fighters_df)} fighters")
    print(f"- {len(detailed_stats)} detailed profiles")
    print(f"- {len(rankings)} weight class rankings")
    print(f"- {len(events)} upcoming events")

if __name__ == "__main__":
    main()
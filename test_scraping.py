#!/usr/bin/env python3
"""
Test script para verificar el scraping automático de peleadores
"""
import sys
from pathlib import Path

# Add scripts to path
sys.path.append(str(Path(__file__).parent / 'scripts'))

from data_collection import MMADataCollector

def test_scraping():
    """Test scraping de Mateusz Gamrot"""
    print("="*60)
    print("Testing MMA Fighter Scraping")
    print("="*60)

    collector = MMADataCollector()

    # Test con Mateusz Gamrot
    fighter_name = "Mateusz Gamrot"
    print(f"\n🔍 Searching for: {fighter_name}")

    result = collector.search_and_scrape_fighter(fighter_name)

    if result:
        print(f"\n✅ SUCCESS! Found fighter data:")
        print("-"*60)
        for key, value in result.items():
            print(f"  {key:25s}: {value}")
        print("-"*60)
        return True
    else:
        print(f"\n❌ FAILED: Could not find {fighter_name}")
        return False

if __name__ == "__main__":
    success = test_scraping()
    sys.exit(0 if success else 1)

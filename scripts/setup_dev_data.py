"""
Setup rápido: Crear modelo dummy y datos de prueba
"""
import pickle
import xgboost as xgb
import numpy as np
import pandas as pd
from pathlib import Path

print("🚀 Configurando datos de desarrollo...\n")

# 1. CREAR MODELO ML
print("📦 Creando modelo XGBoost...")
X_train = np.random.randn(1000, 16)
y_train = (X_train[:, 0] + X_train[:, 3] > 0).astype(int)

model = xgb.XGBClassifier(
    n_estimators=100,
    learning_rate=0.01,
    max_depth=6,
    random_state=42
)
model.fit(X_train, y_train)

model_path = Path('models/mma_prediction_model.pkl')
model_path.parent.mkdir(exist_ok=True)

with open(model_path, 'wb') as f:
    pickle.dump(model, f)

print(f"✅ Modelo creado: {model_path}")
print(f"   Tamaño: {model_path.stat().st_size / 1024:.1f} KB")

# 2. CREAR CSV DE FIGHTERS
print("\n📊 Creando datos de fighters...")

fighters_data = pd.DataFrame({
    'name': [
        'Jon Jones', 'Stipe Miocic', 'Alexander Volkanovski', 'Ilia Topuria',
        'Islam Makhachev', 'Charles Oliveira', 'Leon Edwards', 'Colby Covington',
        'Israel Adesanya', 'Sean Strickland', 'Alex Pereira', 'Robert Whittaker',
        'Kamaru Usman', 'Belal Muhammad', 'Shavkat Rakhmonov', 'Gilbert Burns',
        'Max Holloway', 'Brian Ortega', 'Yair Rodriguez', 'Arnold Allen'
    ],
    'wins': [27, 20, 26, 15, 25, 34, 22, 17, 24, 28, 10, 26, 20, 23, 18, 22, 26, 16, 16, 23],
    'losses': [1, 4, 3, 0, 1, 10, 3, 3, 3, 3, 2, 7, 3, 3, 0, 5, 7, 3, 4, 2],
    'draws': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 3, 0, 1, 1],
    'height': [193, 193, 168, 170, 178, 178, 185, 180, 193, 185, 193, 183, 183, 180, 183, 178, 180, 175, 180, 180],
    'reach': [215, 203, 183, 178, 189, 188, 190, 183, 203, 191, 203, 185, 193, 183, 190, 180, 190, 185, 189, 183],
    'age': [37, 42, 36, 28, 33, 35, 33, 37, 35, 34, 37, 34, 37, 36, 30, 38, 33, 34, 32, 31],
    'weight_class': [
        'heavyweight', 'heavyweight', 'featherweight', 'featherweight',
        'lightweight', 'lightweight', 'welterweight', 'welterweight',
        'middleweight', 'middleweight', 'light-heavyweight', 'middleweight',
        'welterweight', 'welterweight', 'welterweight', 'welterweight',
        'featherweight', 'featherweight', 'featherweight', 'featherweight'
    ],
    'ranking': [1, 2, 1, 2, 1, 2, 1, 3, 2, 1, 2, 3, 4, 5, 6, 7, 3, 4, 5, 6],
    'striking_accuracy': [52.6, 51.2, 48.9, 54.3, 49.2, 47.8, 48.1, 44.2, 51.3, 49.7, 53.1, 50.8, 50.2, 47.9, 52.1, 46.5, 48.3, 45.6, 49.8, 47.2],
    'striking_defense': [62.3, 57.8, 56.1, 61.2, 58.9, 54.2, 59.3, 56.7, 57.2, 60.1, 58.5, 59.8, 60.5, 57.3, 61.8, 55.9, 56.8, 54.1, 58.7, 59.4],
    'takedown_accuracy': [43.8, 41.7, 45.2, 48.5, 53.2, 38.9, 40.1, 46.8, 35.2, 38.7, 36.4, 42.1, 45.9, 49.2, 50.3, 44.7, 42.8, 47.3, 43.9, 41.2],
    'takedown_defense': [95.1, 71.4, 82.6, 78.3, 85.2, 76.8, 81.3, 79.5, 82.1, 77.9, 75.2, 78.6, 82.7, 80.4, 83.9, 77.1, 79.8, 74.2, 76.5, 81.8]
})

csv_path = Path('data/fighters_complete.csv')
csv_path.parent.mkdir(exist_ok=True)

fighters_data.to_csv(csv_path, index=False)

print(f"✅ CSV creado: {csv_path}")
print(f"   Fighters: {len(fighters_data)}")
print(f"   Columnas: {list(fighters_data.columns)}")

# 3. VERIFICACIÓN
print("\n🔍 Verificación:")
print(f"   - Modelo existe: {model_path.exists()}")
print(f"   - CSV existe: {csv_path.exists()}")

print("\n🎉 ¡Setup completado exitosamente!")

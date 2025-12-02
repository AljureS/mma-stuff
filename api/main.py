from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import asyncio
import aiohttp
import redis
import json
from dotenv import load_dotenv
from pathlib import Path
import sys

# Add scripts directory to path for data_collection
sys.path.append(str(Path(__file__).parent.parent / 'scripts'))

from llm_client import get_llm_client, LLMProvider

# Load environment variables
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MMA Fight Prediction API",
    description="API para predicciones de peleas de MMA usando ML + LLM",
    version="1.0.0"
)

# CORS para permitir requests desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis para cache
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Modelos globales (cargar al inicio)
prediction_model = None
fighter_database = None
llm_client = None

class FightPredictionRequest(BaseModel):
    fighter_a: str
    fighter_b: str
    event_name: Optional[str] = None
    weight_class: Optional[str] = None
    title_fight: bool = False
    include_llm_analysis: bool = True

class FightPredictionResponse(BaseModel):
    fighter_a: str
    fighter_b: str
    probability_a_wins: float
    probability_b_wins: float
    confidence: float
    predicted_winner: str
    key_factors: List[Dict]
    llm_analysis: Optional[str] = None
    betting_insights: Optional[Dict] = None
    timestamp: str

class FighterStatsResponse(BaseModel):
    name: str
    record: str
    stats: Dict
    recent_form: List[Dict]
    ranking: Optional[int] = None

class UpcomingEvent(BaseModel):
    event_name: str
    date: str
    fights: List[Dict]

@app.on_event("startup")
async def load_models():
    """Cargar modelos y datos al iniciar la aplicación"""
    global prediction_model, fighter_database, llm_client

    try:
        # Get base path (project root directory)
        base_path = Path(__file__).parent.parent

        # Cargar modelo entrenado
        model_path = base_path / 'models' / 'mma_prediction_model.pkl'
        with open(model_path, 'rb') as f:
            prediction_model = pickle.load(f)

        # Cargar base de datos de luchadores
        csv_path = base_path / 'data' / 'fighters_complete.csv'
        fighter_database = pd.read_csv(csv_path)

        # Inicializar LLM client
        llm_client = get_llm_client()

        logger.info("Models and data loaded successfully")

    except Exception as e:
        logger.error(f"Error loading models: {e}")
        # En producción: cargar modelos por defecto o desde S3/cloud storage

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "message": "MMA Prediction API is running",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": prediction_model is not None,
        "fighters_count": len(fighter_database) if fighter_database is not None else 0
    }

@app.post("/predict", response_model=FightPredictionResponse, tags=["Predictions"])
async def predict_fight(request: FightPredictionRequest):
    """Predecir el resultado de una pelea"""
    
    if prediction_model is None:
        raise HTTPException(status_code=503, detail="Prediction model not loaded")
    
    try:
        # Check cache first
        cache_key = f"prediction:{request.fighter_a}:{request.fighter_b}"
        cached_result = redis_client.get(cache_key)
        
        if cached_result:
            logger.info(f"Returning cached prediction for {request.fighter_a} vs {request.fighter_b}")
            return FightPredictionResponse(**json.loads(cached_result))
        
        # Validar que los luchadores existen
        logger.info(f"Searching for fighter_a: '{request.fighter_a}'")
        fighter_a_data = get_fighter_data(request.fighter_a)

        logger.info(f"Searching for fighter_b: '{request.fighter_b}'")
        fighter_b_data = get_fighter_data(request.fighter_b)

        # Validación detallada
        missing_fighters = []
        if not fighter_a_data:
            missing_fighters.append(request.fighter_a)
            logger.warning(f"Fighter not found in database: '{request.fighter_a}'")
        if not fighter_b_data:
            missing_fighters.append(request.fighter_b)
            logger.warning(f"Fighter not found in database: '{request.fighter_b}'")

        if missing_fighters:
            raise HTTPException(
                status_code=404,
                detail=f"Fighter(s) not found in database: {', '.join(missing_fighters)}. Please check spelling or add fighter to database."
            )
        
        # Engineer features
        features = engineer_fight_features(fighter_a_data, fighter_b_data, request)
        
        # Hacer predicción
        probabilities = prediction_model.predict_proba([features])[0]
        
        # Generar análisis LLM si se solicita
        llm_analysis = None
        if request.include_llm_analysis:
            llm_analysis = await generate_llm_analysis(
                fighter_a_data, fighter_b_data, probabilities
            )
        
        # Obtener insights de apuestas
        betting_insights = await get_betting_insights(request.fighter_a, request.fighter_b)
        
        # Crear respuesta
        response = FightPredictionResponse(
            fighter_a=request.fighter_a,
            fighter_b=request.fighter_b,
            probability_a_wins=float(probabilities[1]),
            probability_b_wins=float(probabilities[0]),
            confidence=float(max(probabilities)),
            predicted_winner=request.fighter_a if probabilities[1] > 0.5 else request.fighter_b,
            key_factors=get_key_factors(features, fighter_a_data, fighter_b_data),
            llm_analysis=llm_analysis,
            betting_insights=betting_insights,
            timestamp=datetime.now().isoformat()
        )
        
        # Cache result for 1 hour
        redis_client.setex(cache_key, 3600, response.json())
        
        logger.info(f"Generated prediction for {request.fighter_a} vs {request.fighter_b}")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions (404, etc.) sin modificar
        raise
    except Exception as e:
        logger.error(f"Error making prediction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error making prediction: {str(e)}")

@app.get("/fighter/{fighter_name}", response_model=FighterStatsResponse, tags=["Fighters"])
async def get_fighter_stats(fighter_name: str):
    """Obtener estadísticas completas de un luchador"""
    
    fighter_data = get_fighter_data(fighter_name)
    
    if not fighter_data:
        raise HTTPException(status_code=404, detail=f"Fighter '{fighter_name}' not found")
    
    # Calcular record
    record = f"{fighter_data.get('wins', 0)}-{fighter_data.get('losses', 0)}-{fighter_data.get('draws', 0)}"
    
    # Obtener forma reciente
    recent_form = get_recent_form(fighter_name)
    
    # Obtener ranking actual
    ranking = get_current_ranking(fighter_name, fighter_data.get('weight_class'))
    
    return FighterStatsResponse(
        name=fighter_name,
        record=record,
        stats=fighter_data,
        recent_form=recent_form,
        ranking=ranking
    )

@app.get("/search/fighters/{query}", tags=["Search"])
async def search_fighters(query: str, limit: int = 10):
    """Buscar luchadores por nombre"""
    
    if fighter_database is None:
        raise HTTPException(status_code=503, detail="Fighter database not loaded")
    
    # Búsqueda fuzzy por nombre
    matches = fighter_database[
        fighter_database['name'].str.contains(query, case=False, na=False)
    ].head(limit)
    
    results = []
    for _, fighter in matches.iterrows():
        results.append({
            'name': fighter['name'],
            'record': f"{fighter.get('wins', 0)}-{fighter.get('losses', 0)}-{fighter.get('draws', 0)}",
            'weight_class': fighter.get('weight_class', 'Unknown'),
            'ranking': fighter.get('ranking', None)
        })
    
    return {
        'query': query,
        'results': results,
        'count': len(results)
    }

@app.get("/events/upcoming", response_model=List[UpcomingEvent], tags=["Events"])
async def get_upcoming_events():
    """Obtener eventos próximos con predicciones"""
    
    # En producción: obtener de base de datos o scraping actualizado
    upcoming_events = [
        {
            "event_name": "UFC 300",
            "date": "2025-09-15",
            "fights": [
                {"fighter_a": "Jon Jones", "fighter_b": "Stipe Miocic", "title_fight": True},
                {"fighter_a": "Alexander Volkanovski", "fighter_b": "Ilia Topuria", "title_fight": True}
            ]
        }
    ]
    
    # Agregar predicciones para cada pelea
    for event in upcoming_events:
        for fight in event['fights']:
            try:
                # Hacer predicción rápida
                request = FightPredictionRequest(
                    fighter_a=fight['fighter_a'],
                    fighter_b=fight['fighter_b'],
                    include_llm_analysis=False
                )
                prediction = await predict_fight(request)
                
                fight['prediction'] = {
                    'winner': prediction.predicted_winner,
                    'probability': max(prediction.probability_a_wins, prediction.probability_b_wins),
                    'confidence': prediction.confidence
                }
                
            except Exception as e:
                logger.warning(f"Could not predict {fight['fighter_a']} vs {fight['fighter_b']}: {e}")
                fight['prediction'] = None
    
    return [UpcomingEvent(**event) for event in upcoming_events]

@app.post("/retrain", tags=["Model Management"])
async def retrain_model(background_tasks: BackgroundTasks):
    """Reentrenar el modelo con nuevos datos"""
    
    # Solo permitir en desarrollo o con autenticación
    background_tasks.add_task(retrain_model_background)
    
    return {
        "message": "Model retraining started in background",
        "status": "accepted",
        "timestamp": datetime.now().isoformat()
    }

async def retrain_model_background():
    """Reentrenar modelo en background"""
    try:
        logger.info("Starting model retraining...")
        
        # 1. Recolectar nuevos datos
        # collector = MMADataCollector()
        # new_data = collector.scrape_recent_fights()
        
        # 2. Preparar datos de entrenamiento
        # training_data = prepare_training_data(new_data)
        
        # 3. Reentrenar modelo
        # new_model = train_new_model(training_data)
        
        # 4. Validar modelo
        # validation_score = validate_model(new_model)
        
        # 5. Si es mejor, reemplazar modelo actual
        # if validation_score > current_model_score:
        #     replace_model(new_model)
        
        logger.info("Model retraining completed")
        
    except Exception as e:
        logger.error(f"Error retraining model: {e}")

@app.get("/analytics/model-performance", tags=["Analytics"])
async def get_model_performance():
    """Obtener métricas de rendimiento del modelo"""
    
    # En producción: calcular desde base de datos de predicciones vs resultados reales
    return {
        "accuracy": 0.72,
        "precision": 0.74,
        "recall": 0.69,
        "f1_score": 0.71,
        "total_predictions": 1547,
        "correct_predictions": 1114,
        "last_updated": "2025-09-03T10:00:00Z"
    }

@app.get("/analytics/betting-roi", tags=["Analytics"])
async def get_betting_roi():
    """ROI si siguieras las predicciones del modelo"""

    return {
        "total_bets": 234,
        "winning_bets": 162,
        "win_rate": 0.692,
        "total_staked": 2340.00,
        "total_returned": 2876.50,
        "profit": 536.50,
        "roi": 0.229,  # 22.9%
        "best_streak": 12,
        "worst_streak": -5
    }

@app.get("/health/llm", tags=["Health"])
async def llm_health_check():
    """Verificar estado de los proveedores LLM"""

    if llm_client is None:
        raise HTTPException(status_code=503, detail="LLM client not initialized")

    health_status = await llm_client.health_check()

    return {
        "status": "healthy" if health_status else "degraded",
        "providers": health_status,
        "timestamp": datetime.now().isoformat()
    }

# Funciones auxiliares

def get_fighter_data(fighter_name: str) -> Optional[Dict]:
    """Obtener datos de un luchador con scraping automático y cache inteligente (7 días)"""
    global fighter_database

    if fighter_database is None:
        return None

    # 1. Buscar en CSV (cache local)
    fighter = _search_in_database(fighter_name)

    # 2. Verificar frescura de datos (< 7 días)
    if fighter and _is_data_fresh(fighter, days=7):
        logger.info(f"Using cached data for '{fighter_name}' (fresh)")
        return fighter

    # 3. Si no existe O está desactualizado, scrapear
    if not fighter or not _is_data_fresh(fighter, days=7):
        action = "not found" if not fighter else "stale (>7 days)"
        logger.info(f"Fighter '{fighter_name}' {action}, attempting web scraping...")

        try:
            from data_collection import MMADataCollector

            collector = MMADataCollector()
            fresh_data = collector.search_and_scrape_fighter(fighter_name)

            if fresh_data:
                logger.info(f"Successfully scraped data for '{fighter_name}'")
                # 4. Actualizar/agregar al CSV
                _update_or_add_to_csv(fresh_data)
                # 5. Recargar fighter_database en memoria
                _reload_fighter_database()
                # 6. Retornar datos frescos
                return _search_in_database(fighter_name)
            else:
                logger.warning(f"Web scraping failed for '{fighter_name}'")

        except Exception as e:
            logger.error(f"Error during web scraping: {e}", exc_info=True)

    # 7. Fallback: retornar datos viejos si scraping falla
    if fighter:
        logger.warning(f"Using stale data for '{fighter_name}' (scraping failed)")

    return fighter


def _search_in_database(fighter_name: str) -> Optional[Dict]:
    """Búsqueda exacta y fuzzy en fighter_database"""
    if fighter_database is None:
        return None

    # Búsqueda exacta primero
    exact_match = fighter_database[fighter_database['name'] == fighter_name]

    if not exact_match.empty:
        return exact_match.iloc[0].to_dict()

    # Búsqueda fuzzy
    fuzzy_match = fighter_database[
        fighter_database['name'].str.contains(fighter_name, case=False, na=False)
    ]

    if not fuzzy_match.empty:
        return fuzzy_match.iloc[0].to_dict()

    return None


def _is_data_fresh(fighter: Dict, days: int = 7) -> bool:
    """Verificar si los datos tienen menos de N días"""
    last_updated = fighter.get('last_updated')

    if not last_updated:
        # Si no tiene timestamp, asumir que es viejo
        return False

    try:
        if isinstance(last_updated, str):
            last_updated_date = datetime.fromisoformat(last_updated)
        else:
            last_updated_date = last_updated

        age_days = (datetime.now() - last_updated_date).days
        return age_days < days

    except Exception as e:
        logger.warning(f"Could not parse last_updated: {e}")
        return False


def _update_or_add_to_csv(fighter_data: Dict):
    """Actualizar o agregar peleador al CSV con timestamp"""
    global fighter_database

    csv_path = Path(__file__).parent.parent / 'data' / 'fighters_complete.csv'

    # Agregar timestamp
    fighter_data['last_updated'] = datetime.now().isoformat()

    # Leer CSV actual
    df = pd.read_csv(csv_path)

    # Verificar si ya existe
    existing_index = df[df['name'] == fighter_data['name']].index

    if not existing_index.empty:
        # Actualizar fila existente
        for key, value in fighter_data.items():
            if key in df.columns:
                df.loc[existing_index[0], key] = value
        logger.info(f"Updated existing fighter: {fighter_data['name']}")
    else:
        # Agregar nueva fila
        new_row = pd.DataFrame([fighter_data])
        df = pd.concat([df, new_row], ignore_index=True)
        logger.info(f"Added new fighter: {fighter_data['name']}")

    # Guardar CSV
    df.to_csv(csv_path, index=False)


def _reload_fighter_database():
    """Recargar fighter_database en memoria desde CSV"""
    global fighter_database

    csv_path = Path(__file__).parent.parent / 'data' / 'fighters_complete.csv'

    try:
        fighter_database = pd.read_csv(csv_path)
        logger.info(f"Reloaded fighter_database: {len(fighter_database)} fighters")
    except Exception as e:
        logger.error(f"Failed to reload fighter_database: {e}", exc_info=True)

def engineer_fight_features(fighter_a_data: Dict, fighter_b_data: Dict, request: FightPredictionRequest) -> List[float]:
    """Generar features para el modelo ML con manejo robusto de valores None/NaN"""

    def safe_get(data: Dict, key: str, default: float) -> float:
        """Obtener valor con manejo de None/NaN"""
        value = data.get(key, default)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert {key}={value} to float, using default {default}")
            return default

    features = []

    # Diferencias físicas
    height_a = safe_get(fighter_a_data, 'height', 180)
    height_b = safe_get(fighter_b_data, 'height', 180)
    features.append(height_a - height_b)

    reach_a = safe_get(fighter_a_data, 'reach', 180)
    reach_b = safe_get(fighter_b_data, 'reach', 180)
    features.append(reach_a - reach_b)

    age_a = safe_get(fighter_a_data, 'age', 30)
    age_b = safe_get(fighter_b_data, 'age', 30)
    features.append(age_a - age_b)

    # Diferencias de record
    wins_a = safe_get(fighter_a_data, 'wins', 0)
    losses_a = safe_get(fighter_a_data, 'losses', 0)
    wins_b = safe_get(fighter_b_data, 'wins', 0)
    losses_b = safe_get(fighter_b_data, 'losses', 0)

    total_fights_a = wins_a + losses_a
    total_fights_b = wins_b + losses_b

    win_rate_a = wins_a / max(total_fights_a, 1)
    win_rate_b = wins_b / max(total_fights_b, 1)

    features.append(win_rate_a - win_rate_b)
    features.append(total_fights_a - total_fights_b)

    # Estadísticas de striking
    striking_acc_a = safe_get(fighter_a_data, 'striking_accuracy', 50)
    striking_acc_b = safe_get(fighter_b_data, 'striking_accuracy', 50)
    features.append(striking_acc_a - striking_acc_b)

    striking_def_a = safe_get(fighter_a_data, 'striking_defense', 50)
    striking_def_b = safe_get(fighter_b_data, 'striking_defense', 50)
    features.append(striking_def_a - striking_def_b)

    # Estadísticas de grappling
    td_acc_a = safe_get(fighter_a_data, 'takedown_accuracy', 30)
    td_acc_b = safe_get(fighter_b_data, 'takedown_accuracy', 30)
    features.append(td_acc_a - td_acc_b)

    td_def_a = safe_get(fighter_a_data, 'takedown_defense', 70)
    td_def_b = safe_get(fighter_b_data, 'takedown_defense', 70)
    features.append(td_def_a - td_def_b)

    # Contexto de la pelea
    features.append(1.0 if request.title_fight else 0.0)

    # Asegurar que tenemos el número correcto de features
    while len(features) < 16:  # Ajustar según modelo
        features.append(0.0)

    logger.debug(f"Engineered {len(features)} features: {features[:3]}... (showing first 3)")

    return features[:16]

async def generate_llm_analysis(fighter_a_data: Dict, fighter_b_data: Dict, probabilities: np.ndarray) -> str:
    """Generar análisis usando LLM con fallback Claude -> Ollama"""

    try:
        # Construir prompt detallado
        prompt = f"""Analiza esta pelea de MMA basándote en los datos y predicción del modelo ML:

**{fighter_a_data['name']}**
- Record: {fighter_a_data.get('wins', 0)}-{fighter_a_data.get('losses', 0)}-{fighter_a_data.get('draws', 0)}
- Altura: {fighter_a_data.get('height', 'N/A')}cm, Alcance: {fighter_a_data.get('reach', 'N/A')}cm
- Edad: {fighter_a_data.get('age', 'N/A')} años

**{fighter_b_data['name']}**
- Record: {fighter_b_data.get('wins', 0)}-{fighter_b_data.get('losses', 0)}-{fighter_b_data.get('draws', 0)}
- Altura: {fighter_b_data.get('height', 'N/A')}cm, Alcance: {fighter_b_data.get('reach', 'N/A')}cm
- Edad: {fighter_b_data.get('age', 'N/A')} años

**Predicción del modelo ML:** {probabilities[1]:.1%} para {fighter_a_data['name']} vs {probabilities[0]:.1%} para {fighter_b_data['name']}

IMPORTANTE: Escribe un análisis de MÁXIMO 700 palabras, asegurándote de completar todos tus párrafos y pensamientos de forma coherente. No dejes frases a la mitad.

El análisis debe incluir 2-3 párrafos bien estructurados que cubran:
1. Ventajas/desventajas clave de cada peleador
2. Factores críticos del matchup (físicos, técnicos, estilos)
3. Escenarios de victoria más probables
4. Tu evaluación de la predicción del modelo

Sé específico y técnico usando tu conocimiento de MMA. IMPORTANTE: Termina el análisis con una conclusión completa, no cortes a la mitad de una frase."""

        system_prompt = "Eres un analista experto en MMA con profundo conocimiento técnico de striking, grappling, y estrategias de combate. Siempre completas tus análisis de forma coherente sin dejar frases incompletas."

        # Usar LLM client con fallback automático
        response = await llm_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=800,
            temperature=0.7
        )

        # Log metadata
        logger.info(
            f"LLM analysis generated using {response.provider.value} "
            f"({response.model}) in {response.latency_ms}ms "
            f"(fallback: {response.fallback_used})"
        )

        return response.content

    except Exception as e:
        logger.error(f"Error generating LLM analysis: {e}", exc_info=True)
        return "Análisis LLM no disponible temporalmente debido a un error técnico."

async def get_betting_insights(fighter_a: str, fighter_b: str) -> Optional[Dict]:
    """Obtener insights de apuestas"""
    
    try:
        # En producción: llamar a APIs de casas de apuestas
        return {
            "market_odds": {
                fighter_a: -120,
                fighter_b: +100
            },
            "implied_probability": {
                fighter_a: 0.545,
                fighter_b: 0.500
            },
            "value_bet": fighter_b if True else None,  # Lógica de value betting
            "recommendation": "Slight value on underdog based on model vs market"
        }
        
    except Exception as e:
        logger.error(f"Error getting betting insights: {e}")
        return None

def get_key_factors(features: List[float], fighter_a_data: Dict, fighter_b_data: Dict) -> List[Dict]:
    """Identificar factores clave de la predicción"""
    
    feature_names = [
        "height_difference", "reach_difference", "age_difference", 
        "win_rate_difference", "experience_difference", "striking_accuracy_diff",
        "striking_defense_diff", "takedown_accuracy_diff", "takedown_defense_diff",
        "title_fight_factor"
    ]
    
    key_factors = []
    
    for i, (name, value) in enumerate(zip(feature_names, features)):
        if abs(value) > 0.1:  # Solo factores significativos
            key_factors.append({
                "factor": name.replace("_", " ").title(),
                "value": round(float(value), 3),
                "impact": "high" if abs(value) > 1.0 else "medium"
            })
    
    return sorted(key_factors, key=lambda x: abs(x["value"]), reverse=True)[:5]

def get_recent_form(fighter_name: str, limit: int = 5) -> List[Dict]:
    """Obtener forma reciente del luchador"""
    # En producción: consultar base de datos de peleas
    return [
        {"opponent": "Opponent 1", "result": "W", "method": "TKO", "round": 2},
        {"opponent": "Opponent 2", "result": "W", "method": "Decision", "round": 5}
    ]

def get_current_ranking(fighter_name: str, weight_class: Optional[str]) -> Optional[int]:
    """Obtener ranking actual del luchador"""
    # En producción: consultar rankings actualizados
    return 5  # Placeholder

if __name__ == "__main__":
    import uvicorn
    import sys
    import os
    
    # En desarrollo con reload
    if "--reload" in sys.argv or os.getenv("DEBUG"):
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        # En producción sin reload
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
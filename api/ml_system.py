import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, log_loss
import requests
from datetime import datetime
import logging

class MMAPredictor:
    def __init__(self, llm_model=None):
        self.prediction_model = None
        self.llm_model = llm_model
        self.feature_columns = [
            'height_diff', 'reach_diff', 'age_diff', 'experience_diff',
            'win_rate_diff', 'finish_rate_diff', 'takedown_acc_diff',
            'takedown_def_diff', 'sig_str_acc_diff', 'sig_str_def_diff',
            'cardio_score_diff', 'power_score_diff', 'grappling_score_diff',
            'recent_form_diff', 'opponent_quality_diff', 'style_matchup_score'
        ]
        
    def load_fighter_data(self, fighter_name):
        """Cargar datos de un luchador desde múltiples fuentes"""
        # UFC Stats API (simulado)
        ufc_stats = self._get_ufc_stats(fighter_name)
        
        # Betting odds (simulado)
        betting_data = self._get_betting_odds(fighter_name)
        
        # Redes sociales sentiment (opcional)
        sentiment_data = self._get_social_sentiment(fighter_name)
        
        return {
            **ufc_stats,
            **betting_data,
            **sentiment_data
        }
    
    def _get_ufc_stats(self, fighter_name):
        """Obtener estadísticas oficiales de UFC"""
        # En producción: scraping de UFCStats.com o API
        return {
            'name': fighter_name,
            'wins': 25, 'losses': 1, 'draws': 0,
            'height': 193, 'reach': 215, 'age': 36,
            'sig_strikes_landed': 1487, 'sig_strikes_attempted': 2567,
            'takedowns_landed': 23, 'takedowns_attempted': 47,
            'knockdowns': 8, 'submissions': 6,
            'avg_fight_time': 12.5, 'title_fights': 8
        }
    
    def _get_betting_odds(self, fighter_name):
        """Obtener odds de casas de apuestas"""
        # APIs de DraftKings, Bet365, etc.
        return {
            'current_odds': -150,  # Favorito
            'market_confidence': 0.75,
            'public_bet_percentage': 0.68
        }
    
    def _get_social_sentiment(self, fighter_name):
        """Análisis de sentiment en redes sociales"""
        # Twitter API, Reddit API
        return {
            'social_sentiment': 0.65,  # -1 a 1
            'hype_score': 0.8,
            'controversy_score': 0.2
        }
    
    def engineer_features(self, fighter_a_data, fighter_b_data):
        """Crear features para el modelo ML"""
        features = {}
        
        # Diferencias físicas
        features['height_diff'] = fighter_a_data['height'] - fighter_b_data['height']
        features['reach_diff'] = fighter_a_data['reach'] - fighter_b_data['reach']
        features['age_diff'] = fighter_a_data['age'] - fighter_b_data['age']
        
        # Diferencias de experiencia
        total_fights_a = sum([fighter_a_data['wins'], fighter_a_data['losses'], fighter_a_data['draws']])
        total_fights_b = sum([fighter_b_data['wins'], fighter_b_data['losses'], fighter_b_data['draws']])
        features['experience_diff'] = total_fights_a - total_fights_b
        
        # Tasas de éxito
        win_rate_a = fighter_a_data['wins'] / total_fights_a if total_fights_a > 0 else 0
        win_rate_b = fighter_b_data['wins'] / total_fights_b if total_fights_b > 0 else 0
        features['win_rate_diff'] = win_rate_a - win_rate_b
        
        # Estadísticas de striking
        sig_str_acc_a = fighter_a_data['sig_strikes_landed'] / fighter_a_data['sig_strikes_attempted']
        sig_str_acc_b = fighter_b_data['sig_strikes_landed'] / fighter_b_data['sig_strikes_attempted']
        features['sig_str_acc_diff'] = sig_str_acc_a - sig_str_acc_b
        
        # Estadísticas de takedown
        td_acc_a = fighter_a_data['takedowns_landed'] / fighter_a_data['takedowns_attempted']
        td_acc_b = fighter_b_data['takedowns_landed'] / fighter_b_data['takedowns_attempted']
        features['takedown_acc_diff'] = td_acc_a - td_acc_b
        
        # Calcular scores compuestos
        features['power_score_diff'] = self._calculate_power_score(fighter_a_data) - self._calculate_power_score(fighter_b_data)
        features['grappling_score_diff'] = self._calculate_grappling_score(fighter_a_data) - self._calculate_grappling_score(fighter_b_data)
        features['cardio_score_diff'] = self._calculate_cardio_score(fighter_a_data) - self._calculate_cardio_score(fighter_b_data)
        
        # Análisis de estilo (simplificado)
        features['style_matchup_score'] = self._calculate_style_matchup(fighter_a_data, fighter_b_data)
        
        # Llenar features faltantes con 0
        for col in self.feature_columns:
            if col not in features:
                features[col] = 0
                
        return features
    
    def _calculate_power_score(self, fighter_data):
        """Score de poder de golpe"""
        knockdown_rate = fighter_data['knockdowns'] / (fighter_data['wins'] + fighter_data['losses'])
        ko_rate = 0.4  # Simplificado - en realidad calcular de los métodos de victoria
        return (knockdown_rate * 0.6 + ko_rate * 0.4) * 100
    
    def _calculate_grappling_score(self, fighter_data):
        """Score de lucha en suelo"""
        td_rate = fighter_data['takedowns_landed'] / (fighter_data['wins'] + fighter_data['losses'])
        sub_rate = fighter_data['submissions'] / (fighter_data['wins'] + fighter_data['losses'])
        return (td_rate * 0.4 + sub_rate * 0.6) * 100
    
    def _calculate_cardio_score(self, fighter_data):
        """Score de resistencia"""
        avg_fight_time = fighter_data['avg_fight_time']  # en minutos
        # Fighters que van a decisión tienden a tener mejor cardio
        decision_rate = 0.3  # Simplificado
        return (avg_fight_time / 15) * 0.7 + decision_rate * 0.3
    
    def _calculate_style_matchup(self, fighter_a, fighter_b):
        """Análisis de compatibilidad de estilos"""
        # Simplificado: striker vs grappler, etc.
        # En realidad sería más complejo basado en estadísticas
        power_a = self._calculate_power_score(fighter_a)
        grappling_a = self._calculate_grappling_score(fighter_a)
        power_b = self._calculate_power_score(fighter_b)
        grappling_b = self._calculate_grappling_score(fighter_b)
        
        # Si A es striker y B es grappler, ventaja para el grappler en early rounds
        if power_a > grappling_a and grappling_b > power_b:
            return -0.1  # Ligera ventaja para B
        elif grappling_a > power_a and power_b > grappling_b:
            return 0.1   # Ligera ventaja para A
        else:
            return 0     # Neutral
    
    def train_model(self, training_data):
        """Entrenar el modelo de predicción"""
        X = training_data[self.feature_columns]
        y = training_data['winner']  # 1 si ganó fighter_a, 0 si ganó fighter_b
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # XGBoost para clasificación binaria
        self.prediction_model = xgb.XGBClassifier(
            n_estimators=1000,
            learning_rate=0.01,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='logloss'
        )
        
        # Entrenar con early stopping
        self.prediction_model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            early_stopping_rounds=50,
            verbose=False
        )
        
        # Evaluar modelo
        train_pred = self.prediction_model.predict_proba(X_train)[:, 1]
        test_pred = self.prediction_model.predict_proba(X_test)[:, 1]
        
        train_accuracy = accuracy_score(y_train, self.prediction_model.predict(X_train))
        test_accuracy = accuracy_score(y_test, self.prediction_model.predict(X_test))
        
        print(f"Training Accuracy: {train_accuracy:.3f}")
        print(f"Test Accuracy: {test_accuracy:.3f}")
        print(f"Train Log Loss: {log_loss(y_train, train_pred):.3f}")
        print(f"Test Log Loss: {log_loss(y_test, test_pred):.3f}")
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': self.feature_columns,
            'importance': self.prediction_model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\nTop 10 Most Important Features:")
        print(feature_importance.head(10))
        
        return {
            'train_accuracy': train_accuracy,
            'test_accuracy': test_accuracy,
            'feature_importance': feature_importance
        }
    
    def predict_fight(self, fighter_a_name, fighter_b_name):
        """Predecir resultado de pelea"""
        if not self.prediction_model:
            raise ValueError("Model not trained yet. Call train_model() first.")
        
        # Cargar datos
        fighter_a_data = self.load_fighter_data(fighter_a_name)
        fighter_b_data = self.load_fighter_data(fighter_b_name)
        
        # Engineer features
        features = self.engineer_features(fighter_a_data, fighter_b_data)
        
        # Predecir probabilidades
        X = pd.DataFrame([features])[self.feature_columns]
        probabilities = self.prediction_model.predict_proba(X)[0]
        
        # Análisis con LLM si está disponible
        llm_analysis = ""
        if self.llm_model:
            llm_analysis = self._generate_llm_analysis(
                fighter_a_data, fighter_b_data, probabilities
            )
        
        return {
            'fighter_a': fighter_a_name,
            'fighter_b': fighter_b_name,
            'probability_a_wins': probabilities[1],
            'probability_b_wins': probabilities[0],
            'confidence': max(probabilities),
            'prediction': fighter_a_name if probabilities[1] > 0.5 else fighter_b_name,
            'key_features': self._get_key_features(features),
            'llm_analysis': llm_analysis,
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_llm_analysis(self, fighter_a_data, fighter_b_data, probabilities):
        """Generar análisis cualitativo con LLM"""
        if not self.llm_model:
            return "LLM analysis not available"
            
        prompt = f"""
        Analiza esta pelea de MMA basándote en los siguientes datos:

        Luchador A: {fighter_a_data['name']}
        - Record: {fighter_a_data['wins']}-{fighter_a_data['losses']}-{fighter_a_data['draws']}
        - Altura: {fighter_a_data['height']}cm, Alcance: {fighter_a_data['reach']}cm
        - Edad: {fighter_a_data['age']} años
        
        Luchador B: {fighter_b_data['name']}
        - Record: {fighter_b_data['wins']}-{fighter_b_data['losses']}-{fighter_b_data['draws']}
        - Altura: {fighter_b_data['height']}cm, Alcance: {fighter_b_data['reach']}cm
        - Edad: {fighter_b_data['age']} años
        
        Predicción del modelo ML: {probabilities[1]:.1%} probabilidad para {fighter_a_data['name']}
        
        Proporciona un análisis detallado que incluya:
        1. Ventajas/desventajas de cada luchador
        2. Factores clave que podrían determinar el resultado
        3. Escenarios de victoria para cada uno
        4. Tu evaluación de la predicción del modelo
        
        Sé específico y usa tu conocimiento de MMA.
        """
        
        try:
            # Aquí irían las llamadas al modelo LLM
            # return self.llm_model.generate(prompt)
            return "Análisis LLM: [Placeholder - aquí iría el análisis detallado del modelo]"
        except Exception as e:
            return f"Error generating LLM analysis: {str(e)}"
    
    def _get_key_features(self, features):
        """Identificar las features más importantes para esta predicción"""
        if not self.prediction_model:
            return []
            
        # Obtener feature importance del modelo
        feature_importance = self.prediction_model.feature_importances_
        
        # Combinar con valores actuales
        key_features = []
        for i, feature in enumerate(self.feature_columns):
            importance = feature_importance[i]
            value = features[feature]
            
            if abs(value) > 0.1 and importance > 0.02:  # Thresholds arbitrarios
                key_features.append({
                    'feature': feature,
                    'value': value,
                    'importance': importance
                })
        
        # Ordenar por importancia
        key_features.sort(key=lambda x: x['importance'], reverse=True)
        
        return key_features[:5]  # Top 5

# Ejemplo de uso
def main():
    # Crear predictor
    predictor = MMAPredictor()
    
    # Simular datos de entrenamiento
    # En realidad cargarías from database/CSV
    training_data = pd.DataFrame({
        # Features simuladas para 1000 peleas históricas
        **{col: np.random.randn(1000) for col in predictor.feature_columns},
        'winner': np.random.choice([0, 1], 1000)
    })
    
    # Entrenar modelo
    print("Training model...")
    results = predictor.train_model(training_data)
    
    # Predecir pelea
    print("\nPredicting fight...")
    prediction = predictor.predict_fight("Jon Jones", "Stipe Miocic")
    
    print(f"\nFight Prediction:")
    print(f"Fighter A: {prediction['fighter_a']}")
    print(f"Fighter B: {prediction['fighter_b']}")
    print(f"Prediction: {prediction['prediction']} wins")
    print(f"Probability: {prediction['probability_a_wins']:.1%} vs {prediction['probability_b_wins']:.1%}")
    print(f"Confidence: {prediction['confidence']:.1%}")
    print(f"\nKey factors:")
    for factor in prediction['key_features']:
        print(f"- {factor['feature']}: {factor['value']:.3f} (importance: {factor['importance']:.3f})")

if __name__ == "__main__":
    main()
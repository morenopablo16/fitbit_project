import unittest
from datetime import datetime, timedelta
from db import DatabaseManager, insert_daily_summary, init_db
from alert_rules import evaluate_all_alerts
import json
import statistics
import logging
import os

# Configure logging
log_dir = "test_results"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{log_dir}/threshold_validation_results.log"),
        logging.StreamHandler()
    ]
)

class TestThresholdsValidation(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db = DatabaseManager()
        self.db.connect()
        self.base_date = datetime.now().date()
        
        # Crear usuario de prueba
        result = self.db.execute_query("""
            INSERT INTO users (name, email, created_at)
            VALUES ('Usuario Real', 'real_user@example.com', NOW())
            RETURNING id;
        """)
        self.user_id = result[0][0]
        logging.info(f"Test environment initialized with user_id: {self.user_id}")

    def tearDown(self):
        self.db.close()
        logging.info("Test environment cleaned up")

    def test_real_data_patterns(self):
        """Validación de umbrales usando patrones de datos reales"""
        logging.info("Starting threshold validation test with real data patterns")
        
        # Patrones reales observados (basados en los 3 dispositivos de prueba)
        patterns = {
            'normal_weekday': {
                'steps': (8000, 12000),
                'heart_rate': (65, 75),
                'sleep_minutes': (420, 480),
                'sedentary_minutes': (700, 900)
            },
            'active_day': {
                'steps': (12000, 15000),
                'heart_rate': (70, 85),
                'sleep_minutes': (360, 420),
                'sedentary_minutes': (500, 700)
            },
            'sedentary_day': {
                'steps': (3000, 6000),
                'heart_rate': (60, 70),
                'sleep_minutes': (480, 540),
                'sedentary_minutes': (900, 1200)
            }
        }
        
        logging.info(f"Using data patterns: {json.dumps(patterns, indent=2)}")

        # Simular 30 días de datos con patrones reales
        alerts_generated = []
        daily_data = []  # Para almacenar los datos diarios
        
        for i in range(30):
            date = self.base_date - timedelta(days=i)
            
            # Seleccionar patrón según el día
            if i % 7 in [5, 6]:  # Fines de semana
                pattern = patterns['sedentary_day']
                pattern_type = 'sedentary_day'
            elif i % 7 in [1, 3]:  # Días activos
                pattern = patterns['active_day']
                pattern_type = 'active_day'
            else:  # Días normales
                pattern = patterns['normal_weekday']
                pattern_type = 'normal_weekday'
            
            # Insertar datos con variación aleatoria dentro del patrón
            data = {
                'steps': statistics.mean(pattern['steps']),
                'heart_rate': statistics.mean(pattern['heart_rate']),
                'sleep_minutes': statistics.mean(pattern['sleep_minutes']),
                'sedentary_minutes': statistics.mean(pattern['sedentary_minutes'])
            }
            
            daily_record = {
                'day': i,
                'date': date.isoformat(),
                'pattern_type': pattern_type,
                'metrics': data
            }
            daily_data.append(daily_record)
            
            logging.info(f"Day {i}: Inserting {pattern_type} data: {json.dumps(data)}")
            
            insert_daily_summary(
                user_id=self.user_id,
                date=date,
                **data
            )
            
            # Evaluar alertas
            evaluate_all_alerts(self.user_id, datetime.combine(date, datetime.min.time()))
            
            # Recopilar alertas generadas
            alerts = self.db.execute_query(
                "SELECT alert_type, priority, details FROM alerts WHERE user_id = %s AND DATE(alert_time) = %s",
                (self.user_id, date)
            )
            if alerts:
                day_alerts = [{
                    'day': i,
                    'date': date.isoformat(),
                    'pattern': pattern_type,
                    'alert_type': alert[0],
                    'priority': alert[1],
                    'details': alert[2]
                } for alert in alerts]
                alerts_generated.extend(day_alerts)
                logging.info(f"Day {i}: Generated {len(day_alerts)} alerts")

        # Análisis de resultados
        results = {
            'test_duration_days': 30,
            'total_alerts': len(alerts_generated),
            'daily_data': daily_data,
            'alerts_generated': alerts_generated,
            'alerts_by_pattern': {},
            'alerts_by_type': {},
            'false_positive_rate': 0,
            'detection_rate': 0
        }
        
        # Análisis por tipo de día
        for alert in alerts_generated:
            pattern = alert['pattern']
            alert_type = alert['alert_type']
            results['alerts_by_pattern'][pattern] = results['alerts_by_pattern'].get(pattern, 0) + 1
            results['alerts_by_type'][alert_type] = results['alerts_by_type'].get(alert_type, 0) + 1
        
        # Calcular tasas
        expected_alerts = len([d for d in daily_data if d['pattern_type'] != 'normal_weekday'])
        actual_alerts = len(alerts_generated)
        results['false_positive_rate'] = (actual_alerts - expected_alerts) / 30 * 100
        results['detection_rate'] = (expected_alerts - (actual_alerts - expected_alerts)) / expected_alerts * 100
        
        logging.info(f"Test results: {json.dumps(results, indent=2)}")
        
        # Validaciones
        self.assertLess(len(alerts_generated), 15, 
                       "Demasiadas alertas generadas para un patrón normal de actividad")
        
        weekend_alerts = sum(1 for a in alerts_generated if a['pattern'] == 'sedentary_day')
        self.assertLess(weekend_alerts, 8, 
                       "Demasiadas alertas generadas para fines de semana")

if __name__ == '__main__':
    unittest.main() 
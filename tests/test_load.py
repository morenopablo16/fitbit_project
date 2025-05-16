import unittest
import concurrent.futures
from datetime import datetime, timedelta
from db import DatabaseManager, insert_daily_summary, init_db
from alert_rules import evaluate_all_alerts
import time
import random
import logging
import json
import os

# Configure logging
log_dir = "test_results"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{log_dir}/load_test_results.log"),
        logging.StreamHandler()
    ]
)

class TestSystemLoad(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db = DatabaseManager()
        self.db.connect()
        self.base_date = datetime.now().date()
        logging.info("Test environment initialized")
        
    def tearDown(self):
        self.db.close()
        logging.info("Test environment cleaned up")

    def simulate_user_data(self, user_id):
        """Simula la inserción de datos y evaluación de alertas para un usuario"""
        try:
            logging.info(f"Starting simulation for user {user_id}")
            # Insertar datos históricos (7 días)
            for i in range(7):
                date = self.base_date - timedelta(days=i)
                # Simular variabilidad normal en los datos
                steps = random.randint(8000, 12000)
                hr = random.randint(65, 75)
                sleep = random.randint(420, 480)
                sedentary = random.randint(700, 900)
                
                data = {
                    'user_id': user_id,
                    'date': date.isoformat(),
                    'steps': steps,
                    'heart_rate': hr,
                    'sleep_minutes': sleep,
                    'sedentary_minutes': sedentary,
                    'active_minutes': random.randint(30, 90)
                }
                logging.debug(f"Inserting data for user {user_id}: {json.dumps(data)}")
                
                insert_daily_summary(**data)
            
            # Evaluar alertas
            start_time = time.time()
            evaluate_all_alerts(user_id, datetime.combine(self.base_date, datetime.min.time()))
            processing_time = time.time() - start_time
            
            logging.info(f"User {user_id} simulation completed in {processing_time:.2f} seconds")
            return processing_time
        except Exception as e:
            logging.error(f"Error simulating user {user_id}: {str(e)}")
            return f"Error for user {user_id}: {str(e)}"

    def test_concurrent_users(self):
        """Prueba el sistema con múltiples usuarios concurrentes"""
        NUM_USERS = 50  # Simular 50 usuarios concurrentes
        logging.info(f"Starting load test with {NUM_USERS} concurrent users")
        
        # Crear usuarios de prueba
        user_ids = []
        for i in range(NUM_USERS):
            result = self.db.execute_query(
                "INSERT INTO users (name, email, created_at) VALUES (%s, %s, NOW()) RETURNING id",
                (f"Test User {i}", f"test{i}@example.com")
            )
            user_ids.append(result[0][0])
        logging.info(f"Created {len(user_ids)} test users")
        
        # Ejecutar pruebas concurrentes
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_user = {executor.submit(self.simulate_user_data, user_id): user_id 
                            for user_id in user_ids}
            
            processing_times = []
            errors = []
            for future in concurrent.futures.as_completed(future_to_user):
                user_id = future_to_user[future]
                try:
                    processing_time = future.result()
                    if isinstance(processing_time, float):
                        processing_times.append(processing_time)
                    else:
                        errors.append(processing_time)
                except Exception as e:
                    errors.append(f"Exception for user {user_id}: {str(e)}")
        
        # Analizar y registrar resultados
        if processing_times:
            avg_time = sum(processing_times) / len(processing_times)
            max_time = max(processing_times)
            min_time = min(processing_times)
            
            results = {
                'total_users': NUM_USERS,
                'successful_tests': len(processing_times),
                'failed_tests': len(errors),
                'processing_times': {
                    'average': avg_time,
                    'maximum': max_time,
                    'minimum': min_time,
                    'distribution': processing_times
                },
                'errors': errors
            }
            
            logging.info(f"Load test results: {json.dumps(results, indent=2)}")
            
            # Verificar que los tiempos sean aceptables
            self.assertLess(avg_time, 1.0, "Tiempo promedio de procesamiento demasiado alto")
            self.assertLess(max_time, 2.0, "Tiempo máximo de procesamiento demasiado alto")
            
            if errors:
                logging.warning(f"Test completed with {len(errors)} errors")
                for error in errors:
                    logging.warning(error)

if __name__ == '__main__':
    unittest.main() 
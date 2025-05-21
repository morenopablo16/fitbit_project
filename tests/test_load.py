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
import numpy as np

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
            start_time = time.time()
            records_processed = 0
            
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
                records_processed += 1
            
            # Evaluar alertas
            alert_start_time = time.time()
            evaluate_all_alerts(user_id, datetime.combine(self.base_date, datetime.min.time()))
            alert_processing_time = time.time() - alert_start_time
            
            total_time = time.time() - start_time
            throughput = records_processed / total_time if total_time > 0 else 0
            
            logging.info(f"User {user_id} simulation completed in {total_time:.2f} seconds")
            logging.info(f"Throughput: {throughput:.2f} records/second")
            
            return {
                'total_time': total_time,
                'alert_time': alert_processing_time,
                'throughput': throughput,
                'records_processed': records_processed
            }
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
            alert_times = []
            throughputs = []
            errors = []
            
            for future in concurrent.futures.as_completed(future_to_user):
                user_id = future_to_user[future]
                try:
                    result = future.result()
                    if isinstance(result, dict):
                        processing_times.append(result['total_time'])
                        alert_times.append(result['alert_time'])
                        throughputs.append(result['throughput'])
                    else:
                        errors.append(result)
                except Exception as e:
                    errors.append(f"Exception for user {user_id}: {str(e)}")
        
        # Calcular métricas estadísticas
        if processing_times:
            avg_time = np.mean(processing_times)
            max_time = np.max(processing_times)
            min_time = np.min(processing_times)
            p95_time = np.percentile(processing_times, 95)
            p99_time = np.percentile(processing_times, 99)
            
            avg_throughput = np.mean(throughputs)
            total_throughput = sum(throughputs)
            
            results = {
                'total_users': NUM_USERS,
                'successful_tests': len(processing_times),
                'failed_tests': len(errors),
                'processing_times': {
                    'average': avg_time,
                    'maximum': max_time,
                    'minimum': min_time,
                    'p95': p95_time,
                    'p99': p99_time,
                    'distribution': processing_times
                },
                'alert_times': {
                    'average': np.mean(alert_times),
                    'maximum': np.max(alert_times),
                    'minimum': np.min(alert_times)
                },
                'throughput': {
                    'average': avg_throughput,
                    'total': total_throughput,
                    'distribution': throughputs
                },
                'errors': errors
            }
            
            # Log results in a format suitable for thesis annex
            logging.info("\n=== LOAD TEST RESULTS FOR THESIS ANNEX ===")
            logging.info(f"Total Users: {NUM_USERS}")
            logging.info(f"Successful Tests: {len(processing_times)}")
            logging.info(f"Failed Tests: {len(errors)}")
            logging.info("\nProcessing Times:")
            logging.info(f"- Average: {avg_time:.2f}s")
            logging.info(f"- P95: {p95_time:.2f}s")
            logging.info(f"- P99: {p99_time:.2f}s")
            logging.info(f"- Maximum: {max_time:.2f}s")
            logging.info("\nThroughput:")
            logging.info(f"- Average: {avg_throughput:.2f} records/second")
            logging.info(f"- Total: {total_throughput:.2f} records/second")
            logging.info("\nAlert Processing:")
            logging.info(f"- Average: {np.mean(alert_times):.2f}s")
            logging.info(f"- Maximum: {np.max(alert_times):.2f}s")
            logging.info("=========================================")
            
            # Verificar que los tiempos sean aceptables
            self.assertLess(avg_time, 1.0, "Tiempo promedio de procesamiento demasiado alto")
            self.assertLess(p95_time, 1.2, "Latencia P95 demasiado alta")
            self.assertLess(max_time, 2.0, "Tiempo máximo de procesamiento demasiado alto")
            
            if errors:
                logging.warning(f"Test completed with {len(errors)} errors")
                for error in errors:
                    logging.warning(error)

if __name__ == '__main__':
    unittest.main() 
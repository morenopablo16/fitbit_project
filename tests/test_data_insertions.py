import unittest
from datetime import datetime, timedelta
from db import DatabaseManager
import logging
import os
import random

# Configure logging
log_dir = "test_results"
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger('test_data_insertions')
logger.setLevel(logging.INFO)

# Create file handler
log_file = os.path.join(log_dir, 'data_insertion.log')
file_handler = logging.FileHandler(log_file, mode='w')
file_handler.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class TestDataInsertion(unittest.TestCase):
    def setUp(self):
        """Initialize database connection and test users."""
        self.db = DatabaseManager()
        self.db.connect()
        self.test_users = [
            {'id': 204, 'name': 'Test User 1', 'email': 'test1@example.com'},
            {'id': 205, 'name': 'Test User 2', 'email': 'test2@example.com'},
            {'id': 206, 'name': 'Test User 3', 'email': 'test3@example.com'}
        ]
        
        # Clean up any existing test data
        self.cleanup_test_data()
        
    def tearDown(self):
        """Close database connection."""
        self.db.close()

    def cleanup_test_data(self):
        """Safely remove existing test data."""
        try:
            # Delete data for test users
            for user in self.test_users:
                self.db.execute_query(
                    "DELETE FROM daily_summaries WHERE user_id = %s",
                    (user['id'],)
                )
                self.db.execute_query(
                    "DELETE FROM intraday_metrics WHERE user_id = %s",
                    (user['id'],)
                )
                self.db.execute_query(
                    "DELETE FROM sleep_logs WHERE user_id = %s",
                    (user['id'],)
                )
                self.db.execute_query(
                    "DELETE FROM alerts WHERE user_id = %s",
                    (user['id'],)
                )
            self.db.commit()
            logger.info("Cleaned up existing test data")
        except Exception as e:
            logger.error(f"Error cleaning up test data: {str(e)}")
            self.db.rollback()
            raise

    def generate_intraday_data(self, user_id, date, pattern='normal'):
        """Generate intraday data for a specific date and pattern."""
        base_values = {
            'normal': {
                'steps': (500, 1000),
                'heart_rate': (65, 85),
                'calories': (50, 150),
                'active_minutes': (2, 5)
            },
            'high_activity': {
                'steps': (800, 1500),
                'heart_rate': (75, 95),
                'calories': (80, 200),
                'active_minutes': (4, 8)
            },
            'low_activity': {
                'steps': (200, 600),
                'heart_rate': (55, 75),
                'calories': (30, 100),
                'active_minutes': (1, 3)
            },
            'high_heart_rate': {
                'steps': (500, 1000),
                'heart_rate': (100, 120),  # Anomalous high heart rate
                'calories': (50, 150),
                'active_minutes': (2, 5)
            },
            'low_steps': {
                'steps': (100, 400),  # Anomalous low steps
                'heart_rate': (65, 85),
                'calories': (30, 100),
                'active_minutes': (1, 3)
            },
            'low_sleep': {
                'steps': (500, 1000),
                'heart_rate': (65, 85),
                'calories': (50, 150),
                'active_minutes': (2, 5)
            }
        }

        values = base_values[pattern]
        data = []
        
        # Generate data for each hour
        for hour in range(24):
            time = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
            
            # Generate data for each metric type
            for metric_type, (min_val, max_val) in values.items():
                value = random.randint(min_val, max_val)
                data.append((user_id, time, metric_type, value))
        
        return data

    def insert_daily_summary(self, user_id, date, pattern='normal'):
        """Insert daily summary data for a specific date and pattern."""
        base_values = {
            'normal': {
                'steps': 10000,
                'heart_rate': 75,
                'sleep_minutes': 420,
                'calories': 2000,
                'distance': 7.5,
                'floors': 10,
                'elevation': 100,
                'active_minutes': 45,
                'sedentary_minutes': 600,
                'nutrition_calories': 2200,
                'water': 2.0,
                'weight': 70.0,
                'bmi': 22.0,
                'fat': 20.0,
                'oxygen_saturation': 98.0,
                'respiratory_rate': 16.0,
                'temperature': 36.5
            },
            'high_activity': {
                'steps': 15000,
                'heart_rate': 85,
                'sleep_minutes': 360,
                'calories': 2500,
                'distance': 10.0,
                'floors': 15,
                'elevation': 150,
                'active_minutes': 60,
                'sedentary_minutes': 480,
                'nutrition_calories': 2500,
                'water': 2.5,
                'weight': 70.0,
                'bmi': 22.0,
                'fat': 19.0,
                'oxygen_saturation': 98.0,
                'respiratory_rate': 18.0,
                'temperature': 36.7
            },
            'low_activity': {
                'steps': 5000,
                'heart_rate': 65,
                'sleep_minutes': 480,
                'calories': 1800,
                'distance': 3.5,
                'floors': 5,
                'elevation': 50,
                'active_minutes': 30,
                'sedentary_minutes': 720,
                'nutrition_calories': 2000,
                'water': 1.8,
                'weight': 70.0,
                'bmi': 22.0,
                'fat': 21.0,
                'oxygen_saturation': 97.0,
                'respiratory_rate': 14.0,
                'temperature': 36.3
            },
            'high_heart_rate': {
                'steps': 10000,
                'heart_rate': 110,  # Anomalous high
                'sleep_minutes': 420,
                'calories': 2000,
                'distance': 7.5,
                'floors': 10,
                'elevation': 100,
                'active_minutes': 45,
                'sedentary_minutes': 600,
                'nutrition_calories': 2200,
                'water': 2.0,
                'weight': 70.0,
                'bmi': 22.0,
                'fat': 20.0,
                'oxygen_saturation': 98.0,
                'respiratory_rate': 16.0,
                'temperature': 36.5
            },
            'low_steps': {
                'steps': 3000,  # Anomalous low
                'heart_rate': 75,
                'sleep_minutes': 420,
                'calories': 1800,
                'distance': 3.0,
                'floors': 5,
                'elevation': 50,
                'active_minutes': 20,
                'sedentary_minutes': 800,
                'nutrition_calories': 1800,
                'water': 1.8,
                'weight': 70.0,
                'bmi': 22.0,
                'fat': 21.0,
                'oxygen_saturation': 97.0,
                'respiratory_rate': 15.0,
                'temperature': 36.2
            },
            'low_sleep': {
                'steps': 10000,
                'heart_rate': 75,
                'sleep_minutes': 300,  # Anomalous low
                'calories': 2000,
                'distance': 7.5,
                'floors': 10,
                'elevation': 100,
                'active_minutes': 45,
                'sedentary_minutes': 600,
                'nutrition_calories': 2200,
                'water': 2.0,
                'weight': 70.0,
                'bmi': 22.0,
                'fat': 20.0,
                'oxygen_saturation': 98.0,
                'respiratory_rate': 16.0,
                'temperature': 36.5
            }
        }

        values = base_values[pattern]
        self.db.execute_query("""
            INSERT INTO daily_summaries 
            (user_id, date, steps, heart_rate, sleep_minutes, calories, distance,
             floors, elevation, active_minutes, sedentary_minutes, nutrition_calories,
             water, weight, bmi, fat, oxygen_saturation, respiratory_rate, temperature)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, date,
            values['steps'], values['heart_rate'], values['sleep_minutes'],
            values['calories'], values['distance'], values['floors'],
            values['elevation'], values['active_minutes'], values['sedentary_minutes'],
            values['nutrition_calories'], values['water'], values['weight'],
            values['bmi'], values['fat'], values['oxygen_saturation'],
            values['respiratory_rate'], values['temperature']
        ))

    def test_insert_all_data(self):
        """Insert all required test data, including multiple normal and anomalous days for threshold and alert tests."""
        try:
            users = self.test_users
            start_date = datetime(2025, 5, 8)  # 14 días desde el 8 al 21 de mayo
            days = 14
            anomalies = [
                {'pattern': 'high_heart_rate', 'desc': 'HR muy alto'},
                {'pattern': 'low_steps', 'desc': 'Pasos muy bajos'},
                {'pattern': 'low_sleep', 'desc': 'Sueño muy bajo'}
            ]
            anomaly_days = [0, 1, 2]  # Días 1-3 serán anómalos
            total_anomalies = 0
            total_daily = 0
            total_intraday = 0
            for user in users:
                for i in range(days):
                    date = (start_date + timedelta(days=i)).date()
                    if i in anomaly_days:
                        pattern = anomalies[i]['pattern']
                        desc = anomalies[i]['desc']
                        self.insert_daily_summary(user['id'], date, pattern=pattern)
                        intraday_data = self.generate_intraday_data(user['id'], date, pattern=pattern)
                        logger.info(f"Inserted {desc} anomaly for user {user['id']} on {date}")
                        total_anomalies += 1
                    else:
                        # Alternar entre normal y high_activity para dar variedad
                        pattern = 'normal' if i % 2 == 0 else 'high_activity'
                        self.insert_daily_summary(user['id'], date, pattern=pattern)
                        intraday_data = self.generate_intraday_data(user['id'], date, pattern=pattern)
                    # Insertar intraday data
                    self.db.execute_many(
                        """
                        INSERT INTO intraday_metrics (user_id, time, type, value)
                        VALUES (%s, %s, %s, %s)
                        """,
                        intraday_data
                    )
                    total_daily += 1
                    total_intraday += len(intraday_data)
            self.db.commit()
            logger.info("\n=== Test Data Insertion Summary ===")
            logger.info(f"✅ Users: {len(users)}")
            logger.info(f"✅ Days per user: {days}")
            logger.info(f"✅ Total days: {len(users)*days}")
            logger.info(f"✅ Anomalies inserted: {total_anomalies * len(users)}")
            logger.info(f"✅ Total records: {total_daily * len(users)} daily summaries, {total_intraday} intraday metrics")
            logger.info("================================\n")
        except Exception as e:
            logger.error(f"Error inserting test data: {str(e)}")
            self.db.rollback()
            raise

if __name__ == '__main__':
    unittest.main() 
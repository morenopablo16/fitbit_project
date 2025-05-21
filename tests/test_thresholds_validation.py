import unittest
import logging
from datetime import datetime, timedelta
from db import DatabaseManager
from alert_rules import (
    check_activity_drop,
    check_sedentary_increase,
    check_sleep_duration_change,
    check_heart_rate_anomaly,
    check_intraday_activity_drop
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_results/thresholds_test.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TestThresholdsValidation(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.db = DatabaseManager()
        if not self.db.connect():
            raise Exception("Could not connect to database")
        
        # Clean up any existing test data
        self.db.execute_query("DELETE FROM alerts WHERE user_id IN (204, 205, 206)")
        self.db.execute_query("DELETE FROM daily_summaries WHERE user_id IN (204, 205, 206)")
        self.db.execute_query("DELETE FROM intraday_metrics WHERE user_id IN (204, 205, 206)")
        self.db.commit()

    def tearDown(self):
        """Close database connection."""
        self.db.close()

    def test_thresholds_validation(self):
        """Test threshold validation using alert_rules.py functions."""
        try:
            # Test users and dates
            test_users = [204, 205, 206]
            test_dates = [
                datetime(2025, 5, 15),  # High heart rate
                datetime(2025, 5, 16),  # Low steps
                datetime(2025, 5, 17),  # Low sleep
                datetime(2025, 5, 18),  # Normal
                datetime(2025, 5, 19),  # Normal
                datetime(2025, 5, 20),  # Normal
                datetime(2025, 5, 21)   # Normal
            ]
            
            # Initialize statistics
            stats = {
                'total_tests': 0,
                'alerts_triggered': 0,
                'by_priority': {'high': 0, 'medium': 0},
                'by_type': {
                    'activity_drop': 0,
                    'sedentary_increase': 0,
                    'sleep_duration_change': 0,
                    'heart_rate_anomaly': 0,
                    'intraday_activity_drop': 0
                }
            }

            # Test each user and date
            for user_id in test_users:
                logger.info(f"\nTesting user {user_id}")
                
                for test_date in test_dates:
                    logger.info(f"Testing date: {test_date.date()}")
                    
                    # Test activity drop
                    if check_activity_drop(user_id, test_date):
                        stats['alerts_triggered'] += 1
                        stats['by_type']['activity_drop'] += 1
                        logger.info(f"Activity drop alert triggered for user {user_id} on {test_date.date()}")
                    stats['total_tests'] += 1

                    # Test sedentary increase
                    if check_sedentary_increase(user_id, test_date):
                        stats['alerts_triggered'] += 1
                        stats['by_type']['sedentary_increase'] += 1
                        logger.info(f"Sedentary increase alert triggered for user {user_id} on {test_date.date()}")
                    stats['total_tests'] += 1

                    # Test sleep duration change
                    if check_sleep_duration_change(user_id, test_date):
                        stats['alerts_triggered'] += 1
                        stats['by_type']['sleep_duration_change'] += 1
                        logger.info(f"Sleep duration change alert triggered for user {user_id} on {test_date.date()}")
                    stats['total_tests'] += 1

                    # Test heart rate anomaly
                    if check_heart_rate_anomaly(user_id, test_date):
                        stats['alerts_triggered'] += 1
                        stats['by_type']['heart_rate_anomaly'] += 1
                        logger.info(f"Heart rate anomaly alert triggered for user {user_id} on {test_date.date()}")
                    stats['total_tests'] += 1

                    # Test intraday activity drop
                    if check_intraday_activity_drop(user_id, test_date):
                        stats['alerts_triggered'] += 1
                        stats['by_type']['intraday_activity_drop'] += 1
                        logger.info(f"Intraday activity drop alert triggered for user {user_id} on {test_date.date()}")
                    stats['total_tests'] += 1

            # Log final summary
            logger.info("\n=== Test Summary ===")
            logger.info(f"Total tests: {stats['total_tests']}")
            logger.info(f"Alerts triggered: {stats['alerts_triggered']}")
            
            logger.info("\nBy Alert Type:")
            for alert_type, count in stats['by_type'].items():
                logger.info(f"- {alert_type}: {count}")

            # Verify we have alerts
            self.assertGreater(stats['alerts_triggered'], 0, "No alerts were generated")
            
        except Exception as e:
            logger.error(f"Error testing alerts: {str(e)}")
            raise

if __name__ == '__main__':
    unittest.main() 
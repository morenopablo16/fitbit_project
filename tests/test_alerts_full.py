import unittest
from datetime import datetime, timedelta
from db import DatabaseManager
import logging
import os

# Configure logging
log_dir = "test_results"
os.makedirs(log_dir, exist_ok=True)

# Create a custom formatter for the summary section
class SummaryFormatter(logging.Formatter):
    def format(self, record):
        if hasattr(record, 'summary'):
            return record.msg
        return super().format(record)

# Configure logging with two handlers
logger = logging.getLogger('test_alerts_full')
logger.setLevel(logging.INFO)

# Create file handler
log_file = os.path.join(log_dir, 'alerts_test.log')
file_handler = logging.FileHandler(log_file, mode='w')
file_handler.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatters
standard_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
summary_formatter = SummaryFormatter()

file_handler.setFormatter(standard_formatter)
console_handler.setFormatter(standard_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class TestAllAlertTypes(unittest.TestCase):
    def setUp(self):
        """Initialize database connection."""
        self.db = DatabaseManager()
        self.db.connect()
        self.test_users = [204, 205, 206]  # Test user IDs
        self.alert_stats = {
            'total': 0,
            'by_type': {},
            'by_priority': {'high': 0, 'medium': 0, 'low': 0},
            'by_user': {}
        }

    def tearDown(self):
        """Close database connection."""
        self.db.close()

    def test_all_alert_types(self):
        """Test all alert types and log results."""
        try:
            # Get alerts for each user
            for user_id in self.test_users:
                alerts = self.db.execute_query(
                    "SELECT * FROM alerts WHERE user_id = %s ORDER BY alert_time DESC",
                    (user_id,)
                )
                
                # Process alerts
                for alert in alerts:
                    self.alert_stats['total'] += 1
                    
                    # Count by type
                    alert_type = alert['alert_type']
                    self.alert_stats['by_type'][alert_type] = self.alert_stats['by_type'].get(alert_type, 0) + 1
                    
                    # Count by priority
                    priority = alert['priority']
                    self.alert_stats['by_priority'][priority] += 1
                    
                    # Count by user
                    self.alert_stats['by_user'][user_id] = self.alert_stats['by_user'].get(user_id, 0) + 1
                    
                    # Log individual alert details
                    logger.info(f"\n===== Alert: {alert_type} =====")
                    logger.info(f"User ID: {user_id}")
                    logger.info(f"Time: {alert['alert_time']}")
                    logger.info(f"Priority: {priority}")
                    logger.info(f"Value: {alert['triggering_value']}")
                    logger.info(f"Threshold: {alert['threshold_value']}")
                    logger.info(f"Details: {alert['details']}")
            
            # Log summary
            logger.info("\n=== Summary ===")
            logger.info(f"Total Alerts: {self.alert_stats['total']}")
            
            logger.info("\nBy Type:")
            for alert_type, count in self.alert_stats['by_type'].items():
                logger.info(f"- {alert_type}: {count}")
            
            logger.info("\nBy Priority:")
            for priority, count in self.alert_stats['by_priority'].items():
                logger.info(f"- {priority}: {count}")
            
            logger.info("\nBy User:")
            for user_id, count in self.alert_stats['by_user'].items():
                logger.info(f"- User {user_id}: {count}")
            
            # Verify we have alerts
            self.assertGreater(self.alert_stats['total'], 0, "No alerts were generated")
            
        except Exception as e:
            logger.error(f"Error testing alerts: {str(e)}")
            raise

if __name__ == '__main__':
    unittest.main() 
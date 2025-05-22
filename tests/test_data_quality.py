import os
import sys
import logging
from datetime import datetime, timedelta, time
import json

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_daily_summaries, get_intraday_metrics, get_sleep_logs, DatabaseManager
from alert_rules import get_triggered_alerts

# Configure logging directory
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs', 'data_quality')
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'detailed_data_quality.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def cleanup_test_data(user_id, test_date):
    """
    Clean up any existing test data for a specific user and date.
    """
    db = DatabaseManager()
    if db.connect():
        try:
            # Delete entries from daily_summaries for the past 7 days
            start_date = test_date - timedelta(days=7)
            db.execute_query("""
                DELETE FROM daily_summaries 
                WHERE user_id = %s AND date >= %s AND date <= %s
            """, (user_id, start_date.date(), test_date.date()))
            
            # Delete entries from intraday_metrics for the same period
            db.execute_query("""
                DELETE FROM intraday_metrics 
                WHERE user_id = %s AND time >= %s AND time <= %s
            """, (user_id, start_date, test_date))
            
            # Delete entries from alerts for the same period
            db.execute_query("""
                DELETE FROM alerts 
                WHERE user_id = %s AND alert_time >= %s AND alert_time <= %s
            """, (user_id, start_date, test_date))
            
            db.commit()
        finally:
            db.close()

def test_data_quality_scenario(user_id, test_date, test_data, expected_alerts):
    """
    Test for data quality scenarios using the get_triggered_alerts function.
    Returns a dictionary with test results and reasoning.
    """
    result = {
        'user_id': user_id,
        'test_date': test_date,
        'expected': expected_alerts,
        'triggered': [],
        'details': {},
        'reason': ''
    }
    
    try:
        # First, clean up any existing test data
        cleanup_test_data(user_id, test_date)
        
        # Insert test data
        db = DatabaseManager()
        if db.connect():
            try:
                # Insert historical data for the week prior to test date
                historical_date = test_date - timedelta(days=7)
                for i in range(7):
                    current_date = historical_date + timedelta(days=i)
                    # Insert normal historical data
                    db.execute_query("""
                        INSERT INTO daily_summaries (
                            user_id, date, steps, heart_rate, sleep_minutes,
                            calories, distance, floors, elevation,
                            active_minutes, sedentary_minutes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        user_id, current_date,
                        8000, 75, 480,  # Normal values
                        2000, 5.0, 10, 100.0,
                        60, 600
                    ))
                    
                    # Insert normal heart rate data for historical days
                    for hour in range(24):
                        current_time = datetime.combine(current_date, time(hour=hour))
                        db.execute_query("""
                            INSERT INTO intraday_metrics (user_id, time, type, value)
                            VALUES (%s, %s, 'heart_rate', %s)
                        """, (user_id, current_time, 75))  # Normal heart rate
                
                # Insert test day data
                db.execute_query("""
                    INSERT INTO daily_summaries (
                        user_id, date, steps, heart_rate, sleep_minutes,
                        calories, distance, floors, elevation,
                        active_minutes, sedentary_minutes,
                        nutrition_calories, water, weight, bmi, fat,
                        oxygen_saturation, respiratory_rate, temperature
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id, test_date.date(),
                    test_data.get('steps', None),
                    test_data.get('heart_rate', None),
                    test_data.get('sleep_minutes', None),
                    test_data.get('calories', None),
                    test_data.get('distance', None),
                    test_data.get('floors', None),
                    test_data.get('elevation', None),
                    test_data.get('active_minutes', None),
                    test_data.get('sedentary_minutes', None),
                    test_data.get('nutrition_calories', None),
                    test_data.get('water', None),
                    test_data.get('weight', None),
                    test_data.get('bmi', None),
                    test_data.get('fat', None),
                    test_data.get('oxygen_saturation', None),
                    test_data.get('respiratory_rate', None),
                    test_data.get('temperature', None)
                ))
                
                # Insert test day heart rate data if provided
                if 'heart_rate_data' in test_data:
                    for hr_time, value in test_data['heart_rate_data']:
                        db.execute_query("""
                            INSERT INTO intraday_metrics (user_id, time, type, value)
                            VALUES (%s, %s, 'heart_rate', %s)
                        """, (user_id, hr_time, value))
                
                db.commit()
            finally:
                db.close()
        
        # Evaluate alerts using the new function
        triggered_alerts = get_triggered_alerts(user_id, test_date)
        result['triggered'] = triggered_alerts
        
        # Compare with expected alerts
        result['details'] = {
            'triggered_alerts': triggered_alerts,
            'expected_alerts': expected_alerts,
            'test_data': test_data
        }
        
        result['reason'] = f"Data quality test completed. Triggered: {len(result['triggered'])} alerts"
        
    except Exception as e:
        result['reason'] = f'Error during test: {str(e)}'
        
    return result

def generate_logs(test_results):
    """
    Generate detailed and summary logs from test results.
    """
    # Generate detailed log
    with open(os.path.join(LOG_DIR, 'detailed_data_quality.log'), 'w') as f:
        f.write("=== Detailed Data Quality Test Results ===\n\n")
        for user_id, results in test_results.items():
            f.write(f"\nUser ID: {user_id}\n")
            f.write("=" * 50 + "\n")
            for date_type, date_results in results.items():
                f.write(f"\n{date_type.upper()} DATA:\n")
                f.write("-" * 30 + "\n")
                for alert_type, result in date_results.items():
                    f.write(f"\nAlert Type: {alert_type}\n")
                    f.write("-" * 20 + "\n")
                    f.write(f"Expected: {result['expected']}\n")
                    f.write(f"Triggered: {result['triggered']}\n")
                    f.write(f"Reason: {result['reason']}\n")
                    if result['details']:
                        f.write("\nDetails:\n")
                        for key, value in result['details'].items():
                            f.write(f"  {key}: {value}\n")
                    f.write("\n")

    # Generate summary log
    with open(os.path.join(LOG_DIR, 'summary_data_quality.log'), 'w') as f:
        f.write("=== Data Quality Test Summary ===\n\n")
        total_scenarios = 0
        successful_scenarios = 0
        total_alerts = 0
        expected_alerts = 0
        triggered_alerts = 0

        for user_id, results in test_results.items():
            f.write(f"\nUser ID: {user_id}\n")
            f.write("=" * 50 + "\n")
            for date_type, date_results in results.items():
                f.write(f"\n{date_type.upper()} DATA:\n")
                f.write("-" * 30 + "\n")
                for alert_type, result in date_results.items():
                    total_scenarios += 1
                    if result['triggered'] == result['expected']:
                        successful_scenarios += 1
                    
                    total_alerts += len(result['expected'])
                    expected_alerts += len(result['expected'])
                    triggered_alerts += len(result['triggered'])

                    status = '✓' if result['triggered'] == result['expected'] else '✗'
                    f.write(f"\n{alert_type}:\n")
                    f.write(f"  Status: {status}\n")
                    f.write(f"  Expected Alerts: {result['expected']}\n")
                    f.write(f"  Triggered Alerts: {result['triggered']}\n")
                    f.write(f"  Reason: {result['reason']}\n")

        f.write("\n=== Overall Statistics ===\n")
        f.write(f"Total Scenarios Tested: {total_scenarios}\n")
        f.write(f"Successful Scenarios: {successful_scenarios}\n")
        f.write(f"Total Expected Alerts: {expected_alerts}\n")
        f.write(f"Total Triggered Alerts: {triggered_alerts}\n")
        
        success_rate = (successful_scenarios / total_scenarios * 100) if total_scenarios > 0 else 0
        alert_accuracy = (triggered_alerts / expected_alerts * 100) if expected_alerts > 0 else 0
        
        f.write(f"\nSuccess Rate: {success_rate:.1f}%\n")
        f.write(f"Alert Accuracy: {alert_accuracy:.1f}%\n")

def run_data_quality_tests():
    """
    Run all data quality tests.
    """
    test_results = {}
    
    # Define specific test dates
    test_dates = {
        'missing_critical': datetime(2024, 4, 17),  # Updated date for missing data tests
        'anomalous_values': datetime(2024, 4, 18),  # Updated date for anomalous values tests
        'partial_data': datetime(2024, 4, 19)  # Updated date for partial data tests
    }
    
    # Test user IDs
    test_users = [1, 2, 3]  # Example user IDs
    
    for user_id in test_users:
        test_results[user_id] = {}
        
        # Test scenario 1: Missing critical data
        test_data_1 = {
            'steps': None,
            'heart_rate': None,
            'sleep_minutes': None,
            'oxygen_saturation': None
        }
        expected_alerts_1 = ['data_quality']
        
        # Test scenario 2: Anomalous values
        test_data_2 = {
            'steps': 100000,  # Unrealistic number of steps
            'heart_rate': 250,  # Unrealistic heart rate
            'sleep_minutes': 2000,  # Unrealistic sleep duration
            'oxygen_saturation': 50  # Unrealistic oxygen saturation
        }
        expected_alerts_2 = ['data_quality']
        
        # Test scenario 3: Partial data
        test_data_3 = {
            'steps': 5000,
            'heart_rate': None,
            'sleep_minutes': 480,
            'oxygen_saturation': None
        }
        expected_alerts_3 = ['data_quality']
        
        # Run tests for each scenario
        test_results[user_id]['missing_critical'] = test_data_quality_scenario(
            user_id, test_dates['missing_critical'], test_data_1, expected_alerts_1)
        
        test_results[user_id]['anomalous_values'] = test_data_quality_scenario(
            user_id, test_dates['anomalous_values'], test_data_2, expected_alerts_2)
        
        test_results[user_id]['partial_data'] = test_data_quality_scenario(
            user_id, test_dates['partial_data'], test_data_3, expected_alerts_3)
    
    # Generate logs
    generate_logs(test_results)
    
    return test_results

if __name__ == '__main__':
    run_data_quality_tests()
import json
import os
import logging
from datetime import datetime, timedelta
import psycopg2
import requests
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/fitbit_personal.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    "host": "tt1b0ye4qb.wuphxgc8qn.tsdb.cloud.timescale.com",
    "database": "tsdb",
    "user": "tsdbadmin",
    "password": "h6jcpcnwrhthgfzl",
    "port": "32317",
    "sslmode": "require"
}

# Fitbit API configuration
FITBIT_CONFIG = {
    "access_token": "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIyM1FLMlkiLCJzdWIiOiJDRzZaTDYiLCJpc3MiOiJGaXRiaXQiLCJ0eXAiOiJhY2Nlc3NfdG9rZW4iLCJzY29wZXMiOiJyc29jIHJlY2cgcnNldCByaXJuIHJveHkgcm51dCBycHJvIHJzbGUgcmNmIHJhY3QgcmxvYyBycmVzIHJ3ZWkgcmhyIHJ0ZW0iLCJleHAiOjE3NDgzOTQ5OTAsImlhdCI6MTc0ODM2NjE5MH0.DZVEYEYANSGVGXdjS6upni48UMKfsOyXt96qoONoQw0",
    "refresh_token": "b4c44b74f63b0b930f2b77da0b7a63b13e6b2460730c139efa3d76238948b762",
    "user_id": "-"  # Use "-" for personal mode
}

def get_db_connection():
    """Create and return a database connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def init_db():
    """Initialize the database with necessary tables."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Crear tabla de usuarios
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                email VARCHAR(255) NOT NULL UNIQUE,
                access_token TEXT,
                refresh_token TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Crear tabla de resúmenes diarios
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_summaries (
                id SERIAL,
                user_id INTEGER REFERENCES users(id),
                date DATE NOT NULL,
                steps INTEGER,
                heart_rate INTEGER,
                sleep_minutes INTEGER,
                calories INTEGER,
                distance FLOAT,
                floors INTEGER,
                elevation FLOAT,
                active_minutes INTEGER,
                sedentary_minutes INTEGER,
                nutrition_calories INTEGER,
                water FLOAT,
                weight FLOAT,
                bmi FLOAT,
                fat FLOAT,
                oxygen_saturation FLOAT,
                respiratory_rate FLOAT,
                temperature FLOAT,
                UNIQUE(user_id, date)
            );
        """)
        
        # Convertir a hipertabla
        cur.execute("""
            SELECT create_hypertable('daily_summaries', 'date', 
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)
        
        # Crear tabla de métricas intradía
        cur.execute("""
            CREATE TABLE IF NOT EXISTS intraday_metrics (
                id SERIAL,
                user_id INTEGER REFERENCES users(id),
                time TIMESTAMPTZ NOT NULL,
                type VARCHAR(50) NOT NULL,
                value FLOAT NOT NULL
            );
        """)
        
        # Convertir a hipertabla
        cur.execute("""
            SELECT create_hypertable('intraday_metrics', 'time',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)

        # Crear tabla de registros de sueño
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sleep_logs (
                id SERIAL,
                user_id INTEGER REFERENCES users(id),
                start_time TIMESTAMPTZ NOT NULL,
                end_time TIMESTAMPTZ NOT NULL,
                duration_ms INTEGER,
                efficiency INTEGER,
                minutes_asleep INTEGER,
                minutes_awake INTEGER,
                minutes_in_rem INTEGER,
                minutes_in_light INTEGER,
                minutes_in_deep INTEGER
            );
        """)
        
        # Convertir a hipertabla
        cur.execute("""
            SELECT create_hypertable('sleep_logs', 'start_time',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)

        # Crear tabla de alertas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL,
                alert_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER REFERENCES users(id),
                alert_type VARCHAR(100) NOT NULL,
                priority VARCHAR(20) NOT NULL,
                triggering_value DOUBLE PRECISION,
                threshold_value VARCHAR(50),
                details TEXT,
                acknowledged BOOLEAN DEFAULT FALSE,
                acknowledged_at TIMESTAMPTZ,
                acknowledged_by INTEGER REFERENCES users(id),
                PRIMARY KEY (id, alert_time)
            );
        """)
        
        # Convertir a hipertabla
        cur.execute("""
            SELECT create_hypertable('alerts', 'alert_time',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)
        
        conn.commit()
        logger.info("Database initialized successfully with TimeScaleDB")
        return True
                
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def get_fitbit_data(access_token, date_str):
    """Get Fitbit data for a specific date."""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    data = {
        'steps': 0,
        'distance': 0,
        'calories': 0,
        'floors': 0,
        'elevation': 0,
        'active_minutes': 0,
        'sedentary_minutes': 0,
        'heart_rate': 0,
        'sleep_minutes': 0,
        'nutrition_calories': 0,
        'water': 0,
        'spo2': 0,
        'respiratory_rate': 0,
        'temperature': 0
    }

    try:
        # Datos de actividad diaria
        activity_url = f"https://api.fitbit.com/1/user/-/activities/date/{date_str}.json"
        response = requests.get(activity_url, headers=headers)
        response.raise_for_status()
        
        activity_data = response.json()
        if 'summary' in activity_data:
            summary = activity_data['summary']
            data.update({
                'steps': summary.get('steps', 0),
                'distance': summary.get('distances', [{}])[0].get('distance', 0),
                'calories': summary.get('caloriesOut', 0),
                'floors': summary.get('floors', 0),
                'elevation': summary.get('elevation', 0),
                'active_minutes': summary.get('veryActiveMinutes', 0),
                'sedentary_minutes': summary.get('sedentaryMinutes', 0)
            })

        # Frecuencia cardíaca
        heart_rate_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{date_str}/1d.json"
        response = requests.get(heart_rate_url, headers=headers)
        response.raise_for_status()
        
        heart_rate_data = response.json()
        if 'activities-heart' in heart_rate_data and heart_rate_data['activities-heart']:
            data['heart_rate'] = heart_rate_data['activities-heart'][0].get('value', {}).get('restingHeartRate', 0)

        # Sueño
        sleep_url = f"https://api.fitbit.com/1.2/user/-/sleep/date/{date_str}.json"
        response = requests.get(sleep_url, headers=headers)
        response.raise_for_status()
        
        sleep_data = response.json()
        if 'sleep' in sleep_data:
            data['sleep_minutes'] = sum(log.get('minutesAsleep', 0) for log in sleep_data['sleep'])

        # Log de datos recopilados
        logger.info(f"\nDatos recopilados para {date_str}:")
        for key, value in data.items():
            logger.info(f"{key}: {value}")

        return data

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise  # Reenviar error 401 para manejo de token expirado
        logger.error(f"Error HTTP al obtener datos de Fitbit: {e}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado al obtener datos de Fitbit: {e}")
        return None

def get_intraday_data(access_token, date_str):
    """Get intraday data for a specific date."""
    headers = {"Authorization": f"Bearer {access_token}"}
    detail_level = "1min"  # Using 1min as per API documentation
    
    try:
        # Verificar scopes del token
        oauth_url = "https://api.fitbit.com/1.1/oauth2/introspect"
        oauth_headers = headers.copy()
        oauth_headers["Content-Type"] = "application/x-www-form-urlencoded"
        oauth_data = {"token": access_token}
        
        oauth_response = requests.post(oauth_url, headers=oauth_headers, data=oauth_data)
        logger.info(f"Token introspection status: {oauth_response.status_code}")
        
        if oauth_response.status_code == 200:
            oauth_data = oauth_response.json()
            scopes = oauth_data.get("scope", "")
            logger.info(f"Available scopes: {scopes}")
            if "HEARTRATE" not in scopes:
                logger.warning("Token does not have HEARTRATE scope. Intraday heart rate data will not be available.")
        else:
            logger.warning(f"Could not verify token scopes: {oauth_response.status_code}")

        # 1. FRECUENCIA CARDÍACA INTRADÍA
        # Using the correct endpoint format for heart rate intraday data
        heart_rate_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{date_str}/{date_str}/{detail_level}.json"
        logger.info(f"Requesting heart rate intraday data from: {heart_rate_url}")
        
        response = requests.get(heart_rate_url, headers=headers)
        response.raise_for_status()
        
        # Print detailed response data
        logger.info("=== Heart Rate API Response Details ===")
        logger.info(f"URL: {heart_rate_url}")
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Headers: {dict(response.headers)}")
        logger.info("Response Body:")
        logger.info(json.dumps(response.json(), indent=2))
        logger.info("=====================================")
        
        heart_data = response.json()
        
        # Check for intraday data in the response
        if 'activities-heart-intraday' in heart_data:
            intraday_data = heart_data['activities-heart-intraday']
            dataset = intraday_data.get('dataset', [])
            dataset_interval = intraday_data.get('datasetInterval', 'N/A')
            dataset_type = intraday_data.get('datasetType', 'N/A')
            
            logger.info(f"Intraday data details:")
            logger.info(f"- Dataset interval: {dataset_interval}")
            logger.info(f"- Dataset type: {dataset_type}")
            logger.info(f"- Number of data points: {len(dataset)}")
            
            if dataset:
                # Log first few data points for verification
                logger.info("Sample data points:")
                for point in dataset[:3]:
                    logger.info(f"  Time: {point.get('time')}, Value: {point.get('value')}")
            
            for point in dataset:
                time_str = point.get('time')
                value = point.get('value')
                if time_str and value:
                    timestamp = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                    yield ('heart_rate', timestamp, value)
        else:
            logger.warning("No intraday heart rate data available in response")
            # Log the summary data if available
            if 'activities-heart' in heart_data:
                for activity in heart_data['activities-heart']:
                    logger.info(f"Summary data for {activity.get('dateTime')}:")
                    logger.info(f"- Resting heart rate: {activity.get('value', {}).get('restingHeartRate', 'N/A')}")
                    logger.info(f"- Heart rate zones: {activity.get('value', {}).get('heartRateZones', [])}")
            
            # Intentar con el endpoint alternativo
            alt_heart_rate_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{date_str}/1d/{detail_level}.json"
            logger.info(f"Trying alternative endpoint: {alt_heart_rate_url}")
            
            alt_response = requests.get(alt_heart_rate_url, headers=headers)
            if alt_response.status_code == 200:
                alt_heart_data = alt_response.json()
                logger.info("Alternative endpoint response:")
                logger.info(json.dumps(alt_heart_data, indent=2))
                
                if 'activities-heart-intraday' in alt_heart_data:
                    logger.info("Found intraday data in alternative endpoint!")
                    intraday_data = alt_heart_data['activities-heart-intraday']
                    dataset = intraday_data.get('dataset', [])
                    
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value:
                            timestamp = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                            yield ('heart_rate', timestamp, value)

        # 2. PASOS INTRADÍA (Steps)
        steps_url = f"https://api.fitbit.com/1/user/-/activities/steps/date/{date_str}/1d/{detail_level}.json"
        logger.info(f"\n=== Steps API Request ===")
        logger.info(f"URL: {steps_url}")
        
        steps_response = requests.get(steps_url, headers=headers)
        logger.info(f"Status Code: {steps_response.status_code}")
        
        if steps_response.status_code == 200:
            steps_data = steps_response.json()
            logger.info("Response Body:")
            logger.info(json.dumps(steps_data, indent=2))
            
            if 'activities-steps-intraday' in steps_data:
                intraday_data = steps_data['activities-steps-intraday']
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de pasos: {len(dataset)}")
                
                for point in dataset:
                    time_str = point.get('time')
                    value = point.get('value')
                    if time_str and value:
                        timestamp = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                        yield ('steps', timestamp, value)
            else:
                logger.warning("No intraday steps data available in response")
        else:
            logger.error(f"Error getting steps data: {steps_response.status_code}")
            logger.error(f"Response: {steps_response.text}")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise  # Reenviar error 401 para manejo de token expirado
        elif e.response.status_code == 429:
            logger.error("Rate limit exceeded. Waiting for reset...")
            reset_time = int(e.response.headers.get('fitbit-rate-limit-reset', 60))
            logger.info(f"Rate limit will reset in {reset_time} seconds")
            time.sleep(reset_time)
            return None
        logger.error(f"Error HTTP al obtener datos intradía: {e}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado al obtener datos intradía: {e}")
        return None

def reset_tables():
    """Drop and recreate all relevant tables."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Drop tables if exist (order matters for foreign keys)
        cur.execute("DROP TABLE IF EXISTS alerts CASCADE;")
        cur.execute("DROP TABLE IF EXISTS sleep_logs CASCADE;")
        cur.execute("DROP TABLE IF EXISTS intraday_metrics CASCADE;")
        cur.execute("DROP TABLE IF EXISTS daily_summaries CASCADE;")
        cur.execute("DROP TABLE IF EXISTS users CASCADE;")
        conn.commit()
        logger.info("All tables dropped successfully.")
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    # Recreate tables
    init_db()

def log_daily_summaries(user_id, start_date, end_date):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT * FROM daily_summaries
            WHERE user_id = %s AND date BETWEEN %s AND %s
            ORDER BY date ASC;
        """, (user_id, start_date, end_date))
        rows = cur.fetchall()
        logger.info(f"\n=== RAW daily_summaries for user_id={user_id} ===")
        for row in rows:
            logger.info(row)
    except Exception as e:
        logger.error(f"Error querying daily_summaries: {e}")
    finally:
        cur.close()
        conn.close()


def log_intraday_metrics(user_id, start_date, end_date):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Raw data
        cur.execute("""
            SELECT * FROM intraday_metrics
            WHERE user_id = %s AND time::date BETWEEN %s AND %s
            ORDER BY time ASC;
        """, (user_id, start_date, end_date))
        rows = cur.fetchall()
        logger.info(f"\n=== RAW intraday_metrics for user_id={user_id} ===")
        for row in rows:
            logger.info(row)
        # Aggregated by 5 minutes
        cur.execute("""
            SELECT type, date_trunc('minute', time) - INTERVAL '1 minute' * (EXTRACT(MINUTE FROM time)::int % 5) AS time_5min, AVG(value) as avg_value
            FROM intraday_metrics
            WHERE user_id = %s AND time::date BETWEEN %s AND %s
            GROUP BY type, time_5min
            ORDER BY type, time_5min ASC;
        """, (user_id, start_date, end_date))
        agg_rows = cur.fetchall()
        logger.info(f"\n=== intraday_metrics aggregated by 5min for user_id={user_id} ===")
        for row in agg_rows:
            logger.info(row)
    except Exception as e:
        logger.error(f"Error querying intraday_metrics: {e}")
    finally:
        cur.close()
        conn.close()

def collect_historical_data(days=3):
    """Collect historical data for the specified number of days."""
    if not FITBIT_CONFIG['access_token']:
        logger.error("No access token provided")
        return False

    try:
        # Reset and reinitialize tables
        reset_tables()

        # Create user if not exists
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (email, access_token, refresh_token)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token
            RETURNING id;
        """, ("Wearable2LivelyAgeign@gmail.com", FITBIT_CONFIG['access_token'], FITBIT_CONFIG['refresh_token']))
        user_id = cur.fetchone()[0]
        conn.commit()

        # Collect data for each day
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            logger.info(f"Collecting data for {date_str}")

            try:
                # Get daily summary (commented out as it works correctly)
                """
                daily_data = get_fitbit_data(FITBIT_CONFIG['access_token'], date_str)
                if daily_data:
                    cur.execute('''
                        INSERT INTO daily_summaries (
                            user_id, date, steps, heart_rate, sleep_minutes,
                            calories, distance, floors, elevation, active_minutes,
                            sedentary_minutes, nutrition_calories, water, weight,
                            bmi, fat, oxygen_saturation, respiratory_rate, temperature
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (user_id, date) DO UPDATE SET
                            steps = EXCLUDED.steps,
                            heart_rate = EXCLUDED.heart_rate,
                            sleep_minutes = EXCLUDED.sleep_minutes,
                            calories = EXCLUDED.calories,
                            distance = EXCLUDED.distance,
                            floors = EXCLUDED.floors,
                            elevation = EXCLUDED.elevation,
                            active_minutes = EXCLUDED.active_minutes,
                            sedentary_minutes = EXCLUDED.sedentary_minutes,
                            nutrition_calories = EXCLUDED.nutrition_calories,
                            water = EXCLUDED.water,
                            weight = EXCLUDED.weight,
                            bmi = EXCLUDED.bmi,
                            fat = EXCLUDED.fat,
                            oxygen_saturation = EXCLUDED.oxygen_saturation,
                            respiratory_rate = EXCLUDED.respiratory_rate,
                            temperature = EXCLUDED.temperature;
                    ''', (
                        user_id, date_str,
                        daily_data['steps'],
                        daily_data['heart_rate'],
                        daily_data['sleep_minutes'],
                        daily_data['calories'],
                        daily_data['distance'],
                        daily_data['floors'],
                        daily_data['elevation'],
                        daily_data['active_minutes'],
                        daily_data['sedentary_minutes'],
                        daily_data['nutrition_calories'],
                        daily_data['water'],
                        daily_data.get('weight', 0),
                        daily_data.get('bmi', 0),
                        daily_data.get('fat', 0),
                        daily_data.get('spo2', 0),
                        daily_data.get('respiratory_rate', 0),
                        daily_data.get('temperature', 0)
                    ))
                    conn.commit()
                    logger.info(f"Daily data saved for {date_str}")
                """

                # Get and save intraday data with improved error handling
                try:
                    # Only collect intraday data for May 26, 2025
                    if date_str == "2025-05-26":
                        intraday_data_points = 0
                        for metric_type, timestamp, value in get_intraday_data(FITBIT_CONFIG['access_token'], date_str):
                            try:
                                cur.execute("""
                                    INSERT INTO intraday_metrics (user_id, time, type, value)
                                    VALUES (%s, %s, %s, %s)
                                """, (user_id, timestamp, metric_type, value))
                                conn.commit()
                                intraday_data_points += 1
                                logger.info(f"Intraday data saved: {metric_type} at {timestamp} with value {value}")
                            except Exception as e:
                                logger.error(f"Error saving intraday data point: {e}")
                                logger.error(f"Failed data: metric_type={metric_type}, timestamp={timestamp}, value={value}")
                                conn.rollback()
                                continue
                        
                        logger.info(f"Total intraday data points saved for {date_str}: {intraday_data_points}")
                        
                        if intraday_data_points == 0:
                            logger.warning(f"No intraday data points were saved for {date_str}")
                            logger.warning("This might indicate an issue with the API response or data format")
                    else:
                        logger.info(f"Skipping intraday data collection for {date_str} (only collecting for May 26)")
                        
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 401:
                        logger.error("Authentication error (401) - Token might be expired")
                        raise  # Re-raise to handle token refresh
                    elif e.response.status_code == 429:
                        logger.error("Rate limit exceeded (429) - Need to implement backoff strategy")
                        time.sleep(60)  # Wait for 1 minute before retrying
                    else:
                        logger.error(f"HTTP error while getting intraday data: {e}")
                        logger.error(f"Response status: {e.response.status_code}")
                        logger.error(f"Response text: {e.response.text}")
                except Exception as e:
                    logger.error(f"Unexpected error while getting intraday data: {e}")
                    logger.error("Stack trace:", exc_info=True)

            except Exception as e:
                logger.error(f"Error collecting data for {date_str}: {e}")
                logger.error("Stack trace:", exc_info=True)
                conn.rollback()

            # Sleep to respect API rate limits
            time.sleep(1)  # 1 second between requests
            current_date += timedelta(days=1)

        # Log daily summaries for the period
        log_daily_summaries(user_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        # Log intraday metrics for the period
        log_intraday_metrics(user_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

        logger.info("Historical data collection completed")
        return True
    except Exception as e:
        logger.error(f"Error collecting historical data: {e}")
        logger.error("Stack trace:", exc_info=True)
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    logger.info("Starting Fitbit personal data collection")
    collect_historical_data()
    logger.info("Finished Fitbit personal data collection") 
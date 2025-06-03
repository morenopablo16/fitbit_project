def get_checkpoint(email):
    """Lee el checkpoint de logs/checkpoint_intraday_{email}.json. Devuelve un dict {metric: last_timestamp_str}."""
    checkpoint_path = f"logs/checkpoint_intraday_{email}.json"
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"No se pudo leer el checkpoint para {email}: {e}")
    return {}

def update_checkpoint(email, checkpoint):
    """Guarda el checkpoint dict en logs/checkpoint_intraday_{email}.json."""
    checkpoint_path = f"logs/checkpoint_intraday_{email}.json"
    try:
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"No se pudo guardar el checkpoint para {email}: {e}")

from base64 import b64encode
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
from db import get_unique_emails, get_latest_user_id_by_email, insert_intraday_metric
import psycopg2
import sys
import os
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/fitbit_intraday_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# --- INTRADAY TOKEN MANAGEMENT ---
INTRADAY_USERS = [
    {
        'email': 'wearable1livelyageign@gmail.com',
        'client_id': os.getenv('INTRADAY_CLIENT_ID_1'),
        'client_secret': os.getenv('INTRADAY_CLIENT_SECRET_1'),
    },
    {
        'email': 'wearable2livelyageign@gmail.com',
        'client_id': os.getenv('INTRADAY_CLIENT_ID_2'),
        'client_secret': os.getenv('INTRADAY_CLIENT_SECRET_2'),
    },
]

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT'),
    'sslmode': 'require',
}

def get_db_conn():
    return psycopg2.connect(**DB_CONFIG)

def create_intraday_tokens_table():
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS intraday_tokens (
                    email VARCHAR(255) PRIMARY KEY,
                    access_token TEXT,
                    refresh_token TEXT,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            conn.commit()

def get_intraday_tokens(email):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT access_token, refresh_token FROM intraday_tokens WHERE email = %s', (email,))
            row = cur.fetchone()
            return row if row else (None, None)

def update_intraday_tokens(email, access_token, refresh_token):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO intraday_tokens (email, access_token, refresh_token, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (email) DO UPDATE SET access_token = EXCLUDED.access_token, refresh_token = EXCLUDED.refresh_token, updated_at = CURRENT_TIMESTAMP
            ''', (email, access_token, refresh_token))
            conn.commit()

def refresh_access_token(refresh_token, client_id, client_secret):
    """
    Refresca el access token usando el refresh token según el estándar OAuth 2.0 (RFC 6749).
    Requiere el client_id y client_secret correctos para el usuario.
    """
    url = "https://api.fitbit.com/oauth2/token"
    # Autenticación del cliente usando Basic Auth
    auth_header = b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    # Parámetros de la solicitud
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    logger.info(f"Refreshing token for client_id {client_id} with refresh_token: {refresh_token[:10]}...")
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        new_tokens = response.json()
        logger.info(f"Token refreshed successfully for client_id {client_id}")
        return new_tokens.get("access_token"), new_tokens.get("refresh_token")
    else:
        logger.error(f"Error refreshing token for client_id {client_id}: {response.status_code}, {response.text}")
        return None, None

def get_intraday_data(access_token, email, date_str=None, checkpoint_time=None):
    """
    Recoge datos intradía para un usuario y un día concreto.
    Si checkpoint_time está definido, solo inserta datos posteriores a ese timestamp.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    if date_str is None:
        today = datetime.now().strftime("%Y-%m-%d")
    else:
        today = date_str
    user_id = get_latest_user_id_by_email(email)
    if not user_id:
        logger.error(f"Error: No se encontró user_id para el email {email}")
        return False

    # Cargar o inicializar checkpoint
    checkpoint = get_checkpoint(email)

    try:
        logger.info(f"\n=== INICIALIZANDO RECOLECCIÓN DE DATOS INTRADÍA PARA {email} ({today}) ===")
        logger.info(f"Token de acceso (primeros 10 caracteres): {access_token[:10]}...")
        total_heart_rate_points = 0
        total_steps_points = 0
        total_calories_points = 0
        total_active_zone_points = 0
        total_distance_points = 0
        detail_level = "1min"

        # 1. FRECUENCIA CARDÍACA INTRADÍA (Heart Rate)
        heart_rate_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de frecuencia cardíaca intradía: {heart_rate_url}")
        heart_response = requests.get(heart_rate_url, headers=headers)
        logger.info(f"Respuesta frecuencia cardíaca: Status {heart_response.status_code}")
        last_hr_ts = checkpoint.get("heart_rate")
        if heart_response.status_code == 200:
            heart_data = heart_response.json()
            if 'activities-heart-intraday' in heart_data:
                intraday_data = heart_data['activities-heart-intraday']
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de frecuencia cardíaca: {len(dataset)}")
                if dataset:
                    logger.info(f"Ejemplos de datos de frecuencia cardíaca:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value is not None:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            if not last_hr_ts or timestamp > datetime.strptime(last_hr_ts, "%Y-%m-%d %H:%M:%S"):
                                insert_intraday_metric(user_id, timestamp, 'heart_rate', value)
                                total_heart_rate_points += 1
                                checkpoint["heart_rate"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        # 2. PASOS INTRADÍA (Steps)
        steps_url = f"https://api.fitbit.com/1/user/-/activities/steps/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de pasos intradía: {steps_url}")
        steps_response = requests.get(steps_url, headers=headers)
        logger.info(f"Respuesta pasos: Status {steps_response.status_code}")
        last_steps_ts = checkpoint.get("steps")
        if steps_response.status_code == 200:
            steps_data = steps_response.json()
            if 'activities-steps-intraday' in steps_data:
                intraday_data = steps_data['activities-steps-intraday']
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de pasos: {len(dataset)}")
                if dataset:
                    logger.info(f"Ejemplos de datos de pasos:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value is not None:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            if not last_steps_ts or timestamp > datetime.strptime(last_steps_ts, "%Y-%m-%d %H:%M:%S"):
                                insert_intraday_metric(user_id, timestamp, 'steps', value)
                                total_steps_points += 1
                                checkpoint["steps"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        # 3. CALORÍAS INTRADÍA (Calories)
        calories_url = f"https://api.fitbit.com/1/user/-/activities/calories/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de calorías intradía: {calories_url}")
        calories_response = requests.get(calories_url, headers=headers)
        logger.info(f"Respuesta calorías: Status {calories_response.status_code}")
        last_calories_ts = checkpoint.get("calories")
        if calories_response.status_code == 200:
            calories_data = calories_response.json()
            if 'activities-calories-intraday' in calories_data:
                intraday_data = calories_data['activities-calories-intraday']
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de calorías: {len(dataset)}")
                if dataset:
                    logger.info(f"Ejemplos de datos de calorías:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value is not None:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            if not last_calories_ts or timestamp > datetime.strptime(last_calories_ts, "%Y-%m-%d %H:%M:%S"):
                                insert_intraday_metric(user_id, timestamp, 'calories', value)
                                total_calories_points += 1
                                checkpoint["calories"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        # 4. DISTANCIA INTRADÍA (Distance)
        distance_url = f"https://api.fitbit.com/1/user/-/activities/distance/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de distancia intradía: {distance_url}")
        distance_response = requests.get(distance_url, headers=headers)
        logger.info(f"Respuesta distancia: Status {distance_response.status_code}")
        last_distance_ts = checkpoint.get("distance")
        if distance_response.status_code == 200:
            distance_data = distance_response.json()
            if 'activities-distance-intraday' in distance_data:
                intraday_data = distance_data['activities-distance-intraday']
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de distancia: {len(dataset)}")
                if dataset:
                    logger.info(f"Ejemplos de datos de distancia:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value is not None:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            if not last_distance_ts or timestamp > datetime.strptime(last_distance_ts, "%Y-%m-%d %H:%M:%S"):
                                insert_intraday_metric(user_id, timestamp, 'distance', value)
                                total_distance_points += 1
                                checkpoint["distance"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        # 5. MINUTOS EN ZONAS ACTIVAS (Active Zone Minutes)
        azm_url = f"https://api.fitbit.com/1/user/-/activities/active-zone-minutes/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de minutos activos intradía: {azm_url}")
        azm_response = requests.get(azm_url, headers=headers)
        logger.info(f"Respuesta minutos activos: Status {azm_response.status_code}")
        last_azm_ts = checkpoint.get("active_zone_minutes")
        if azm_response.status_code == 200:
            azm_data = azm_response.json()
            intraday_key = 'activities-active-zone-minutes-intraday'
            if intraday_key in azm_data:
                intraday_data = azm_data[intraday_key]
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de minutos activos: {len(dataset)}")
                if dataset:
                    logger.info(f"Ejemplos de datos de minutos activos:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value is not None:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            if not last_azm_ts or timestamp > datetime.strptime(last_azm_ts, "%Y-%m-%d %H:%M:%S"):
                                insert_intraday_metric(user_id, timestamp, 'active_zone_minutes', value)
                                total_active_zone_points += 1
                                checkpoint["active_zone_minutes"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Guardar checkpoint actualizado
        update_checkpoint(email, checkpoint)

        total_points = (total_heart_rate_points + total_steps_points + total_calories_points + total_distance_points + total_active_zone_points)
        logger.info("\n=== RESUMEN DE RECOLECCIÓN DE DATOS INTRADÍA ===")
        logger.info(f"Puntos de frecuencia cardíaca: {total_heart_rate_points}")
        logger.info(f"Puntos de pasos: {total_steps_points}")
        logger.info(f"Puntos de calorías: {total_calories_points}")
        logger.info(f"Puntos de distancia: {total_distance_points}")
        logger.info(f"Puntos de minutos activos: {total_active_zone_points}")
        logger.info(f"Total de puntos recolectados: {total_points}")
        if total_points > 0:
            logger.info("\n✅ RECOLECCIÓN DE DATOS INTRADÍA EXITOSA")
            return True
        else:
            logger.warning("\n❌ NO SE PUDIERON RECOLECTAR DATOS INTRADÍA")
            return False
    except requests.exceptions.HTTPError as e:
        if hasattr(e, 'response') and e.response and e.response.status_code == 401:
            logger.error(f"Error de autenticación (401): {str(e)}")
            raise
        logger.error(f"Error HTTP al obtener datos intradía: {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al obtener datos intradía: {str(e)}", exc_info=True)
        return False

def process_intraday_users():
    """
    Procesa los usuarios personales para recopilar datos intradía de Fitbit.
    """
    for user in INTRADAY_USERS:
        email = user['email']
        client_id = user['client_id']
        client_secret = user['client_secret']
        if not client_id or not client_secret:
            logger.error(f"Faltan credenciales para {email} en .env")
            continue

        # Get tokens from DB
        access_token, refresh_token = get_intraday_tokens(email)
        if not access_token or not refresh_token:
            logger.warning(f"No se encontraron tokens válidos para {email} en intraday_tokens. Inserte los tokens iniciales.")
            continue

        # Historical backfill: last 7 days (including today)
        today = datetime.now().date()
        start_date = today - timedelta(days=6)
        up_to_date = True
        for day in range(7):
            date = start_date + timedelta(days=day)
            date_str = date.strftime('%Y-%m-%d')
            try:
                logger.info(f"Recolectando datos intradía para {email} en {date_str}")
                success = get_intraday_data_for_date(access_token, email, date_str)
                if not success:
                    up_to_date = False
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response and e.response.status_code == 401:
                    logger.warning(f"Token expirado para {email}. Intentando refrescar el token...")
                    new_access_token, new_refresh_token = refresh_access_token(refresh_token, client_id, client_secret)
                    if new_access_token and new_refresh_token:
                        update_intraday_tokens(email, new_access_token, new_refresh_token)
                        access_token, refresh_token = new_access_token, new_refresh_token
                        try:
                            success = get_intraday_data_for_date(access_token, email, date_str)
                            if not success:
                                up_to_date = False
                        except Exception as e2:
                            logger.error(f"Error tras refrescar token para {email}: {e2}")
                            up_to_date = False
                    else:
                        logger.error(f"No se pudo refrescar el token para {email}. Reautorice el dispositivo.")
                        up_to_date = False
                elif hasattr(e, 'response') and e.response and e.response.status_code == 429:
                    logger.warning(f"Rate limit alcanzado para {email} en {date_str}. Deteniendo backfill.")
                    up_to_date = False
                    break
                else:
                    logger.error(f"Error HTTP al obtener datos intradía para {email}: {e}")
                    up_to_date = False
            except Exception as e:
                logger.error(f"Error inesperado al procesar {email} en {date_str}: {e}", exc_info=True)
                up_to_date = False
        if up_to_date:
            logger.info(f"Usuario {email} está up to date. Todos los datos intradía recopilados hasta {today}.")

def get_intraday_data_for_date(access_token, email, date_str):
    # Wrapper que asegura checkpoint por usuario/fecha
    return get_intraday_data(access_token, email, date_str)

if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    logger.info("=== INICIO DE EJECUCIÓN DE FITBIT INTRADAY ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    create_intraday_tokens_table()
    process_intraday_users()
    logger.info("=== FIN DE EJECUCIÓN DE FITBIT INTRADAY ===")
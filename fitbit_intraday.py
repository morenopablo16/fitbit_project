"""
FITBIT INTRADAY - MODULAR BACKFILL & CHECKPOINT

Este script permite recopilar datos intradía de Fitbit para múltiples usuarios, con lógica robusta de checkpoint y backfill.

FUNCIONALIDAD PRINCIPAL:
- Para cada usuario, usa checkpoint para saber hasta qué fecha se han recopilado datos.
- Si defines BACKFILL_START_DATE y BACKFILL_END_DATE, solo recopila datos entre esas fechas (ambas incluidas), útil para backfill histórico.
- Si ambas variables están a None, el script funciona en modo normal: solo recopila el día actual si ya está al día (ideal para ejecución periódica tipo cron).
- El checkpoint se guarda por usuario y permite reanudar si se interrumpe la ejecución.
- El rango de backfill es fácilmente modificable editando las variables al principio del script.
- Cuando termines el backfill, pon ambas variables a None para volver al modo normal.

Variables clave a modificar:
    BACKFILL_START_DATE = "2025-05-21"  # Primer día a recopilar (incluido)
    BACKFILL_END_DATE = "2025-05-28"    # Último día a recopilar (incluido)

Si tienes dudas, revisa este bloque o busca 'BACKFILL' en el código.
"""

from base64 import b64encode
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
from db import get_unique_emails, get_latest_user_id_by_email, insert_intraday_metric, get_user_tokens, update_users_tokens
import sys
import os
import json
import time
import logging

# Configuración de logs
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

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')

# --- CHECKPOINT HELPERS ---
def get_checkpoint(email):
    checkpoint_path = f"logs/checkpoint_intraday_{email}.json"
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"No se pudo leer el checkpoint para {email}: {e}")
    return {}

def update_checkpoint(email, checkpoint):
    checkpoint_path = f"logs/checkpoint_intraday_{email}.json"
    try:
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"No se pudo guardar el checkpoint para {email}: {e}")

# --- TOKEN REFRESH ---
def refresh_access_token(refresh_token):
    url = "https://api.fitbit.com/oauth2/token"
    auth_header = b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    logger.info(f"Refreshing token for refresh_token: {refresh_token[:10]}...")
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        new_tokens = response.json()
        logger.info(f"Token refreshed successfully")
        return new_tokens.get("access_token"), new_tokens.get("refresh_token")
    else:
        logger.error(f"Error refreshing token: {response.status_code}, {response.text}")
        return None, None

# --- INTRADAY DATA COLLECTION ---
def get_intraday_data(access_token, email, date_str=None):
    headers = {"Authorization": f"Bearer {access_token}"}
    if date_str is None:
        today = datetime.now().strftime("%Y-%m-%d")
    else:
        today = date_str
    user_id = get_latest_user_id_by_email(email)
    if not user_id:
        logger.error(f"Error: No se encontró user_id para el email {email}")
        return False
    checkpoint = get_checkpoint(email)
    try:
        logger.info(f"\n=== INICIALIZANDO RECOLECCIÓN DE DATOS INTRADÍA PARA {email} ({today}) ===")
        total_heart_rate_points = 0
        total_steps_points = 0
        total_calories_points = 0
        total_active_zone_points = 0
        total_distance_points = 0
        detail_level = "15min"
        # 1. FRECUENCIA CARDÍACA INTRADÍA (Heart Rate)
        heart_rate_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/{detail_level}.json"
        heart_response = requests.get(heart_rate_url, headers=headers)
        last_hr_ts = checkpoint.get("heart_rate")
        if heart_response.status_code == 200:
            heart_data = heart_response.json()
            if 'activities-heart-intraday' in heart_data:
                intraday_data = heart_data['activities-heart-intraday']
                dataset = intraday_data.get('dataset', [])
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
        steps_response = requests.get(steps_url, headers=headers)
        last_steps_ts = checkpoint.get("steps")
        if steps_response.status_code == 200:
            steps_data = steps_response.json()
            if 'activities-steps-intraday' in steps_data:
                intraday_data = steps_data['activities-steps-intraday']
                dataset = intraday_data.get('dataset', [])
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
        calories_response = requests.get(calories_url, headers=headers)
        last_calories_ts = checkpoint.get("calories")
        if calories_response.status_code == 200:
            calories_data = calories_response.json()
            if 'activities-calories-intraday' in calories_data:
                intraday_data = calories_data['activities-calories-intraday']
                dataset = intraday_data.get('dataset', [])
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
        distance_response = requests.get(distance_url, headers=headers)
        last_distance_ts = checkpoint.get("distance")
        if distance_response.status_code == 200:
            distance_data = distance_response.json()
            if 'activities-distance-intraday' in distance_data:
                intraday_data = distance_data['activities-distance-intraday']
                dataset = intraday_data.get('dataset', [])
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
        azm_response = requests.get(azm_url, headers=headers)
        last_azm_ts = checkpoint.get("active_zone_minutes")
        if azm_response.status_code == 200:
            azm_data = azm_response.json()
            intraday_key = 'activities-active-zone-minutes-intraday'
            if intraday_key in azm_data:
                intraday_data = azm_data[intraday_key]
                dataset = intraday_data.get('dataset', [])
                for point in dataset:
                    time_str = point.get('time')
                    value = point.get('value')
                    if time_str and value is not None:
                        timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                        if not last_azm_ts or timestamp > datetime.strptime(last_azm_ts, "%Y-%m-%d %H:%M:%S"):
                            insert_intraday_metric(user_id, timestamp, 'active_zone_minutes', value)
                            total_active_zone_points += 1
                            checkpoint["active_zone_minutes"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        update_checkpoint(email, checkpoint)
        total_points = (total_heart_rate_points + total_steps_points + total_calories_points + total_distance_points + total_active_zone_points)
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

# === CONFIGURACIÓN DE BACKFILL ===
# Si quieres hacer backfill de un rango concreto, pon las fechas en formato 'YYYY-MM-DD'.
# Si no quieres backfill, deja ambas como None.
BACKFILL_START_DATE = "2025-05-21"  # Primer día a recopilar (incluido)
BACKFILL_END_DATE = "2025-05-28"    # Último día a recopilar (incluido)

# --- MAIN WORKFLOW ---
def process_all_users():
    unique_emails = get_unique_emails()
    if not unique_emails:
        logger.error("No se encontraron emails en la base de datos")
        return
    today = datetime.now().date()
    for email in unique_emails:
        logger.info(f"\n=== Procesando usuario: {email} ===")
        access_token, refresh_token = get_user_tokens(email)
        if not access_token or not refresh_token:
            logger.warning(f"No se encontraron tokens válidos para el correo {email}. Es necesario vincular nuevamente el dispositivo.")
            continue
        current_access_token = access_token
        current_refresh_token = refresh_token
        # Leer checkpoint
        checkpoint_path = f"logs/checkpoint_intraday_{email}.json"
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            last_date_str = checkpoint_data.get('last_date')
            if last_date_str:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            else:
                last_date = None
        else:
            last_date = None
        # Determinar rango de fechas a procesar
        if BACKFILL_START_DATE and BACKFILL_END_DATE:
            # Modo backfill: solo recopilar entre esas fechas
            start_date = datetime.strptime(BACKFILL_START_DATE, "%Y-%m-%d").date()
            end_date = datetime.strptime(BACKFILL_END_DATE, "%Y-%m-%d").date()
            if last_date is not None and last_date >= start_date:
                # Si el checkpoint ya está dentro del rango, continuar desde el siguiente día
                current_date = last_date + timedelta(days=1)
            else:
                current_date = start_date
            # Solo procesar hasta end_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                try:
                    logger.info(f"Recolectando datos intradía para {email} en {date_str}")
                    success = get_intraday_data(current_access_token, email, date_str)
                    # Guardar checkpoint
                    with open(checkpoint_path, 'w', encoding='utf-8') as f:
                        json.dump({'last_date': date_str}, f)
                    if not success:
                        logger.warning(f"No se pudieron recolectar datos para {email} en {date_str}")
                except requests.exceptions.HTTPError as e:
                    if hasattr(e, 'response') and e.response and e.response.status_code == 401:
                        logger.warning(f"Token expirado para {email}. Intentando refrescar el token...")
                        new_access_token, new_refresh_token = refresh_access_token(current_refresh_token)
                        if new_access_token and new_refresh_token:
                            update_users_tokens(email, new_access_token, new_refresh_token)
                            current_access_token = new_access_token
                            current_refresh_token = new_refresh_token
                            try:
                                success = get_intraday_data(current_access_token, email, date_str)
                                with open(checkpoint_path, 'w', encoding='utf-8') as f:
                                    json.dump({'last_date': date_str}, f)
                                if not success:
                                    logger.warning(f"No se pudieron recolectar datos tras refrescar token para {email} en {date_str}")
                            except Exception as e2:
                                logger.error(f"Error tras refrescar token para {email}: {e2}")
                        else:
                            logger.error(f"No se pudo refrescar el token para {email}. Reautorice el dispositivo.")
                            break
                    elif hasattr(e, 'response') and e.response and e.response.status_code == 429:
                        logger.warning(f"Rate limit alcanzado para {email} en {date_str}. Deteniendo procesamiento.")
                        break
                    else:
                        logger.error(f"Error HTTP al obtener datos intradía para {email}: {e}")
                except Exception as e:
                    logger.error(f"Error inesperado al procesar {email} en {date_str}: {e}", exc_info=True)
                time.sleep(1)
                current_date += timedelta(days=1)
            logger.info(f"Usuario {email} procesado hasta {end_date} (modo backfill).")
        else:
            # Modo normal: recopilar solo el día actual si ya está al día
            if last_date is None or last_date < today:
                current_date = today
                date_str = current_date.strftime('%Y-%m-%d')
                try:
                    logger.info(f"Recolectando datos intradía para {email} en {date_str}")
                    success = get_intraday_data(current_access_token, email, date_str)
                    with open(checkpoint_path, 'w', encoding='utf-8') as f:
                        json.dump({'last_date': date_str}, f)
                    if not success:
                        logger.warning(f"No se pudieron recolectar datos para {email} en {date_str}")
                except requests.exceptions.HTTPError as e:
                    if hasattr(e, 'response') and e.response and e.response.status_code == 401:
                        logger.warning(f"Token expirado para {email}. Intentando refrescar el token...")
                        new_access_token, new_refresh_token = refresh_access_token(current_refresh_token)
                        if new_access_token and new_refresh_token:
                            update_users_tokens(email, new_access_token, new_refresh_token)
                            current_access_token = new_access_token
                            current_refresh_token = new_refresh_token
                            try:
                                success = get_intraday_data(current_access_token, email, date_str)
                                with open(checkpoint_path, 'w', encoding='utf-8') as f:
                                    json.dump({'last_date': date_str}, f)
                                if not success:
                                    logger.warning(f"No se pudieron recolectar datos tras refrescar token para {email} en {date_str}")
                            except Exception as e2:
                                logger.error(f"Error tras refrescar token para {email}: {e2}")
                        else:
                            logger.error(f"No se pudo refrescar el token para {email}. Reautorice el dispositivo.")
                    elif hasattr(e, 'response') and e.response and e.response.status_code == 429:
                        logger.warning(f"Rate limit alcanzado para {email} en {date_str}. Deteniendo procesamiento.")
                    else:
                        logger.error(f"Error HTTP al obtener datos intradía para {email}: {e}")
                except Exception as e:
                    logger.error(f"Error inesperado al procesar {email} en {date_str}: {e}", exc_info=True)
                time.sleep(1)
            logger.info(f"Usuario {email} procesado para el día {today} (modo normal).")
    logger.info("=== FIN DE EJECUCIÓN DE FITBIT INTRADAY ===")

if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    logger.info("=== INICIO DE EJECUCIÓN DE FITBIT INTRADAY (MODO MULTI-USUARIO DB) ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    process_all_users()
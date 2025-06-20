from base64 import b64encode
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
from db import get_unique_emails, save_to_db, get_user_tokens, get_latest_user_id_by_email, update_users_tokens, insert_daily_summary, insert_intraday_metric, DatabaseManager

import sys
import os
import json
import time
from alert_rules import evaluate_all_alerts

# Configuración de logs
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/fitbit.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

def refresh_access_token(refresh_token):
    """
    Refresca el access token usando el refresh token según el estándar OAuth 2.0 (RFC 6749).
    """
    url = "https://api.fitbit.com/oauth2/token"
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    
    # Autenticación del cliente usando Basic Auth
    auth_header = b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Parámetros de la solicitud
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    # Hacer la solicitud POST
    response = requests.post(url, headers=headers, data=data)
    
    # Verificar la respuesta
    if response.status_code == 200:
        # Si la solicitud es exitosa, devolver los nuevos tokens
        new_tokens = response.json()
        print(f"Token refreshed successfully: {new_tokens}")
        return new_tokens.get("access_token"), new_tokens.get("refresh_token")
    else:
        # Si la solicitud falla, imprimir el error y devolver None
        print(f"Error refreshing token: {response.status_code}, {response.text}")
        return None, None
    


def get_fitbit_data(access_token, email):
    headers = {"Authorization": f"Bearer {access_token}"}
    def fetch_and_store(date_str):
        user_id = get_latest_user_id_by_email(email)
        db = DatabaseManager()
        if not user_id:
            logger.error(f"Error: No se encontró user_id para el email {email}")
            return False
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
            # Nutrición
            nutrition_url = f"https://api.fitbit.com/1/user/-/foods/log/date/{date_str}.json"
            response = requests.get(nutrition_url, headers=headers)
            response.raise_for_status()
            nutrition_data = response.json()
            if 'summary' in nutrition_data:
                data['nutrition_calories'] = nutrition_data['summary'].get('calories', 0)
            # Agua
            water_url = f"https://api.fitbit.com/1/user/-/foods/log/water/date/{date_str}.json"
            response = requests.get(water_url, headers=headers)
            response.raise_for_status()
            water_data = response.json()
            if 'summary' in water_data:
                data['water'] = water_data['summary'].get('water', 0)
            # SpO2
            spo2_url = f"https://api.fitbit.com/1/user/-/spo2/date/{date_str}.json"
            response = requests.get(spo2_url, headers=headers)
            if response.status_code == 200:
                spo2_data = response.json()
                if isinstance(spo2_data.get('value'), dict):
                    data['spo2'] = float(spo2_data['value'].get('avg', 0))
                else:
                    data['spo2'] = float(spo2_data.get('value', 0))
            # Frecuencia respiratoria
            respiratory_rate_url = f"https://api.fitbit.com/1/user/-/br/date/{date_str}.json"
            response = requests.get(respiratory_rate_url, headers=headers)
            if response.status_code == 200:
                respiratory_data = response.json()
                if isinstance(respiratory_data.get('value'), dict):
                    data['respiratory_rate'] = float(respiratory_data['value'].get('breathingRate', 0))
                else:
                    data['respiratory_rate'] = float(respiratory_data.get('value', 0))
            # Temperatura
            temperature_url = f"https://api.fitbit.com/1/user/-/temp/core/date/{date_str}.json"
            response = requests.get(temperature_url, headers=headers)
            if response.status_code == 200:
                temperature_data = response.json()
                data['temperature'] = temperature_data.get('value', 0)
            # Guardar en la base de datos
            insert_daily_summary(
                user_id=user_id,
                date=date_str,
                **data
            )
            # Evaluar alertas después de guardar los datos
            current_date = datetime.strptime(date_str, "%Y-%m-%d")
            alerts = evaluate_all_alerts(user_id, current_date)
            if alerts:
                logger.info(f"Alertas generadas para {email}: {alerts}")
            # Verificar calidad de datos
            if any(v == 0 for v in [data['steps'], data['active_minutes'], data['heart_rate']]):
                if db.connect():
                    try:
                        db.insert_alert(
                            user_id=user_id,
                            alert_type='data_quality',
                            priority='high',
                            triggering_value=0,
                            threshold='30',
                            timestamp=current_date,
                            details="alerts.data_quality.zero_values"
                        )
                    finally:
                        db.close()
            logger.info(f"Datos recopilados para {email} en {date_str}:")
            for key, value in data.items():
                logger.info(f"{key}: {value}")
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise
            elif e.response.status_code == 429:
                logger.warning(f"Rate limit (429) alcanzado para {email} en {date_str}")
                raise
            logger.error(f"Error HTTP al obtener datos de Fitbit: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al obtener datos de Fitbit: {e}")
            return False
    return fetch_and_store

def process_emails(emails):

    # Filtrar correos electrónicos vacíos
    valid_emails = [email for email in emails if email and email.strip()]
    if not valid_emails:
        logger.warning("No se proporcionaron correos electrónicos válidos para procesar.")
        return

    # Rango de fechas
    START_DATE = datetime(2025, 2, 1)
    END_DATE = datetime.now()

    for email in valid_emails:
        logger.info(f"\n=== Procesando usuario: {email} ===")
        # Obtener y desencriptar los tokens
        access_token, refresh_token = get_user_tokens(email)
        if not access_token or not refresh_token:
            logger.warning(f"No se encontraron tokens válidos para el correo {email}. Es necesario vincular nuevamente el dispositivo.")
            continue

        # Checkpoint path
        checkpoint_path = f"logs/checkpoint_{email.replace('@','_at_')}.json"
        # Leer checkpoint
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, 'r') as f:
                checkpoint = json.load(f)
            last_date_str = checkpoint.get('last_date')
            if last_date_str:
                current_date = datetime.strptime(last_date_str, "%Y-%m-%d")
            else:
                current_date = START_DATE
        else:
            current_date = START_DATE

        fetch_and_store = get_fitbit_data(access_token, email)
        rate_limit_hit = False
        current_access_token = access_token
        current_refresh_token = refresh_token
        while current_date <= END_DATE:
            date_str = current_date.strftime("%Y-%m-%d")
            logger.info(f"Procesando {date_str} para {email}")
            try:
                success = fetch_and_store(date_str)
                if success:
                    logger.info(f"Datos recopilados exitosamente para {email} en {date_str}.")
                # Guardar checkpoint
                with open(checkpoint_path, 'w') as f:
                    json.dump({'last_date': date_str}, f)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    logger.warning(f"Token expirado para el correo {email}. Intentando refrescar el token...")
                    new_access_token, new_refresh_token = refresh_access_token(current_refresh_token)
                    if new_access_token and new_refresh_token:
                        update_users_tokens(email, new_access_token, new_refresh_token)
                        current_access_token = new_access_token
                        current_refresh_token = new_refresh_token
                        fetch_and_store = get_fitbit_data(current_access_token, email)
                        continue  # Reintentar el mismo día con el nuevo token
                    else:
                        logger.error(f"No se pudo refrescar el token para el correo {email}. Es necesario vincular nuevamente el dispositivo.")
                        break
                elif e.response.status_code == 429:
                    logger.warning(f"Rate limit alcanzado para {email} en {date_str}. Guardando checkpoint y saltando al siguiente usuario.")
                    with open(checkpoint_path, 'w') as f:
                        json.dump({'last_date': date_str}, f)
                    rate_limit_hit = True
                    break
                else:
                    logger.error(f"Error HTTP al obtener datos de Fitbit para el correo {email}: {e}")
            except Exception as e:
                logger.error(f"Error inesperado al procesar el correo {email} en {date_str}: {e}")
            # Sleep para evitar rate limit
            time.sleep(1)
            current_date += timedelta(days=1)

        if not rate_limit_hit and current_date > END_DATE:
            logger.info(f"Usuario {email} está up to date. Todos los datos recopilados hasta {END_DATE.strftime('%Y-%m-%d')}.")

if __name__ == "__main__":
    # Crear directorio de logs si no existe
    os.makedirs("logs", exist_ok=True)
    # Obtener la lista de emails únicos
    unique_emails = get_unique_emails()
    if not unique_emails:
        logger.error("No se encontraron emails en la base de datos")
        sys.exit(1)
    logger.info(f"Emails únicos encontrados en la base de datos: {unique_emails}")
    process_emails(unique_emails)
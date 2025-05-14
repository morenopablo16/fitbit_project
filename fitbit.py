from base64 import b64encode
from dotenv import load_dotenv
import requests
from datetime import datetime
from db import get_unique_emails, save_to_db, get_user_tokens, get_latest_user_id_by_email, update_users_tokens, insert_daily_summary, insert_intraday_metric, DatabaseManager
import sys
import os
from alert_rules import evaluate_all_alerts

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
    today = datetime.now().strftime("%Y-%m-%d")
    user_id = get_latest_user_id_by_email(email)
    db = DatabaseManager()
    
    if not user_id:
        print(f"Error: No se encontró user_id para el email {email}")
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
        activity_url = f"https://api.fitbit.com/1/user/-/activities/date/{today}.json"
        response = requests.get(activity_url, headers=headers)
        response.raise_for_status()  # Lanzará una excepción si hay error HTTP
        
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
        heart_rate_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d.json"
        response = requests.get(heart_rate_url, headers=headers)
        response.raise_for_status()
        
        heart_rate_data = response.json()
        if 'activities-heart' in heart_rate_data and heart_rate_data['activities-heart']:
            data['heart_rate'] = heart_rate_data['activities-heart'][0].get('value', {}).get('restingHeartRate', 0)

        # Sueño
        sleep_url = f"https://api.fitbit.com/1.2/user/-/sleep/date/{today}.json"
        response = requests.get(sleep_url, headers=headers)
        response.raise_for_status()
        
        sleep_data = response.json()
        if 'sleep' in sleep_data:
            data['sleep_minutes'] = sum(log.get('minutesAsleep', 0) for log in sleep_data['sleep'])

        # Nutrición
        nutrition_url = f"https://api.fitbit.com/1/user/-/foods/log/date/{today}.json"
        response = requests.get(nutrition_url, headers=headers)
        response.raise_for_status()
        
        nutrition_data = response.json()
        if 'summary' in nutrition_data:
            data['nutrition_calories'] = nutrition_data['summary'].get('calories', 0)

        # Agua
        water_url = f"https://api.fitbit.com/1/user/-/foods/log/water/date/{today}.json"
        response = requests.get(water_url, headers=headers)
        response.raise_for_status()
        
        water_data = response.json()
        if 'summary' in water_data:
            data['water'] = water_data['summary'].get('water', 0)

        # SpO2
        spo2_url = f"https://api.fitbit.com/1/user/-/spo2/date/{today}.json"
        response = requests.get(spo2_url, headers=headers)
        if response.status_code == 200:  # SpO2 podría no estar disponible
            spo2_data = response.json()
            if isinstance(spo2_data.get('value'), dict):
                data['spo2'] = float(spo2_data['value'].get('avg', 0))
            else:
                data['spo2'] = float(spo2_data.get('value', 0))

        # Frecuencia respiratoria
        respiratory_rate_url = f"https://api.fitbit.com/1/user/-/br/date/{today}.json"
        response = requests.get(respiratory_rate_url, headers=headers)
        if response.status_code == 200:  # Frecuencia respiratoria podría no estar disponible
            respiratory_data = response.json()
            if isinstance(respiratory_data.get('value'), dict):
                data['respiratory_rate'] = float(respiratory_data['value'].get('breathingRate', 0))
            else:
                data['respiratory_rate'] = float(respiratory_data.get('value', 0))

        # Temperatura
        temperature_url = f"https://api.fitbit.com/1/user/-/temp/core/date/{today}.json"
        response = requests.get(temperature_url, headers=headers)
        if response.status_code == 200:  # Temperatura podría no estar disponible
            temperature_data = response.json()
            data['temperature'] = temperature_data.get('value', 0)

        # Guardar en la base de datos
        insert_daily_summary(
            user_id=user_id,
            date=today,
            **data
        )

        # Evaluar alertas después de guardar los datos
        current_date = datetime.now()
        alerts = evaluate_all_alerts(user_id, current_date)
        if alerts:
            print(f"Alertas generadas para {email}: {alerts}")

        # Verificar calidad de datos
        if any(v == 0 for v in [data['steps'], data['active_minutes'], data['heart_rate']]):
            if db.connect():
                db.insert_alert(
                    user_id=user_id,
                    alert_type='data_quality',
                    priority='high',
                    value=0,
                    threshold='30',  # Valor mínimo esperado para considerar datos válidos
                    timestamp=current_date
                )
                db.close()

        # Log de datos recopilados
        print(f"\nDatos recopilados para {email} en {today}:")
        for key, value in data.items():
            print(f"{key}: {value}")

        return True

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise  # Reenviar error 401 para manejo de token expirado
        print(f"Error HTTP al obtener datos de Fitbit: {e}")
        return False
    except Exception as e:
        print(f"Error inesperado al obtener datos de Fitbit: {e}")
        return False

def process_emails(emails):
    """
    Procesa una lista de correos electrónicos para recopilar datos de Fitbit.
    """
    # Filtrar correos electrónicos vacíos
    valid_emails = [email for email in emails if email and email.strip()]
    
    if not valid_emails:
        print("No se proporcionaron correos electrónicos válidos para procesar.")
        return
    
    for email in valid_emails:
        try:
            # Obtener el user_id más reciente asociado al correo electrónico
            user_id = get_latest_user_id_by_email(email)
            if not user_id:
                print(f"No se encontró un usuario con el correo {email}. Verifique que el usuario esté registrado.")
                continue
           
            # Obtener y desencriptar los tokens
            access_token, refresh_token = get_user_tokens(email)
            if not access_token or not refresh_token:
                print(f"No se encontraron tokens válidos para el correo {email}. Es necesario vincular nuevamente el dispositivo.")
                continue

            # Intentar obtener los datos de Fitbit
            try:
                success = get_fitbit_data(access_token, email)
                if success:
                    print(f"Datos recopilados exitosamente para {email}.")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:  # Token expirado
                    print(f"Token expirado para el correo {email}. Intentando refrescar el token...")
                    new_access_token, new_refresh_token = refresh_access_token(refresh_token)
                    if new_access_token and new_refresh_token:
                        # Actualizar los tokens en la base de datos
                        update_users_tokens(email, new_access_token, new_refresh_token)

                        # Volver a intentar la solicitud con el nuevo token
                        try:
                            success = get_fitbit_data(new_access_token, email)
                            if success:
                                print(f"Datos recopilados exitosamente para {email} después de refrescar el token.")
                        except requests.exceptions.HTTPError as e:
                            print(f"Error HTTP al obtener datos de Fitbit para el correo {email} después de refrescar el token: {e}")
                    else:
                        print(f"No se pudo refrescar el token para el correo {email}. Es necesario vincular nuevamente el dispositivo.")
                else:
                    print(f"Error HTTP al obtener datos de Fitbit para el correo {email}: {e}")
        except Exception as e:
            print(f"Error inesperado al procesar el correo {email}: {e}")

if __name__ == "__main__":
    # Verificar que se proporcionen los argumentos necesarios
    # if len(sys.argv) < 2:
    #     print("Usage: python fitbit.py <email1> <email2> ...")
    #     sys.exit(1)

    # Obtener la lista de correos electrónicos desde los argumentos de la terminal
    # emails = sys.argv[1:]
    emails = ["Wearable4LivelyAgeign@gmail.com", ""]
    # # Obtener la lista de emails únicos
    # unique_emails = get_unique_emails()
    # print(f"Emails únicos: {unique_emails}") 

    # Procesar cada correo electrónico
    process_emails(emails)
from base64 import b64encode
from dotenv import load_dotenv
import requests
from datetime import datetime
from db import get_unique_emails, save_to_db, get_user_tokens, get_latest_user_id_by_email, update_users_tokens, insert_daily_summary, insert_intraday_metric
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

    # Datos de actividad diaria (pasos, distancia, calorías, pisos, elevación, minutos activos, minutos sedentarios)
    activity_url = f"https://api.fitbit.com/1/user/-/activities/date/{today}.json"
    response = requests.get(activity_url, headers=headers)
    print(f"Activity API response status: {response.status_code}")
    print(f"Activity API response: {response.json()}")
    if (response.status_code == 401 and  response.json().get("errors", [{}])[0].get("errorType") == "expired_token"):
        raise requests.exceptions.HTTPError("Token expirado", response=response)
    
    activity_data = response.json()
    steps = activity_data.get("summary", {}).get("steps", 0)
    distance = activity_data.get("summary", {}).get("distances", [{}])[0].get("distance", 0)
    calories = activity_data.get("summary", {}).get("caloriesOut", 0)
    floors = activity_data.get("summary", {}).get("floors", 0)
    elevation = activity_data.get("summary", {}).get("elevation", 0)
    active_minutes = activity_data.get("summary", {}).get("veryActiveMinutes", 0)
    sedentary_minutes = activity_data.get("summary", {}).get("sedentaryMinutes", 0)

    # Frecuencia cardíaca promedio diaria
    heart_rate_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d.json"
    response = requests.get(heart_rate_url, headers=headers)
    print(f"Heart Rate API response status: {response.status_code}")
    print(f"Heart Rate API response: {response.json()}")
    heart_rate_data = response.json()
    heart_rate = heart_rate_data.get("activities-heart", [{}])[0].get("value", {}).get("restingHeartRate", 0)

    # Sueño (tiempo total y fases del sueño)
    sleep_url = f"https://api.fitbit.com/1.2/user/-/sleep/date/{today}.json"
    response = requests.get(sleep_url, headers=headers)
    print(f"Sleep API response status: {response.status_code}")
    print(f"Sleep API response: {response.json()}")
    sleep_data = response.json()
    sleep_minutes = sum([log.get("minutesAsleep", 0) for log in sleep_data.get("sleep", [])])

    # Nutrición (calorías consumidas)
    nutrition_url = f"https://api.fitbit.com/1/user/-/foods/log/date/{today}.json"
    response = requests.get(nutrition_url, headers=headers)
    print(f"Nutrition API response status: {response.status_code}")
    print(f"Nutrition API response: {response.json()}")
    nutrition_data = response.json()
    nutrition_calories = nutrition_data.get("summary", {}).get("calories", 0)

    # Agua (consumo de agua)
    water_url = f"https://api.fitbit.com/1/user/-/foods/log/water/date/{today}.json"
    response = requests.get(water_url, headers=headers)
    print(f"Water API response status: {response.status_code}")
    print(f"Water API response: {response.json()}")
    water_data = response.json()
    water = water_data.get("summary", {}).get("water", 0)

    # Oxígeno en sangre (SpO2)
    spo2_url = f"https://api.fitbit.com/1/user/-/spo2/date/{today}.json"
    response = requests.get(spo2_url, headers=headers)
    print(f"SpO2 API response status: {response.status_code}")
    print(f"SpO2 API response: {response.json()}")
    spo2_data = response.json()
    spo2 = spo2_data.get("value", 0)

 # Frecuencia respiratoria
    respiratory_rate_url = f"https://api.fitbit.com/1/user/-/br/date/{today}.json"
    response = requests.get(respiratory_rate_url, headers=headers)
    print(f"Respiratory Rate API response status: {response.status_code}")
    print(f"Respiratory Rate API response: {response.json()}")
    respiratory_rate_data = response.json()
    respiratory_rate = 0  # Valor por defecto
    if respiratory_rate_data.get("br"):
        respiratory_rate = respiratory_rate_data.get("br", [{}])[0].get("value", 0)

    # Temperatura corporal
    temperature_url = f"https://api.fitbit.com/1/user/-/temp/core/date/{today}.json"
    response = requests.get(temperature_url, headers=headers)
    print(f"Temperature API response status: {response.status_code}")
    print(f"Temperature API response: {response.json()}")
    temperature_data = response.json()
    temperature = temperature_data.get("value", 0)

    # Guardar en la base de datos usando la nueva función insert_daily_summary
    date = datetime.now().strftime("%Y-%m-%d")
    user_id = get_latest_user_id_by_email(email)
    insert_daily_summary(
        user_id=user_id,
        date=date,
        steps=steps,
        heart_rate=heart_rate,
        sleep_minutes=sleep_minutes,
        calories=calories,
        distance=distance,
        floors=floors,
        elevation=elevation,
        active_minutes=active_minutes,
        sedentary_minutes=sedentary_minutes,
        nutrition_calories=nutrition_calories,
        water=water,
        oxygen_saturation=spo2,
        respiratory_rate=respiratory_rate,
        temperature=temperature
    )

    # Evaluar alertas después de guardar los datos
    alerts = evaluate_all_alerts(user_id)
    if alerts:
        print(f"Alertas generadas para {email}: {alerts}")

    # Imprimir los datos recopilados
    print(f"Email: {email}")
    print(f"Date: {date}")
    print(f"Steps: {steps}")
    print(f"Distance: {distance} km")
    print(f"Calories: {calories} kcal")
    print(f"Floors: {floors}")
    print(f"Elevation: {elevation} m")
    print(f"Active Minutes: {active_minutes} min")
    print(f"Sedentary Minutes: {sedentary_minutes} min")
    print(f"Heart Rate: {heart_rate} bpm")
    print(f"Sleep Minutes: {sleep_minutes} min")
    print(f"Nutrition Calories: {nutrition_calories} kcal")
    print(f"Water: {water} L")
    print(f"SpO2: {spo2}%")
    print(f"Respiratory Rate: {respiratory_rate} breaths/min")
    print(f"Temperature: {temperature} °C")

def process_emails(emails):
    """
    Procesa una lista de correos electrónicos para recopilar datos de Fitbit.
    """
    for email in emails:
        # Obtener el user_id más reciente asociado al correo electrónico
        user_id = get_latest_user_id_by_email(email)
        if not user_id:
            print(f"No se encontró un usuario con el correo {email}.")
            continue
       
       
        # Obtener y desencriptar los tokens
        access_token, refresh_token = get_user_tokens(email)
        if not access_token or not refresh_token:
            print(f"No se encontraron tokens válidos para el correo {email}.")
            continue

        # Intentar obtener los datos de Fitbit
        try:
            get_fitbit_data(access_token, email)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:  # Token expirado
                print(f"Token expirado para el correo {email}. Intentando refrescar el token...")
                new_access_token, new_refresh_token = refresh_access_token(refresh_token)
                if new_access_token and new_refresh_token:
                    # Actualizar los tokens en la base de datos
                    update_users_tokens(email, new_access_token, new_refresh_token)

                    # Volver a intentar la solicitud con el nuevo token
                    try:
                        get_fitbit_data(new_access_token, email)
                    except requests.exceptions.HTTPError as e:
                        print(f"Error al obtener datos de Fitbit para el correo {email} después de refrescar el token: {e}")
                else:
                    print(f"No se pudo refrescar el token para el correo {email}.")
            else:
                print(f"Error al obtener datos de Fitbit para el correo {email}: {e}")

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
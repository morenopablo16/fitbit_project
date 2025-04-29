from base64 import b64encode
from dotenv import load_dotenv
import requests
from datetime import datetime
from db import get_unique_emails, get_user_tokens, get_latest_user_id_by_email, update_users_tokens, insert_intraday_metric
import sys
import os

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

def get_intraday_data(access_token, email):
    headers = {"Authorization": f"Bearer {access_token}"}
    today = datetime.now().strftime("%Y-%m-%d")
    user_id = get_latest_user_id_by_email(email)

    # Intraday Steps (1-minute granularity)
    steps_intraday_url = f"https://api.fitbit.com/1/user/-/activities/steps/date/{today}/1d/1min.json"
    response = requests.get(steps_intraday_url, headers=headers)
    if response.status_code == 401 and response.json().get("errors", [{}])[0].get("errorType") == "expired_token":
        raise requests.exceptions.HTTPError("Token expirado", response=response)
    if response.status_code == 200:
        steps_data = response.json().get("activities-steps-intraday", {}).get("dataset", [])
        if steps_data:
            for item in steps_data:
                timestamp = datetime.strptime(f"{today} {item['time']}", "%Y-%m-%d %H:%M:%S")
                insert_intraday_metric(user_id, timestamp, "steps", item['value'])
            print(f"Intraday Steps data collected for {email}")
        else:
            print(f"No intraday steps data available for {email}")
    else:
        print(f"Error fetching intraday steps for {email}: {response.status_code}, {response.text}")

    # Intraday Heart Rate (1-minute granularity)
    heart_rate_intraday_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/1min.json"
    response = requests.get(heart_rate_intraday_url, headers=headers)
    if response.status_code == 200:
        heart_rate_data = response.json().get("activities-heart-intraday", {}).get("dataset", [])
        if heart_rate_data:
            for item in heart_rate_data:
                timestamp = datetime.strptime(f"{today} {item['time']}", "%Y-%m-%d %H:%M:%S")
                insert_intraday_metric(user_id, timestamp, "heart_rate", item['value'])
            print(f"Intraday Heart Rate data collected for {email}")
        else:
            print(f"No intraday heart rate data available for {email}")
    else:
        print(f"Error fetching intraday heart rate for {email}: {response.status_code}, {response.text}")

    # Intraday Active Zone Minutes (1-minute granularity)
    azm_intraday_url = f"https://api.fitbit.com/1/user/-/activities/active-zone-minutes/date/{today}/1d/1min.json"
    response = requests.get(azm_intraday_url, headers=headers)
    if response.status_code == 200:
        azm_data = response.json().get("activities-active-zone-minutes-intraday", {}).get("dataset", [])
        if azm_data:
            for item in azm_data:
                timestamp = datetime.strptime(f"{today} {item['time']}", "%Y-%m-%d %H:%M:%S")
                insert_intraday_metric(user_id, timestamp, "active_zone_minutes", item['value'])
            print(f"Intraday Active Zone Minutes data collected for {email}")
        else:
            print(f"No intraday active zone minutes data available for {email}")
    else:
        print(f"Error fetching intraday active zone minutes for {email}: {response.status_code}, {response.text}")

    # Intraday Calories (1-minute granularity)
    calories_intraday_url = f"https://api.fitbit.com/1/user/-/activities/calories/date/{today}/1d/1min.json"
    response = requests.get(calories_intraday_url, headers=headers)
    if response.status_code == 200:
        calories_data = response.json().get("activities-calories-intraday", {}).get("dataset", [])
        if calories_data:
            for item in calories_data:
                timestamp = datetime.strptime(f"{today} {item['time']}", "%Y-%m-%d %H:%M:%S")
                insert_intraday_metric(user_id, timestamp, "calories", item['value'])
            print(f"Intraday Calories data collected for {email}")
        else:
            print(f"No intraday calories data available for {email}")
    else:
        print(f"Error fetching intraday calories for {email}: {response.status_code}, {response.text}")

def process_emails(emails):
    """
    Procesa una lista de correos electrónicos para recopilar datos de Fitbit.
    """
    for email in emails:
        if not email:  # Skip empty emails
            continue
            
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
            get_intraday_data(access_token, email)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:  # Token expirado
                print(f"Token expirado para el correo {email}. Intentando refrescar el token...")
                new_access_token, new_refresh_token = refresh_access_token(refresh_token)
                if new_access_token and new_refresh_token:
                    # Actualizar los tokens en la base de datos
                    update_users_tokens(email, new_access_token, new_refresh_token)

                    # Volver a intentar la solicitud con el nuevo token
                    try:
                        get_intraday_data(new_access_token, email)
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
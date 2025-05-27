from base64 import b64encode
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
from db import get_unique_emails, get_user_tokens, get_latest_user_id_by_email, update_users_tokens, insert_intraday_metric
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
    
    logger.info(f"Refreshing token with refresh_token: {refresh_token[:10]}...")
    
    # Hacer la solicitud POST
    response = requests.post(url, headers=headers, data=data)
    
    # Verificar la respuesta
    if response.status_code == 200:
        # Si la solicitud es exitosa, devolver los nuevos tokens
        new_tokens = response.json()
        logger.info(f"Token refreshed successfully")
        return new_tokens.get("access_token"), new_tokens.get("refresh_token")
    else:
        # Si la solicitud falla, imprimir el error y devolver None
        logger.error(f"Error refreshing token: {response.status_code}, {response.text}")
        return None, None

def get_intraday_data(access_token, email):
    headers = {"Authorization": f"Bearer {access_token}"}
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    user_id = get_latest_user_id_by_email(email)
    
    if not user_id:
        logger.error(f"Error: No se encontró user_id para el email {email}")
        return False

    try:
        logger.info(f"\n=== INICIALIZANDO RECOLECCIÓN DE DATOS INTRADÍA PARA {email} ({today}) ===")
        logger.info(f"Token de acceso (primeros 10 caracteres): {access_token[:10]}...")
        
        # Verificar acceso a datos intradía y suscripción
        logger.info("\n=== VERIFICANDO PERMISO DE ACCESO A DATOS INTRADÍA ===")
        
        # Verificar permisos del token (OAuth introspection)
        oauth_url = "https://api.fitbit.com/1.1/oauth2/introspect"
        oauth_headers = headers.copy()
        oauth_headers["Content-Type"] = "application/x-www-form-urlencoded"
        oauth_data = {"token": access_token}
        
        oauth_response = requests.post(oauth_url, headers=oauth_headers, data=oauth_data)
        logger.info(f"Verificación de token OAuth: {oauth_response.status_code}")
        
        if oauth_response.status_code == 200:
            oauth_data = oauth_response.json()
            logger.info(f"Información del token: {oauth_data}")
            scopes = oauth_data.get("scope", "")
            logger.info(f"Scopes disponibles: {scopes}")
        else:
            logger.warning(f"No se pudo verificar el token OAuth: {oauth_response.status_code}, {oauth_response.text}")
        
        # Obtener perfil para verificar el tipo de usuario
        profile_url = "https://api.fitbit.com/1/user/-/profile.json"
        logger.info(f"Verificando perfil para comprobar tipo de usuario: {profile_url}")
        
        profile_response = requests.get(profile_url, headers=headers)
        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            logger.info(f"Perfil obtenido con éxito - Token válido")
            # Registrar información útil del perfil para diagnóstico
            if 'user' in profile_data:
                user_info = profile_data['user']
                logger.info(f"ID de usuario: {user_info.get('encodedId', 'N/A')}")
                logger.info(f"Tipo de cuenta: {user_info.get('memberSince', 'N/A')}")
                logger.info(f"Dispositivo: {user_info.get('deviceVersion', 'N/A')}")
        else:
            logger.error(f"Error al obtener perfil: {profile_response.status_code}, {profile_response.text}")

        # Contadores para estadísticas de datos intradía
        total_heart_rate_points = 0
        total_steps_points = 0
        total_calories_points = 0
        total_active_zone_points = 0
        total_distance_points = 0
        
        # Solo usar nivel de detalle de 1 minuto
        detail_level = "1min"
        
        logger.info(f"\n=== INTENTANDO RECOLECTAR DATOS INTRADÍA CON NIVEL DE DETALLE: {detail_level} ===")
        
        # 1. FRECUENCIA CARDÍACA INTRADÍA (Heart Rate)
        heart_rate_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de frecuencia cardíaca intradía: {heart_rate_url}")
        
        heart_response = requests.get(heart_rate_url, headers=headers)
        logger.info(f"Respuesta frecuencia cardíaca: Status {heart_response.status_code}")
        
        if heart_response.status_code == 200:
            heart_data = heart_response.json()
            logger.info(f"Estructura de respuesta: {json.dumps(heart_data, indent=2)[:500]}...")
            
            # Verificar si hay datos intradía de frecuencia cardíaca
            if 'activities-heart-intraday' in heart_data:
                intraday_data = heart_data['activities-heart-intraday']
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de frecuencia cardíaca: {len(dataset)}")
                
                if dataset:
                    # Registrar ejemplos de datos
                    logger.info(f"Ejemplos de datos de frecuencia cardíaca:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    
                    # Guardar datos en la base de datos
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            insert_intraday_metric(user_id, timestamp, 'heart_rate', value)
                            total_heart_rate_points += 1
                    
                    logger.info(f"Guardados {total_heart_rate_points} puntos de frecuencia cardíaca con detalle {detail_level}")
                else:
                    logger.warning(f"No se encontraron datos de frecuencia cardíaca para {detail_level}")
            else:
                logger.warning(f"No se encontró la sección 'activities-heart-intraday' en la respuesta")
        else:
            logger.error(f"Error al obtener datos de frecuencia cardíaca: {heart_response.status_code}")
            logger.error(f"Detalles: {heart_response.text}")
        
        # 2. PASOS INTRADÍA (Steps)
        steps_url = f"https://api.fitbit.com/1/user/-/activities/steps/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de pasos intradía: {steps_url}")
        
        steps_response = requests.get(steps_url, headers=headers)
        logger.info(f"Respuesta pasos: Status {steps_response.status_code}")
        
        if steps_response.status_code == 200:
            steps_data = steps_response.json()
            
            if 'activities-steps-intraday' in steps_data:
                intraday_data = steps_data['activities-steps-intraday']
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de pasos: {len(dataset)}")
                
                if dataset:
                    # Registrar ejemplos de datos
                    logger.info(f"Ejemplos de datos de pasos:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    
                    # Guardar datos en la base de datos
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            insert_intraday_metric(user_id, timestamp, 'steps', value)
                            total_steps_points += 1
                    
                    logger.info(f"Guardados {total_steps_points} puntos de pasos con detalle {detail_level}")
                else:
                    logger.warning(f"No se encontraron datos de pasos para {detail_level}")
            else:
                logger.warning(f"No se encontró la sección 'activities-steps-intraday' en la respuesta")
        else:
            logger.error(f"Error al obtener datos de pasos: {steps_response.status_code}")
            logger.error(f"Detalles: {steps_response.text}")
        
        # 3. CALORÍAS INTRADÍA (Calories)
        calories_url = f"https://api.fitbit.com/1/user/-/activities/calories/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de calorías intradía: {calories_url}")
        
        calories_response = requests.get(calories_url, headers=headers)
        logger.info(f"Respuesta calorías: Status {calories_response.status_code}")
        
        if calories_response.status_code == 200:
            calories_data = calories_response.json()
            
            if 'activities-calories-intraday' in calories_data:
                intraday_data = calories_data['activities-calories-intraday']
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de calorías: {len(dataset)}")
                
                if dataset:
                    # Registrar ejemplos de datos
                    logger.info(f"Ejemplos de datos de calorías:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    
                    # Guardar datos en la base de datos
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            insert_intraday_metric(user_id, timestamp, 'calories', value)
                            total_calories_points += 1
                    
                    logger.info(f"Guardados {total_calories_points} puntos de calorías con detalle {detail_level}")
                else:
                    logger.warning(f"No se encontraron datos de calorías para {detail_level}")
            else:
                logger.warning(f"No se encontró la sección 'activities-calories-intraday' en la respuesta")
        else:
            logger.error(f"Error al obtener datos de calorías: {calories_response.status_code}")
            logger.error(f"Detalles: {calories_response.text}")
        
        # 4. DISTANCIA INTRADÍA (Distance)
        distance_url = f"https://api.fitbit.com/1/user/-/activities/distance/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de distancia intradía: {distance_url}")
        
        distance_response = requests.get(distance_url, headers=headers)
        logger.info(f"Respuesta distancia: Status {distance_response.status_code}")
        
        if distance_response.status_code == 200:
            distance_data = distance_response.json()
            
            if 'activities-distance-intraday' in distance_data:
                intraday_data = distance_data['activities-distance-intraday']
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de distancia: {len(dataset)}")
                
                if dataset:
                    # Registrar ejemplos de datos
                    logger.info(f"Ejemplos de datos de distancia:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    
                    # Guardar datos en la base de datos
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            insert_intraday_metric(user_id, timestamp, 'distance', value)
                            total_distance_points += 1
                    
                    logger.info(f"Guardados {total_distance_points} puntos de distancia con detalle {detail_level}")
                else:
                    logger.warning(f"No se encontraron datos de distancia para {detail_level}")
            else:
                logger.warning(f"No se encontró la sección 'activities-distance-intraday' en la respuesta")
        else:
            logger.error(f"Error al obtener datos de distancia: {distance_response.status_code}")
            logger.error(f"Detalles: {distance_response.text}")
        
        # 5. MINUTOS EN ZONAS ACTIVAS (Active Zone Minutes)
        azm_url = f"https://api.fitbit.com/1/user/-/activities/active-zone-minutes/date/{today}/1d/{detail_level}.json"
        logger.info(f"Solicitud de minutos activos intradía: {azm_url}")
        
        azm_response = requests.get(azm_url, headers=headers)
        logger.info(f"Respuesta minutos activos: Status {azm_response.status_code}")
        
        if azm_response.status_code == 200:
            azm_data = azm_response.json()
            logger.info(f"Claves en respuesta AZM: {azm_data.keys()}")
            
            # El formato puede variar según la documentación, verificar ambas estructuras posibles
            intraday_key = 'activities-active-zone-minutes-intraday'
            if intraday_key in azm_data:
                intraday_data = azm_data[intraday_key]
                dataset = intraday_data.get('dataset', [])
                logger.info(f"Puntos de datos de minutos activos: {len(dataset)}")
                
                if dataset:
                    # Registrar ejemplos de datos
                    logger.info(f"Ejemplos de datos de minutos activos:")
                    for point in dataset[:3]:
                        logger.info(f"  {point}")
                    
                    # Guardar datos en la base de datos
                    for point in dataset:
                        time_str = point.get('time')
                        value = point.get('value')
                        if time_str and value:
                            timestamp = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            insert_intraday_metric(user_id, timestamp, 'active_zone_minutes', value)
                            total_active_zone_points += 1
                    
                    logger.info(f"Guardados {total_active_zone_points} puntos de minutos activos con detalle {detail_level}")
                else:
                    logger.warning(f"No se encontraron datos de minutos activos para {detail_level}")
            else:
                logger.warning(f"No se encontró la sección '{intraday_key}' en la respuesta")
        else:
            logger.error(f"Error al obtener datos de minutos activos: {azm_response.status_code}")
            logger.error(f"Detalles: {azm_response.text}")
        
        # Resumen de la recopilación de datos
        total_points = (total_heart_rate_points + total_steps_points + 
                        total_calories_points + total_distance_points + 
                        total_active_zone_points)
        
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
            logger.warning("Posibles causas:")
            logger.warning("1. La aplicación no tiene permisos para acceder a datos intradía.")
            logger.warning("2. No se ha solicitado acceso a datos intradía a Fitbit (ver documentación).")
            logger.warning("3. El usuario no ha generado datos intradía en el día actual.")
            logger.warning("4. El dispositivo Fitbit no está sincronizado o no recopila estos datos.")
            logger.warning("5. El token de acceso no tiene los scopes necesarios.")
            
            # Recomendación basada en documentación
            logger.info("\n=== RECOMENDACIÓN ===")
            logger.info("Para uso personal, asegúrese de que la aplicación Fitbit tenga configurados los permisos adecuados.")
            logger.info("Para uso en modo servidor (aplicación que accede a datos de otros usuarios),")
            logger.info("debe solicitar acceso especial a Fitbit a través del Issue Tracker:")
            logger.info("https://dev.fitbit.com/build/reference/web-api/intraday/")
            
            return False

    except requests.exceptions.HTTPError as e:
        if hasattr(e, 'response') and e.response and e.response.status_code == 401:
            logger.error(f"Error de autenticación (401): {str(e)}")
            raise  # Reenviar error 401 para manejo de token expirado
        logger.error(f"Error HTTP al obtener datos intradía: {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al obtener datos intradía: {str(e)}", exc_info=True)
        return False

def process_emails(emails):
    """
    Procesa una lista de correos electrónicos para recopilar datos intradía de Fitbit.
    """
    # Filtrar correos electrónicos vacíos
    valid_emails = [email for email in emails if email and email.strip()]
    
    if not valid_emails:
        logger.warning("No se proporcionaron correos electrónicos válidos para procesar.")
        return
    
    for email in valid_emails:
        try:
            # Obtener el user_id más reciente asociado al correo electrónico
            user_id = get_latest_user_id_by_email(email)
            if not user_id:
                logger.warning(f"No se encontró un usuario con el correo {email}. Verifique que el usuario esté registrado.")
                continue
       
            # Obtener y desencriptar los tokens
            access_token, refresh_token = get_user_tokens(email)
            if not access_token or not refresh_token:
                logger.warning(f"No se encontraron tokens válidos para el correo {email}. Es necesario vincular nuevamente el dispositivo.")
                continue

            # Intentar obtener los datos de Fitbit
            try:
                logger.info(f"Iniciando recolección de datos intradía para {email}")
                success = get_intraday_data(access_token, email)
                if success:
                    logger.info(f"Datos intradía recopilados exitosamente para {email}.")
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response and e.response.status_code == 401:
                    logger.warning(f"Token expirado para el correo {email}. Intentando refrescar el token...")
                    new_access_token, new_refresh_token = refresh_access_token(refresh_token)
                    if new_access_token and new_refresh_token:
                        # Actualizar los tokens en la base de datos
                        update_users_tokens(email, new_access_token, new_refresh_token)

                        # Volver a intentar la solicitud con el nuevo token
                        try:
                            success = get_intraday_data(new_access_token, email)
                            if success:
                                logger.info(f"Datos intradía recopilados exitosamente para {email} después de refrescar el token.")
                        except requests.exceptions.HTTPError as e:
                            logger.error(f"Error HTTP al obtener datos intradía para {email} después de refrescar el token: {e}")
                    else:
                        logger.error(f"No se pudo refrescar el token para {email}. Es necesario vincular nuevamente el dispositivo.")
                else:
                    logger.error(f"Error HTTP al obtener datos intradía para {email}: {e}")
        except Exception as e:
            logger.error(f"Error inesperado al procesar el correo {email}: {e}", exc_info=True)

if __name__ == "__main__":
    # Asegurar que el directorio de logs existe
    os.makedirs("logs", exist_ok=True)
    
    # Registrar versión y ambiente
    logger.info("=== INICIO DE EJECUCIÓN DE FITBIT INTRADAY ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    emails = ["Wearable4LivelyAgeign@gmail.com", ""]
    logger.info(f"Procesando emails: {emails}")
    process_emails(emails)
    
    logger.info("=== FIN DE EJECUCIÓN DE FITBIT INTRADAY ===")
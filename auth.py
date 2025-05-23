import base64
import hashlib
import os
import random
from shlex import quote
import string
import requests
from config import AUTH_URL, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

TOKEN_URL = "https://api.fitbit.com/oauth2/token"

def get_tokens(code, code_verifier):
    """
    Intercambia el código de autorización por tokens usando PKCE.
    """
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    
    print(f"Requesting tokens with payload: {payload}")  # Debug log
    print(f"Using headers: {headers}")  # Debug log
    
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    print(f"Token response status: {response.status_code}")  # Debug log
    print(f"Token response body: {response.text}")  # Debug log
    
    if response.status_code != 200:
        raise Exception(f"Error de Fitbit: {response.text}")
    
    tokens = response.json()
    return tokens.get("access_token"), tokens.get("refresh_token")

def generate_state(length=16):
    """
    Genera un parámetro state aleatorio.
    """
    characters = string.ascii_letters + string.digits
    state = ''.join(random.choice(characters) for i in range(length))
    return state

def generate_code_verifier():
    """
    Genera un code_verifier aleatorio.
    """
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')
    return code_verifier


def generate_code_challenge(code_verifier):
    """
    Genera el code_challenge usando SHA-256.
    """
    # Asegurar que el code_verifier es una cadena
    if isinstance(code_verifier, bytes):
        code_verifier = code_verifier.decode('utf-8')
        
    sha256 = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(sha256).rstrip(b'=').decode('utf-8')
    return code_challenge

def refresh_token(refresh_token):
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(TOKEN_URL, data=payload)
    tokens = response.json()
    return tokens.get("access_token"), tokens.get("refresh_token")

def generate_auth_url(code_challenge, state):
    """
    Genera la URL de autorización para Fitbit con los parámetros adecuados.
    """
    from urllib.parse import urlencode
    
    # Lista de scopes separados por espacios
    scopes = "activity cardio_fitness electrocardiogram heartrate irregular_rhythm_notifications location nutrition oxygen_saturation profile respiratory_rate settings sleep social temperature weight"
    
    # Crear diccionario de parámetros
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'scope': scopes,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'state': state,
        'redirect_uri': REDIRECT_URI,
        'expires_in': '2592000',
        'prompt': 'login consent',  # Forzar login y consentimiento cada vez
        'access_type': 'offline',   # Solicitar refresh_token
    }
    
    # Construir la URL con los parámetros correctamente codificados
    auth_url = f"{AUTH_URL}?{urlencode(params)}"
    
    print(f"Generated auth URL: {auth_url}")  # Debug log
    return auth_url

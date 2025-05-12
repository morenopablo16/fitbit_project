import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()
ADMIN_MAIL = os.getenv("ADMIN_MAIL")
ADMIN_PSSW = os.getenv("ADMIN_PSSW")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# URL de redirección basada en el entorno
#REDIRECT_URI = "http://localhost:5000/livelyageing/callback"
REDIRECT_URI = "https://tango.ing.unimo.it/livelyageing/callback"
# if os.getenv("FLASK_ENV") == "production":
#     REDIRECT_URI = "https://tango.ing.unimo.it/livelyageing/callback"
#     #REDIRECT_URI = "http://localhost:5000/livelyageing/callback"
# else:
#     # URL local para desarrollo
#     REDIRECT_URI = "http://localhost:5000/livelyageing/callback"
#     #REDIRECT_URI = "https://tango.ing.unimo.it/livelyageing/callback"

AUTH_URL = "https://www.fitbit.com/oauth2/authorize"
TOKEN_URL = "https://api.fitbit.com/oauth2/token"

DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'port': os.getenv("DB_PORT"),
    'database': os.getenv("DB_NAME"),
    "sslmode": "require"
}


# Lista de usuarios Fitbit (correos electrónicos)
USERS = [
    # {"email": "Wearable1LivelyAgeign@gmail.com", "auth_code": None, "access_token": None, "refresh_token": None},
    # {"email": "Wearable2LivelyAgeign@gmail.com", "auth_code": None, "access_token": None, "refresh_token": None},
    {"email": "Wearable4LivelyAgeign@gmail.com ", "auth_code": None, "access_token": None, "refresh_token": None}
]


import requests
from base64 import b64encode
# Datos de la app
CLIENT_ID = "23QK2Y"
CLIENT_SECRET = "15dff85f95fb2b521461fa4e0c9abf2b"
REDIRECT_URI = "https://localhost/callback"

# Código de autorización copiado de la URL
AUTHORIZATION_CODE = "63711b420ba538ee5992f215dda90a96df7354cd"
# Construir headers con autenticación básica
auth_header = b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth_header}",
    "Content-Type": "application/x-www-form-urlencoded"
}

# Parámetros para el POST
data = {
    "client_id": CLIENT_ID,
    "grant_type": "authorization_code",
    "redirect_uri": REDIRECT_URI,
    "code": AUTHORIZATION_CODE
}

print("Enviando solicitud a Fitbit...")
print(f"Headers: {headers}")
print(f"Data: {data}")

# Enviar la solicitud a Fitbit
response = requests.post("https://api.fitbit.com/oauth2/token", headers=headers, data=data)

if response.status_code == 200:
    tokens = response.json()
    print("\n✅ TOKENS OBTENIDOS CORRECTAMENTE:")
    print(f"Access Token: {tokens['access_token']}")
    print(f"Refresh Token: {tokens['refresh_token']}")
    print(f"Scope: {tokens['scope']}")
    print(f"Expires In: {tokens['expires_in']} seconds")
    
    # Guardar los tokens en un archivo para uso posterior
    with open("tokens.txt", "w") as f:
        f.write(f"Access Token: {tokens['access_token']}\n")
        f.write(f"Refresh Token: {tokens['refresh_token']}\n")
else:
    print(f"\n❌ ERROR: {response.status_code}")
    print("Respuesta completa:")
    print(response.text) 
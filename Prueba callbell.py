"""
Testea los dos formatos posibles de autenticación de Callbell.
"""
import requests

TOKEN = "bDfAzWJk9pMj5y8Y3U4RzuzzU9WSXYea.dd284001db7b17a762da3c3ce9edee1e8b98117b69b5b97dd8c484a7e98499cc"

url = "https://api.callbell.eu/v1/contacts"

# Formato 1 — Token token=
headers1 = {"Authorization": f"Token token={TOKEN}"}
r1 = requests.get(url, headers=headers1)
print(f"Formato 1 'Token token=...' → Status: {r1.status_code}")

# Formato 2 — Bearer
headers2 = {"Authorization": f"Bearer {TOKEN}"}
r2 = requests.get(url, headers=headers2)
print(f"Formato 2 'Bearer ...'      → Status: {r2.status_code}")

# Formato 3 — Solo el token
headers3 = {"Authorization": TOKEN}
r3 = requests.get(url, headers=headers3)
print(f"Formato 3 'Solo token'      → Status: {r3.status_code}")

# Formato 4 — Como parámetro en la URL
r4 = requests.get(f"{url}?api_key={TOKEN}")
print(f"Formato 4 'api_key en URL'  → Status: {r4.status_code}")

print("\n✅ El formato correcto es el que devuelva status 200")
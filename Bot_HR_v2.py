"""
Webhook de validación para Callbell + Google Sheets
"""

import re
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, jsonify

app = Flask(__name__)

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
SPREADSHEET_ID    = "1nEpSfYuIGeZ-PF9FNNaGuYHN5m1fl-izoEXoStrfqLk"
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON", "")

# ─── CONEXIÓN A GOOGLE SHEETS ─────────────────────────────────────────────────
def get_sheets_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    if os.path.exists(GOOGLE_CREDS_JSON):
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_JSON, scopes=scopes)
    else:
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def cargar_empleados():
    """Lee la hoja Empleados y devuelve dict {(telefono, dni): nombre}"""
    client      = get_sheets_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    ws          = spreadsheet.worksheet("Empleados")
    filas       = ws.get_all_records()
    empleados   = {}
    for fila in filas:
        telefono = re.sub(r'\D', '', str(fila.get("telefono", "")).strip())
        dni      = str(fila.get("dni", "")).strip()
        nombre   = str(fila.get("nombre", "")).strip()
        if telefono and dni:
            empleados[(telefono, dni)] = nombre
    return empleados

def validar_formato_dni(dni):
    return bool(re.fullmatch(r'\d{1,8}', dni.strip()))

def validar_identidad(telefono, dni):
    tel_limpio = re.sub(r'\D', '', telefono)
    print(f">>> Buscando — tel: '{tel_limpio}' | dni: '{dni.strip()}'")
    resultado = cargar_empleados().get((tel_limpio, dni.strip()))
    print(f">>> Resultado: {resultado}")
    return resultado

# ─── ENDPOINT PRINCIPAL ───────────────────────────────────────────────────────
@app.route("/validar", methods=["POST"])
def validar():
    try:
        data     = request.json or {}
        telefono = re.sub(r'\D', '', str(data.get("telefono", "")))
        dni      = str(data.get("dni", "")).strip()

        print(f"Validando → tel: {telefono} | dni: {dni}")

        if not validar_formato_dni(dni):
            return jsonify({"valido": False, "motivo": "dni_invalido"}), 200

        nombre = validar_identidad(telefono, dni)

        if not nombre:
            return jsonify({"valido": False, "motivo": "no_encontrado"}), 200

        return jsonify({"valido": True, "nombre": nombre}), 200

    except Exception as e:
        print(f"ERROR en /validar: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Validador RRHH activo ✅"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
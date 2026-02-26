"""
Webhook de validación para Callbell + API iCheck con fallback a Google Sheets
Renueva el token de iCheck automáticamente cada 6 horas
"""

import re
import os
import json
import threading
import requests
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, jsonify

app = Flask(__name__)

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
ICHECK_API_BASE   = "http://api.icheck.com.ar/api"
PRODUCT_ID        = int(os.environ.get("ICHECK_PRODUCT_ID", 2020))
SPREADSHEET_ID    = "1nEpSfYuIGeZ-PF9FNNaGuYHN5m1fl-izoEXoStrfqLk"
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON", "")

# ─── ESTADO DEL TOKEN EN MEMORIA ─────────────────────────────────────────────
token_state = {
    "access_token":  os.environ.get("ICHECK_ACCESS_TOKEN", ""),
    "refresh_token": os.environ.get("ICHECK_REFRESH_TOKEN", ""),
    "lock": threading.Lock()
}

# ─── RENOVACIÓN DE TOKEN ──────────────────────────────────────────────────────
def renovar_token():
    print(">>> Renovando token iCheck...")
    try:
        payload = {
            "Access Token":  token_state["access_token"],
            "Refresh Token": token_state["refresh_token"],
            "Product Id":    PRODUCT_ID,
            "Version":       "1.0.0",
            "Server":        "api.icheck.com.ar",
            "Origin":        "iCheck"
        }
        r = requests.post(
            f"{ICHECK_API_BASE}/RenovacionTokenExterno",
            json=payload,
            timeout=15
        )
        r.raise_for_status()
        data = r.json()
        with token_state["lock"]:
            token_state["access_token"]  = data.get("Access Token",  token_state["access_token"])
            token_state["refresh_token"] = data.get("Refresh Token", token_state["refresh_token"])
        print(">>> Token renovado OK")
    except Exception as e:
        print(f">>> ERROR renovando token: {e}")

def programar_renovacion():
    renovar_token()
    timer = threading.Timer(6 * 3600, programar_renovacion)
    timer.daemon = True
    timer.start()

# ─── ICHECK: OBTENER EMPLEADOS ────────────────────────────────────────────────
def obtener_empleados_icheck():
    with token_state["lock"]:
        access  = token_state["access_token"]
        refresh = token_state["refresh_token"]

    headers = {
        "Access_Token":  access,
        "Refresh_Token": refresh,
        "FechaDesde":    "20200101",
        "FechaHasta":    "20200101",
        "Filter_Estado": "1",
        "FormatoJson":   "Personas"
    }
    r = requests.get(
        f"{ICHECK_API_BASE}/GetInformationJsons",
        headers=headers,
        timeout=20
    )
    r.raise_for_status()
    return r.json()

def buscar_empleado_icheck(telefono, dni):
    tel_limpio = re.sub(r'\D', '', telefono)
    dni_limpio = dni.strip()
    empleados  = obtener_empleados_icheck()
    for emp in empleados:
        tel_emp = re.sub(r'\D', '', str(emp.get("Telefono_Celular", "")))
        dni_emp = str(emp.get("Documento", "")).strip()
        if tel_emp == tel_limpio and dni_emp == dni_limpio:
            return emp
    return None

# ─── GOOGLE SHEETS: FALLBACK ──────────────────────────────────────────────────
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

def buscar_empleado_sheets(telefono, dni):
    tel_limpio = re.sub(r'\D', '', telefono)
    dni_limpio = dni.strip()
    client      = get_sheets_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    ws          = spreadsheet.worksheet("Empleados")
    filas       = ws.get_all_records()
    for fila in filas:
        tel_fila = re.sub(r'\D', '', str(fila.get("telefono", "")).strip())
        dni_fila = str(fila.get("dni", "")).strip()
        if tel_fila == tel_limpio and dni_fila == dni_limpio:
            return {
                "Nombre":          str(fila.get("nombre", "")),
                "Apellido":        str(fila.get("apellido", "")),
                "Legajo":          str(fila.get("legajo", "")),
                "Sucursal":        str(fila.get("sucursal", "")),
                "Telefono_Celular": str(fila.get("telefono", "")),
                "Documento":       dni_limpio
            }
    return None

# ─── VALIDACIÓN PRINCIPAL CON FALLBACK ───────────────────────────────────────
def validar_formato_dni(dni):
    return bool(re.fullmatch(r'\d{1,8}', dni.strip()))

def buscar_empleado(telefono, dni):
    """Intenta iCheck primero, si falla cae a Google Sheets."""
    try:
        print(">>> Buscando en iCheck...")
        empleado = buscar_empleado_icheck(telefono, dni)
        if empleado is not None:
            print(">>> Encontrado en iCheck")
        else:
            print(">>> No encontrado en iCheck")
        return empleado, "icheck"
    except Exception as e:
        print(f">>> iCheck falló: {e} — usando fallback Google Sheets")
        try:
            empleado = buscar_empleado_sheets(telefono, dni)
            return empleado, "sheets"
        except Exception as e2:
            print(f">>> Google Sheets también falló: {e2}")
            raise e2

# ─── ENDPOINT /validar ────────────────────────────────────────────────────────
@app.route("/validar", methods=["POST"])
def validar():
    try:
        data     = request.json or {}
        telefono = re.sub(r'\D', '', str(data.get("telefono", "")))
        dni      = str(data.get("dni", "")).strip()

        print(f"Validando → tel: {telefono} | dni: {dni}")

        if not validar_formato_dni(dni):
            return jsonify({"valido": False, "motivo": "dni_invalido"}), 200

        empleado, fuente = buscar_empleado(telefono, dni)
        print(f">>> Fuente de datos: {fuente}")

        if not empleado:
            return jsonify({"valido": False, "motivo": "no_encontrado"}), 200

        return jsonify({
            "valido":   True,
            "nombre":   empleado.get("Nombre", ""),
            "apellido": empleado.get("Apellido", ""),
            "legajo":   empleado.get("Legajo", ""),
            "sucursal": empleado.get("Sucursal", ""),
            "dni":      empleado.get("Documento", ""),
            "cbu":      empleado.get("Cbu", ""),
            "banco":    empleado.get("Banco", ""),
            "telefono": empleado.get("Telefono_Celular", "")
        }), 200

    except Exception as e:
        print(f"ERROR en /validar: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ─── ENDPOINT /webhook ────────────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    return jsonify({"status": "ok"}), 200

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Validador RRHH activo ✅"}), 200

# ─── INICIO ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    programar_renovacion()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
"""
Servicio de envío de mails para ausencias - Bot RRHH
Llama a este endpoint desde Callbell cuando un empleado informa una ausencia
"""

import os
import json
import re
import smtplib
import gspread
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
from datetime import datetime
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
SMTP_SERVER       = os.environ.get("SMTP_SERVER", "webmail.cristobalcolon.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", 25))
SMTP_USER         = os.environ.get("SMTP_USER", "noreply@cristobalcolon.com")
SMTP_PASS         = os.environ.get("SMTP_PASS", "")
SPREADSHEET_ID    = "1nEpSfYuIGeZ-PF9FNNaGuYHN5m1fl-izoEXoStrfqLk"
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON", "")

# ─── GOOGLE SHEETS ────────────────────────────────────────────────────────────
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

def obtener_email_supervisor(sucursal):
    """Busca el email del supervisor según la sucursal en Google Sheets."""
    try:
        client      = get_sheets_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        ws          = spreadsheet.worksheet("Supervisores")
        filas       = ws.get_all_records()
        print(f">>> Filas en Supervisores: {filas}")
        print(f">>> Buscando sucursal: '{sucursal}'")
        for fila in filas:
            suc_fila = str(fila.get("sucursal", "")).strip()
            print(f">>> Comparando '{suc_fila}' con '{sucursal.strip()}'")
            if suc_fila == sucursal.strip():
                return fila.get("email", ""), fila.get("supervisor", "")
    except Exception as e:
        print(f">>> Error buscando supervisor: {e}")
        import traceback
        traceback.print_exc()
    return None, None

# ─── ENVÍO DE MAIL ────────────────────────────────────────────────────────────
def enviar_mail(destinatario, supervisor, datos):
    nombre   = datos.get("nombre", "")
    apellido = datos.get("apellido", "")
    dni      = datos.get("dni", "")
    legajo   = datos.get("legajo", "")
    sucursal = datos.get("sucursal", "")
    motivo   = datos.get("motivo", "")
    fecha    = datetime.now().strftime("%d/%m/%Y %H:%M")

    asunto = f"Aviso de ausencia - {apellido} {nombre}"

    cuerpo = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #cc0000;">Aviso de Ausencia</h2>
        <p>Estimado/a <strong>{supervisor}</strong>,</p>
        <p>Se informa la siguiente ausencia registrada a través del sistema de RRHH:</p>
        <table style="border-collapse: collapse; width: 100%; max-width: 500px;">
            <tr style="background-color: #f2f2f2;">
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Nombre y Apellido</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{nombre} {apellido}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>DNI</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{dni}</td>
            </tr>
            <tr style="background-color: #f2f2f2;">
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Legajo</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{legajo}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Sucursal</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{sucursal}</td>
            </tr>
            <tr style="background-color: #f2f2f2;">
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Motivo</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{motivo}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Fecha y Hora</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{fecha}</td>
            </tr>
        </table>
        <br>
        <p style="font-size: 12px; color: #888;">Este mensaje fue generado automáticamente por el sistema de RRHH de Cristóbal Colón.</p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = SMTP_USER
    msg["To"]      = destinatario
    msg.attach(MIMEText(cuerpo, "html"))

    # ── MODO TEST: simula envío sin SMTP ──
    print(f">>> [TEST] Mail simulado a {destinatario} ({supervisor})")
    print(f">>> [TEST] Asunto: {asunto}")
    print(f">>> [TEST] Cuerpo HTML generado correctamente")
    # ── Descomentar cuando IT habilite puerto 587 ──
    # with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
    #     server.ehlo()
    #     server.starttls()
    #     server.login(SMTP_USER, SMTP_PASS)
    #     server.sendmail(SMTP_USER, destinatario, msg.as_string())
    # print(f">>> Mail enviado a {destinatario} ({supervisor})")

# ─── ENDPOINT /notificar ──────────────────────────────────────────────────────
@app.route("/notificar", methods=["POST"])
def notificar():
    try:
        data     = request.json or {}
        sucursal = str(data.get("sucursal", "")).strip()
        nombre   = str(data.get("nombre", "")).strip()
        apellido = str(data.get("apellido", "")).strip()
        dni      = str(data.get("dni", "")).strip()
        legajo   = str(data.get("legajo", "")).strip()
        motivo   = str(data.get("motivo", "")).strip()

        print(f"Notificando ausencia → {apellido} {nombre} | Sucursal: {sucursal} | Motivo: {motivo}")

        if not sucursal:
            return jsonify({"enviado": False, "motivo": "sucursal_vacia"}), 200

        email_supervisor, nombre_supervisor = obtener_email_supervisor(sucursal)

        if not email_supervisor:
            print(f">>> No se encontró supervisor para sucursal: {sucursal}")
            return jsonify({"enviado": False, "motivo": "supervisor_no_encontrado"}), 200

        enviar_mail(email_supervisor, nombre_supervisor, {
            "nombre":   nombre,
            "apellido": apellido,
            "dni":      dni,
            "legajo":   legajo,
            "sucursal": sucursal,
            "motivo":   motivo
        })

        return jsonify({"enviado": True, "supervisor": nombre_supervisor}), 200

    except Exception as e:
        print(f"ERROR en /notificar: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"enviado": False, "error": str(e)}), 500

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Mailer RRHH activo ✅"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
"""
Bot de WhatsApp para Callbell + Google Sheets
Requiere: pip install flask requests gspread google-auth
"""

import re
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, jsonify
from datetime import datetime
import requests

app = Flask(__name__)

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────
CALLBELL_API_TOKEN = os.environ.get("CALLBELL_API_TOKEN", "bDfAzWJk9pMj5y8Y3U4RzuzzU9WSXYea.dd284001db7b17a762da3c3ce9edee1e8b98117b69b5b97dd8c484a7e98499cc")
SPREADSHEET_ID     = "1nEpSfYuIGeZ-PF9FNNaGuYHN5m1fl-izoEXoStrfqLk"
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON", r"c:\Users\carlo\OneDrive\Desktop\Python\BOT HR\bot-hhrr-622fa7f9a2ce.json")

# ─── CONEXIÓN A GOOGLE SHEETS ─────────────────────────────────────────────────
def get_sheets_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Si es un archivo local, cargarlo directamente
    if os.path.exists(GOOGLE_CREDS_JSON):
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_JSON, scopes=scopes)
    else:
        # En Render viene como string JSON en variable de entorno
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_sheet(nombre_hoja, encabezados=None):
    """Obtiene una hoja, la crea con encabezados si no existe."""
    client = get_sheets_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = spreadsheet.worksheet(nombre_hoja)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=nombre_hoja, rows=1000, cols=10)
        if encabezados:
            ws.append_row(encabezados)
    return ws

# ─── SESIONES EN MEMORIA ─────────────────────────────────────────────────────
sessions = {}

# ─── OPERACIONES CON GOOGLE SHEETS ───────────────────────────────────────────
def cargar_empleados():
    """Lee la hoja Empleados y devuelve dict {(telefono, dni): nombre}"""
    ws = get_sheet("Empleados", ["telefono", "dni", "nombre"])
    filas = ws.get_all_records()
    empleados = {}
    for fila in filas:
        telefono = re.sub(r'\D', '', str(fila.get("telefono", "")).strip())
        dni      = str(fila.get("dni", "")).strip()
        nombre   = str(fila.get("nombre", "")).strip()
        if telefono and dni:
            empleados[(telefono, dni)] = nombre
    return empleados

def registrar_ausencia(telefono, dni, nombre, motivo):
    ws = get_sheet("Ausencias", ["Fecha", "Teléfono", "DNI", "Nombre", "Motivo"])
    ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), telefono, dni, nombre, motivo])

def registrar_archivo(telefono, dni, nombre, motivo, url_archivo):
    ws = get_sheet("Documentos", ["Fecha", "Teléfono", "DNI", "Nombre", "Motivo", "URL Archivo"])
    ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), telefono, dni, nombre, motivo, url_archivo])

# ─── VALIDACIONES ────────────────────────────────────────────────────────────
def validar_formato_dni(dni):
    return bool(re.fullmatch(r'\d{1,8}', dni.strip()))

def validar_identidad(telefono, dni):
    tel_limpio = re.sub(r'\D', '', telefono)
    print(f">>> Buscando — tel: '{tel_limpio}' | dni: '{dni.strip()}'")
    resultado = cargar_empleados().get((tel_limpio, dni.strip()))
    print(f">>> Resultado: {resultado}")
    return resultado

# ─── ENVÍO DE MENSAJES ───────────────────────────────────────────────────────
def enviar_mensaje(telefono, texto):
    url = "https://api.callbell.eu/v1/messages/send"
    headers = {
        "Authorization": f"Bearer {CALLBELL_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": telefono,
        "from": "whatsapp",
        "type": "text",
        "content": {"text": texto}
    }
    r = requests.post(url, headers=headers, json=payload)
    print(f"Envío mensaje → {r.status_code}: {r.text}")

def enviar_botones(telefono, texto, botones):
    cuerpo = f"{texto}\n\n"
    for b in botones:
        cuerpo += f"▶️ {b}\n"
    cuerpo += "\n_Respondé con el número de la opción._"
    enviar_mensaje(telefono, cuerpo)

# ─── MENÚS ───────────────────────────────────────────────────────────────────
MENU_PRINCIPAL = [
    "1) Avisar ausencias",
    "2) Consultas",
    "3) Beneficios",
    "4) Actualizar datos",
    "5) Otros temas"
]

MENU_AUSENCIAS = [
    "1) Enfermedad propia",
    "2) Enfermedad familiar",
    "3) Problema personal",
    "4) Fallecimiento",
    "5) Accidente in itinere",
    "6) Volver al menú anterior"
]

MENU_CIERRE = [
    "1) Sí, necesito ayuda con otra cosa",
    "2) Quiero hablar con un representante de RRHH",
    "3) No, ya está todo bien. ¡Gracias!"
]

MENU_CONSULTAS = [
    "1) Licencias",
    "2) Sueldo/Recibo",
    "3) Obra Social",
    "4) CBU/Banco",
    "5) Actualización de legajo",
    "6) Baja Voluntaria",
    "7) Volver al menú anterior"
]

MENU_LICENCIAS = [
    "1) Tipos de licencias",
    "2) Días que corresponden",
    "3) Documentación necesaria",
    "4) Dónde enviarla",
    "5) Volver al menú anterior"
]

MENU_ACTUALIZACION_LEGAJO = [
    "1) Domicilio",
    "2) Estado civil/matrimonio",
    "3) Hijos",
    "4) Otros datos",
    "5) Volver al menú anterior"
]

MENSAJES_CONSULTAS = {
    "2": (
        "• *Fecha de pago:* Ingresá a milegajo.com o a la app Mi Legajo.\n"
        "• *Dónde ver tu recibo digital:* Ingresá a milegajo.com o a la app Mi Legajo.\n"
        "• Para consultas puntuales, escribí a:\n"
        "📩 administracionrrhh@cristobalcolon.com"
    ),
    "3": (
        "¿Qué necesitás saber sobre la obra social?\n\n"
        "• Afiliación\n"
        "• Grupo familiar\n"
        "• Cambios de cobertura"
    ),
    "4": (
        "Para actualizar CBU o datos bancarios, escribí a:\n"
        "📩 administracionrrhh@cristobalcolon.com"
    ),
    "6": "⚠️ Mensaje de Baja Voluntaria próximamente.",  # placeholder
}

MENSAJES_LICENCIAS = {
    "1": "⚠️ Tipos de licencias — próximamente.",  # placeholder
    "2": "⚠️ Días que corresponden — próximamente.",  # placeholder
    "3": "⚠️ Documentación necesaria — próximamente.",  # placeholder
    "4": "⚠️ Dónde enviarla — próximamente.",  # placeholder
}

MENSAJES_ACTUALIZACION_LEGAJO = {
    "1": (
        "Para actualizar tu domicilio, ingresá a:\n"
        "🌐 tulegajo.com\n\n"
        "Descargá el formulario, completalo y seguí las instrucciones de la plataforma."
    ),
    "2": "Para actualizar datos, escribí a:\n📩 analistarrhh@cristobalcolon.com",
    "3": "Para actualizar datos, escribí a:\n📩 analistarrhh@cristobalcolon.com",
    "4": "Para actualizar datos, escribí a:\n📩 analistarrhh@cristobalcolon.com",
}


MENSAJES_AUSENCIA = {
    "1": (
        "Por favor adjuntá el certificado o documentación por este medio.\n\n"
        "⚠️ *Importante:*\n"
        "• La recepción del certificado no implica la justificación automática.\n"
        "• Toda documentación es evaluada por Auditoría de RH.\n"
        "• El original debe presentarse dentro de las *48 horas* una vez reincorporado/a.\n"
        "• En licencias prolongadas (+72 hs), Auditoría puede solicitar verificación en centro médico.\n"
        "• RH podrá enviar médico a domicilio al último domicilio declarado."
    ),
    "2": (
        "Por favor adjuntá el certificado o documentación por este medio.\n\n"
        "⚠️ *Importante:*\n"
        "• La recepción del certificado no implica la justificación automática.\n"
        "• Toda documentación es evaluada por Auditoría de RH.\n"
        "• El original debe presentarse dentro de las *48 horas* una vez reincorporado/a.\n"
        "• Las ausencias por enfermedad familiar son justificadas, pero no pagas.\n"
        "• Ante cualquier duda, comunicate con RH."
    ),
    "3": (
        "Podés adjuntar la documentación correspondiente por este medio.\n\n"
        "⚠️ *Importante:*\n"
        "• La recepción del documento no implica la justificación automática.\n"
        "• Auditoría de RH lo revisará.\n"
        "• El original debe presentarse dentro de las *48 horas* una vez reincorporado/a.\n\n"
        "_Si no tenés documentación, respondé *No tengo*._"
    ),
    "4": (
        "Acompañamos este momento y lamentamos profundamente tu pérdida. 🕊️\n\n"
        "Por favor, cuando te sea posible, enviá la documentación correspondiente "
        "para registrar la ausencia.\n\n"
        "Si necesitás hablar con alguien de RH, estamos a disposición."
    ),
    "5": (
        "Si sufriste un accidente yendo o volviendo del trabajo, debés avisar *EN EL MOMENTO*.\n\n"
        "1️⃣ Avisá inmediatamente a tu supervisor.\n"
        "2️⃣ Llamá a Federación Patronal (CAP):\n"
        "📞 *0810-333-0096*\n\n"
        "Tené a mano:\n"
        "• DNI\n"
        "• Domicilio y teléfono\n"
        "• Fecha y hora del accidente\n"
        "• Lugar y cómo ocurrió\n"
        "• Si intervino policía o SAME\n"
        "• Nombre de quien realiza la denuncia\n\n"
        "La ART te indicará el prestador médico o traslado.\n"
        "El empleador debe entregarte el *Formulario de Denuncia Administrativa*.\n\n"
        "Por favor adjuntá la documentación de respaldo por este medio cuando puedas."
    ),
}

def mostrar_menu_consultas(telefono, nombre):
    enviar_botones(telefono, f"{nombre}, ¿sobre qué querés consultar?", MENU_CONSULTAS)

def mostrar_menu_licencias(telefono, nombre):
    enviar_botones(telefono, f"{nombre}, ¿qué querés saber sobre licencias?", MENU_LICENCIAS)

def mostrar_menu_actualizacion_legajo(telefono, nombre):
    enviar_botones(telefono, f"{nombre}, ¿qué dato querés actualizar?", MENU_ACTUALIZACION_LEGAJO)

def mostrar_menu_principal(telefono, nombre):
    enviar_botones(telefono, f"¿En qué puedo ayudarte, {nombre}?", MENU_PRINCIPAL)

def mostrar_menu_ausencias(telefono, nombre):
    enviar_botones(telefono, f"{nombre}, seleccioná el motivo de la ausencia:", MENU_AUSENCIAS)

def mostrar_menu_cierre(telefono, nombre):
    enviar_botones(telefono, f"¿Hay algo más en lo que pueda ayudarte, {nombre}?", MENU_CIERRE)

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def extraer_opcion(msg):
    match = re.match(r'^(\d+)', msg.strip())
    return match.group(1) if match else msg.strip().lower()

# ─── MÁQUINA DE ESTADOS ──────────────────────────────────────────────────────
def procesar_mensaje(telefono, mensaje):
    msg    = mensaje.strip()
    sesion = sessions.get(telefono, {})
    estado = sesion.get("estado", "inicio")

    if estado == "inicio":
        sessions[telefono] = {"estado": "esperando_dni"}
        enviar_mensaje(telefono,
            "¡Hola! Soy Cristobal, tu asistente virtual de RRHH 👋\n"
            "Por favor, ingresá tu *DNI* (solo números, sin puntos):"
        )

    elif estado == "esperando_dni":
        if not validar_formato_dni(msg):
            enviar_mensaje(telefono,
                "❌ El formato del DNI no es correcto.\n"
                "Debe contener solo números, sin puntos (máximo 8 dígitos).\n"
                "Por favor, ingresalo nuevamente:"
            )
            return
        nombre = validar_identidad(telefono, msg)
        if not nombre:
            enviar_mensaje(telefono,
                "⚠️ No pudimos validar tus datos.\n"
                "Verificá que el DNI sea correcto o comunicate con RRHH."
            )
            sessions[telefono]["estado"] = "esperando_dni"
            return
        sessions[telefono].update({"estado": "menu_principal", "dni": msg, "nombre": nombre})
        mostrar_menu_principal(telefono, nombre)

    elif estado == "menu_principal":
        opcion = extraer_opcion(msg)
        nombre = sessions[telefono]["nombre"]
        if opcion == "1":
            sessions[telefono]["estado"] = "menu_ausencias"
            mostrar_menu_ausencias(telefono, nombre)
        elif opcion == "2":
            sessions[telefono]["estado"] = "menu_consultas"
            mostrar_menu_consultas(telefono, nombre)
        elif opcion in ("3", "4", "5"):
            labels = {"3": "Beneficios", "4": "Actualizar datos", "5": "Otros temas"}
            enviar_mensaje(telefono,
                f"{nombre}, la sección *{labels[opcion]}* estará disponible próximamente.\n"
                "Enviá *menú* para volver al inicio."
            )
        else:
            mostrar_menu_principal(telefono, nombre)

    elif estado == "menu_consultas":
        opcion = extraer_opcion(msg)
        nombre = sessions[telefono]["nombre"]
        if opcion == "7":
            sessions[telefono]["estado"] = "menu_principal"
            mostrar_menu_principal(telefono, nombre)
        elif opcion == "1":
            sessions[telefono]["estado"] = "menu_licencias"
            mostrar_menu_licencias(telefono, nombre)
        elif opcion == "5":
            sessions[telefono]["estado"] = "menu_actualizacion_legajo"
            mostrar_menu_actualizacion_legajo(telefono, nombre)
        elif opcion in MENSAJES_CONSULTAS:
            enviar_mensaje(telefono, MENSAJES_CONSULTAS[opcion])
            sessions[telefono]["estado"] = "cierre"
            mostrar_menu_cierre(telefono, nombre)
        else:
            mostrar_menu_consultas(telefono, nombre)

    elif estado == "menu_licencias":
        opcion = extraer_opcion(msg)
        nombre = sessions[telefono]["nombre"]
        if opcion == "5":
            sessions[telefono]["estado"] = "menu_consultas"
            mostrar_menu_consultas(telefono, nombre)
        elif opcion in MENSAJES_LICENCIAS:
            enviar_mensaje(telefono, MENSAJES_LICENCIAS[opcion])
            sessions[telefono]["estado"] = "cierre"
            mostrar_menu_cierre(telefono, nombre)
        else:
            mostrar_menu_licencias(telefono, nombre)

    elif estado == "menu_actualizacion_legajo":
        opcion = extraer_opcion(msg)
        nombre = sessions[telefono]["nombre"]
        if opcion == "5":
            sessions[telefono]["estado"] = "menu_consultas"
            mostrar_menu_consultas(telefono, nombre)
        elif opcion in MENSAJES_ACTUALIZACION_LEGAJO:
            enviar_mensaje(telefono, MENSAJES_ACTUALIZACION_LEGAJO[opcion])
            sessions[telefono]["estado"] = "cierre"
            mostrar_menu_cierre(telefono, nombre)
        else:
            mostrar_menu_actualizacion_legajo(telefono, nombre)

    elif estado == "menu_ausencias":
        opcion = extraer_opcion(msg)
        nombre = sessions[telefono]["nombre"]
        if opcion == "6":
            sessions[telefono]["estado"] = "menu_principal"
            mostrar_menu_principal(telefono, nombre)
        elif opcion in MOTIVOS:
            motivo = MOTIVOS[opcion]
            registrar_ausencia(telefono, sessions[telefono]["dni"], nombre, motivo)
            sessions[telefono]["estado"] = f"esperando_archivo_{opcion}"
            sessions[telefono]["motivo"] = motivo
            enviar_mensaje(telefono, MENSAJES_AUSENCIA[opcion])
        else:
            mostrar_menu_ausencias(telefono, nombre)

    elif estado.startswith("esperando_archivo_"):
        nombre        = sessions[telefono]["nombre"]
        motivo        = sessions[telefono]["motivo"]
        tipo_msg      = sessions[telefono].get("tipo_mensaje", "text")
        opcion_actual = estado.replace("esperando_archivo_", "")

        if tipo_msg in ("document", "image", "video"):
            url_archivo = sessions[telefono].get("url_archivo", "")
            registrar_archivo(telefono, sessions[telefono]["dni"], nombre, motivo, url_archivo)
            enviar_mensaje(telefono,
                f"✅ Gracias, {nombre}. Tu documentación fue recibida y será evaluada por Auditoría de RH."
            )
            sessions[telefono]["estado"] = "cierre"
            mostrar_menu_cierre(telefono, nombre)
        elif opcion_actual == "3" and msg.lower() in ("no", "no tengo", "sin documentación", "omitir"):
            enviar_mensaje(telefono,
                f"Entendido, {nombre}. Tu ausencia fue registrada.\n"
                "Recordá presentar el original dentro de las 48 hs de reincorporarte."
            )
            sessions[telefono]["estado"] = "cierre"
            mostrar_menu_cierre(telefono, nombre)
        else:
            enviar_mensaje(telefono,
                "⏳ Estoy esperando que adjuntes el archivo (imagen, PDF o documento).\n"
                + ("Si no tenés documentación, respondé *No tengo*." if opcion_actual == "3" else "")
            )

    elif estado == "cierre":
        opcion = extraer_opcion(msg)
        nombre = sessions[telefono]["nombre"]
        if opcion == "1":
            sessions[telefono]["estado"] = "menu_principal"
            mostrar_menu_principal(telefono, nombre)
        elif opcion == "2":
            sessions[telefono]["estado"] = "inicio"
            enviar_mensaje(telefono,
                f"Entendido, {nombre}. En breve un representante de RRHH se va a comunicar con vos. "
                "¡Que tengas un buen día! 👋"
            )
        elif opcion == "3":
            sessions[telefono]["estado"] = "inicio"
            enviar_mensaje(telefono,
                f"¡Perfecto, {nombre}! Fue un gusto ayudarte. "
                "Cualquier consulta no dudes en escribirnos. 😊"
            )
        else:
            mostrar_menu_cierre(telefono, nombre)

    else:
        nombre = sessions.get(telefono, {}).get("nombre", "")
        if msg.lower() in ("menú", "menu", "inicio"):
            sessions[telefono]["estado"] = "menu_principal"
            mostrar_menu_principal(telefono, nombre)
        else:
            enviar_mensaje(telefono, "No entendí tu mensaje. Enviá *menú* para volver al inicio.")

# ─── ENDPOINT VALIDAR (para Callbell Flow) ───────────────────────────────────
@app.route("/validar", methods=["POST"])
def validar():
    try:
        data     = request.json or {}
        telefono = re.sub(r'\D', '', str(data.get("telefono", "")))
        dni      = str(data.get("dni", "")).strip()

        print(f"Validando → tel: {telefono} | dni: {dni}")

        if not validar_formato_dni(dni):
            return jsonify({"valido": False, "motivo": "dni_invalido"}), 200

        print("Conectando a Google Sheets...")
        nombre = validar_identidad(telefono, dni)
        print(f"Resultado: {nombre}")

        if not nombre:
            return jsonify({"valido": False, "motivo": "no_encontrado"}), 200

        return jsonify({"valido": True, "nombre": nombre}), 200

    except Exception as e:
        print(f"ERROR en /validar: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ─── ENDPOINT REGISTRAR (para Callbell Flow) ─────────────────────────────────
@app.route("/registrar", methods=["POST"])
def registrar():
    data     = request.json or {}
    telefono = re.sub(r'\D', '', str(data.get("telefono", "")))
    dni      = str(data.get("dni", "")).strip()
    nombre   = str(data.get("nombre", "")).strip()
    motivo   = str(data.get("motivo", "")).strip()

    print(f"Registrando → {nombre} | motivo: {motivo}")

    try:
        registrar_ausencia(telefono, dni, nombre, motivo)
        return jsonify({"registrado": True}), 200
    except Exception as e:
        print(f"Error registrando: {e}")
        return jsonify({"registrado": False, "error": str(e)}), 500

# ─── WEBHOOK ─────────────────────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Webhook recibido:", json.dumps(data, indent=2, ensure_ascii=False))

    try:
        payload = data["payload"]

        if payload.get("status") != "received":
            print("Mensaje propio ignorado.")
            return jsonify({"status": "ok"}), 200

        mensaje      = (payload.get("text") or "").strip()
        telefono     = re.sub(r'\D', '', payload["from"])
        attachments  = payload.get("attachments", [])
        tipo_mensaje = "image" if attachments else payload.get("type", "text")
        url_archivo  = attachments[0] if attachments else ""

        print(f">>> Tipo: {tipo_mensaje} | Texto: '{mensaje}' | Adjunto: {url_archivo}")

        if telefono not in sessions:
            sessions[telefono] = {}
        sessions[telefono]["tipo_mensaje"] = tipo_mensaje
        sessions[telefono]["url_archivo"]  = url_archivo

        if not mensaje and not attachments:
            print("Mensaje vacío ignorado.")
            return jsonify({"status": "ok"}), 200

        procesar_mensaje(telefono, mensaje)

    except (KeyError, TypeError) as e:
        print(f"Error procesando webhook: {e}")

    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Bot RRHH activo ✅"}), 200

if __name__ == "__main__":
    app.run(port=5000, debug=True)
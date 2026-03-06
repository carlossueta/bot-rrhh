"""
token_refresher.py  —  Servicio independiente de renovación de tokens iCheck
Corre en Render como Worker Service.
Cada 4hs:
  1. Lee el refresh_token desde Google Sheets (hoja 'Tokens', B2)
  2. Llama al endpoint OAuth de iCheck
  3. Escribe el nuevo access_token (B1) y refresh_token (B2) en Sheets
"""

import os
import json
import logging
import requests
import gspread
from google.oauth2.service_account import Credentials
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
ICHECK_TOKEN_URL   = "https://api.icheck-in.com/oauth/token"
ICHECK_PRODUCT_ID  = os.environ["ICHECK_PRODUCT_ID"]
SPREADSHEET_ID     = "1nEpSfYuIGeZ-PF9FNNaGuYHN5m1fl-izoEXoStrfqLk"
TOKENS_SHEET       = "Tokens"
CELL_ACCESS_TOKEN  = "B1"
CELL_REFRESH_TOKEN = "B2"
CELL_UPDATED_AT    = "B3"
INTERVALO_HORAS    = 4


# ── Sheets ────────────────────────────────────────────────────────────────────
def _sheets_client():
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def leer_refresh_token() -> str:
    client = _sheets_client()
    sheet  = client.open_by_key(SPREADSHEET_ID).worksheet(TOKENS_SHEET)
    token  = sheet.acell(CELL_REFRESH_TOKEN).value
    if not token:
        raise ValueError("refresh_token vacío en Sheets (B2). Cargarlo manualmente la primera vez.")
    return token.strip()


def guardar_tokens(access_token: str, refresh_token: str):
    client = _sheets_client()
    sheet  = client.open_by_key(SPREADSHEET_ID).worksheet(TOKENS_SHEET)
    ahora  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.update(CELL_ACCESS_TOKEN,  [[access_token]])
    sheet.update(CELL_REFRESH_TOKEN, [[refresh_token]])
    sheet.update(CELL_UPDATED_AT,    [[ahora]])
    log.info(f"✅ Tokens guardados en Sheets — {ahora}")


# ── Renovación ────────────────────────────────────────────────────────────────
def renovar_tokens():
    log.info("━" * 50)
    log.info("🔄 Iniciando renovación de tokens iCheck")
    try:
        refresh_token = leer_refresh_token()

        resp = requests.post(
            ICHECK_TOKEN_URL,
            json={
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
                "product_id":    ICHECK_PRODUCT_ID,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            log.error(f"❌ iCheck respondió {resp.status_code}: {resp.text}")
            return

        data         = resp.json()
        access_token = data.get("access_token") or data.get("token")
        new_refresh  = data.get("refresh_token") or refresh_token  # algunos endpoints no devuelven nuevo refresh

        if not access_token:
            log.error(f"Respuesta sin access_token: {data}")
            return

        guardar_tokens(access_token, new_refresh)
        log.info("✅ Renovación completada")

    except Exception as e:
        log.exception(f"💥 Error en renovación: {e}")
    log.info("━" * 50)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("🚀 token_refresher iniciando...")

    # Verificación inmediata al arrancar
    renovar_tokens()

    scheduler = BlockingScheduler(timezone="America/Argentina/Buenos_Aires")
    scheduler.add_job(
        renovar_tokens,
        trigger="interval",
        hours=INTERVALO_HORAS,
        id="renovar_tokens",
        max_instances=1,
        coalesce=True,
    )

    log.info(f"⏱  Próxima renovación en {INTERVALO_HORAS}hs")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("🛑 Servicio detenido.")
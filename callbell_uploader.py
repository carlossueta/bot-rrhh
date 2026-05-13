"""
Microservicio: recibe una URL de adjunto de Callbell,
la sube a Cloudinary y devuelve la URL permanente.
"""

import os
import requests
import cloudinary
import cloudinary.uploader
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

CALLBELL_API_TOKEN = os.environ.get("CALLBELL_API_TOKEN", "")

cloudinary.config(
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.environ.get("CLOUDINARY_API_KEY"),
    api_secret = os.environ.get("CLOUDINARY_API_SECRET"),
    secure     = True
)

@app.route("/subir", methods=["POST"])
def subir():
    """
    Espera un JSON tipo:
        { "url": "https://callbell.../archivo.jpg" }
    
    Devuelve:
        { "ok": true, "url": "https://res.cloudinary.com/..." }
    """
    try:
        data = request.json or {}
        url_callbell = str(data.get("url", "")).strip()
        # Opcional: identificador para organizar carpetas en Cloudinary
        identificador = str(data.get("telefono", "") or data.get("id", "") or "sin-id").strip()

        print(f">>> Subiendo a Cloudinary | URL Callbell: {url_callbell}")

        if not url_callbell:
            return jsonify({"ok": False, "error": "falta_url"}), 400

        # Descargar archivo desde Callbell (intenta sin auth, fallback con Bearer)
        r = requests.get(url_callbell, timeout=20)
        if r.status_code in (401, 403) and CALLBELL_API_TOKEN:
            headers = {"Authorization": f"Bearer {CALLBELL_API_TOKEN}"}
            r = requests.get(url_callbell, headers=headers, timeout=20)
        r.raise_for_status()

        # Subir a Cloudinary
        result = cloudinary.uploader.upload(
            r.content,
            folder        = f"justificantes/{identificador}",
            resource_type = "auto",
            public_id     = datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        url_cloudinary = result.get("secure_url", "")
        print(f">>> Cloudinary OK: {url_cloudinary}")

        return jsonify({"ok": True, "url": url_cloudinary}), 200

    except Exception as e:
        print(f"ERROR en /subir: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Callbell Uploader activo ✅"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=True)
from app import programar_renovacion

def on_starting(server):
    """Se ejecuta al arrancar gunicorn, antes de los workers."""
    programar_renovacion()
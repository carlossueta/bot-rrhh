from Bot_HR_v2 import programar_renovacion

def on_starting(server):
    """Se ejecuta al arrancar gunicorn, antes de los workers."""
    programar_renovacion()
from Bot_HR_v2 import programar_renovacion, _cargar_tokens_iniciales, token_state

def on_starting(server):
    """Se ejecuta al arrancar gunicorn, antes de los workers."""
    access, refresh = _cargar_tokens_iniciales()
    token_state["access_token"]  = access
    token_state["refresh_token"] = refresh
    programar_renovacion()
import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

# Flask
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_in_prod_32c")

# QR Encryption
_fernet_key = os.getenv("QR_FERNET_KEY")
if not _fernet_key:
    # Generar una clave nueva si no existe (solo para desarrollo)
    _fernet_key = Fernet.generate_key().decode()
    print(f"[AVISO] QR_FERNET_KEY no configurada. Usando clave temporal: {_fernet_key}")
    print("[AVISO] Agrega QR_FERNET_KEY al archivo .env para producción.")
QR_FERNET_KEY = _fernet_key.encode() if isinstance(_fernet_key, str) else _fernet_key

# Gmail
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# App
NOMBRE_EMPRESA = os.getenv("NOMBRE_EMPRESA", "Campamento")

# --- Railway Persistence Logic ---
# Railway usa la variable de entorno RAILWAY_ENVIRONMENT para identificar que está corriendo allí
if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"):
    default_db_path = "/data/campamento.db"
else:
    default_db_path = "campamento.db"

DATABASE_PATH = os.getenv("DATABASE_PATH", default_db_path)
PORT = int(os.getenv("PORT", 5000))

# Ciclos de turno iniciales (días_faena, días_descanso)
# ref_inicio: fecha de referencia del grupo según calendarización
TURNOS_BASE = {
    "14x14-A": {"work": 14, "rest": 14, "ref_inicio": "2026-03-12"},
    "14x14-B": {"work": 14, "rest": 14, "ref_inicio": "2026-03-26"},
    "14x14-C": {"work": 14, "rest": 14, "ref_inicio": "2026-03-05"},
    "14x14-D": {"work": 14, "rest": 14, "ref_inicio": "2026-03-19"},
    "8x6-A":   {"work": 8,  "rest": 6,  "ref_inicio": "2026-03-24"},
    "8x6-B":   {"work": 8,  "rest": 6,  "ref_inicio": "2026-03-31"},
    "4X3":     {"work": 4,  "rest": 3,  "ref_inicio": "2026-03-30"},
    "5X2":     {"work": 5,  "rest": 2,  "ref_inicio": "2026-03-30"},
}

GRUPOS_BASE = {
    "14x14-A": "14x14-AB",   
    "14x14-B": "14x14-AB",
    "14x14-C": "14x14-CD",   
    "14x14-D": "14x14-CD",
    "8x6-A":   "8x6",        
    "8x6-B":   "8x6",
    "4X3":     "4x3-5x2",    
    "5X2":     "4x3-5x2",
}

CONTRATURNOS_BASE = {
    "14x14-A": "14x14-B",
    "14x14-B": "14x14-A",
    "14x14-C": "14x14-D",
    "14x14-D": "14x14-C",
    "8x6-A":   "8x6-B",
    "8x6-B":   "8x6-A",
    "4X3":     "5X2",
    "5X2":     "4X3",
}

# Horas antes de llegada para enviar notificación
HORAS_NOTIFICACION = 48

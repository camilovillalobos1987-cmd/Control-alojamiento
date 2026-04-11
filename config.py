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

# Ciclos de turno (días_faena, días_descanso)
# ref_inicio: fecha de referencia del grupo según calendarización (Abril 2026)
TURNOS = {
    # ── Tipos genéricos (sin calendarización fija) ─────────────────────────
    "14x14":   {"work": 14, "rest": 14},
    "5x2":     {"work": 5,  "rest": 2},
    "8x6":     {"work": 8,  "rest": 6},
    "7x7":     {"work": 7,  "rest": 7},
    "15x13":   {"work": 15, "rest": 13},
    "Noche":   {"work": 14, "rest": 14},
    # ── Tipos calendarizados (con fecha de inicio de ciclo de referencia) ──
    # Par A↔B: cuando A trabaja B descansa (misma cama, nunca se ven)
    # Par C↔D: cuando C trabaja D descansa (misma cama, nunca se ven)
    # A y C se CRUZAN 7 días → NO pueden compartir pieza
    "14x14-A": {"work": 14, "rest": 14, "ref_inicio": "2026-03-12"},
    "14x14-B": {"work": 14, "rest": 14, "ref_inicio": "2026-03-26"},
    "14x14-C": {"work": 14, "rest": 14, "ref_inicio": "2026-03-05"},
    "14x14-D": {"work": 14, "rest": 14, "ref_inicio": "2026-03-19"},
    "8x6-A":   {"work": 8,  "rest": 6,  "ref_inicio": "2026-03-24"},
    "8x6-B":   {"work": 8,  "rest": 6,  "ref_inicio": "2026-03-31"},
    "4X3":     {"work": 4,  "rest": 3,  "ref_inicio": "2026-03-30"},
    "5X2":     {"work": 5,  "rest": 2,  "ref_inicio": "2026-03-30"},
}

# Grupos de compatibilidad: solo turnos del MISMO grupo pueden compartir cama
# sin riesgo de cruce (o con cruce mínimo aceptable).
GRUPOS_TURNOS = {
    "14x14-A": "14x14-AB",   # A y B se turnan: nunca coinciden en la pieza
    "14x14-B": "14x14-AB",
    "14x14-C": "14x14-CD",   # C y D se turnan: nunca coinciden en la pieza
    "14x14-D": "14x14-CD",
    "8x6-A":   "8x6",        # A y B se turnan (coinciden 1 noche, aceptable)
    "8x6-B":   "8x6",
    "4X3":     "4x3-5x2",    # Comparten entre sí por diseño
    "5X2":     "4x3-5x2",
}

# Pares de contraturnos (cama caliente: el que llega ocupa la cama del que sale)
CONTRATURNOS = {
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

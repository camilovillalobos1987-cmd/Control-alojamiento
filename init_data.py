"""
Script para inicializar la base de datos con:
- Módulos A, B, C, D
- 2 pisos por módulo
- 20 habitaciones por piso
Total: 160 habitaciones

Ejecutar una sola vez: python init_data.py
"""
from database import init_db, crear_habitacion, get_db, usuario_existe, crear_usuario
from auth import hash_password

MODULOS = ["A", "B", "C", "D"]
PISOS = [1, 2]
HABITACIONES_POR_PISO = 20


def init():
    print("Inicializando base de datos...")
    init_db()

    conn = get_db()
    existentes = conn.execute("SELECT COUNT(*) FROM habitaciones").fetchone()[0]
    conn.close()

    if existentes > 0:
        print(f"Ya existen {existentes} habitaciones. No se crearán duplicados.")
    else:
        count = 0
        for modulo in MODULOS:
            for piso in PISOS:
                for num in range(1, HABITACIONES_POR_PISO + 1):
                    numero = f"{num:02d}"
                    crear_habitacion(modulo, piso, numero)
                    count += 1
        print(f"✅ {count} habitaciones creadas en módulos {', '.join(MODULOS)}.")

    # ── Usuarios por defecto ─────────────────────────────────────────────────
    usuarios_default = [
        ("admin",  "admin123",  "admin",  "Administrador"),
        ("visor",  "visor123",  "viewer", "Visor"),
    ]
    for username, password, rol, nombre in usuarios_default:
        if not usuario_existe(username):
            crear_usuario(username, hash_password(password), rol, nombre)
            print(f"[OK] Usuario '{username}' ({rol}) creado.")
        else:
            print(f"[--] Usuario '{username}' ya existe.")

    print("[OK] Base de datos lista -> campamento.db")


if __name__ == "__main__":
    init()

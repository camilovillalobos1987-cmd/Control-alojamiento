#!/usr/bin/env python3
"""
Migración de datos SQLite -> PostgreSQL (una sola vez).

Uso:
    DATABASE_URL="postgresql://usuario:clave@host:5432/bd" \
        python scripts/migrar_sqlite_a_pg.py [ruta_sqlite]

    - [ruta_sqlite] por defecto: campamento.db (o DATABASE_PATH del .env)
    - Crea el esquema en PostgreSQL si no existe (init_db + migrar_db).
    - Copia todas las tablas respetando el orden de las FK.
    - Ajusta las secuencias SERIAL al max(id) de cada tabla.

Requisito: la BD SQLite debe estar migrada a la última versión
(la app lo hace sola al arrancar: migrar_db es idempotente).
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE_URL, DATABASE_PATH  # noqa: E402

TABLAS_ORDEN = [
    "habitaciones",
    "turnos",
    "usuarios",
    "trabajadores",
    "movimientos",
    "novedades",
    "censo",
    "notificaciones_log",
]


def main():
    if not DATABASE_URL:
        sys.exit("ERROR: define DATABASE_URL con la conexión a PostgreSQL.")

    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else DATABASE_PATH
    if not os.path.exists(sqlite_path):
        sys.exit(f"ERROR: no existe el SQLite origen: {sqlite_path}")

    import psycopg

    print(f"Origen : {sqlite_path}")
    print(f"Destino: PostgreSQL ({DATABASE_URL.split('@')[-1]})")

    # 1. Esquema en destino
    import database as db
    assert db.USE_PG, "DATABASE_URL no fue detectada por database.py"
    db.init_db()
    db.migrar_db()
    print("Esquema PostgreSQL listo.")

    # 2. Copiar datos
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    dst = psycopg.connect(DATABASE_URL)
    dcur = dst.cursor()

    total = 0
    for tabla in TABLAS_ORDEN:
        existe = src.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (tabla,)).fetchone()
        if not existe:
            print(f"  {tabla}: no existe en origen, se omite")
            continue
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({tabla})").fetchall()]
        rows = src.execute(f"SELECT * FROM {tabla}").fetchall()
        if not rows:
            print(f"  {tabla}: 0 filas")
            continue
        col_list = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(["%s"] * len(cols))
        dcur.executemany(
            f'INSERT INTO "{tabla}" ({col_list}) VALUES ({ph}) '
            f"ON CONFLICT DO NOTHING",
            [tuple(r) for r in rows],
        )
        # 3. Ajustar secuencia al max(id)
        if "id" in cols:
            dcur.execute(f'SELECT max("id") FROM "{tabla}"')
            max_id = dcur.fetchone()[0]
            if max_id:
                dcur.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, 'id'), %s)",
                    (tabla, max_id),
                )
        print(f"  {tabla}: {len(rows)} filas")
        total += len(rows)

    dst.commit()

    # 4. Verificación rápida
    print("\nVerificación en destino:")
    for tabla in TABLAS_ORDEN:
        n = dcur.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
        print(f"  {tabla}: {n}")

    dcur.close()
    dst.close()
    src.close()
    print(f"\nMigración completa: {total} filas copiadas.")
    print("Revisa los conteos y luego apunta tu deploy a PostgreSQL.")


if __name__ == "__main__":
    main()

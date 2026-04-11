import sqlite3
import json
from datetime import datetime
from config import DATABASE_PATH


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS trabajadores (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre              TEXT NOT NULL,
            rut                 TEXT UNIQUE NOT NULL,
            cargo               TEXT,
            turno               TEXT CHECK(turno IN ('14x14','5x2','8x6','7x7','15x13','Noche')),
            email               TEXT,
            estado              TEXT DEFAULT 'En descanso' CHECK(estado IN (
                                    'Activo en campamento','En descanso','Permiso',
                                    'Falla','Licencia Médica','Vacaciones','Desvinculado'
                                )),
            fecha_inicio_ciclo  TEXT,
            qr_token            TEXT UNIQUE,
            qr_revocado         INTEGER DEFAULT 0,
            habitacion_id       INTEGER REFERENCES habitaciones(id) ON DELETE SET NULL,
            created_at          TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS habitaciones (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo          TEXT NOT NULL,
            piso            INTEGER NOT NULL,
            numero          TEXT NOT NULL,
            estado          TEXT DEFAULT 'Disponible' CHECK(estado IN (
                                'Disponible','Mantenimiento'
                            )),
            capacidad       INTEGER DEFAULT 3,
            UNIQUE(modulo, piso, numero)
        );

        CREATE TABLE IF NOT EXISTS movimientos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_id   INTEGER REFERENCES trabajadores(id),
            fecha_hora      TEXT DEFAULT (datetime('now','localtime')),
            tipo            TEXT CHECK(tipo IN ('Entrada','Salida')),
            metodo          TEXT DEFAULT 'QR',
            observacion     TEXT
        );

        CREATE TABLE IF NOT EXISTS novedades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_id   INTEGER REFERENCES trabajadores(id),
            tipo            TEXT CHECK(tipo IN (
                                'Cambio de Turno','Permiso','Falla',
                                'Licencia Médica','Vacaciones','Desvinculación','Otro'
                            )),
            fecha_inicio    TEXT,
            fecha_fin       TEXT,
            pieza_liberada  INTEGER DEFAULT 0,
            observacion     TEXT,
            registrado_por  TEXT DEFAULT 'Administrador',
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS notificaciones_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_id   INTEGER REFERENCES trabajadores(id),
            tipo            TEXT,
            destinatario    TEXT,
            enviado_en      TEXT DEFAULT (datetime('now','localtime')),
            status          TEXT DEFAULT 'Enviado'
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            rol         TEXT NOT NULL DEFAULT 'viewer' CHECK(rol IN ('admin','viewer')),
            nombre      TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS censo (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_id   INTEGER REFERENCES trabajadores(id) ON DELETE CASCADE,
            habitacion_id   INTEGER REFERENCES habitaciones(id) ON DELETE SET NULL,
            fecha           TEXT DEFAULT (date('now','localtime')),
            hora            TEXT DEFAULT (time('now','localtime')),
            usuario         TEXT
        );

        CREATE TABLE IF NOT EXISTS turnos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT UNIQUE NOT NULL,
            work        INTEGER NOT NULL,
            rest        INTEGER NOT NULL,
            ref_inicio  TEXT,
            grupo       TEXT,
            contraturno TEXT
        );
    """)
    conn.commit()
    conn.close()


def migrar_db():
    """
    Migración incremental. Se ejecuta en cada arranque y es idempotente.
    Agrega columnas nuevas si no existen y migra datos del esquema antiguo (1:1) al nuevo (1:N).
    """
    conn = get_db()

    # ── 1. Agregar habitacion_id a trabajadores ──────────────────────────────
    cols_t = {r[1] for r in conn.execute("PRAGMA table_info(trabajadores)").fetchall()}
    if 'habitacion_id' not in cols_t:
        conn.execute("ALTER TABLE trabajadores ADD COLUMN habitacion_id INTEGER REFERENCES habitaciones(id)")
        # Migrar: copiar la relación inversa desde habitaciones.trabajador_id
        conn.execute("""
            UPDATE trabajadores
            SET habitacion_id = (
                SELECT h.id FROM habitaciones h WHERE h.trabajador_id = trabajadores.id
            )
        """)

    # ── 2. Agregar capacidad a habitaciones ──────────────────────────────────
    cols_h = {r[1] for r in conn.execute("PRAGMA table_info(habitaciones)").fetchall()}
    if 'capacidad' not in cols_h:
        conn.execute("ALTER TABLE habitaciones ADD COLUMN capacidad INTEGER DEFAULT 3")

    # ── 3. Relajar CHECK constraint en habitaciones.estado (Disponible ya no es Ocupada)
    #       SQLite no soporta ALTER para CHECK, pero la columna 'estado' pasa a ser
    #       solo 'Disponible' | 'Mantenimiento'. Dejamos filas con 'Ocupada' como
    #       'Disponible' porque el conteo de ocupantes viene de trabajadores.
    conn.execute("""
        UPDATE habitaciones SET estado = 'Disponible' WHERE estado = 'Ocupada'
    """)

    # ── 4. Crear tabla censo si no existe (BD ya iniciada antes de esta versión) ──
    tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if 'censo' not in tablas:
        conn.execute("""
            CREATE TABLE censo (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                trabajador_id   INTEGER REFERENCES trabajadores(id) ON DELETE CASCADE,
                habitacion_id   INTEGER REFERENCES habitaciones(id) ON DELETE SET NULL,
                fecha           TEXT DEFAULT (date('now','localtime')),
                hora            TEXT DEFAULT (time('now','localtime')),
                usuario         TEXT
            )
        """)

    # ── 4.5. Crear tabla turnos si no existe y poblarla ──
    if 'turnos' not in tablas:
        conn.execute("""
            CREATE TABLE turnos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT UNIQUE NOT NULL,
                work        INTEGER NOT NULL,
                rest        INTEGER NOT NULL,
                ref_inicio  TEXT,
                grupo       TEXT,
                contraturno TEXT
            )
        """)
        
    count_t = conn.execute("SELECT COUNT(*) FROM turnos").fetchone()[0]
    if count_t == 0:
        from config import TURNOS_BASE, GRUPOS_BASE, CONTRATURNOS_BASE
        for t_name, t_data in TURNOS_BASE.items():
            conn.execute("""
                INSERT INTO turnos (nombre, work, rest, ref_inicio, grupo, contraturno)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (t_name, t_data.get("work"), t_data.get("rest"), t_data.get("ref_inicio"), GRUPOS_BASE.get(t_name), CONTRATURNOS_BASE.get(t_name)))


    # ── 5. Eliminar CHECK restrictivo de turno para aceptar nuevos tipos ────
    # SQLite no permite ALTER COLUMN, se recrea la tabla si el esquema antiguo
    # aún tiene CHECK(turno IN ('14x14','5x2',...))
    schema_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='trabajadores' AND type='table'"
    ).fetchone()
    if schema_row and "CHECK(turno IN" in (schema_row[0] or ""):
        conn.executescript("""
            PRAGMA foreign_keys = OFF;

            CREATE TABLE trabajadores_new (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre              TEXT NOT NULL,
                rut                 TEXT UNIQUE NOT NULL,
                cargo               TEXT,
                turno               TEXT,
                email               TEXT,
                estado              TEXT DEFAULT 'En descanso' CHECK(estado IN (
                                        'Activo en campamento','En descanso','Permiso',
                                        'Falla','Licencia Médica','Vacaciones','Desvinculado'
                                    )),
                fecha_inicio_ciclo  TEXT,
                qr_token            TEXT UNIQUE,
                qr_revocado         INTEGER DEFAULT 0,
                habitacion_id       INTEGER REFERENCES habitaciones(id) ON DELETE SET NULL,
                created_at          TEXT DEFAULT (datetime('now','localtime'))
            );

            INSERT INTO trabajadores_new
                SELECT id, nombre, rut, cargo, turno, email, estado,
                       fecha_inicio_ciclo, qr_token, qr_revocado, habitacion_id, created_at
                FROM trabajadores;

            DROP TABLE trabajadores;
            ALTER TABLE trabajadores_new RENAME TO trabajadores;

            PRAGMA foreign_keys = ON;
        """)

    conn.commit()
    conn.close()


# ─────────────────────────── TRABAJADORES ──────────────────────────────────

def _estado_visual(activos: int, capacidad: int, estado_manual: str) -> str:
    """
    Retorna el estado visual de una habitación según occupancy FÍSICA (activos en campamento).
    libre | parcial | completa | mantenimiento
    """
    if estado_manual == 'Mantenimiento':
        return 'mantenimiento'
    if activos == 0:
        return 'libre'
    if activos >= capacidad:
        return 'completa'
    return 'parcial'


def get_todos_trabajadores():
    conn = get_db()
    rows = conn.execute("""
        SELECT t.*, h.modulo, h.piso, h.numero as pieza
        FROM trabajadores t
        LEFT JOIN habitaciones h ON h.id = t.habitacion_id
        ORDER BY t.nombre
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trabajador(id):
    conn = get_db()
    row = conn.execute("""
        SELECT t.*, h.id as hab_id, h.modulo, h.piso, h.numero as pieza,
               h.capacidad,
               (SELECT COUNT(*) FROM trabajadores t2
                WHERE t2.habitacion_id = h.id AND t2.estado != 'Desvinculado') as hab_ocupantes
        FROM trabajadores t
        LEFT JOIN habitaciones h ON h.id = t.habitacion_id
        WHERE t.id = ?
    """, (id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def crear_trabajador(data: dict) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO trabajadores (nombre, rut, cargo, turno, email, estado, fecha_inicio_ciclo)
        VALUES (:nombre, :rut, :cargo, :turno, :email, :estado, :fecha_inicio_ciclo)
    """, data)
    id_nuevo = c.lastrowid
    conn.commit()
    conn.close()
    return id_nuevo


def actualizar_trabajador(id: int, data: dict):
    conn = get_db()
    conn.execute("""
        UPDATE trabajadores
        SET nombre=:nombre, rut=:rut, cargo=:cargo, turno=:turno, email=:email,
            estado=:estado, fecha_inicio_ciclo=:fecha_inicio_ciclo
        WHERE id=:id
    """, {**data, "id": id})
    conn.commit()
    conn.close()


def actualizar_estado_trabajador(id: int, estado: str):
    conn = get_db()
    conn.execute("UPDATE trabajadores SET estado=? WHERE id=?", (estado, id))
    conn.commit()
    conn.close()


def guardar_qr_token(id: int, token: str):
    conn = get_db()
    conn.execute("UPDATE trabajadores SET qr_token=?, qr_revocado=0 WHERE id=?", (token, id))
    conn.commit()
    conn.close()


def revocar_qr(id: int):
    conn = get_db()
    conn.execute("UPDATE trabajadores SET qr_revocado=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()


def get_trabajador_by_token(token: str):
    conn = get_db()
    row = conn.execute("""
        SELECT t.*, h.modulo, h.piso, h.numero as pieza
        FROM trabajadores t
        LEFT JOIN habitaciones h ON h.id = t.habitacion_id
        WHERE t.qr_token=? AND t.qr_revocado=0
    """, (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────── HABITACIONES ──────────────────────────────────

def get_todas_habitaciones():
    """Retorna todas las habitaciones con conteo de ocupantes y estado visual.

    activos     = trabajadores con estado 'Activo en campamento' (físicamente presentes)
    asignados   = todos los asignados no desvinculados (incluye los en descanso)
    en_descanso = asignados - activos
    camas_libres= capacidad - activos  (camas disponibles hoy)
    estado_visual se basa en activos (ocupación física real)
    """
    conn = get_db()
    rows = conn.execute("""
        SELECT h.*,
               COALESCE(SUM(CASE WHEN t.estado='Activo en campamento' THEN 1 ELSE 0 END), 0) as activos,
               COALESCE(COUNT(CASE WHEN t.estado != 'Desvinculado' THEN 1 END), 0)           as asignados
        FROM habitaciones h
        LEFT JOIN trabajadores t ON t.habitacion_id = h.id
        GROUP BY h.id
        ORDER BY h.modulo, h.piso, h.numero
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['ocupantes']    = d['activos']                         # alias compatibilidad
        d['en_descanso']  = d['asignados'] - d['activos']
        d['camas_libres'] = max(0, d['capacidad'] - d['activos'])
        d['estado_visual'] = _estado_visual(d['activos'], d['capacidad'], d['estado'])
        result.append(d)
    return result


def get_habitacion(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM habitaciones WHERE id=?", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_ocupantes_habitacion(hab_id: int) -> list:
    """Trabajadores activos asignados a esta habitación."""
    conn = get_db()
    rows = conn.execute("""
        SELECT id, nombre, turno, cargo, estado, rut
        FROM trabajadores
        WHERE habitacion_id = ? AND estado != 'Desvinculado'
        ORDER BY nombre
    """, (hab_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def renombrar_modulo(modulo_actual: str, modulo_nuevo: str):
    """Cambia el nombre de un módulo completo en todas sus habitaciones."""
    conn = get_db()
    conn.execute("UPDATE habitaciones SET modulo = ? WHERE modulo = ?",
                 (modulo_nuevo, modulo_actual))
    conn.commit()
    conn.close()


def eliminar_modulo(modulo: str) -> int:
    """
    Elimina todas las habitaciones de un módulo.
    Desvincula automáticamente a los trabajadores asignados.
    Retorna la cantidad de habitaciones eliminadas.
    """
    conn = get_db()
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM habitaciones WHERE modulo = ?", (modulo,)
    ).fetchall()]
    if ids:
        conn.execute(
            f"UPDATE trabajadores SET habitacion_id = NULL "
            f"WHERE habitacion_id IN ({','.join('?'*len(ids))})", ids
        )
    n = conn.execute("DELETE FROM habitaciones WHERE modulo = ?", (modulo,)).rowcount
    conn.commit()
    conn.close()
    return n


def eliminar_habitacion(id: int) -> int:
    """
    Elimina una habitación individual.
    Desvincula a los trabajadores asignados. Retorna cantidad de ocupantes liberados.
    """
    conn = get_db()
    n_trabajadores = conn.execute(
        "SELECT COUNT(*) FROM trabajadores WHERE habitacion_id = ?", (id,)
    ).fetchone()[0]
    conn.execute("UPDATE trabajadores SET habitacion_id = NULL WHERE habitacion_id = ?", (id,))
    conn.execute("DELETE FROM habitaciones WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return n_trabajadores


def admin_limpiar_bd():
    """Elimina TODO el contenido manteniendo la estructura, excepto el usuario admin."""
    conn = get_db()
    tablas = ["censo", "movimientos", "novedades", "notificaciones_log", "habitaciones", "trabajadores"]
    for t in tablas:
        conn.execute(f"DELETE FROM {t}")
        conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")

    conn.execute("DELETE FROM usuarios WHERE username != 'admin'")

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════
#   TURNOS DINÁMICOS
# ═══════════════════════════════════════════════════════
def get_turnos_dicts():
    """Devuelve las estructuras necesarias simulando el antiguo comportamiento de config.py"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM turnos").fetchall()
    conn.close()
    
    turnos = {}
    grupos = {}
    contraturnos = {}
    for r in rows:
        n = r["nombre"]
        turnos[n] = {"work": r["work"], "rest": r["rest"], "ref_inicio": r["ref_inicio"]}
        if r["grupo"]: grupos[n] = r["grupo"]
        if r["contraturno"]: contraturnos[n] = r["contraturno"]
        
    return turnos, grupos, contraturnos

def get_turnos_list():
    """Devuelve la lista para el UI administrativo."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM turnos ORDER BY nombre").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def crear_turno_db(data):
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO turnos (nombre, work, rest, ref_inicio, grupo, contraturno)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (data["nombre"].strip(), int(data["work"]), int(data["rest"]), data.get("ref_inicio") or None, data.get("grupo") or None, data.get("contraturno") or None))
        conn.commit()
    finally:
        conn.close()

def eliminar_turno_db(id):
    conn = get_db()
    conn.execute("DELETE FROM turnos WHERE id = ?", (id,))
    conn.commit()
    conn.close()


def agregar_piezas_modulo(modulo: str, piso: int, cantidad: int, capacidad: int = 3) -> int:
    """
    Agrega 'cantidad' habitaciones a un módulo/piso, numerándolas
    automáticamente a partir del mayor número existente + 1.
    Retorna cuántas fueron creadas.
    """
    conn = get_db()
    existentes = [r[0] for r in conn.execute(
        "SELECT numero FROM habitaciones WHERE modulo = ? AND piso = ?", (modulo, piso)
    ).fetchall()]

    # Calcular siguiente número
    nums = []
    for n in existentes:
        try:
            nums.append(int(n))
        except (ValueError, TypeError):
            pass
    siguiente = (max(nums) + 1) if nums else 1

    creadas = 0
    for i in range(cantidad):
        numero = f"{siguiente + i:02d}"
        try:
            conn.execute(
                "INSERT INTO habitaciones (modulo, piso, numero, capacidad) VALUES (?,?,?,?)",
                (modulo, piso, numero, capacidad)
            )
            creadas += 1
        except Exception:
            pass  # UNIQUE constraint (ya existe ese número)

    conn.commit()
    conn.close()
    return creadas


def get_habitaciones_disponibles():
    """Habitaciones con al menos una cama libre (basado en activos físicamente)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT h.*,
               COALESCE(SUM(CASE WHEN t.estado='Activo en campamento' THEN 1 ELSE 0 END), 0) as activos,
               (h.capacidad - COALESCE(SUM(CASE WHEN t.estado='Activo en campamento' THEN 1 ELSE 0 END), 0)) as camas_libres
        FROM habitaciones h
        LEFT JOIN trabajadores t ON t.habitacion_id = h.id
        WHERE h.estado != 'Mantenimiento'
        GROUP BY h.id
        HAVING camas_libres > 0
        ORDER BY h.modulo, h.piso, h.numero
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['ocupantes'] = d['activos']
        result.append(d)
    return result


def asignar_habitacion(hab_id: int, trabajador_id: int) -> bool:
    """
    Asigna una habitación al trabajador.
    La capacidad se verifica solo contra trabajadores 'Activo en campamento'
    (los que están 'En descanso' libran la cama físicamente).
    Retorna False si ya hay >= capacidad trabajadores activos.
    """
    conn = get_db()
    hab = conn.execute("SELECT * FROM habitaciones WHERE id=?", (hab_id,)).fetchone()
    if not hab:
        conn.close()
        return False
    hab = dict(hab)

    # Solo contar trabajadores físicamente presentes (activos en campamento)
    activos = conn.execute("""
        SELECT COUNT(*) FROM trabajadores
        WHERE habitacion_id=? AND id!=? AND estado='Activo en campamento'
    """, (hab_id, trabajador_id)).fetchone()[0]

    if activos >= hab.get('capacidad', 3):
        conn.close()
        return False

    conn.execute("UPDATE trabajadores SET habitacion_id=? WHERE id=?", (hab_id, trabajador_id))
    conn.commit()
    conn.close()
    return True


def asignar_habitacion_aleatoria(trabajador_id: int) -> dict | None:
    """
    Elige aleatoriamente una habitación con camas libres y asigna al trabajador.
    Retorna el dict de la habitación asignada, o None si no hay disponibles.
    """
    conn = get_db()
    hab = conn.execute("""
        SELECT h.*, COUNT(t.id) as ocupantes
        FROM habitaciones h
        LEFT JOIN trabajadores t
               ON t.habitacion_id = h.id AND t.estado != 'Desvinculado'
        WHERE h.estado != 'Mantenimiento'
        GROUP BY h.id
        HAVING ocupantes < h.capacidad
        ORDER BY RANDOM()
        LIMIT 1
    """).fetchone()
    if not hab:
        conn.close()
        return None
    hab = dict(hab)
    conn.execute("UPDATE trabajadores SET habitacion_id=? WHERE id=?", (hab["id"], trabajador_id))
    conn.commit()
    conn.close()
    return hab


def get_trabajadores_sin_habitacion() -> list:
    """Trabajadores activos/descanso que no tienen habitación asignada."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM trabajadores
        WHERE habitacion_id IS NULL AND estado != 'Desvinculado'
        ORDER BY nombre
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def liberar_habitacion_de_trabajador(trabajador_id: int):
    conn = get_db()
    conn.execute("UPDATE trabajadores SET habitacion_id=NULL WHERE id=?", (trabajador_id,))
    conn.commit()
    conn.close()


def crear_habitacion(modulo: str, piso: int, numero: str, capacidad: int = 3) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO habitaciones (modulo, piso, numero, capacidad) VALUES (?,?,?,?)",
        (modulo, piso, numero, capacidad)
    )
    id_nuevo = c.lastrowid
    conn.commit()
    conn.close()
    return id_nuevo


def actualizar_estado_habitacion(hab_id: int, estado: str):
    conn = get_db()
    conn.execute("UPDATE habitaciones SET estado=? WHERE id=?", (estado, hab_id))
    conn.commit()
    conn.close()


# ─────────────────────────── MOVIMIENTOS ───────────────────────────────────

def registrar_movimiento(trabajador_id: int, tipo: str, metodo: str = "QR", obs: str = ""):
    conn = get_db()
    conn.execute(
        "INSERT INTO movimientos (trabajador_id, tipo, metodo, observacion) VALUES (?,?,?,?)",
        (trabajador_id, tipo, metodo, obs)
    )
    conn.commit()
    conn.close()


def get_ultimo_movimiento(trabajador_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM movimientos WHERE trabajador_id=? ORDER BY fecha_hora DESC LIMIT 1",
        (trabajador_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_movimientos(limit: int = 200, trabajador_id: int = None):
    conn = get_db()
    if trabajador_id:
        rows = conn.execute("""
            SELECT m.*, t.nombre, t.rut
            FROM movimientos m JOIN trabajadores t ON m.trabajador_id=t.id
            WHERE m.trabajador_id=?
            ORDER BY m.fecha_hora DESC LIMIT ?
        """, (trabajador_id, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT m.*, t.nombre, t.rut, t.cargo
            FROM movimientos m JOIN trabajadores t ON m.trabajador_id=t.id
            ORDER BY m.fecha_hora DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────── NOVEDADES ─────────────────────────────────────

def registrar_novedad(data: dict) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO novedades (trabajador_id, tipo, fecha_inicio, fecha_fin,
                               pieza_liberada, observacion, registrado_por)
        VALUES (:trabajador_id, :tipo, :fecha_inicio, :fecha_fin,
                :pieza_liberada, :observacion, :registrado_por)
    """, data)
    id_nuevo = c.lastrowid
    conn.commit()
    conn.close()
    return id_nuevo


def get_novedades(limit: int = 100):
    conn = get_db()
    rows = conn.execute("""
        SELECT n.*, t.nombre, t.rut
        FROM novedades n JOIN trabajadores t ON n.trabajador_id=t.id
        ORDER BY n.created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_novedades_mes(year: int, month: int):
    conn = get_db()
    
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year}-12-31"
    else:
        # Easy way to get end of month in sqlite without complex date operations
        end_date = f"{year}-{month+1:02d}-01"
        
    rows = conn.execute("""
        SELECT *
        FROM novedades
        WHERE fecha_inicio < ? AND (fecha_fin IS NULL OR fecha_fin >= ?)
    """, (end_date if month != 12 else f"{year+1}-01-01", start_date)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_novedad_vigente(trabajador_id: int) -> dict | None:
    """
    Retorna la novedad más reciente del trabajador.
    La aplicación (app.py) se encarga de definir si está activa hoy o si es futura.
    """
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM novedades
        WHERE trabajador_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (trabajador_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────── CENSO ────────────────────────────────────────

def registrar_censo(trabajador_id: int, habitacion_id, usuario: str):
    """Registra que este trabajador fue verificado físicamente durante el censo del día."""
    conn = get_db()
    conn.execute("""
        INSERT INTO censo (trabajador_id, habitacion_id, usuario)
        VALUES (?, ?, ?)
    """, (trabajador_id, habitacion_id, usuario))
    conn.commit()
    conn.close()


def get_censo_hoy_por_habitacion() -> dict:
    """
    Retorna dict { hab_id: {'verificados': N, 'total': M} } con los datos
    del censo del día para cada habitación con trabajadores asignados.
    """
    from datetime import date
    hoy = date.today().isoformat()
    conn = get_db()

    # Trabajadores verificados hoy por habitacion
    verificados_rows = conn.execute("""
        SELECT habitacion_id, COUNT(DISTINCT trabajador_id) as verificados
        FROM censo
        WHERE fecha = ?
        GROUP BY habitacion_id
    """, (hoy,)).fetchall()

    # Total asignados por habitacion
    totales_rows = conn.execute("""
        SELECT habitacion_id, COUNT(*) as total
        FROM trabajadores
        WHERE habitacion_id IS NOT NULL AND estado != 'Desvinculado'
        GROUP BY habitacion_id
    """).fetchall()

    conn.close()

    result = {}
    for r in totales_rows:
        result[r["habitacion_id"]] = {"verificados": 0, "total": r["total"]}
    for r in verificados_rows:
        if r["habitacion_id"] in result:
            result[r["habitacion_id"]]["verificados"] = r["verificados"]
        else:
            result[r["habitacion_id"]] = {"verificados": r["verificados"], "total": 0}
    return result


def get_ultimo_censo_trabajador(trabajador_id: int) -> dict | None:
    """Retorna el último registro de censo de este trabajador, si existe."""
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM censo WHERE trabajador_id = ?
        ORDER BY fecha DESC, hora DESC LIMIT 1
    """, (trabajador_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────── UTILIDADES DEV ───────────────────────────────

def limpiar_bd_desarrollo():
    """
    Elimina todos los datos operativos manteniendo solo la tabla usuarios.
    USO EXCLUSIVO EN DESARROLLO.
    """
    conn = get_db()
    conn.executescript("""
        DELETE FROM censo;
        DELETE FROM movimientos;
        DELETE FROM novedades;
        DELETE FROM notificaciones_log;
        UPDATE trabajadores SET habitacion_id = NULL;
        DELETE FROM trabajadores;
        DELETE FROM habitaciones;
        DELETE FROM sqlite_sequence
         WHERE name IN ('trabajadores','habitaciones','movimientos',
                        'novedades','censo','notificaciones_log');
    """)
    conn.commit()
    conn.close()


# ─────────────────────────── DASHBOARD ─────────────────────────────────────

def get_metricas_dashboard():
    from datetime import date
    conn = get_db()

    total_trabajadores = conn.execute(
        "SELECT COUNT(*) FROM trabajadores WHERE estado != 'Desvinculado'"
    ).fetchone()[0]

    hoy = date.today().isoformat()
    # Solo contamos como "Con Licencia/Excepción" si la novedad MÁS RECIENTE ya inició
    con_licencia = conn.execute("""
        SELECT COUNT(DISTINCT t.id) FROM trabajadores t
        JOIN (SELECT trabajador_id, MAX(fecha_inicio) as fecha_inicio FROM novedades GROUP BY trabajador_id) n 
          ON n.trabajador_id = t.id
        WHERE t.estado IN ('Licencia Médica','Vacaciones','Permiso','Falla')
          AND n.fecha_inicio <= ?
    """, (hoy,)).fetchone()[0]

    # Para campamento/descanso, contamos los que tienen ese estado, PLUS los que están en estado de excepción pero su novedad es FUTURA.
    # Dado que no sabemos si los del futuro están "En campamento" o "En descanso" sin la lógica de python,
    # simplemente vamos a contar el resto de los trabajadores activos que NO están en licencia vigente.
    # Así el gráfico "Estado del Personal" siempre cuadra con el Total General.
    
    # Trabajadores "En campamento" directos o excepciones futuras (asumimos que si no ha llegado su licencia, están en su rutina normal)
    # Como simplificación en SQL, traemos todos los demás que no califican en con_licencia.
    trabajadores_excepcion_futura = conn.execute("""
        SELECT COUNT(DISTINCT t.id) FROM trabajadores t
        JOIN (SELECT trabajador_id, MAX(fecha_inicio) as fecha_inicio FROM novedades GROUP BY trabajador_id) n
          ON n.trabajador_id = t.id
        WHERE t.estado IN ('Licencia Médica','Vacaciones','Permiso','Falla')
          AND n.fecha_inicio > ?
    """, (hoy,)).fetchone()[0]
    
    en_campamento_base = conn.execute(
        "SELECT COUNT(*) FROM trabajadores WHERE estado='Activo en campamento'"
    ).fetchone()[0]
    
    en_descanso_base = conn.execute(
        "SELECT COUNT(*) FROM trabajadores WHERE estado='En descanso'"
    ).fetchone()[0]
    
    # Asignamos temporalmente las "excepciones futuras" a "en campamento" para que cuadren los totales
    # (Lo ideal sería calcular su ciclo en Python, pero este dashboard solo muestra totales globales)
    en_campamento = en_campamento_base + (trabajadores_excepcion_futura // 2) + (trabajadores_excepcion_futura % 2)
    en_descanso = en_descanso_base + (trabajadores_excepcion_futura // 2)

    total_habitaciones = conn.execute(
        "SELECT COUNT(*) FROM habitaciones"
    ).fetchone()[0]

    # Habitaciones llenas = todas las camas tomadas
    completas = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT h.id FROM habitaciones h
            JOIN trabajadores t ON t.habitacion_id = h.id AND t.estado != 'Desvinculado'
            GROUP BY h.id HAVING COUNT(t.id) >= h.capacidad
        )
    """).fetchone()[0]

    # Habitaciones parcialmente ocupadas
    parciales = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT h.id FROM habitaciones h
            JOIN trabajadores t ON t.habitacion_id = h.id AND t.estado != 'Desvinculado'
            GROUP BY h.id HAVING COUNT(t.id) < h.capacidad
        )
    """).fetchone()[0]

    libres = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT h.id FROM habitaciones h
            LEFT JOIN trabajadores t ON t.habitacion_id = h.id AND t.estado != 'Desvinculado'
            WHERE h.estado != 'Mantenimiento'
            GROUP BY h.id HAVING COUNT(t.id) = 0
        )
    """).fetchone()[0]

    mantenimiento = conn.execute(
        "SELECT COUNT(*) FROM habitaciones WHERE estado='Mantenimiento'"
    ).fetchone()[0]

    # Total camas
    total_camas = conn.execute(
        "SELECT COALESCE(SUM(capacidad), 0) FROM habitaciones WHERE estado != 'Mantenimiento'"
    ).fetchone()[0]

    camas_ocupadas = conn.execute(
        "SELECT COUNT(*) FROM trabajadores WHERE habitacion_id IS NOT NULL AND estado != 'Desvinculado'"
    ).fetchone()[0]

    pct_ocupacion = round((camas_ocupadas / total_camas * 100) if total_camas > 0 else 0, 1)

    # Por turno
    por_turno = conn.execute("""
        SELECT turno, COUNT(*) as total,
               SUM(CASE WHEN estado='Activo en campamento' THEN 1 ELSE 0 END) as en_faena
        FROM trabajadores WHERE estado != 'Desvinculado'
        GROUP BY turno
    """).fetchall()

    # Últimos movimientos
    ultimos_mov = conn.execute("""
        SELECT m.fecha_hora, m.tipo, t.nombre, t.cargo,
               h.modulo, h.piso, h.numero as pieza
        FROM movimientos m
        JOIN trabajadores t ON m.trabajador_id = t.id
        LEFT JOIN habitaciones h ON h.id = t.habitacion_id
        ORDER BY m.fecha_hora DESC LIMIT 10
    """).fetchall()

    # Resumen por módulo (ahora basado en ocupantes, no en estado)
    por_modulo = conn.execute("""
        SELECT h.modulo,
               COUNT(DISTINCT h.id) as total,
               SUM(h.capacidad) as total_camas,
               COUNT(t.id) as ocupantes
        FROM habitaciones h
        LEFT JOIN trabajadores t
               ON t.habitacion_id = h.id AND t.estado != 'Desvinculado'
        GROUP BY h.modulo
        ORDER BY h.modulo
    """).fetchall()

    conn.close()

    return {
        "total_trabajadores": total_trabajadores,
        "en_campamento":      en_campamento,
        "en_descanso":        en_descanso,
        "con_licencia":       con_licencia,
        "total_habitaciones": total_habitaciones,
        "completas":          completas,
        "parciales":          parciales,
        "libres":             libres,
        "mantenimiento":      mantenimiento,
        "total_camas":        total_camas,
        "camas_ocupadas":     camas_ocupadas,
        "pct_ocupacion":      pct_ocupacion,
        "por_turno":          [dict(r) for r in por_turno],
        "ultimos_movimientos":[dict(r) for r in ultimos_mov],
        "por_modulo":         [dict(r) for r in por_modulo],
    }


# ─────────────────────────── NOTIFICACIONES LOG ────────────────────────────

def log_notificacion(trabajador_id: int, tipo: str, destinatario: str, status: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO notificaciones_log (trabajador_id, tipo, destinatario, status) VALUES (?,?,?,?)",
        (trabajador_id, tipo, destinatario, status)
    )
    conn.commit()
    conn.close()


# ─────────────────────────── USUARIOS ──────────────────────────────────

def get_usuario_by_username(username: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_usuario_by_id(user_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_todos_usuarios():
    conn = get_db()
    rows = conn.execute("SELECT id, username, rol, nombre, created_at FROM usuarios ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def crear_usuario(username: str, password_hash: str, rol: str, nombre: str = ""):
    conn = get_db()
    conn.execute(
        "INSERT INTO usuarios (username, password, rol, nombre) VALUES (?,?,?,?)",
        (username, password_hash, rol, nombre)
    )
    conn.commit()
    conn.close()


def usuario_existe(username: str) -> bool:
    conn = get_db()
    row = conn.execute("SELECT id FROM usuarios WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row is not None

def eliminar_usuario(user_id: int):
    conn = get_db()
    conn.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

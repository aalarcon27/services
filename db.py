# -*- coding: utf-8 -*-
"""
Base de datos de la app de Proyectos.

Un solo modulo que sirve para SQLite (desarrollo local, archivo
proyectos.db) y Postgres/Supabase (produccion) sin tener que mantener
dos archivos separados: detecta el entorno mirando si existe el
secreto DB_URL de Streamlit. Si no hay secretos configurados (como en
tu PC), usa SQLite solo.
"""
import os
import sqlite3
import datetime
import streamlit as st

RUTA_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proyectos.db")

USUARIOS_INICIALES = [
    ("ambar", "Ambar Alarcón", "admin"),
    ("luis", "Luis Zevallos", "editor"),
    ("vivian", "Vivian", "editor"),
    ("jaime", "Jaime Ríos", "editor"),
    ("jorge", "Jorge", "visor"),
    ("frank", "Frank", "visor"),
    ("cesar", "Cesar", "visor"),
    ("luisq", "Luisq", "visor"),
]

PALETA_COLORES = [
    "#4C6EF5", "#F76707", "#12B886", "#E64980", "#7048E8",
    "#FAB005", "#15AABF", "#E03131", "#2F9E44", "#1971C2",
]


def _tiene_secreto(clave):
    try:
        return clave in st.secrets
    except Exception:
        return False


_MODO = "postgres" if _tiene_secreto("DB_URL") else "sqlite"


def _con():
    if _MODO == "postgres":
        import psycopg2
        return psycopg2.connect(st.secrets["DB_URL"], sslmode="require")
    con = sqlite3.connect(RUTA_DB)
    con.row_factory = sqlite3.Row
    return con


def _cur(con):
    if _MODO == "postgres":
        import psycopg2.extras
        return con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return con.cursor()


def _q(sql):
    return sql.replace("?", "%s") if _MODO == "postgres" else sql


def _fetchall(sql, params=()):
    con = _con(); cur = _cur(con)
    cur.execute(_q(sql), params)
    rows = cur.fetchall()
    cur.close(); con.close()
    return [dict(r) for r in rows]


def _fetchone(sql, params=()):
    con = _con(); cur = _cur(con)
    cur.execute(_q(sql), params)
    row = cur.fetchone()
    cur.close(); con.close()
    return dict(row) if row else None


def _insertar(sql, params=()):
    """INSERT que devuelve el id nuevo (SERIAL en Postgres, AUTOINCREMENT en SQLite)."""
    con = _con(); cur = _cur(con)
    if _MODO == "postgres":
        cur.execute(_q(sql) + " RETURNING id", params)
        nid = cur.fetchone()["id"]
    else:
        cur.execute(sql, params)
        nid = cur.lastrowid
    con.commit(); cur.close(); con.close()
    return nid


def _ejecutar(sql, params=()):
    """UPDATE/DELETE sin retorno."""
    con = _con(); cur = _cur(con)
    cur.execute(_q(sql), params)
    con.commit(); cur.close(); con.close()


def _tiene_columna(cur, tabla, columna):
    cur.execute(f"PRAGMA table_info({tabla})")
    return any(fila["name"] == columna for fila in cur.fetchall())


# ===================================================================
# INICIALIZACION
# ===================================================================
def init_db():
    con = _con(); cur = con.cursor()
    autoinc = "SERIAL" if _MODO == "postgres" else "INTEGER"
    pk = "PRIMARY KEY" if _MODO == "postgres" else "PRIMARY KEY AUTOINCREMENT"

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS usuarios (
            id         {autoinc} {pk},
            usuario    TEXT UNIQUE NOT NULL,
            nombre     TEXT NOT NULL,
            clave_hash TEXT NOT NULL,
            rol        TEXT DEFAULT 'usuario'
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS personal (
            id      {autoinc} {pk},
            nombre  TEXT NOT NULL,
            activo  BOOLEAN DEFAULT TRUE
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS proyectos (
            id              {autoinc} {pk},
            nombre          TEXT NOT NULL,
            cliente         TEXT,
            color           TEXT,
            pm_usuario      TEXT,
            prevencionista  TEXT,
            creado_por      TEXT,
            creado_en       TEXT
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS sst_requisitos (
            id           {autoinc} {pk},
            proyecto_id  INTEGER NOT NULL,
            nombre       TEXT NOT NULL,
            enviado      BOOLEAN DEFAULT FALSE,
            aprobado     BOOLEAN DEFAULT FALSE
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS servicios (
            id              {autoinc} {pk},
            proyecto_id     INTEGER NOT NULL,
            nombre          TEXT NOT NULL,
            fecha_inicio    TEXT NOT NULL,
            fecha_fin       TEXT NOT NULL,
            confirmado      BOOLEAN DEFAULT FALSE,
            creado_por      TEXT,
            modificado_por  TEXT,
            modificado_en   TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS servicio_personal (
            servicio_id  INTEGER NOT NULL,
            personal_id  INTEGER NOT NULL,
            PRIMARY KEY (servicio_id, personal_id)
        )
    """)
    con.commit(); cur.close(); con.close()


# ===================================================================
# USUARIOS
# ===================================================================
def crear_usuario(usuario, nombre, clave_hash, rol="usuario"):
    _insertar("INSERT INTO usuarios (usuario, nombre, clave_hash, rol) VALUES (?,?,?,?)",
              (usuario, nombre, clave_hash, rol))


def obtener_usuario(usuario):
    return _fetchone("SELECT * FROM usuarios WHERE usuario = ?", (usuario,))


def contar_usuarios():
    con = _con(); cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM usuarios")
    n = cur.fetchone()[0]; cur.close(); con.close()
    return n


def listar_usuarios():
    return _fetchall("SELECT usuario, nombre, rol FROM usuarios ORDER BY rol, usuario")


def listar_usuarios_pm():
    """Usuarios que pueden ser Project Manager (admin/editor)."""
    return _fetchall("SELECT usuario, nombre FROM usuarios WHERE rol IN ('admin','editor') ORDER BY nombre")


def cambiar_clave(usuario, clave_hash):
    _ejecutar("UPDATE usuarios SET clave_hash = ? WHERE usuario = ?", (clave_hash, usuario))


def seed_usuarios(hash_fn):
    con = _con(); cur = con.cursor()
    creados = 0
    for usuario, nombre, rol in USUARIOS_INICIALES:
        if _MODO == "postgres":
            cur.execute(_q("""
                INSERT INTO usuarios (usuario, nombre, clave_hash, rol) VALUES (?,?,?,?)
                ON CONFLICT (usuario) DO NOTHING
            """), (usuario, nombre, hash_fn(usuario), rol))
        else:
            cur.execute("""
                INSERT OR IGNORE INTO usuarios (usuario, nombre, clave_hash, rol) VALUES (?,?,?,?)
            """, (usuario, nombre, hash_fn(usuario), rol))
        creados += cur.rowcount
    con.commit(); cur.close(); con.close()
    return creados


# ===================================================================
# PERSONAL (roster de tecnicos agendables)
# ===================================================================
def listar_personal(solo_activos=False):
    sql = "SELECT * FROM personal"
    if solo_activos:
        sql += " WHERE activo = TRUE"
    sql += " ORDER BY nombre"
    return _fetchall(sql)


def crear_personal(nombre):
    return _insertar("INSERT INTO personal (nombre, activo) VALUES (?, TRUE)", (nombre,))


def editar_personal(pid, nombre, activo):
    _ejecutar("UPDATE personal SET nombre = ?, activo = ? WHERE id = ?", (nombre, activo, pid))


def eliminar_personal(pid):
    _ejecutar("DELETE FROM servicio_personal WHERE personal_id = ?", (pid,))
    _ejecutar("DELETE FROM personal WHERE id = ?", (pid,))


# ===================================================================
# PROYECTOS
# ===================================================================
def crear_proyecto(nombre, cliente, pm_usuario, prevencionista, creado_por):
    n = _fetchone("SELECT COUNT(*) AS n FROM proyectos")["n"]
    color = PALETA_COLORES[n % len(PALETA_COLORES)]
    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    return _insertar("""
        INSERT INTO proyectos (nombre, cliente, color, pm_usuario, prevencionista, creado_por, creado_en)
        VALUES (?,?,?,?,?,?,?)
    """, (nombre, cliente, color, pm_usuario, prevencionista, creado_por, ahora))


def listar_proyectos():
    return _fetchall("SELECT * FROM proyectos ORDER BY nombre")


def obtener_proyecto(pid):
    return _fetchone("SELECT * FROM proyectos WHERE id = ?", (pid,))


def editar_proyecto(pid, nombre, cliente, pm_usuario, prevencionista, color=None):
    if color:
        _ejecutar("""UPDATE proyectos SET nombre=?, cliente=?, pm_usuario=?, prevencionista=?, color=?
                     WHERE id=?""", (nombre, cliente, pm_usuario, prevencionista, color, pid))
    else:
        _ejecutar("""UPDATE proyectos SET nombre=?, cliente=?, pm_usuario=?, prevencionista=?
                     WHERE id=?""", (nombre, cliente, pm_usuario, prevencionista, pid))


def eliminar_proyecto(pid):
    servicios = _fetchall("SELECT id FROM servicios WHERE proyecto_id = ?", (pid,))
    for s in servicios:
        _ejecutar("DELETE FROM servicio_personal WHERE servicio_id = ?", (s["id"],))
    _ejecutar("DELETE FROM servicios WHERE proyecto_id = ?", (pid,))
    _ejecutar("DELETE FROM sst_requisitos WHERE proyecto_id = ?", (pid,))
    _ejecutar("DELETE FROM proyectos WHERE id = ?", (pid,))


# ===================================================================
# REQUISITOS SST (libres por proyecto)
# ===================================================================
def listar_sst(proyecto_id):
    return _fetchall("SELECT * FROM sst_requisitos WHERE proyecto_id = ? ORDER BY id", (proyecto_id,))


def agregar_sst(proyecto_id, nombre):
    return _insertar("""INSERT INTO sst_requisitos (proyecto_id, nombre, enviado, aprobado)
                        VALUES (?,?,FALSE,FALSE)""", (proyecto_id, nombre))


def actualizar_sst(sst_id, enviado, aprobado):
    _ejecutar("UPDATE sst_requisitos SET enviado=?, aprobado=? WHERE id=?",
              (enviado, aprobado, sst_id))


def eliminar_sst(sst_id):
    _ejecutar("DELETE FROM sst_requisitos WHERE id = ?", (sst_id,))


# ===================================================================
# SERVICIOS (agendados en el calendario) + conflictos de personal
# ===================================================================
def verificar_conflictos(personal_ids, fecha_inicio, fecha_fin, excluir_servicio_id=None):
    """Devuelve una lista de conflictos: [{'personal_id', 'personal_nombre', 'servicio'}]
    para cualquier persona de personal_ids que ya tenga otro servicio con fechas cruzadas."""
    if not personal_ids:
        return []
    conflictos = []
    for pid in personal_ids:
        sql = """
            SELECT s.id, s.nombre, s.fecha_inicio, s.fecha_fin, p.nombre AS personal_nombre
            FROM servicio_personal sp
            JOIN servicios s ON s.id = sp.servicio_id
            JOIN personal p ON p.id = sp.personal_id
            WHERE sp.personal_id = ?
              AND s.fecha_inicio <= ? AND s.fecha_fin >= ?
        """
        params = [pid, fecha_fin, fecha_inicio]
        if excluir_servicio_id:
            sql += " AND s.id != ?"
            params.append(excluir_servicio_id)
        for fila in _fetchall(sql, tuple(params)):
            conflictos.append({"personal_id": pid, "personal_nombre": fila["personal_nombre"],
                               "servicio": fila["nombre"], "fecha_inicio": fila["fecha_inicio"],
                               "fecha_fin": fila["fecha_fin"]})
    return conflictos


def crear_servicio(proyecto_id, nombre, fecha_inicio, fecha_fin, personal_ids, confirmado, creado_por):
    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    sid = _insertar("""
        INSERT INTO servicios (proyecto_id, nombre, fecha_inicio, fecha_fin, confirmado,
                               creado_por, modificado_por, modificado_en)
        VALUES (?,?,?,?,?,?,?,?)
    """, (proyecto_id, nombre, fecha_inicio, fecha_fin, confirmado, creado_por, creado_por, ahora))
    for pid in personal_ids:
        _ejecutar("INSERT INTO servicio_personal (servicio_id, personal_id) VALUES (?,?)", (sid, pid))
    return sid


def actualizar_servicio(sid, nombre, fecha_inicio, fecha_fin, personal_ids, confirmado, modificado_por):
    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    _ejecutar("""
        UPDATE servicios SET nombre=?, fecha_inicio=?, fecha_fin=?, confirmado=?,
                             modificado_por=?, modificado_en=?
        WHERE id=?
    """, (nombre, fecha_inicio, fecha_fin, confirmado, modificado_por, ahora, sid))
    _ejecutar("DELETE FROM servicio_personal WHERE servicio_id = ?", (sid,))
    for pid in personal_ids:
        _ejecutar("INSERT INTO servicio_personal (servicio_id, personal_id) VALUES (?,?)", (sid, pid))


def eliminar_servicio(sid):
    _ejecutar("DELETE FROM servicio_personal WHERE servicio_id = ?", (sid,))
    _ejecutar("DELETE FROM servicios WHERE id = ?", (sid,))


def obtener_servicio(sid):
    s = _fetchone("SELECT * FROM servicios WHERE id = ?", (sid,))
    if not s:
        return None
    s["personal"] = _fetchall("""
        SELECT sp.personal_id, pe.nombre AS personal_nombre
        FROM servicio_personal sp JOIN personal pe ON pe.id = sp.personal_id
        WHERE sp.servicio_id = ?
    """, (sid,))
    s["personal_ids"] = [r["personal_id"] for r in s["personal"]]
    return s


def listar_servicios(proyecto_id=None):
    """Servicios con su proyecto (nombre/color) y personal asignado, para armar el calendario."""
    sql = """
        SELECT s.*, p.nombre AS proyecto_nombre, p.color AS proyecto_color,
               p.cliente AS cliente, p.pm_usuario AS pm_usuario,
               p.prevencionista AS prevencionista
        FROM servicios s JOIN proyectos p ON p.id = s.proyecto_id
    """
    params = ()
    if proyecto_id:
        sql += " WHERE s.proyecto_id = ?"
        params = (proyecto_id,)
    sql += " ORDER BY s.fecha_inicio"
    servicios = _fetchall(sql, params)
    asignaciones = _fetchall("""
        SELECT sp.servicio_id, sp.personal_id, pe.nombre AS personal_nombre
        FROM servicio_personal sp JOIN personal pe ON pe.id = sp.personal_id
    """)
    por_servicio = {}
    for a in asignaciones:
        por_servicio.setdefault(a["servicio_id"], []).append(
            {"personal_id": a["personal_id"], "personal_nombre": a["personal_nombre"]})
    for s in servicios:
        s["personal"] = por_servicio.get(s["id"], [])
        s["personal_ids"] = [x["personal_id"] for x in s["personal"]]
    return servicios

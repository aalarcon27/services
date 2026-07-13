# -*- coding: utf-8 -*-
"""
Proyectos INPROCESS - calendario de servicios y personal (Streamlit).

Correr:  pip install streamlit streamlit-calendar
         streamlit run app.py
"""
from datetime import date

import streamlit as st

import db
import auth
from calendario import mostrar_calendario, restar_dia, sumar_dia
from drag_scheduler import drag_scheduler

st.set_page_config(page_title="Proyectos INPROCESS", page_icon="📅", layout="wide")

db.init_db()
db.seed_usuarios(auth.hash_clave)

ROL_ADMIN = "admin"
ROLES_EDITOR = ("admin", "editor")
ROL_VISOR = "visor"


# ===================================================================
# LOGIN
# ===================================================================
def pantalla_login():
    st.title("📅 Proyectos INPROCESS")
    with st.form("login"):
        u = st.text_input("Usuario")
        c = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar"):
            usr = db.obtener_usuario(u.strip())
            if usr and auth.verificar_clave(c, usr["clave_hash"]):
                st.session_state.update(usuario=usr["usuario"], nombre=usr["nombre"], rol=usr["rol"])
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")


# ===================================================================
# FORMULARIO COMPARTIDO: crear/editar/eliminar un servicio
# ===================================================================
def _formulario_servicio(proyecto_id, servicio=None, prefill_fechas=None, key_sufijo=""):
    """Devuelve True si se guardo/elimino algo (el caller debe hacer st.rerun())."""
    personal_todos = db.listar_personal(solo_activos=True)
    opciones_ids = [p["id"] for p in personal_todos]
    nombres_por_id = {p["id"]: p["nombre"] for p in personal_todos}
    es_nuevo = servicio is None

    with st.form(f"form_servicio_{key_sufijo}"):
        nombre = st.text_input("Nombre del servicio", value=(servicio["nombre"] if servicio else ""))
        c1, c2 = st.columns(2)
        d_ini = date.fromisoformat(servicio["fecha_inicio"]) if servicio else (
            prefill_fechas["inicio"] if prefill_fechas else date.today())
        d_fin = date.fromisoformat(servicio["fecha_fin"]) if servicio else (
            prefill_fechas["fin"] if prefill_fechas else date.today())
        fecha_inicio = c1.date_input("Fecha inicio", value=d_ini)
        fecha_fin = c2.date_input("Fecha fin", value=d_fin)
        seleccion = st.multiselect("Personal asignado", options=opciones_ids,
                                   default=(servicio["personal_ids"] if servicio else []),
                                   format_func=lambda pid: nombres_por_id.get(pid, "?"))
        confirmado = st.checkbox("Fecha confirmada", value=(bool(servicio["confirmado"]) if servicio else False))
        b1, b2 = st.columns(2)
        guardar = b1.form_submit_button("➕ Crear servicio" if es_nuevo else "💾 Guardar cambios")
        eliminar = False if es_nuevo else b2.form_submit_button("🗑 Eliminar servicio")

    if guardar:
        if not nombre:
            st.error("Ponle un nombre al servicio.")
            return False
        if fecha_fin < fecha_inicio:
            st.error("La fecha fin no puede ser antes que la fecha de inicio.")
            return False
        excluir = servicio["id"] if servicio else None
        conflictos = db.verificar_conflictos(seleccion, fecha_inicio.isoformat(), fecha_fin.isoformat(), excluir)
        if conflictos:
            c = conflictos[0]
            st.error(f"⚠ {c['personal_nombre']} ya está en '{c['servicio']}' del "
                    f"{c['fecha_inicio']} al {c['fecha_fin']}. No se puede asignar en paralelo.")
            return False
        usuario = st.session_state["usuario"]
        if es_nuevo:
            db.crear_servicio(proyecto_id, nombre, fecha_inicio.isoformat(), fecha_fin.isoformat(),
                              seleccion, confirmado, usuario)
        else:
            db.actualizar_servicio(servicio["id"], nombre, fecha_inicio.isoformat(), fecha_fin.isoformat(),
                                   seleccion, confirmado, usuario)
        st.success("Guardado.")
        return True

    if eliminar:
        db.eliminar_servicio(servicio["id"])
        st.success("Servicio eliminado.")
        return True

    return False


NUEVO_PROYECTO = "__nuevo__"


def _formulario_agendar():
    """Un solo formulario: elige un proyecto existente o crea uno nuevo al vuelo,
    y agenda el servicio (fechas/personal) en el mismo envío."""
    proyectos = db.listar_proyectos()
    pms = db.listar_usuarios_pm()
    etiquetas = {NUEVO_PROYECTO: "➕ Proyecto nuevo"}
    etiquetas.update({p["id"]: p["nombre"] for p in proyectos})
    seleccion_proy = st.selectbox("Proyecto", options=[NUEVO_PROYECTO] + [p["id"] for p in proyectos],
                                  format_func=lambda v: etiquetas[v], key="agendar_sel_proy")

    nombre_proy = cliente_proy = pm_proy = prevencionista_proy = None
    if seleccion_proy == NUEVO_PROYECTO:
        c1, c2 = st.columns(2)
        nombre_proy = c1.text_input("Nombre del proyecto", key="agendar_np_nombre")
        cliente_proy = c2.text_input("Cliente", key="agendar_np_cliente")
        c3, c4 = st.columns(2)
        pm_proy = c3.selectbox("PM", options=[u["usuario"] for u in pms],
                               format_func=lambda u: next(x["nombre"] for x in pms if x["usuario"] == u),
                               key="agendar_np_pm")
        prevencionista_proy = c4.text_input("Prevencionista", key="agendar_np_prev")

    st.markdown("**Servicio**")
    rango = st.session_state.get("rango_nuevo")
    nombre_serv = st.text_input("Nombre del servicio", key="agendar_serv_nombre")
    c5, c6 = st.columns(2)
    fecha_inicio = c5.date_input("Fecha inicio", value=(rango["inicio"] if rango else date.today()),
                                 key="agendar_fi")
    fecha_fin = c6.date_input("Fecha fin", value=(rango["fin"] if rango else date.today()), key="agendar_ff")
    personal_todos = db.listar_personal(solo_activos=True)
    seleccion_personal = st.multiselect(
        "Personal asignado", options=[p["id"] for p in personal_todos],
        format_func=lambda pid: next((p["nombre"] for p in personal_todos if p["id"] == pid), "?"),
        key="agendar_personal")
    confirmado_serv = st.checkbox("Fecha confirmada", key="agendar_confirmado")

    if st.button("📅 Agendar", type="primary", key="agendar_submit"):
        if seleccion_proy == NUEVO_PROYECTO and not nombre_proy:
            st.error("Ponle un nombre al proyecto nuevo.")
            return
        if not nombre_serv:
            st.error("Ponle un nombre al servicio.")
            return
        if fecha_fin < fecha_inicio:
            st.error("La fecha fin no puede ser antes que la fecha de inicio.")
            return
        conflictos = db.verificar_conflictos(seleccion_personal, fecha_inicio.isoformat(), fecha_fin.isoformat())
        if conflictos:
            c = conflictos[0]
            st.error(f"⚠ {c['personal_nombre']} ya está en '{c['servicio']}' del "
                    f"{c['fecha_inicio']} al {c['fecha_fin']}. No se puede asignar en paralelo.")
            return
        usuario = st.session_state["usuario"]
        if seleccion_proy == NUEVO_PROYECTO:
            proyecto_id = db.crear_proyecto(nombre_proy, cliente_proy, pm_proy, prevencionista_proy, usuario)
        else:
            proyecto_id = seleccion_proy
        db.crear_servicio(proyecto_id, nombre_serv, fecha_inicio.isoformat(), fecha_fin.isoformat(),
                          seleccion_personal, confirmado_serv, usuario)
        st.success("Agendado.")
        st.session_state["rango_nuevo"] = None
        st.rerun()


# ===================================================================
# CALENDARIO
# ===================================================================
def _procesar_resultado_calendario(resultado, editable):
    if not resultado:
        return
    marca = (resultado.get("callback"), str(resultado))
    if marca == st.session_state.get("_cal_marca"):
        return  # ya procesado en un rerun anterior
    st.session_state["_cal_marca"] = marca

    cb = resultado.get("callback")
    if cb == "eventClick":
        st.session_state["ver_servicio_id"] = int(resultado["eventClick"]["event"]["id"])
    elif cb == "eventChange" and editable:
        ev = resultado["eventChange"]["event"]
        sid = int(ev["id"])
        nueva_inicio = ev["start"][:10]
        nueva_fin = restar_dia(ev["end"][:10])
        servicio = db.obtener_servicio(sid)
        conflictos = db.verificar_conflictos(servicio["personal_ids"], nueva_inicio, nueva_fin,
                                             excluir_servicio_id=sid)
        if conflictos:
            c = conflictos[0]
            st.error(f"⚠ No se pudo mover: {c['personal_nombre']} ya tiene '{c['servicio']}' "
                    f"del {c['fecha_inicio']} al {c['fecha_fin']}.")
        else:
            db.actualizar_servicio(sid, servicio["nombre"], nueva_inicio, nueva_fin,
                                   servicio["personal_ids"], servicio["confirmado"],
                                   st.session_state["usuario"])
            st.success("Fechas actualizadas.")
            st.rerun()
    elif cb == "select" and editable:
        st.session_state["rango_nuevo"] = {
            "inicio": date.fromisoformat(resultado["select"]["start"][:10]),
            "fin": date.fromisoformat(restar_dia(resultado["select"]["end"][:10])),
        }
    elif cb == "dateClick" and editable:
        dia = date.fromisoformat(resultado["dateClick"]["date"][:10])
        st.session_state["rango_nuevo"] = {"inicio": dia, "fin": dia}


def _seccion_arrastrar_personal(editable):
    if not editable:
        return
    todos_servicios = db.listar_servicios()
    personal_todos = db.listar_personal(solo_activos=True)
    if not todos_servicios or not personal_todos:
        return

    st.divider()
    st.markdown("### 🖱️ Asignar personal (arrastra un nombre a una fecha del calendario)")
    etiquetas_serv = {s["id"]: f"{s['proyecto_nombre']} — {s['nombre']}" for s in todos_servicios}
    sid_activo = st.selectbox("¿Qué servicio estás agendando?",
                              options=[s["id"] for s in todos_servicios],
                              format_func=lambda i: etiquetas_serv[i], key="drag_sel_servicio")
    servicio_activo = next(s for s in todos_servicios if s["id"] == sid_activo)

    eventos_drag = [
        {"id": str(p["personal_id"]), "title": p["personal_nombre"],
         "start": servicio_activo["fecha_inicio"], "end": sumar_dia(servicio_activo["fecha_fin"])}
        for p in servicio_activo["personal"]
    ]
    personal_arg = [{"id": p["id"], "nombre": p["nombre"]} for p in personal_todos]

    resultado_drag = drag_scheduler(personal_arg, eventos_drag, color=servicio_activo["proyecto_color"],
                                    fecha_inicial=servicio_activo["fecha_inicio"],
                                    key=f"drag_{sid_activo}")

    marca = str(resultado_drag)
    if resultado_drag and marca != st.session_state.get("_drag_marca"):
        st.session_state["_drag_marca"] = marca
        accion = resultado_drag.get("accion")
        if accion in ("asignar", "mover"):
            person_id = resultado_drag["personId"] if accion == "asignar" else int(resultado_drag["eventId"])
            fecha = resultado_drag["fecha"]
            nuevos_ids = sorted(set(servicio_activo["personal_ids"]) | {person_id})
            nueva_inicio = min(servicio_activo["fecha_inicio"], fecha)
            nueva_fin = max(servicio_activo["fecha_fin"], fecha)
            conflictos = db.verificar_conflictos([person_id], nueva_inicio, nueva_fin,
                                                 excluir_servicio_id=sid_activo)
            if conflictos:
                c = conflictos[0]
                st.error(f"⚠ {c['personal_nombre']} ya está en '{c['servicio']}' del "
                        f"{c['fecha_inicio']} al {c['fecha_fin']}. No se puede asignar en paralelo.")
            else:
                db.actualizar_servicio(sid_activo, servicio_activo["nombre"], nueva_inicio, nueva_fin,
                                       nuevos_ids, servicio_activo["confirmado"], st.session_state["usuario"])
                st.success("Personal asignado.")
                st.rerun()

    asignados = servicio_activo["personal"]
    if asignados:
        st.caption(f"Asignados: {', '.join(p['personal_nombre'] for p in asignados)}  ·  "
                  f"{servicio_activo['fecha_inicio']} a {servicio_activo['fecha_fin']}")
        c1, c2 = st.columns([3, 1])
        quitar_id = c1.selectbox(
            "Quitar a alguien de este servicio", options=[p["personal_id"] for p in asignados],
            format_func=lambda pid: next(p["personal_nombre"] for p in asignados if p["personal_id"] == pid),
            key=f"quitar_sel_{sid_activo}", label_visibility="collapsed")
        if c2.button("🗑 Quitar", key=f"quitar_btn_{sid_activo}"):
            nuevos_ids = [p["personal_id"] for p in asignados if p["personal_id"] != quitar_id]
            db.actualizar_servicio(sid_activo, servicio_activo["nombre"], servicio_activo["fecha_inicio"],
                                   servicio_activo["fecha_fin"], nuevos_ids, servicio_activo["confirmado"],
                                   st.session_state["usuario"])
            st.rerun()


def pantalla_calendario():
    st.subheader("📅 Calendario de servicios")
    rol = st.session_state["rol"]
    editable = rol in ROLES_EDITOR

    if editable:
        cpers, cagenda = st.columns([1, 2])
        with cpers:
            with st.expander("➕ Nuevo personal"):
                with st.form("cal_nuevo_personal", clear_on_submit=True):
                    c1, c2 = st.columns([3, 1])
                    nombre_p = c1.text_input("Nombre del técnico", label_visibility="collapsed",
                                             placeholder="Nombre completo")
                    if c2.form_submit_button("Agregar") and nombre_p:
                        db.crear_personal(nombre_p)
                        st.success(f"'{nombre_p}' agregado.")
                        st.rerun()
        with cagenda:
            with st.expander("📅 Agendar (proyecto/servicio)",
                             expanded=bool(st.session_state.get("rango_nuevo"))):
                _formulario_agendar()

        if not db.listar_personal():
            st.info("👆 Agrega al menos un **personal** para poder asignarlo a un servicio.")

    _seccion_arrastrar_personal(editable)

    proyectos_todos = db.listar_proyectos()
    if proyectos_todos:
        chips = " &nbsp;&nbsp; ".join(
            f"<span style='background-color:{p['color']};color:white;padding:2px 10px;"
            f"border-radius:10px;font-size:0.85em'>{p['nombre']}</span>" for p in proyectos_todos)
        st.markdown(chips, unsafe_allow_html=True)

    servicios = db.listar_servicios()
    resultado = mostrar_calendario(servicios, editable=editable)
    _procesar_resultado_calendario(resultado, editable)

    if st.session_state.get("ver_servicio_id"):
        sid = st.session_state["ver_servicio_id"]
        s = db.obtener_servicio(sid)
        if not s:
            st.session_state["ver_servicio_id"] = None
        else:
            proyecto = db.obtener_proyecto(s["proyecto_id"])
            st.divider()
            st.markdown(f"### 🛠 {s['nombre']} — proyecto: {proyecto['nombre'] if proyecto else '?'}")
            if editable:
                if _formulario_servicio(s["proyecto_id"], servicio=s, key_sufijo=f"cal_{sid}"):
                    st.session_state["ver_servicio_id"] = None
                    st.rerun()
            else:
                nombres = {p["id"]: p["nombre"] for p in db.listar_personal()}
                st.write(f"Fechas: {s['fecha_inicio']} a {s['fecha_fin']}")
                st.write("Personal: " + (", ".join(nombres.get(pid, "?") for pid in s["personal_ids"]) or "sin asignar"))
                st.write("Confirmado: " + ("Sí ✅" if s["confirmado"] else "No ⚠"))
            if st.button("✖ Cerrar panel"):
                st.session_state["ver_servicio_id"] = None
                st.rerun()

    if st.session_state.get("rango_nuevo") and editable:
        rango = st.session_state["rango_nuevo"]
        st.info(f"📌 Fechas tomadas del calendario: **{rango['inicio']} a {rango['fin']}** — "
               "complétalo en '📅 Agendar' arriba.")
        if st.button("Cancelar"):
            st.session_state["rango_nuevo"] = None
            st.rerun()


# ===================================================================
# PROYECTOS
# ===================================================================
def pantalla_proyectos():
    st.subheader("📁 Proyectos")
    rol = st.session_state["rol"]
    editable = rol in ROLES_EDITOR
    pms = db.listar_usuarios_pm()

    if editable:
        with st.expander("➕ Nuevo proyecto"):
            with st.form("nuevo_proyecto", clear_on_submit=True):
                nombre = st.text_input("Nombre del proyecto")
                cliente = st.text_input("Cliente")
                pm = st.selectbox("PM (Project Manager)", options=[u["usuario"] for u in pms],
                                  format_func=lambda u: next(x["nombre"] for x in pms if x["usuario"] == u))
                prevencionista = st.text_input("Prevencionista")
                if st.form_submit_button("Crear proyecto") and nombre:
                    db.crear_proyecto(nombre, cliente, pm, prevencionista, st.session_state["usuario"])
                    st.success("Proyecto creado.")
                    st.rerun()

    proyectos = db.listar_proyectos()
    if not proyectos:
        st.info("Aún no hay proyectos.")
        return

    nombres_opt = {p["id"]: f"🟦 {p['nombre']} — {p['cliente'] or 'sin cliente'}" for p in proyectos}
    sel = st.selectbox("Ver proyecto", options=list(nombres_opt.keys()), format_func=lambda i: nombres_opt[i])
    _detalle_proyecto(sel, editable, pms)


def _detalle_proyecto(pid, editable, pms):
    p = db.obtener_proyecto(pid)
    st.markdown(
        f"## <span style='background-color:{p['color']};color:white;padding:2px 10px;"
        f"border-radius:6px'>{p['nombre']}</span>", unsafe_allow_html=True)

    if editable:
        with st.form(f"editar_proy_{pid}"):
            nombre = st.text_input("Nombre", value=p["nombre"])
            cliente = st.text_input("Cliente", value=p["cliente"] or "")
            usuarios_pm = [u["usuario"] for u in pms]
            idx = usuarios_pm.index(p["pm_usuario"]) if p["pm_usuario"] in usuarios_pm else 0
            pm = st.selectbox("PM", options=usuarios_pm, index=idx,
                              format_func=lambda u: next(x["nombre"] for x in pms if x["usuario"] == u))
            prevencionista = st.text_input("Prevencionista", value=p["prevencionista"] or "")
            if st.form_submit_button("💾 Guardar datos del proyecto"):
                db.editar_proyecto(pid, nombre, cliente, pm, prevencionista)
                st.success("Actualizado.")
                st.rerun()
        if st.session_state.get(f"confirm_del_proy_{pid}"):
            st.warning(f"¿Eliminar el proyecto '{p['nombre']}' y todos sus servicios? Esto no se puede deshacer.")
            cc1, cc2 = st.columns(2)
            if cc1.button("✅ Sí, eliminar proyecto", key=f"delproyok_{pid}"):
                db.eliminar_proyecto(pid)
                st.session_state.pop(f"confirm_del_proy_{pid}", None)
                st.success("Proyecto eliminado.")
                st.rerun()
            if cc2.button("❌ Cancelar", key=f"delproyno_{pid}"):
                st.session_state.pop(f"confirm_del_proy_{pid}", None)
                st.rerun()
        else:
            if st.button("🗑 Eliminar proyecto", key=f"delproy_{pid}"):
                st.session_state[f"confirm_del_proy_{pid}"] = True
                st.rerun()
    else:
        pm_nombre = next((x["nombre"] for x in pms if x["usuario"] == p["pm_usuario"]), p["pm_usuario"])
        st.write(f"**Cliente:** {p['cliente'] or '-'}")
        st.write(f"**PM:** {pm_nombre or '-'}")
        st.write(f"**Prevencionista:** {p['prevencionista'] or '-'}")

    st.divider()
    st.markdown("### ✅ Requisitos SST")
    sst = db.listar_sst(pid)
    if not sst:
        st.caption("Sin requisitos agregados todavía.")
    for r in sst:
        c1, c2, c3, c4 = st.columns([3, 1, 1, 0.6])
        c1.write(r["nombre"])
        enviado = c2.checkbox("Enviado", value=bool(r["enviado"]), key=f"sst_env_{r['id']}", disabled=not editable)
        aprobado = c3.checkbox("Aprobado", value=bool(r["aprobado"]), key=f"sst_apr_{r['id']}", disabled=not editable)
        if editable and (enviado != bool(r["enviado"]) or aprobado != bool(r["aprobado"])):
            db.actualizar_sst(r["id"], enviado, aprobado)
            st.rerun()
        if editable and c4.button("🗑", key=f"sst_del_{r['id']}"):
            db.eliminar_sst(r["id"])
            st.rerun()
    if editable:
        with st.form(f"nuevo_sst_{pid}", clear_on_submit=True):
            c1, c2 = st.columns([4, 1])
            nuevo = c1.text_input("Nuevo requisito SST", label_visibility="collapsed",
                                  placeholder="Ej: Plan de seguridad, ATS, Seguro SCTR...")
            if c2.form_submit_button("➕ Agregar") and nuevo:
                db.agregar_sst(pid, nuevo)
                st.rerun()

    st.divider()
    st.markdown("### 🗓 Servicios agendados")
    servicios = db.listar_servicios(proyecto_id=pid)
    if not servicios:
        st.caption("Sin servicios agendados todavía.")
    for s in servicios:
        estado = "✅ confirmado" if s["confirmado"] else "⚠ no confirmado"
        personal_txt = ", ".join(x["personal_nombre"] for x in s["personal"]) or "sin personal"
        with st.expander(f"{s['nombre']} · {s['fecha_inicio']} → {s['fecha_fin']} · {estado} · {personal_txt}"):
            if editable:
                if _formulario_servicio(pid, servicio=s, key_sufijo=f"proy_{s['id']}"):
                    st.rerun()
            else:
                st.write(f"Fechas: {s['fecha_inicio']} a {s['fecha_fin']}")
                st.write(f"Personal: {personal_txt}")
                st.write(f"Confirmado: {'Sí' if s['confirmado'] else 'No'}")

    if editable:
        with st.expander("➕ Nuevo servicio para este proyecto"):
            if _formulario_servicio(pid, key_sufijo=f"nuevo_{pid}"):
                st.rerun()


# ===================================================================
# PERSONAL (roster de tecnicos)
# ===================================================================
def pantalla_personal():
    st.subheader("👷 Personal técnico")
    rol = st.session_state["rol"]
    editable = rol in ROLES_EDITOR

    if editable:
        with st.form("nuevo_personal", clear_on_submit=True):
            c1, c2 = st.columns([4, 1])
            nombre = c1.text_input("Nombre del técnico", label_visibility="collapsed",
                                   placeholder="Nombre completo")
            if c2.form_submit_button("➕ Agregar") and nombre:
                db.crear_personal(nombre)
                st.rerun()

    for p in db.listar_personal():
        c1, c2, c3 = st.columns([3, 1, 1])
        c1.write(p["nombre"] + ("" if p["activo"] else "  _(inactivo)_"))
        if editable:
            if c2.button("Desactivar" if p["activo"] else "Activar", key=f"tog_pers_{p['id']}"):
                db.editar_personal(p["id"], p["nombre"], not p["activo"])
                st.rerun()
            if c3.button("🗑", key=f"del_pers_{p['id']}"):
                db.eliminar_personal(p["id"])
                st.rerun()


# ===================================================================
# USUARIOS (solo admin) y MI CUENTA
# ===================================================================
def pantalla_usuarios():
    st.subheader("👥 Gestión de usuarios")
    st.dataframe(db.listar_usuarios(), use_container_width=True, hide_index=True)

    st.markdown("**Agregar usuario nuevo**")
    with st.form("nuevo_usuario"):
        u = st.text_input("Usuario")
        n = st.text_input("Nombre completo")
        c = st.text_input("Contraseña inicial", type="password")
        rol = st.selectbox("Rol", ["editor", "visor", "admin"])
        if st.form_submit_button("Crear usuario"):
            if not u or not c:
                st.error("Usuario y contraseña son obligatorios.")
            elif db.obtener_usuario(u.strip()):
                st.error("Ya existe un usuario con ese nombre.")
            else:
                db.crear_usuario(u.strip(), n.strip() or u.strip(), auth.hash_clave(c), rol)
                st.success(f"Usuario '{u}' creado con rol '{rol}'.")
                st.rerun()


def pantalla_mi_cuenta():
    st.subheader("🔑 Mi cuenta")
    st.write(f"Usuario: **{st.session_state['usuario']}**  ·  Rol: **{st.session_state.get('rol')}**")
    st.markdown("**Cambiar mi contraseña**")
    with st.form("cambiar_clave"):
        actual = st.text_input("Contraseña actual", type="password")
        nueva = st.text_input("Contraseña nueva", type="password")
        repetir = st.text_input("Repetir contraseña nueva", type="password")
        if st.form_submit_button("Actualizar contraseña"):
            usr = db.obtener_usuario(st.session_state["usuario"])
            if not auth.verificar_clave(actual, usr["clave_hash"]):
                st.error("La contraseña actual no es correcta.")
            elif not nueva:
                st.error("La contraseña nueva no puede estar vacía.")
            elif nueva != repetir:
                st.error("Las contraseñas nuevas no coinciden.")
            else:
                db.cambiar_clave(st.session_state["usuario"], auth.hash_clave(nueva))
                st.success("Contraseña actualizada.")


# ===================================================================
# APP PRINCIPAL
# ===================================================================
if "usuario" not in st.session_state:
    pantalla_login()
else:
    rol = st.session_state.get("rol")

    if rol == ROL_VISOR:
        opciones_menu = ["Calendario", "Proyectos", "Mi cuenta"]
    else:
        opciones_menu = ["Calendario", "Proyectos", "Personal"]
        if rol == ROL_ADMIN:
            opciones_menu.append("Usuarios")
        opciones_menu.append("Mi cuenta")

    with st.sidebar:
        st.write(f"👤 **{st.session_state['nombre']}**")
        st.caption(f"Rol: {rol}")
        seccion = st.radio("Menú", opciones_menu, key="menu_seccion")
        if st.button("Cerrar sesión"):
            for k in list(st.session_state.keys()):
                st.session_state.pop(k, None)
            st.rerun()

    if seccion == "Calendario":
        pantalla_calendario()
    elif seccion == "Proyectos":
        pantalla_proyectos()
    elif seccion == "Personal":
        pantalla_personal()
    elif seccion == "Usuarios":
        pantalla_usuarios()
    elif seccion == "Mi cuenta":
        pantalla_mi_cuenta()

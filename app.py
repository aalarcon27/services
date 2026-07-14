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
from calendario import mostrar_calendario, sumar_dia, restar_dia
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


# ===================================================================
# CALENDARIO — un solo calendario grande con TODOS los proyectos
# ===================================================================
def _etiqueta_proyecto(servicio, pm_nombre):
    partes = [servicio["proyecto_nombre"]]
    if servicio.get("cliente"):
        partes.append(servicio["cliente"])
    partes.append(f"PM {pm_nombre}")
    if servicio.get("prevencionista"):
        partes.append(f"Prev. {servicio['prevencionista']}")
    asignados = ", ".join(p["personal_nombre"] for p in servicio.get("personal", []))
    if asignados:
        partes.append(f"👷 {asignados}")
    return "  ·  ".join(partes)


def _panel_editar_proyecto(sid, pms, editable):
    """Panel que se abre al hacer clic en un proyecto del calendario:
    editar fechas, checklist de SST, personal asignado, eliminar."""
    s = db.obtener_servicio(sid)
    proyecto = db.obtener_proyecto(s["proyecto_id"])
    if not s or not proyecto:
        st.session_state["editar_proyecto_sid"] = None
        return
    color = proyecto["color"]
    ct1, ct2 = st.columns([5, 1])
    ct1.markdown(f"<h3><span style='color:{color}'>●</span> {proyecto['nombre']}</h3>",
                 unsafe_allow_html=True)
    if ct2.button("✖ Cerrar", key=f"cerrar_top_{sid}", type="primary"):
        st.session_state["editar_proyecto_sid"] = None
        st.rerun()

    if not editable:
        pm_nombre = next((x["nombre"] for x in pms if x["usuario"] == proyecto["pm_usuario"]), proyecto["pm_usuario"])
        st.write(f"**Cliente:** {proyecto['cliente'] or '-'}  ·  **PM:** {pm_nombre}  ·  "
                f"**Prevencionista:** {proyecto['prevencionista'] or '-'}")
        st.write(f"**Fechas:** {s['fecha_inicio']} a {s['fecha_fin']}  ·  "
                f"{'✅ confirmado' if s['confirmado'] else '⚠ no confirmado'}")
    else:
        with st.form(f"editar_proy_form_{sid}"):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre", value=proyecto["nombre"])
            cliente = c2.text_input("Cliente", value=proyecto["cliente"] or "")
            usuarios_pm = [u["usuario"] for u in pms]
            idx = usuarios_pm.index(proyecto["pm_usuario"]) if proyecto["pm_usuario"] in usuarios_pm else 0
            c3, c4 = st.columns(2)
            pm = c3.selectbox("PM", options=usuarios_pm, index=idx,
                              format_func=lambda u: next(x["nombre"] for x in pms if x["usuario"] == u))
            prevencionista = c4.text_input("Prevencionista", value=proyecto["prevencionista"] or "")
            c5, c6 = st.columns(2)
            fecha_inicio = c5.date_input("Fecha inicio", value=date.fromisoformat(s["fecha_inicio"]))
            fecha_fin = c6.date_input("Fecha fin", value=date.fromisoformat(s["fecha_fin"]))
            confirmado = st.checkbox("Fecha confirmada", value=bool(s["confirmado"]))
            if st.form_submit_button("💾 Guardar cambios"):
                if fecha_fin < fecha_inicio:
                    st.error("La fecha fin no puede ser antes que la de inicio.")
                else:
                    conflictos = db.verificar_conflictos(s["personal_ids"], fecha_inicio.isoformat(),
                                                         fecha_fin.isoformat(), excluir_servicio_id=sid)
                    if conflictos:
                        c = conflictos[0]
                        st.error(f"⚠ {c['personal_nombre']} ya está en '{c['servicio']}' del "
                                f"{c['fecha_inicio']} al {c['fecha_fin']}. Cambia las fechas o quítalo.")
                    else:
                        db.editar_proyecto(proyecto["id"], nombre, cliente, pm, prevencionista)
                        db.actualizar_servicio(sid, nombre, fecha_inicio.isoformat(), fecha_fin.isoformat(),
                                               s["personal_ids"], confirmado, st.session_state["usuario"])
                        st.success("Guardado.")
                        st.rerun()

    # ---- Personal asignado ----
    st.markdown("**👷 Personal asignado**")
    if not s["personal"]:
        st.caption("Nadie asignado. Arrastra personal sobre la barra del proyecto en el calendario.")
    for p in s["personal"]:
        cc1, cc2 = st.columns([5, 1])
        cc1.write(f"• {p['personal_nombre']}")
        if editable and cc2.button("🗑", key=f"quitar_{sid}_{p['personal_id']}"):
            nuevos = [x["personal_id"] for x in s["personal"] if x["personal_id"] != p["personal_id"]]
            db.actualizar_servicio(sid, s["nombre"], s["fecha_inicio"], s["fecha_fin"], nuevos,
                                   s["confirmado"], st.session_state["usuario"])
            st.rerun()

    # ---- Requisitos SST (checklist) ----
    st.markdown("**✅ Requisitos de seguridad (SST)**")
    sst = db.listar_sst(proyecto["id"])
    if not sst:
        st.caption("Sin requisitos agregados todavía.")
    for r in sst:
        cc1, cc2, cc3, cc4 = st.columns([3, 1, 1, 0.6])
        cc1.write(r["nombre"])
        enviado = cc2.checkbox("Enviado", value=bool(r["enviado"]), key=f"sst_env_{r['id']}", disabled=not editable)
        aprobado = cc3.checkbox("Aprobado", value=bool(r["aprobado"]), key=f"sst_apr_{r['id']}", disabled=not editable)
        if editable and (enviado != bool(r["enviado"]) or aprobado != bool(r["aprobado"])):
            db.actualizar_sst(r["id"], enviado, aprobado)
            st.rerun()
        if editable and cc4.button("🗑", key=f"sst_del_{r['id']}"):
            db.eliminar_sst(r["id"])
            st.rerun()
    if editable:
        with st.form(f"nuevo_sst_cal_{proyecto['id']}", clear_on_submit=True):
            cc1, cc2 = st.columns([4, 1])
            nuevo = cc1.text_input("Nuevo requisito", label_visibility="collapsed",
                                   placeholder="Ej: Plan de seguridad, ATS, Seguro SCTR...")
            if cc2.form_submit_button("➕ Agregar") and nuevo:
                db.agregar_sst(proyecto["id"], nuevo)
                st.rerun()

    if editable:
        st.divider()
        if st.session_state.get(f"confirm_del_{sid}"):
            st.warning(f"¿Eliminar el proyecto '{proyecto['nombre']}'? No se puede deshacer.")
            d1, d2 = st.columns(2)
            if d1.button("✅ Sí, eliminar", key=f"delok_{sid}"):
                db.eliminar_proyecto(proyecto["id"])
                st.session_state["editar_proyecto_sid"] = None
                st.session_state.pop(f"confirm_del_{sid}", None)
                st.rerun()
            if d2.button("❌ Cancelar", key=f"delno_{sid}"):
                st.session_state.pop(f"confirm_del_{sid}", None)
                st.rerun()
        elif st.button("🗑 Eliminar proyecto", key=f"del_{sid}"):
            st.session_state[f"confirm_del_{sid}"] = True
            st.rerun()


def pantalla_calendario():
    st.subheader("📅 Calendario de proyectos")
    rol = st.session_state["rol"]
    editable = rol in ROLES_EDITOR
    pms = db.listar_usuarios_pm()

    servicios = db.listar_servicios()
    if not servicios:
        st.info("Aún no hay proyectos. Créalos en la pestaña **Proyectos** del menú y aparecerán aquí.")
        return

    pm_por_usuario = {u["usuario"]: u["nombre"] for u in pms}
    proyectos_arg = [
        {"id": s["id"],
         "label": _etiqueta_proyecto(s, pm_por_usuario.get(s.get("pm_usuario"), s.get("pm_usuario") or "-")),
         "start": s["fecha_inicio"], "end": sumar_dia(s["fecha_fin"]),
         "color": s["proyecto_color"]}
        for s in servicios
    ]

    if editable:
        personal_todos = db.listar_personal(solo_activos=True)
        if not personal_todos:
            st.info("Aún no hay personal. Agrégalo en la pestaña **Personal** del menú para poder asignarlo.")
        # El personal ya asignado a algun proyecto no aparece en la lista de disponibles
        # (se libera quitandolo desde el proyecto). "Disponible" = sin proyecto asignado.
        ocupados = set()
        for s in servicios:
            ocupados.update(s["personal_ids"])
        disponibles = [p for p in personal_todos if p["id"] not in ocupados]
        personal_arg = [{"id": p["id"], "nombre": p["nombre"]} for p in disponibles]
        if personal_todos and not disponibles:
            st.caption("Todo el personal está asignado. Para liberar a alguien, abre su proyecto y quítalo con 🗑.")
        fecha_ini_cal = min(s["fecha_inicio"] for s in servicios)

        resultado = drag_scheduler(personal_arg, proyectos_arg, fecha_inicial=fecha_ini_cal,
                                   key="drag_calendario")
        _procesar_accion_drag(resultado)
    else:
        mostrar_calendario(servicios, editable=False, key="cal_solo_lectura")

    if st.session_state.get("editar_proyecto_sid"):
        st.divider()
        _panel_editar_proyecto(st.session_state["editar_proyecto_sid"], pms, editable)


def _procesar_accion_drag(resultado):
    if not resultado:
        return
    marca = str(resultado)
    if marca == st.session_state.get("_drag_marca"):
        return
    st.session_state["_drag_marca"] = marca
    accion = resultado.get("accion")

    if accion == "click_proyecto":
        st.session_state["editar_proyecto_sid"] = int(resultado["projectId"])
        st.rerun()

    elif accion == "asignar":
        sid = int(resultado["projectId"])
        person_id = int(resultado["personId"])
        s = db.obtener_servicio(sid)
        if not s:
            return
        if person_id in s["personal_ids"]:
            return
        conflictos = db.verificar_conflictos([person_id], s["fecha_inicio"], s["fecha_fin"],
                                             excluir_servicio_id=sid)
        if conflictos:
            c = conflictos[0]
            st.error(f"⚠ {c['personal_nombre']} ya está en '{c['servicio']}' del "
                    f"{c['fecha_inicio']} al {c['fecha_fin']}. No se puede asignar en paralelo.")
        else:
            nuevos = sorted(set(s["personal_ids"]) | {person_id})
            db.actualizar_servicio(sid, s["nombre"], s["fecha_inicio"], s["fecha_fin"], nuevos,
                                   s["confirmado"], st.session_state["usuario"])
            st.success("Personal asignado.")
            st.rerun()

    elif accion == "mover_proyecto":
        sid = int(resultado["projectId"])
        s = db.obtener_servicio(sid)
        if not s:
            return
        nueva_inicio = resultado["start"]
        nueva_fin = restar_dia(resultado["endExcl"]) if resultado.get("endExcl") else nueva_inicio
        conflictos = db.verificar_conflictos(s["personal_ids"], nueva_inicio, nueva_fin,
                                             excluir_servicio_id=sid)
        if conflictos:
            c = conflictos[0]
            st.error(f"⚠ No se pudo mover: {c['personal_nombre']} quedaría en paralelo con "
                    f"'{c['servicio']}' ({c['fecha_inicio']} a {c['fecha_fin']}).")
        else:
            db.actualizar_servicio(sid, s["nombre"], nueva_inicio, nueva_fin, s["personal_ids"],
                                   s["confirmado"], st.session_state["usuario"])
            st.success("Fechas del proyecto actualizadas.")
        st.rerun()

    elif accion == "sin_proyecto":
        st.warning("Suelta el nombre encima de la barra de un proyecto para asignarlo.")


# ===================================================================
# PROYECTOS
# ===================================================================
def pantalla_proyectos():
    st.subheader("📁 Proyectos")
    rol = st.session_state["rol"]
    editable = rol in ROLES_EDITOR
    pms = db.listar_usuarios_pm()

    if editable:
        st.markdown("### ➕ Crear proyecto nuevo")
        with st.form("nuevo_proyecto", clear_on_submit=True):
            nombre = st.text_input("Nombre del proyecto")
            c1, c2 = st.columns(2)
            cliente = c1.text_input("Cliente")
            pm = c2.selectbox("PM (Project Manager)", options=[u["usuario"] for u in pms],
                              format_func=lambda u: next(x["nombre"] for x in pms if x["usuario"] == u))
            prevencionista = st.text_input("Prevencionista")
            c3, c4 = st.columns(2)
            fecha_inicio = c3.date_input("Fecha inicio", value=date.today())
            fecha_fin = c4.date_input("Fecha fin", value=date.today())
            confirmado = st.checkbox("Fecha confirmada")
            if st.form_submit_button("Crear proyecto", type="primary") and nombre:
                if fecha_fin < fecha_inicio:
                    st.error("La fecha fin no puede ser antes que la de inicio.")
                else:
                    usuario = st.session_state["usuario"]
                    proyecto_id = db.crear_proyecto(nombre, cliente, pm, prevencionista, usuario)
                    db.crear_servicio(proyecto_id, nombre, fecha_inicio.isoformat(),
                                      fecha_fin.isoformat(), [], confirmado, usuario)
                    st.success(f"'{nombre}' creado. Ya aparece en el Calendario.")
                    st.rerun()

    proyectos = db.listar_proyectos()
    if not proyectos:
        st.info("Aún no hay proyectos.")
        return

    st.divider()
    st.markdown("### 📋 Proyectos creados")
    st.caption("Haz clic en un proyecto para ver/editar sus datos y requisitos SST.")
    nombres_opt = {p["id"]: f"● {p['nombre']} — {p['cliente'] or 'sin cliente'}" for p in proyectos}
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

# -*- coding: utf-8 -*-
"""
Armado del calendario interactivo (streamlit_calendar / FullCalendar,
version gratuita). Cada servicio agendado es un evento coloreado segun
su proyecto; arrastrar un evento cambia sus fechas (editable=True).
Reasignar personal se hace aparte, con un formulario normal (ver app.py) -
la vista de "una fila por persona" es una funcion de pago de FullCalendar
que no se usa aqui.
"""
import datetime
from streamlit_calendar import calendar


def sumar_dia(fecha_iso):
    return (datetime.date.fromisoformat(fecha_iso) + datetime.timedelta(days=1)).isoformat()


def restar_dia(fecha_iso):
    return (datetime.date.fromisoformat(fecha_iso) - datetime.timedelta(days=1)).isoformat()


def construir_eventos(servicios):
    eventos = []
    for s in servicios:
        nombres = ", ".join(p["personal_nombre"] for p in s.get("personal", [])) or "sin personal"
        sufijo = "" if s.get("confirmado") else " ⚠ no confirmado"
        eventos.append({
            "id": str(s["id"]),
            "title": f"{s['proyecto_nombre']}: {s['nombre']} — {nombres}{sufijo}",
            "start": s["fecha_inicio"],
            "end": sumar_dia(s["fecha_fin"]),  # FullCalendar usa 'end' exclusivo
            "backgroundColor": s["proyecto_color"],
            "borderColor": s["proyecto_color"],
        })
    return eventos


def mostrar_calendario(servicios, editable, key="calendario_principal"):
    opciones = {
        "initialView": "dayGridMonth",
        "selectable": editable,
        "editable": editable,
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,listMonth",
        },
        "height": 700,
    }
    return calendar(events=construir_eventos(servicios), options=opciones, key=key)

# -*- coding: utf-8 -*-
"""
Componente Streamlit a la medida (sin build/npm): un calendario donde se
arrastra personal desde una lista hasta un dia para agendarlo.
Es un componente "estatico" (protocolo postMessage a mano, sin React).
"""
import os
import streamlit.components.v1 as components

_DIR = os.path.dirname(os.path.abspath(__file__))
_component_func = components.declare_component("drag_scheduler", path=_DIR)


def drag_scheduler(personal, eventos, color="#4C6EF5", fecha_inicial=None, key=None):
    """
    personal: lista de {"id": int, "nombre": str}
    eventos: lista de {"id": str, "title": str, "start": "YYYY-MM-DD",
                        "end": "YYYY-MM-DD" (exclusivo)}
    color: color del proyecto/servicio actual (se usa para los chips y eventos)
    Devuelve un dict con la ultima accion del usuario (o None), con un "ts"
    que cambia en cada accion para que Streamlit detecte el cambio:
      {"accion": "asignar", "personId": ..., "fecha": "YYYY-MM-DD", "ts": ...}
      {"accion": "mover", "eventId": ..., "fecha": "YYYY-MM-DD", "ts": ...}
    """
    return _component_func(personal=personal, eventos=eventos, color=color,
                           fechaInicial=fecha_inicial, key=key, default=None)

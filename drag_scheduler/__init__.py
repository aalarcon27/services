# -*- coding: utf-8 -*-
"""
Componente Streamlit a la medida (sin build/npm): un calendario grande
que muestra TODOS los proyectos como barras de colores, con una lista
de personal a la izquierda que se arrastra encima de la barra de un
proyecto para asignarlo.
Es un componente "estatico" (protocolo postMessage a mano, sin React).
"""
import os
import streamlit.components.v1 as components

_DIR = os.path.dirname(os.path.abspath(__file__))
_component_func = components.declare_component("drag_scheduler", path=_DIR)


def drag_scheduler(personal, proyectos, fecha_inicial=None, key=None):
    """
    personal: lista de {"id": int, "nombre": str}
    proyectos: lista de {"id": int, "label": str, "start": "YYYY-MM-DD",
                         "end": "YYYY-MM-DD" (exclusivo), "color": "#RRGGBB"}
    Devuelve un dict con la ultima accion del usuario (o None):
      {"accion": "asignar", "personId": ..., "projectId": ..., "ts": ...}
      {"accion": "mover_proyecto", "projectId": ..., "start": "YYYY-MM-DD",
       "endExcl": "YYYY-MM-DD", "ts": ...}
      {"accion": "click_proyecto", "projectId": ..., "ts": ...}
      {"accion": "sin_proyecto", "ts": ...}  (soltaron a alguien fuera de una barra)
    """
    return _component_func(personal=personal, proyectos=proyectos,
                           fechaInicial=fecha_inicial, key=key, default=None)

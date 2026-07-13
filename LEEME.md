# Proyectos INPROCESS — calendario de servicios (Streamlit)

App web para planificar operativamente los servicios: calendario 2026 con
colores por proyecto, personal técnico agendado (sin choques de fechas),
requisitos de SST por proyecto y PM asignado.

## Archivos
- `app.py`      → la app (login, calendario, proyectos, personal, usuarios)
- `db.py`       → base de datos. Detecta sola si usar SQLite (tu PC) o
                  Postgres/Supabase (según exista el secreto `DB_URL`).
- `auth.py`     → login con contraseñas hasheadas (igual que Cotiza)
- `calendario.py` → arma los eventos para el componente streamlit_calendar
- `requirements.txt` → dependencias

## Probar en tu PC
    pip install streamlit streamlit-calendar psycopg2-binary
    streamlit run app.py

Se abre en el navegador. Los 8 usuarios de siempre ya quedan creados
automáticamente al primer arranque (mismos usuario/clave que en Cotiza):
admin (ambar), editores (luis, vivian, jaime), visores (jorge, frank,
cesar, luisq).

## Secciones (menú lateral)
1. **Calendario** — vista mensual/semanal navegable por todo 2026. Arrastra
   un servicio para cambiar sus fechas (bloquea si choca con otro servicio
   de la misma persona). Clic en un servicio para ver/editar su detalle.
2. **Proyectos** — crear/editar proyecto (cliente, color automático, PM,
   prevencionista), requisitos de SST con checks de enviado/aprobado, y
   los servicios agendados de ese proyecto.
3. **Personal** — roster de técnicos agendables (no son usuarios de login).
4. **Usuarios** (solo admin) — igual que Cotiza.
5. **Mi cuenta** — cambiar tu propia contraseña.

## Roles
- **admin**  → todo, incluida gestión de usuarios.
- **editor** → agenda servicios, mueve fechas, marca SST. También puede
  ser PM de un proyecto.
- **visor**  → solo ve el calendario y el detalle de proyectos, sin editar.

## Nota sobre el calendario
La vista "arrastrar y cambiar de fila para reasignar personal" es una
función de pago de FullCalendar (Premium/Scheduler, ~$480). No se usa acá
para no depender de esa licencia. En su lugar: arrastrar SÍ cambia fechas
(gratis), y asignar o cambiar el personal de un servicio se hace con un
formulario normal (multiselect) al abrir ese servicio.

## Para la web (Streamlit Cloud + Supabase)
Igual que Cotiza: crea un proyecto en Supabase, pega su cadena de conexión
en los Secrets de Streamlit Cloud como `DB_URL`, y sube este repo a
GitHub. `db.py` detecta el secreto solo y usa Postgres automáticamente —
no hay que renombrar ni swapear ningún archivo.

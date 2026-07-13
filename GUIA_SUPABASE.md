# Guía: desplegar Proyectos INPROCESS en la web

Mismos pasos que ya hiciste para Cotiza, con un proyecto de Supabase
**nuevo y separado** (no se comparte con el Cotizador).

## PARTE 1 — Base de datos en Supabase

1. Entra a **https://supabase.com** → **New project**.
   - Nombre: `proyectos-inprocess`.
   - Database Password: una contraseña fuerte, anótala.
   - Region: la más cercana (ej. South America - São Paulo).
2. Cuando esté listo, clic en **Connect** → sección **Session pooler**
   (NO "Direct connection") → copia la cadena:
   ```
   postgresql://postgres.XXXX:[YOUR-PASSWORD]@aws-0-REGION.pooler.supabase.com:5432/postgres
   ```
3. Reemplaza `[YOUR-PASSWORD]` por tu contraseña. Esa es tu `DB_URL`.

## PARTE 2 — Subir el código a GitHub

1. Crea un repositorio **privado** en GitHub (ej. `proyectos`).
2. Sube todos los archivos de esta carpeta (`app.py`, `db.py`, `auth.py`,
   `calendario.py`, `requirements.txt`, `LEEME.md`).
   A diferencia de Cotiza, aquí **no hay que renombrar nada** — `db.py`
   funciona igual en tu PC (SQLite) y en la web (Postgres), detecta solo
   según exista o no el secreto `DB_URL`.

## PARTE 3 — Desplegar en Streamlit Community Cloud

1. **share.streamlit.io** → **New app** → elige el repo `proyectos`,
   branch `main`, archivo principal `app.py`.
2. Antes de darle Deploy, en **Advanced settings → Secrets** pega:
   ```
   DB_URL = "postgresql://postgres.XXXX:TUCLAVE@aws-0-REGION.pooler.supabase.com:5432/postgres"
   ```
3. **Deploy**. Al terminar, la URL será algo como
   `https://proyectos-xxxxx.streamlit.app`.
4. Los 8 usuarios de siempre se crean solos al primer arranque (mismo
   usuario/clave que en Cotiza).

## PARTE 4 — Dar acceso solo a tu equipo

Igual que hiciste con Cotiza: en la app desplegada → **Settings** →
**Sharing** → **Only specific people** → agrega el correo de cada quien
(incluyéndote a ti misma, para no quedar afuera).

## Si algo falla

- Mismos problemas/soluciones que con Cotiza: revisa que copiaste la
  cadena del **Session pooler** (puerto 5432) y que el usuario incluye
  `postgres.TUPROYECTO`, no solo `postgres`.
- Si la importación o el guardado tarda mucho, es señal de estar usando
  consultas una por una — este proyecto ya usa inserciones agrupadas
  donde corresponde, así que no debería pasar salvo con datos enormes.

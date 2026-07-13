# -*- coding: utf-8 -*-
"""
Autenticacion simple para el equipo INPROCESS.

REGLA DE ORO: las contrasenas NUNCA se guardan en texto plano.
Se guarda solo el "hash" (una huella irreversible). Al hacer login,
se vuelve a calcular el hash de lo que escribe el usuario y se compara.

Aqui uso hashlib (viene con Python, no instala nada) con sal (salt).
Para produccion seria, la opcion mas robusta es la libreria bcrypt:
   pip install bcrypt
y reemplazar hash_clave/verificar_clave. Dejo nota al final.
"""
import os
import hashlib
import hmac


def hash_clave(clave: str) -> str:
    """Genera un hash con sal aleatoria. Formato: sal$hash (ambos en hex)."""
    sal = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, 200_000)
    return sal.hex() + "$" + dk.hex()


def verificar_clave(clave: str, guardado: str) -> bool:
    """Compara la clave escrita contra el hash guardado, de forma segura."""
    try:
        sal_hex, hash_hex = guardado.split("$")
        sal = bytes.fromhex(sal_hex)
        dk = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, 200_000)
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# ============================================================
# ALTERNATIVA MAS ROBUSTA con bcrypt (recomendada si vas a web de verdad):
#
#   import bcrypt
#   def hash_clave(clave):
#       return bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode()
#   def verificar_clave(clave, guardado):
#       return bcrypt.checkpw(clave.encode(), guardado.encode())
# ============================================================

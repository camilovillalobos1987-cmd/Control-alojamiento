"""
auth.py — Sistema de autenticación basado en sesiones Flask.
Roles:  admin  → acceso total
        viewer → solo dashboard y descarga de reportes
"""
from functools import wraps
from flask import session, redirect, url_for, flash, abort
import hashlib
import os


# ── Hashing seguro con PBKDF2 (sin dependencias extra) ──────────────────────

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"{salt}${dk.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        salt, dk_hex = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
        return dk.hex() == dk_hex
    except Exception:
        return False


# ── Helpers de sesión ────────────────────────────────────────────────────────

def login_user(user: dict):
    session["user_id"]   = user["id"]
    session["user_name"] = user.get("nombre") or user["username"]
    session["username"]  = user["username"]
    session["rol"]       = user["rol"]
    session.permanent    = True


def logout_user():
    session.clear()


def current_user() -> dict | None:
    if "user_id" not in session:
        return None
    return {
        "id":       session["user_id"],
        "nombre":   session["user_name"],
        "username": session["username"],
        "rol":      session["rol"],
    }


def is_admin() -> bool:
    return session.get("rol") == "admin"


# ── Decoradores ──────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión para acceder al sistema.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión para acceder al sistema.", "warning")
            return redirect(url_for("login"))
        if session.get("rol") != "admin":
            flash("No tienes permisos para acceder a esta sección.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated

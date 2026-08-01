"""
Utilitarios de autenticacao: hash de senha, JWT, e FastAPI dependencies
(get_current_user, require_super_admin) usadas para proteger rotas.
"""
import os
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)

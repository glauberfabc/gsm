"""
Utilitarios de autenticacao: hash de senha, JWT, e FastAPI dependencies
(get_current_user, require_super_admin) usadas para proteger rotas.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from models.user import User

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7


def _get_secret_key() -> str:
    # Lido dentro da funcao (nao no import do modulo) para nao depender
    # da ordem de load_dotenv() em relacao a este import, igual ao resto
    # do backend/server.py.
    return os.environ["JWT_SECRET_KEY"]


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRATION_DAYS)
    payload = {"sub": user.id, "role": user.role, "exp": expire}
    return jwt.encode(payload, _get_secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _get_secret_key(), algorithms=[JWT_ALGORITHM])

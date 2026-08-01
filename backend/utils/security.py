"""
Utilitarios de autenticacao: hash de senha, JWT, e FastAPI dependencies
(get_current_user, require_super_admin) usadas para proteger rotas.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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


_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token nao fornecido")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido ou expirado")

    db = request.app.state.db
    user_doc = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario nao encontrado")

    return User(**user_doc)


async def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a super admin")
    return current_user

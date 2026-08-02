"""
Rotas de autenticacao: login e dados do usuario logado.
Este router NAO tem protecao global - POST /login precisa ser publico
(GET /me se protege sozinha via Depends(get_current_user) na propria rota).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from models.user import User, UserPublic
from utils.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

_DUMMY_HASH_FOR_TIMING = hash_password("dummy-constant-for-timing-safety")


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request):
    db = request.app.state.db
    user_doc = await db.users.find_one({"email": payload.email}, {"_id": 0})
    hash_to_check = user_doc["password_hash"] if user_doc else _DUMMY_HASH_FOR_TIMING
    password_ok = verify_password(payload.password, hash_to_check)
    if not user_doc or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha invalidos")

    user = User(**user_doc)
    token = create_access_token(user)
    return LoginResponse(access_token=token, user=UserPublic(**user.model_dump()))


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)):
    return UserPublic(**current_user.model_dump())

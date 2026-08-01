"""
Rotas de gerenciamento de usuarios - exclusivas do super_admin.
Protegidas em bloco via dependencies=[Depends(require_super_admin)]
no app.include_router() (ver backend/server.py).
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from models.user import User, UserCreate, UserPublic, UserUpdate
from utils.security import get_current_user, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


async def _count_super_admins(db) -> int:
    return await db.users.count_documents({"role": "super_admin"})


@router.get("", response_model=List[UserPublic])
async def listar_usuarios(request: Request):
    db = request.app.state.db
    docs = await db.users.find({}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return [UserPublic(**d) for d in docs]


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def criar_usuario(payload: UserCreate, request: Request):
    db = request.app.state.db
    existing = await db.users.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ja existe um usuario com esse email")

    user = User(email=payload.email, password_hash=hash_password(payload.password), role=payload.role)
    doc = user.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.users.insert_one(doc)
    return UserPublic(**user.model_dump())


@router.put("/{user_id}", response_model=UserPublic)
async def editar_usuario(user_id: str, payload: UserUpdate, request: Request):
    db = request.app.state.db
    existing = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    updates = {}
    if payload.email is not None:
        updates["email"] = payload.email
    if payload.password is not None:
        updates["password_hash"] = hash_password(payload.password)
    if payload.role is not None:
        if existing["role"] == "super_admin" and payload.role != "super_admin":
            if await _count_super_admins(db) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nao e possivel rebaixar o ultimo super admin",
                )
        updates["role"] = payload.role

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.users.update_one({"id": user_id}, {"$set": updates})

    updated = await db.users.find_one({"id": user_id}, {"_id": 0})
    return UserPublic(**updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_usuario(user_id: str, request: Request, current_user: User = Depends(get_current_user)):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nao e possivel deletar a propria conta")

    db = request.app.state.db
    existing = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    if existing["role"] == "super_admin" and await _count_super_admins(db) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nao e possivel deletar o ultimo super admin")

    await db.users.delete_one({"id": user_id})

#!/usr/bin/env python3
# backend/scripts/create_admin.py
"""
Cria o primeiro super_admin do sistema. Rodar manualmente uma unica vez
(na VPS ou localmente), a partir da raiz do projeto:
    .\.venv\Scripts\python.exe -m backend.scripts.create_admin
"""
import asyncio
import getpass
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from utils.security import hash_password

load_dotenv(Path(__file__).parent.parent / '.env')


async def create_admin():
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Garante o indice unico em email (idempotente - so precisa rodar uma vez,
    # mas nao ha problema em chamar de novo a cada execucao do script).
    await db.users.create_index("email", unique=True)

    email = input("Email do super admin: ").strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        print(f"Ja existe um usuario com o email {email}. Cancelando.")
        client.close()
        return

    password = getpass.getpass("Senha: ")
    password_confirm = getpass.getpass("Confirme a senha: ")
    if password != password_confirm:
        print("As senhas nao conferem. Cancelando.")
        client.close()
        return

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(password),
        "role": "super_admin",
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(doc)
    print(f"Super admin '{email}' criado com sucesso.")
    client.close()


if __name__ == '__main__':
    asyncio.run(create_admin())

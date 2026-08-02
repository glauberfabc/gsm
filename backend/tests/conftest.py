"""
Fixtures compartilhadas pelos testes de autenticacao/usuarios.
Usa pymongo (sincrono) direto na collection `users`, sem depender da API,
para poder montar cenarios que a propria API protege (ex: criar o primeiro
super_admin nao tem endpoint publico).

So afeta os testes que pedem essas fixtures explicitamente (nada autouse) -
os testes existentes em backend/tests/ continuam intocados.
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent.parent / '.env')

from utils.security import hash_password  # noqa: E402

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


@pytest.fixture
def mongo_db():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


@pytest.fixture
def clean_users(mongo_db):
    """Limpa a collection users antes e depois do teste que a solicitar."""
    mongo_db.users.delete_many({})
    yield
    mongo_db.users.delete_many({})


def create_test_user(mongo_db, email, password, role="normal"):
    """Insere um usuario de teste direto no Mongo (sem passar pela API)."""
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    mongo_db.users.insert_one(doc)
    return doc

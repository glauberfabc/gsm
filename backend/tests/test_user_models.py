"""
Testes puros do modelo Pydantic de usuario (backend/models/user.py).
Nao precisam de servidor rodando nem de MongoDB.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pydantic import ValidationError

from models.user import User, UserCreate, UserUpdate, UserPublic


def test_user_create_requires_email_and_password():
    user_create = UserCreate(email="admin@gsm.com", password="senha123")
    assert user_create.email == "admin@gsm.com"
    assert user_create.password == "senha123"
    assert user_create.role == "normal"


def test_user_create_rejects_invalid_role():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", password="x", role="gerente")


def test_user_create_accepts_super_admin_role():
    user_create = UserCreate(email="admin@gsm.com", password="senha123", role="super_admin")
    assert user_create.role == "super_admin"


def test_user_update_all_fields_optional():
    update = UserUpdate()
    assert update.email is None
    assert update.password is None
    assert update.role is None


def test_user_public_has_no_password_hash_field():
    assert "password_hash" not in UserPublic.model_fields


def test_user_generates_id_and_timestamps_automatically():
    user = User(email="a@b.com", password_hash="hashed")
    assert user.id
    assert user.created_at is not None
    assert user.updated_at is not None

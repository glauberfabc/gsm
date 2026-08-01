"""
Testes puros de hashing de senha e JWT (backend/utils/security.py).
Nao precisam de servidor rodando; precisam apenas de JWT_SECRET_KEY
no backend/.env (ver Task 1).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from utils.security import hash_password, verify_password


def test_hash_password_returns_different_string_than_input():
    hashed = hash_password("minhasenha123")
    assert hashed != "minhasenha123"
    assert len(hashed) > 20


def test_verify_password_accepts_correct_password():
    hashed = hash_password("minhasenha123")
    assert verify_password("minhasenha123", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("minhasenha123")
    assert verify_password("senhaerrada", hashed) is False


def test_hash_password_is_salted_differently_each_time():
    hash1 = hash_password("minhasenha123")
    hash2 = hash_password("minhasenha123")
    assert hash1 != hash2

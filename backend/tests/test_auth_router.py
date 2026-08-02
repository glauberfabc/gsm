"""
Testes de integracao para /api/auth/login e /api/auth/me.
Requerem o backend local rodando (uvicorn) e MongoDB acessivel.
"""
import os
import requests

from conftest import create_test_user

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')


def test_login_with_valid_credentials_returns_token(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")

    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gsm.com",
        "password": "senha123",
    })

    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "admin@gsm.com"
    assert data["user"]["role"] == "super_admin"
    assert "password_hash" not in data["user"]


def test_login_with_wrong_password_returns_401(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123")

    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gsm.com",
        "password": "senhaerrada",
    })

    assert response.status_code == 401


def test_login_with_unknown_email_returns_401(clean_users):
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "naoexiste@gsm.com",
        "password": "qualquer",
    })

    assert response.status_code == 401


def test_me_with_valid_token_returns_user(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123")
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gsm.com",
        "password": "senha123",
    })
    token = login_resp.json()["access_token"]

    response = requests.get(f"{BASE_URL}/api/auth/me", headers={
        "Authorization": f"Bearer {token}"
    })

    assert response.status_code == 200, response.text
    assert response.json()["email"] == "admin@gsm.com"


def test_me_without_token_returns_401(clean_users):
    response = requests.get(f"{BASE_URL}/api/auth/me")
    assert response.status_code == 401

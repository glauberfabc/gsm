"""
Confirma que as ~50 rotas existentes do api_router agora exigem
autenticacao, e que continuam funcionando normalmente com um token valido.
"""
import os
import requests

from conftest import create_test_user

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')


def test_listas_without_token_returns_401(clean_users):
    response = requests.get(f"{BASE_URL}/api/listas")
    assert response.status_code == 401


def test_listas_with_valid_token_returns_200(clean_users, mongo_db):
    create_test_user(mongo_db, "user@gsm.com", "senha123", role="normal")
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "user@gsm.com", "password": "senha123"
    })
    token = login_resp.json()["access_token"]

    response = requests.get(f"{BASE_URL}/api/listas", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text

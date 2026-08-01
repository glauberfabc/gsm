"""
Testes de integracao para /api/users (CRUD, exclusivo super_admin).
Requerem o backend local rodando e MongoDB acessivel.
"""
import os
import requests

from conftest import create_test_user

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')


def _login(email, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_normal_user_cannot_list_users(clean_users, mongo_db):
    create_test_user(mongo_db, "user@gsm.com", "senha123", role="normal")
    token = _login("user@gsm.com", "senha123")

    response = requests.get(f"{BASE_URL}/api/users", headers=_auth_headers(token))

    assert response.status_code == 403


def test_super_admin_can_create_and_list_users(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    token = _login("admin@gsm.com", "senha123")

    create_resp = requests.post(f"{BASE_URL}/api/users", headers=_auth_headers(token), json={
        "email": "novo@gsm.com",
        "password": "outrasenha",
        "role": "normal",
    })
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["email"] == "novo@gsm.com"
    assert "password_hash" not in create_resp.json()

    list_resp = requests.get(f"{BASE_URL}/api/users", headers=_auth_headers(token))
    emails = [u["email"] for u in list_resp.json()]
    assert "admin@gsm.com" in emails
    assert "novo@gsm.com" in emails


def test_creating_duplicate_email_returns_409(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    token = _login("admin@gsm.com", "senha123")

    requests.post(f"{BASE_URL}/api/users", headers=_auth_headers(token), json={
        "email": "dup@gsm.com", "password": "x", "role": "normal"
    })
    response = requests.post(f"{BASE_URL}/api/users", headers=_auth_headers(token), json={
        "email": "dup@gsm.com", "password": "y", "role": "normal"
    })

    assert response.status_code == 409


def test_super_admin_can_edit_user_role(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    other = create_test_user(mongo_db, "outro@gsm.com", "senha123", role="normal")
    token = _login("admin@gsm.com", "senha123")

    response = requests.put(f"{BASE_URL}/api/users/{other['id']}", headers=_auth_headers(token), json={
        "role": "super_admin"
    })

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "super_admin"


def test_cannot_delete_own_account(clean_users, mongo_db):
    admin = create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    token = _login("admin@gsm.com", "senha123")

    response = requests.delete(f"{BASE_URL}/api/users/{admin['id']}", headers=_auth_headers(token))

    assert response.status_code == 400


def test_cannot_demote_last_super_admin(clean_users, mongo_db):
    admin = create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    other_admin = create_test_user(mongo_db, "admin2@gsm.com", "senha123", role="super_admin")
    token_admin2 = _login("admin2@gsm.com", "senha123")

    # admin2 deleta o admin original - ainda sobra admin2, deve funcionar
    ok_resp = requests.delete(f"{BASE_URL}/api/users/{admin['id']}", headers=_auth_headers(token_admin2))
    assert ok_resp.status_code == 204

    # agora so sobra admin2 - rebaixar o unico super_admin restante deve falhar
    demote_resp = requests.put(f"{BASE_URL}/api/users/{other_admin['id']}", headers=_auth_headers(token_admin2), json={
        "role": "normal"
    })
    assert demote_resp.status_code == 400


def test_can_delete_normal_user(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    normal = create_test_user(mongo_db, "user@gsm.com", "senha123", role="normal")
    token = _login("admin@gsm.com", "senha123")

    response = requests.delete(f"{BASE_URL}/api/users/{normal['id']}", headers=_auth_headers(token))

    assert response.status_code == 204

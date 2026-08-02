"""
Testes de integracao para o modelo de propriedade de /api/listas:
- super_admin ve/edita/deleta qualquer lista
- usuario normal ve/edita/deleta apenas as listas que ele mesmo criou
- nao ha mais limite de 5 listas por usuario
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


def _clean_listas(mongo_db, nomes):
    mongo_db.listas_medicamentos.delete_many({"nome": {"$in": nomes}})


def test_normal_user_only_sees_own_listas(clean_users, mongo_db):
    create_test_user(mongo_db, "dona@gsm.com", "senha123", role="normal")
    create_test_user(mongo_db, "outra@gsm.com", "senha123", role="normal")
    _clean_listas(mongo_db, ["Lista da Dona", "Lista da Outra"])

    token_dona = _login("dona@gsm.com", "senha123")
    token_outra = _login("outra@gsm.com", "senha123")

    requests.post(f"{BASE_URL}/api/listas", headers=_auth_headers(token_dona), json={
        "nome": "Lista da Dona", "medicamentos": []
    })
    requests.post(f"{BASE_URL}/api/listas", headers=_auth_headers(token_outra), json={
        "nome": "Lista da Outra", "medicamentos": []
    })

    resp_dona = requests.get(f"{BASE_URL}/api/listas", headers=_auth_headers(token_dona))
    nomes_dona = [l["nome"] for l in resp_dona.json()["listas"]]
    assert "Lista da Dona" in nomes_dona
    assert "Lista da Outra" not in nomes_dona

    _clean_listas(mongo_db, ["Lista da Dona", "Lista da Outra"])


def test_super_admin_sees_listas_from_all_users(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    create_test_user(mongo_db, "normal@gsm.com", "senha123", role="normal")
    _clean_listas(mongo_db, ["Lista Do Admin", "Lista Do Normal"])

    token_admin = _login("admin@gsm.com", "senha123")
    token_normal = _login("normal@gsm.com", "senha123")

    requests.post(f"{BASE_URL}/api/listas", headers=_auth_headers(token_admin), json={
        "nome": "Lista Do Admin", "medicamentos": []
    })
    requests.post(f"{BASE_URL}/api/listas", headers=_auth_headers(token_normal), json={
        "nome": "Lista Do Normal", "medicamentos": []
    })

    resp = requests.get(f"{BASE_URL}/api/listas", headers=_auth_headers(token_admin))
    nomes = [l["nome"] for l in resp.json()["listas"]]
    assert "Lista Do Admin" in nomes
    assert "Lista Do Normal" in nomes

    _clean_listas(mongo_db, ["Lista Do Admin", "Lista Do Normal"])


def test_normal_user_cannot_view_edit_or_delete_others_lista(clean_users, mongo_db):
    create_test_user(mongo_db, "dona2@gsm.com", "senha123", role="normal")
    create_test_user(mongo_db, "intruso@gsm.com", "senha123", role="normal")
    _clean_listas(mongo_db, ["Lista Privada"])

    token_dona = _login("dona2@gsm.com", "senha123")
    token_intruso = _login("intruso@gsm.com", "senha123")

    create_resp = requests.post(f"{BASE_URL}/api/listas", headers=_auth_headers(token_dona), json={
        "nome": "Lista Privada", "medicamentos": []
    })
    lista_id = create_resp.json()["lista"]["id"]

    get_resp = requests.get(f"{BASE_URL}/api/listas/{lista_id}", headers=_auth_headers(token_intruso))
    assert get_resp.status_code == 403

    put_resp = requests.put(f"{BASE_URL}/api/listas/{lista_id}", headers=_auth_headers(token_intruso), json={
        "nome": "Nome Alterado"
    })
    assert put_resp.status_code == 403

    delete_resp = requests.delete(f"{BASE_URL}/api/listas/{lista_id}", headers=_auth_headers(token_intruso))
    assert delete_resp.status_code == 403

    # a dona ainda consegue ver a propria lista normalmente
    own_get = requests.get(f"{BASE_URL}/api/listas/{lista_id}", headers=_auth_headers(token_dona))
    assert own_get.status_code == 200

    _clean_listas(mongo_db, ["Lista Privada"])


def test_super_admin_can_edit_and_delete_others_lista(clean_users, mongo_db):
    create_test_user(mongo_db, "admin2@gsm.com", "senha123", role="super_admin")
    create_test_user(mongo_db, "dona3@gsm.com", "senha123", role="normal")
    _clean_listas(mongo_db, ["Lista Da Dona 3"])

    token_admin = _login("admin2@gsm.com", "senha123")
    token_dona = _login("dona3@gsm.com", "senha123")

    create_resp = requests.post(f"{BASE_URL}/api/listas", headers=_auth_headers(token_dona), json={
        "nome": "Lista Da Dona 3", "medicamentos": []
    })
    lista_id = create_resp.json()["lista"]["id"]

    put_resp = requests.put(f"{BASE_URL}/api/listas/{lista_id}", headers=_auth_headers(token_admin), json={
        "nome": "Lista Editada Pelo Admin"
    })
    assert put_resp.status_code == 200

    delete_resp = requests.delete(f"{BASE_URL}/api/listas/{lista_id}", headers=_auth_headers(token_admin))
    assert delete_resp.status_code == 200

    _clean_listas(mongo_db, ["Lista Da Dona 3", "Lista Editada Pelo Admin"])


def test_can_create_more_than_five_listas(clean_users, mongo_db):
    create_test_user(mongo_db, "colecionador@gsm.com", "senha123", role="normal")
    nomes = [f"Lista Extra {i}" for i in range(6)]
    _clean_listas(mongo_db, nomes)

    token = _login("colecionador@gsm.com", "senha123")

    for nome in nomes:
        resp = requests.post(f"{BASE_URL}/api/listas", headers=_auth_headers(token), json={
            "nome": nome, "medicamentos": []
        })
        assert resp.status_code == 201, resp.text

    _clean_listas(mongo_db, nomes)

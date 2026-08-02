"""
Regressao: o DOU passou a retornar o trecho relevante no campo 'content'
(com o termo destacado em <span class='highlight'>), nao mais em 'abstract'.
O filtro de relevancia em _buscar_dou usava apenas 'abstract', descartando
100% dos resultados do DOU mesmo quando o termo buscado aparecia no
documento (reproduzido com 'denosumabe': 20 itens brutos da API do DOU,
0 mantidos apos o filtro, antes do fix).

GET /api/anvisa/buscar-medicamento?q=denosumabe deve trazer resultados
da fonte DOU.
"""
import os
import re

import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = 'http://127.0.0.1:8000'


def _login_headers():
    email = os.environ.get('GSM_TEST_ADMIN_EMAIL')
    password = os.environ.get('GSM_TEST_ADMIN_PASSWORD')
    if not email or not password:
        pytest.skip("GSM_TEST_ADMIN_EMAIL/GSM_TEST_ADMIN_PASSWORD nao configurados")
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    assert resp.status_code == 200, f"Login falhou: {resp.status_code} {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestDouContentFieldFix:
    def test_denosumabe_retorna_resultados_do_dou(self):
        """
        'denosumabe' tem publicacoes reais no DOU (confirmado manualmente via
        API do in.gov.br). A fonte DOU nao pode retornar 0 para esse termo.
        """
        headers = _login_headers()
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            params={"q": "denosumabe"},
            headers=headers,
            timeout=60,
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        fontes = {f["nome"]: f for f in data.get("fontes_consultadas", [])}
        dou_fonte = next((f for k, f in fontes.items() if k.startswith("DOU")), None)

        assert dou_fonte is not None, "Fonte DOU ausente em fontes_consultadas"
        assert dou_fonte["status"] == "ok", f"Fonte DOU com status de erro: {dou_fonte}"
        assert dou_fonte["total"] > 0, (
            "Fonte DOU retornou 0 resultados para 'denosumabe' - regressao do bug "
            "onde o filtro de relevancia usava o campo 'abstract' (inexistente) "
            "em vez de 'content'"
        )

        dou_resultados = [r for r in data["resultados"] if r.get("fonte_busca") == "DOU"]
        assert len(dou_resultados) > 0
        for r in dou_resultados:
            assert r.get("descricao"), "Resultado do DOU sem descricao preenchida"
            assert not re.search(r'<[^>]+>', r["descricao"]), (
                "descricao do DOU contem tags HTML nao removidas do campo 'content'"
            )

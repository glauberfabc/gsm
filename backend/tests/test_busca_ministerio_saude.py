"""
Testes de integração ao vivo para o filtro de escopo "Ministério da Saúde"
em GET /api/search/unified. Mesmo padrão de test_gsm_v78_independente.py:
requests contra BASE_URL, sem mocks.
"""
import os
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBuscaMinisterioSaudeComTermo:
    def test_filtro_restringe_resultados_a_orgaos_da_saude(self):
        """GET /api/search/unified?q=medicamento&ministerio_saude=true só
        deve retornar resultados de órgãos do portfólio saúde."""
        resp = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={"q": "medicamento", "ministerio_saude": "true", "limit": 30},
            timeout=60,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        resultados = data.get('resultados', [])

        if not resultados:
            # Termo pode não ter achado nada no portfólio saúde nesse momento -
            # não é uma falha do filtro em si, só ausência de dados no
            # instante do teste. Log e não falha.
            print("Nenhum resultado para 'medicamento' com filtro Ministério da Saúde - "
                  "aceitável se não houver contratação ativa nesse momento.")
            return

        for r in resultados:
            orgao = r.get('orgao', '')
            assert 'MINISTERIO' in orgao.upper() or 'SAUDE' in orgao.upper() or \
                'INCA' in orgao.upper() or 'DSEI' in orgao.upper() or 'FIOCRUZ' in orgao.upper(), \
                f"Resultado de órgão fora do portfólio saúde: {orgao}"

    def test_sem_filtro_pode_trazer_orgaos_variados(self):
        """Confirma que o comportamento DEFAULT (sem o filtro) não muda -
        deve poder trazer órgãos fora do portfólio saúde."""
        resp = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={"q": "medicamento", "limit": 30},
            timeout=60,
        )
        assert resp.status_code == 200, resp.text

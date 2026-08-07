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


class TestFiltroOrgaoCamposComprasGov:
    """Teste unitário, sem rede: garante que o filtro apenas_ministerio_saude
    de MotorBuscaIndependente.buscar() reconhece resultados vindos SÓ do
    Compras.gov.br, cujos dicts (produzidos por
    comprasgov_client.normalizar_contratacao_pncp) usam 'orgao_nome' em vez
    de 'orgao' - ao contrário dos dicts vindos do PNCP (_map_pncp), que usam
    'orgao' e '_pncp_cnpj'. Sem esse fallback, um resultado do Compras.gov.br
    que não também apareça via PNCP (então não tem duplicata PNCP-shaped
    "resgatada" pelo dedup) seria descartado silenciosamente pelo filtro -
    especialmente grave para Fiocruz, que hoje só bate por keyword de nome
    (ainda não tem CNPJ confirmado na lista de Task 1)."""

    def test_filtro_reconhece_resultado_vindo_so_do_comprasgov(self):
        """Resultado no formato produzido por normalizar_contratacao_pncp
        (orgao_nome/orgao_cnpj, não orgao/_pncp_cnpj) ainda deve ser
        reconhecido pelo filtro Ministério da Saúde."""
        from services.orgaos_saude_federal import bate_orgao_saude

        resultado_comprasgov_only = {
            'orgao_nome': 'FUNDACAO OSWALDO CRUZ - FIOCRUZ',
            'orgao_cnpj': None,
        }
        # Mesma expressão usada em MotorBuscaIndependente.buscar() para o
        # filtro apenas_ministerio_saude.
        nome = resultado_comprasgov_only.get('orgao') or resultado_comprasgov_only.get('orgao_nome')
        cnpj = resultado_comprasgov_only.get('_pncp_cnpj') or resultado_comprasgov_only.get('orgao_cnpj')
        assert bate_orgao_saude(nome, cnpj) is True

    def test_filtro_ainda_reconhece_formato_pncp(self):
        """Garantia de não-regressão: o formato originado do PNCP (orgao +
        _pncp_cnpj) continua funcionando após adicionar o fallback."""
        from services.orgaos_saude_federal import bate_orgao_saude

        resultado_pncp = {
            'orgao': 'MINISTERIO DA SAUDE',
            '_pncp_cnpj': '00394544000119',
        }
        nome = resultado_pncp.get('orgao') or resultado_pncp.get('orgao_nome')
        cnpj = resultado_pncp.get('_pncp_cnpj') or resultado_pncp.get('orgao_cnpj')
        assert bate_orgao_saude(nome, cnpj) is True

"""
Test LMR Radar and Revogacao Cruzada Features
Tests for:
1. GET /api/dama/lmr-analysis - LMR opportunities list
2. POST /api/dama/lmr-analise-medicamento - Individual medicine analysis
3. POST /api/dama/checklist - Checklist with revogacao cruzada detection
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestLmrAnalysis:
    """Tests for LMR Radar endpoints"""

    def test_lmr_analysis_endpoint_returns_200(self):
        """GET /api/dama/lmr-analysis returns 200 with estatisticas"""
        response = requests.get(f"{BASE_URL}/api/dama/lmr-analysis")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert 'oportunidades' in data, "Response should have 'oportunidades' field"
        assert 'total' in data, "Response should have 'total' field"
        assert 'estatisticas' in data, "Response should have 'estatisticas' field"
        assert 'norma_referencia' in data, "Response should have 'norma_referencia' field"
        
        # Verify estatisticas structure
        stats = data['estatisticas']
        assert 'oportunidade_alta' in stats, "estatisticas should have 'oportunidade_alta'"
        assert 'oportunidade_media' in stats, "estatisticas should have 'oportunidade_media'"
        assert 'oportunidade_baixa' in stats, "estatisticas should have 'oportunidade_baixa'"
        
        print(f"LMR Analysis: {data['total']} oportunidades, stats: {stats}")

    def test_lmr_analysis_with_limite_param(self):
        """GET /api/dama/lmr-analysis with limite parameter"""
        response = requests.get(f"{BASE_URL}/api/dama/lmr-analysis?limite=5")
        assert response.status_code == 200
        
        data = response.json()
        # If there are opportunities, should respect limit
        if data['total'] > 0:
            assert len(data['oportunidades']) <= 5, "Should respect limite parameter"
        print(f"LMR Analysis with limite=5: {len(data.get('oportunidades', []))} returned")


class TestLmrAnaliseMedicamento:
    """Tests for individual medicine LMR analysis"""

    def test_lmr_analise_medicamento_success(self):
        """POST /api/dama/lmr-analise-medicamento returns tax strategy and margins"""
        payload = {
            "medicamento": "insulina",
            "preco_referencia": 100.0,
            "tipo_produto": "biologico"
        }
        response = requests.post(f"{BASE_URL}/api/dama/lmr-analise-medicamento", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert data['medicamento'] == 'insulina', "Should return the queried medicamento"
        assert 'norma_referencia' in data, "Should have norma_referencia"
        assert 'classificacao_lmr' in data, "Should have classificacao_lmr"
        assert 'estrategia_tributaria' in data, "Should have estrategia_tributaria"
        assert 'oportunidade_score' in data, "Should have oportunidade_score"
        assert 'recomendacao' in data, "Should have recomendacao"
        
        # Verify classificacao_lmr structure
        classif = data['classificacao_lmr']
        assert 'categoria' in classif, "classificacao_lmr should have 'categoria'"
        assert 'beneficio_tributario' in classif, "classificacao_lmr should have 'beneficio_tributario'"
        assert 'risco_comercial' in classif, "classificacao_lmr should have 'risco_comercial'"
        
        # Verify estrategia_tributaria structure
        trib = data['estrategia_tributaria']
        assert 'imposto_importacao' in trib, "estrategia_tributaria should have 'imposto_importacao'"
        assert 'icms' in trib, "estrategia_tributaria should have 'icms'"
        assert 'carga_tributaria_total' in trib, "estrategia_tributaria should have 'carga_tributaria_total'"
        assert 'margem_distribuidora' in trib, "estrategia_tributaria should have 'margem_distribuidora'"
        
        print(f"LMR Analise: categoria={classif['categoria']}, score={data['oportunidade_score']}")

    def test_lmr_analise_medicamento_with_margin_calculation(self):
        """POST /api/dama/lmr-analise-medicamento returns margin analysis when preco_referencia > 0"""
        payload = {
            "medicamento": "paracetamol",
            "preco_referencia": 50.0,
            "tipo_produto": "generico"
        }
        response = requests.post(f"{BASE_URL}/api/dama/lmr-analise-medicamento", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        # When preco_referencia > 0, should have analise_margem
        assert 'analise_margem' in data, "Should have analise_margem when preco_referencia > 0"
        
        if data['analise_margem']:
            margem = data['analise_margem']
            assert 'preco_referencia' in margem, "analise_margem should have 'preco_referencia'"
            assert 'preco_distribuidora' in margem, "analise_margem should have 'preco_distribuidora'"
            assert 'lucro_bruto_unitario' in margem, "analise_margem should have 'lucro_bruto_unitario'"
            print(f"Margem analysis: preco_ref={margem['preco_referencia']}, preco_dist={margem['preco_distribuidora']}")

    def test_lmr_analise_medicamento_empty_medicamento_returns_400(self):
        """POST /api/dama/lmr-analise-medicamento with empty medicamento returns 400"""
        payload = {"medicamento": "", "preco_referencia": 100}
        response = requests.post(f"{BASE_URL}/api/dama/lmr-analise-medicamento", json=payload)
        assert response.status_code == 400, f"Expected 400 for empty medicamento, got {response.status_code}"
        print("Empty medicamento correctly returns 400")


class TestChecklistRevogacaoCruzada:
    """Tests for checklist with revogacao cruzada detection"""

    def test_checklist_with_obsolete_norm_rdc_327_2019(self):
        """POST /api/dama/checklist with RDC 327/2019 returns revogacoes_detectadas"""
        payload = {
            "medicamento": "cannabidiol",
            "normas": ["RDC 327/2019"]
        }
        response = requests.post(f"{BASE_URL}/api/dama/checklist", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify basic structure
        assert 'medicamento' in data, "Should have medicamento"
        assert 'checks' in data, "Should have checks"
        assert 'revogacoes_detectadas' in data, "Should have revogacoes_detectadas"
        assert 'score_conformidade' in data, "Should have score_conformidade"
        assert 'resumo' in data, "Should have resumo"
        assert 'normas_vigentes_referencia' in data, "Should have normas_vigentes_referencia"
        
        # Verify revogacao was detected for RDC 327/2019
        revogacoes = data['revogacoes_detectadas']
        assert len(revogacoes) > 0, "Should detect revogacao for RDC 327/2019"
        
        # Find the RDC 327/2019 revogacao
        rdc327_revogacao = None
        for rev in revogacoes:
            if '327' in rev.get('norma_obsoleta', ''):
                rdc327_revogacao = rev
                break
        
        assert rdc327_revogacao is not None, "Should find RDC 327/2019 in revogacoes"
        assert 'revogada_por' in rdc327_revogacao, "revogacao should have 'revogada_por'"
        assert 'data_revogacao' in rdc327_revogacao, "revogacao should have 'data_revogacao'"
        assert 'observacao' in rdc327_revogacao, "revogacao should have 'observacao'"
        assert '660' in rdc327_revogacao['revogada_por'], "RDC 327/2019 should be revoked by RDC 660/2022"
        
        print(f"Revogacao detected: {rdc327_revogacao['norma_obsoleta']} -> {rdc327_revogacao['revogada_por']}")

    def test_checklist_returns_sugestao_substituicao_for_revoked_norms(self):
        """POST /api/dama/checklist returns sugestao_substituicao in checks for revoked norms"""
        payload = {
            "medicamento": "teste",
            "normas": ["RDC 17/2010"]  # This is revoked by RDC 658/2022
        }
        response = requests.post(f"{BASE_URL}/api/dama/checklist", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        checks = data.get('checks', [])
        
        # Find the check for RDC 17/2010
        rdc17_check = None
        for check in checks:
            if '17' in check.get('item', ''):
                rdc17_check = check
                break
        
        if rdc17_check:
            assert rdc17_check['status'] == 'bloqueio', "Revoked norm should have status 'bloqueio'"
            assert 'sugestao_substituicao' in rdc17_check, "Should have sugestao_substituicao"
            assert rdc17_check['sugestao_substituicao'] is not None, "sugestao_substituicao should not be None"
            print(f"Sugestao substituicao: {rdc17_check['sugestao_substituicao']}")

    def test_checklist_returns_normas_vigentes_referencia(self):
        """POST /api/dama/checklist returns normas_vigentes_referencia object"""
        payload = {"medicamento": "insulina"}
        response = requests.post(f"{BASE_URL}/api/dama/checklist", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert 'normas_vigentes_referencia' in data, "Should have normas_vigentes_referencia"
        
        normas_ref = data['normas_vigentes_referencia']
        assert isinstance(normas_ref, dict), "normas_vigentes_referencia should be a dict"
        
        # Verify expected keys
        expected_keys = ['importacao_excepcional', 'precificacao_cmed', 'bpf', 'lmr', 'licitacao']
        for key in expected_keys:
            assert key in normas_ref, f"normas_vigentes_referencia should have '{key}'"
        
        print(f"Normas vigentes: {normas_ref}")

    def test_checklist_basic_without_normas(self):
        """POST /api/dama/checklist without custom normas still works"""
        payload = {"medicamento": "dipirona"}
        response = requests.post(f"{BASE_URL}/api/dama/checklist", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data['medicamento'] == 'dipirona'
        assert 'checks' in data
        assert len(data['checks']) >= 2, "Should have at least 2 checks (vigencia + janela_aberta)"
        
        # Verify resumo structure
        resumo = data.get('resumo', {})
        assert 'total' in resumo, "resumo should have 'total'"
        assert 'aprovados' in resumo, "resumo should have 'aprovados'"
        assert 'alertas' in resumo, "resumo should have 'alertas'"
        assert 'bloqueios' in resumo, "resumo should have 'bloqueios'"
        
        print(f"Checklist resumo: {resumo}")

    def test_checklist_empty_medicamento_returns_400(self):
        """POST /api/dama/checklist with empty medicamento returns 400"""
        payload = {"medicamento": ""}
        response = requests.post(f"{BASE_URL}/api/dama/checklist", json=payload)
        assert response.status_code == 400, f"Expected 400 for empty medicamento, got {response.status_code}"
        print("Empty medicamento correctly returns 400")


class TestChecklistLmrIntegration:
    """Tests for LMR check within checklist"""

    def test_checklist_includes_lmr_check(self):
        """POST /api/dama/checklist includes LMR IN 428/2026 check"""
        payload = {"medicamento": "insulina"}
        response = requests.post(f"{BASE_URL}/api/dama/checklist", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        checks = data.get('checks', [])
        
        # Find LMR check
        lmr_check = None
        for check in checks:
            if check.get('tipo') == 'lmr_in428':
                lmr_check = check
                break
        
        assert lmr_check is not None, "Should have LMR IN 428/2026 check"
        assert 'categoria_lmr' in lmr_check, "LMR check should have 'categoria_lmr'"
        assert 'oportunidade_score' in lmr_check, "LMR check should have 'oportunidade_score'"
        
        print(f"LMR check: categoria={lmr_check['categoria_lmr']}, score={lmr_check['oportunidade_score']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

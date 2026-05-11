"""
Test suite for P0 fix: JANELA ABERTA trigger logic redefinition

BEFORE: PNCP direct purchases (dispensas/contratações diretas) could trigger 'janela_aberta = True'
AFTER: Only official DOU/ANVISA/CMED publications with strong proof keywords trigger 'janela_aberta = True'
       PNCP results are now classified as 'indicador_mercado' (market indicators)

Key changes tested:
1. GET /api/anvisa/buscar-medicamento?q=amoxicilina should return janela_aberta=false (no official shortage publication)
2. GET /api/anvisa/buscar-medicamento?q=insulina should return janela_aberta=false (PNCP dispensas exist but no official shortage publication)
3. PNCP results should have 'indicador_mercado: true' field and tipo_alerta='indicador mercado'
4. PNCP results should NOT have 'janela_aberta_detectada' field
5. analise_dama should have 'has_publicacao_oficial' instead of 'has_pncp_prova'
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = 'https://dama-legal-1.preview.emergentagent.com'


class TestJanelaAbertaP0Fix:
    """Test the new JANELA ABERTA trigger logic"""
    
    def test_amoxicilina_janela_aberta_false(self):
        """
        Amoxicilina search should return janela_aberta=false
        because there's no official DOU/ANVISA shortage publication
        """
        response = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "amoxicilina"}, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Main assertion: janela_aberta should be False
        assert data.get('janela_aberta') == False, f"Expected janela_aberta=False for amoxicilina, got {data.get('janela_aberta')}"
        
        # Verify response structure
        assert 'medicamento_buscado' in data
        assert 'resultados' in data
        assert 'fontes_consultadas' in data
        assert 'analise_dama' in data
        
        print(f"✅ Amoxicilina: janela_aberta={data.get('janela_aberta')}, total={data.get('total')}")
    
    def test_insulina_janela_aberta_false_despite_pncp(self):
        """
        Insulina search should return janela_aberta=false
        even if PNCP dispensas exist - PNCP is now just a market indicator
        """
        response = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "insulina"}, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Main assertion: janela_aberta should be False (PNCP doesn't trigger it anymore)
        assert data.get('janela_aberta') == False, f"Expected janela_aberta=False for insulina (PNCP doesn't trigger), got {data.get('janela_aberta')}"
        
        # Check if there are PNCP results
        pncp_results = [r for r in data.get('resultados', []) if 'PNCP' in r.get('fonte_busca', '')]
        print(f"✅ Insulina: janela_aberta={data.get('janela_aberta')}, total={data.get('total')}, PNCP results={len(pncp_results)}")
    
    def test_pncp_results_have_indicador_mercado(self):
        """
        PNCP results should have indicador_mercado=true field
        """
        response = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "insulina"}, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        resultados = data.get('resultados', [])
        
        # Find PNCP results
        pncp_results = [r for r in resultados if 'PNCP' in r.get('fonte_busca', '')]
        
        if len(pncp_results) > 0:
            for r in pncp_results:
                # PNCP results should have indicador_mercado=true
                assert r.get('indicador_mercado') == True, f"PNCP result missing indicador_mercado=true: {r.get('titulo', '')[:50]}"
                print(f"✅ PNCP result has indicador_mercado=true: {r.get('titulo', '')[:50]}")
        else:
            print("⚠️ No PNCP results found for insulina - skipping indicador_mercado check")
    
    def test_pncp_results_tipo_alerta_indicador_mercado(self):
        """
        PNCP results should have tipo_alerta='indicador mercado' instead of 'janela aberta'
        """
        response = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "insulina"}, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        resultados = data.get('resultados', [])
        
        # Find PNCP results
        pncp_results = [r for r in resultados if 'PNCP' in r.get('fonte_busca', '')]
        
        if len(pncp_results) > 0:
            for r in pncp_results:
                tipo_alerta = r.get('tipo_alerta', '')
                # PNCP results should have tipo_alerta='indicador mercado'
                assert tipo_alerta == 'indicador mercado', f"PNCP result has wrong tipo_alerta: expected 'indicador mercado', got '{tipo_alerta}'"
                print(f"✅ PNCP result has tipo_alerta='indicador mercado': {r.get('titulo', '')[:50]}")
        else:
            print("⚠️ No PNCP results found for insulina - skipping tipo_alerta check")
    
    def test_pncp_results_no_janela_aberta_detectada(self):
        """
        PNCP results should NOT have 'janela_aberta_detectada' field
        """
        response = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "insulina"}, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        resultados = data.get('resultados', [])
        
        # Find PNCP results
        pncp_results = [r for r in resultados if 'PNCP' in r.get('fonte_busca', '')]
        
        for r in pncp_results:
            # PNCP results should NOT have janela_aberta_detectada field
            assert 'janela_aberta_detectada' not in r, f"PNCP result should NOT have janela_aberta_detectada: {r.get('titulo', '')[:50]}"
        
        print(f"✅ {len(pncp_results)} PNCP results verified - none have janela_aberta_detectada")
    
    def test_analise_dama_has_publicacao_oficial(self):
        """
        analise_dama should have 'has_publicacao_oficial' field instead of 'has_pncp_prova'
        """
        response = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "insulina"}, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        analise_dama = data.get('analise_dama', {})
        
        # Should have has_publicacao_oficial
        assert 'has_publicacao_oficial' in analise_dama, f"analise_dama missing 'has_publicacao_oficial' field: {analise_dama}"
        
        # Should NOT have has_pncp_prova (old field)
        assert 'has_pncp_prova' not in analise_dama, f"analise_dama should NOT have 'has_pncp_prova' field: {analise_dama}"
        
        print(f"✅ analise_dama has has_publicacao_oficial={analise_dama.get('has_publicacao_oficial')}")


class TestJanelaAbertaTrueScenario:
    """Test scenarios where janela_aberta SHOULD be true (official publications)"""
    
    def test_desabastecimento_keyword_search(self):
        """
        Search for 'desabastecimento' should potentially return janela_aberta=true
        if there are official DOU/ANVISA publications with strong proof keywords
        """
        response = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "desabastecimento"}, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        
        # Check if there are official publications
        analise_dama = data.get('analise_dama', {})
        has_publicacao_oficial = analise_dama.get('has_publicacao_oficial', False)
        janela_aberta = data.get('janela_aberta', False)
        
        # janela_aberta should match has_publicacao_oficial
        assert janela_aberta == has_publicacao_oficial, f"janela_aberta ({janela_aberta}) should match has_publicacao_oficial ({has_publicacao_oficial})"
        
        print(f"✅ Desabastecimento search: janela_aberta={janela_aberta}, has_publicacao_oficial={has_publicacao_oficial}, total={data.get('total')}")


class TestResponseStructure:
    """Test the response structure is correct"""
    
    def test_response_has_required_fields(self):
        """Verify all required fields are present in response"""
        response = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "amoxicilina"}, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        
        # Required top-level fields
        required_fields = ['medicamento_buscado', 'resultados', 'total', 'fontes_consultadas', 'janela_aberta', 'filtro_temporal', 'analise_dama']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # analise_dama required fields
        analise_dama = data.get('analise_dama', {})
        analise_required = ['impacto', 'rotina', 'has_publicacao_oficial']
        for field in analise_required:
            assert field in analise_dama, f"analise_dama missing required field: {field}"
        
        print(f"✅ Response structure verified with all required fields")
    
    def test_fontes_consultadas_structure(self):
        """Verify fontes_consultadas has correct structure"""
        response = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "amoxicilina"}, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        fontes = data.get('fontes_consultadas', [])
        
        assert len(fontes) >= 5, f"Expected at least 5 sources, got {len(fontes)}"
        
        for fonte in fontes:
            assert 'nome' in fonte, f"Fonte missing 'nome': {fonte}"
            assert 'total' in fonte, f"Fonte missing 'total': {fonte}"
            assert 'status' in fonte, f"Fonte missing 'status': {fonte}"
        
        fonte_names = [f['nome'] for f in fontes]
        print(f"✅ Fontes consultadas: {fonte_names}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

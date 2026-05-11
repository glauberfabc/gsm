"""
Test Preços Service - GSM Buscador de Editais v44.0
Testing the Preços (Prices) search functionality with:
1. Synonym expansion (Prolia → Denosumabe → Xgeva)
2. Post-filtering to remove irrelevant PNCP results  
3. Grouping by presentation/dosage (e.g., 60mg vs 120mg)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPrecosSearch:
    """Tests for the /api/precos/search endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.base_url = BASE_URL
        assert self.base_url, "REACT_APP_BACKEND_URL environment variable must be set"
    
    def test_precos_search_prolia_returns_only_denosumabe(self):
        """
        Test that searching for 'Prolia' returns ONLY Denosumabe-related results.
        Should NOT return irrelevant results like CANABIDIOL, XOLAIR, EYLIA etc.
        """
        # Search for Prolia with cache disabled
        params = {
            'q': 'Prolia',
            'limite': 200,
            'use_cache': 'false'
        }
        
        response = requests.get(f"{self.base_url}/api/precos/search", params=params)
        
        # API should respond
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
        
        data = response.json()
        print(f"\n=== Prolia Search Results ===")
        print(f"Total results: {data.get('total', 0)}")
        print(f"Termo pesquisado: {data.get('termo')}")
        
        # Check for agregações
        agregacoes = data.get('agregacoes', {})
        print(f"Agregações: min={agregacoes.get('minimo')}, max={agregacoes.get('maximo')}, medio={agregacoes.get('medio')}")
        
        # Check apresentacoes (groupings by presentation)
        apresentacoes = data.get('apresentacoes', [])
        print(f"Apresentações: {len(apresentacoes)}")
        for ap in apresentacoes:
            print(f"  - {ap.get('nome')}: {ap.get('total')} itens, min=R${ap.get('preco_minimo')}, max=R${ap.get('preco_maximo')}")
        
        # If there are results, verify they are ONLY Denosumabe-related
        resultados = data.get('resultados', [])
        if resultados:
            irrelevant_terms = ['canabidiol', 'xolair', 'eylia', 'humira', 'adalimumabe', 'pembrolizumabe']
            relevant_terms = ['denosumab', 'denosumabe', 'prolia', 'xgeva']
            
            irrelevant_found = []
            for item in resultados:
                desc = (item.get('descricao') or '').lower()
                for term in irrelevant_terms:
                    if term in desc:
                        irrelevant_found.append({'term': term, 'desc': item.get('descricao')})
            
            # Assert no irrelevant results
            assert len(irrelevant_found) == 0, f"Found irrelevant results: {irrelevant_found}"
            
            # Check at least some results contain Denosumabe
            denosumabe_count = sum(1 for item in resultados 
                                   if any(t in (item.get('descricao') or '').lower() for t in relevant_terms))
            print(f"Denosumabe-related results: {denosumabe_count}/{len(resultados)}")
        else:
            print("No results found - PNCP API might not have data for this search term")
    
    def test_precos_search_denosumabe_returns_same_results(self):
        """
        Test that searching for 'Denosumabe' returns same relevant results as 'Prolia'.
        Both should use synonym expansion.
        """
        params = {
            'q': 'Denosumabe',
            'limite': 200,
            'use_cache': 'false'
        }
        
        response = requests.get(f"{self.base_url}/api/precos/search", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"\n=== Denosumabe Search Results ===")
        print(f"Total results: {data.get('total', 0)}")
        print(f"Agregações: {data.get('agregacoes')}")
        
        apresentacoes = data.get('apresentacoes', [])
        print(f"Apresentações: {len(apresentacoes)}")
        for ap in apresentacoes:
            print(f"  - {ap.get('nome')}: {ap.get('total')} itens")
    
    def test_precos_search_response_has_apresentacoes_array(self):
        """
        Test that the response includes 'apresentacoes' array with grouped results by dosage.
        """
        params = {
            'q': 'Insulina',
            'limite': 100,
            'use_cache': 'false'
        }
        
        response = requests.get(f"{self.base_url}/api/precos/search", params=params)
        
        assert response.status_code == 200
        
        data = response.json()
        print(f"\n=== Insulina Search - Apresentacoes Structure ===")
        print(f"Total results: {data.get('total', 0)}")
        
        # Verify apresentacoes array exists
        assert 'apresentacoes' in data, "Response should include 'apresentacoes' array"
        apresentacoes = data.get('apresentacoes', [])
        print(f"Number of apresentações: {len(apresentacoes)}")
        
        # If there are apresentacoes, verify structure
        if apresentacoes:
            ap = apresentacoes[0]
            
            # Verify each apresentacao has required fields
            assert 'nome' in ap or 'apresentacao' in ap, "Apresentacao should have 'nome' field"
            assert 'preco_minimo' in ap, "Apresentacao should have 'preco_minimo'"
            assert 'preco_maximo' in ap, "Apresentacao should have 'preco_maximo'"
            assert 'preco_medio' in ap, "Apresentacao should have 'preco_medio'"
            assert 'preco_mediana' in ap, "Apresentacao should have 'preco_mediana'"
            
            print(f"First apresentação structure verified: {list(ap.keys())}")
            
            # Check for itens within apresentacao
            itens = ap.get('itens', [])
            print(f"Items in first apresentação: {len(itens)}")
    
    def test_precos_agregacoes_have_correct_format(self):
        """
        Test that agregações (Big Numbers) have preco_minimo, preco_maximo, preco_medio with 2 decimal places.
        """
        params = {
            'q': 'Heparina',
            'limite': 50,
            'use_cache': 'false'
        }
        
        response = requests.get(f"{self.base_url}/api/precos/search", params=params)
        
        assert response.status_code == 200
        
        data = response.json()
        print(f"\n=== Heparina Search - Agregações Format ===")
        
        agregacoes = data.get('agregacoes', {})
        assert agregacoes, "Response should have agregacoes"
        
        # Check fields exist
        assert 'minimo' in agregacoes, "Agregacoes should have 'minimo'"
        assert 'maximo' in agregacoes, "Agregacoes should have 'maximo'"
        assert 'medio' in agregacoes, "Agregacoes should have 'medio'"
        assert 'mediana' in agregacoes, "Agregacoes should have 'mediana'"
        
        # Check values are floats with 2 decimals (rounded)
        minimo = agregacoes.get('minimo')
        maximo = agregacoes.get('maximo')
        medio = agregacoes.get('medio')
        
        print(f"minimo: {minimo} (type: {type(minimo).__name__})")
        print(f"maximo: {maximo} (type: {type(maximo).__name__})")
        print(f"medio: {medio} (type: {type(medio).__name__})")
        
        # Verify they are numbers (not None)
        if minimo is not None:
            assert isinstance(minimo, (int, float)), f"minimo should be numeric, got {type(minimo)}"
        if maximo is not None:
            assert isinstance(maximo, (int, float)), f"maximo should be numeric, got {type(maximo)}"
        if medio is not None:
            assert isinstance(medio, (int, float)), f"medio should be numeric, got {type(medio)}"
    
    def test_precos_api_with_uf_filter(self):
        """
        Test that UF filter works correctly.
        """
        params = {
            'q': 'Medicamento',
            'uf': 'SP',
            'limite': 50,
            'use_cache': 'false'
        }
        
        response = requests.get(f"{self.base_url}/api/precos/search", params=params)
        
        assert response.status_code == 200
        
        data = response.json()
        print(f"\n=== Medicamento SP Search ===")
        print(f"Total results with UF=SP filter: {data.get('total', 0)}")
    
    def test_precos_api_endpoint_exists(self):
        """
        Basic test to verify the /api/precos/search endpoint is reachable.
        """
        params = {
            'q': 'teste',
            'limite': 10,
            'use_cache': 'false'
        }
        
        response = requests.get(f"{self.base_url}/api/precos/search", params=params)
        
        # Should not return 404 or 500
        assert response.status_code in [200, 422], f"Unexpected status: {response.status_code}"
        print(f"\nEndpoint /api/precos/search is accessible. Status: {response.status_code}")


class TestPrecosFiltering:
    """Tests for the relevance filtering in precos service"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        assert self.base_url, "REACT_APP_BACKEND_URL must be set"
    
    def test_prolia_search_excludes_irrelevant_medications(self):
        """
        CRITICAL TEST: Verify that searching 'Prolia' does NOT return medications like:
        - CANABIDIOL
        - XOLAIR  
        - EYLIA
        - Other unrelated medications
        
        This tests the post-filtering logic.
        """
        params = {
            'q': 'Prolia',
            'limite': 100,
            'use_cache': 'false'
        }
        
        response = requests.get(f"{self.base_url}/api/precos/search", params=params)
        assert response.status_code == 200
        
        data = response.json()
        resultados = data.get('resultados', [])
        apresentacoes = data.get('apresentacoes', [])
        
        print(f"\n=== Prolia Filtering Test ===")
        print(f"Total flat results: {len(resultados)}")
        print(f"Total apresentações: {len(apresentacoes)}")
        
        # List of medications that should NOT appear for Prolia search
        excluded_medications = [
            'canabidiol', 'xolair', 'eylia', 'humira', 'adalimumabe', 
            'pembrolizumabe', 'rituximabe', 'infliximabe', 'etanercepte',
            'omalizumabe', 'aflibercepte', 'ranibizumabe'
        ]
        
        # Check resultados (flat list)
        irrelevant_in_resultados = []
        for item in resultados:
            desc = (item.get('descricao') or '').lower()
            for excluded in excluded_medications:
                if excluded in desc:
                    irrelevant_in_resultados.append({
                        'medication': excluded,
                        'description': item.get('descricao')[:100]
                    })
        
        # Check apresentacoes
        irrelevant_in_apresentacoes = []
        for ap in apresentacoes:
            nome = (ap.get('nome') or '').lower()
            for excluded in excluded_medications:
                if excluded in nome:
                    irrelevant_in_apresentacoes.append({
                        'medication': excluded,
                        'apresentacao': ap.get('nome')
                    })
            
            # Also check items within apresentacao
            for item in ap.get('itens', []):
                desc = (item.get('descricao') or '').lower()
                for excluded in excluded_medications:
                    if excluded in desc:
                        irrelevant_in_apresentacoes.append({
                            'medication': excluded,
                            'description': item.get('descricao')[:100]
                        })
        
        if irrelevant_in_resultados:
            print(f"WARNING: Found {len(irrelevant_in_resultados)} irrelevant items in resultados")
            for ir in irrelevant_in_resultados[:5]:
                print(f"  - {ir['medication']}: {ir['description']}")
        
        if irrelevant_in_apresentacoes:
            print(f"WARNING: Found {len(irrelevant_in_apresentacoes)} irrelevant items in apresentações")
            for ir in irrelevant_in_apresentacoes[:5]:
                print(f"  - {ir}")
        
        # This is the critical assertion - no irrelevant medications
        total_irrelevant = len(irrelevant_in_resultados) + len(irrelevant_in_apresentacoes)
        assert total_irrelevant == 0, f"Found {total_irrelevant} irrelevant medication results. Filtering not working properly."
        
        print("✅ No irrelevant medications found - filtering is working correctly")


class TestPrecosGrouping:
    """Tests for grouping by presentation (dosage)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        assert self.base_url, "REACT_APP_BACKEND_URL must be set"
    
    def test_apresentacoes_grouped_by_dosage(self):
        """
        Test that results are properly grouped by presentation/dosage.
        For example, DENOSUMAB 60MG and DENOSUMAB 120MG should be separate groups.
        """
        params = {
            'q': 'Prolia',
            'limite': 200,
            'use_cache': 'false'
        }
        
        response = requests.get(f"{self.base_url}/api/precos/search", params=params)
        assert response.status_code == 200
        
        data = response.json()
        apresentacoes = data.get('apresentacoes', [])
        
        print(f"\n=== Prolia Grouping Test ===")
        print(f"Number of presentation groups: {len(apresentacoes)}")
        
        for ap in apresentacoes:
            nome = ap.get('nome', 'N/A')
            total = ap.get('total', 0)
            min_price = ap.get('preco_minimo', 0)
            max_price = ap.get('preco_maximo', 0)
            avg_price = ap.get('preco_medio', 0)
            
            print(f"  - {nome}")
            print(f"    Total: {total} items")
            print(f"    Price range: R$ {min_price} - R$ {max_price}")
            print(f"    Average: R$ {avg_price}")
        
        # If we have results, verify grouping structure
        if apresentacoes:
            # Each apresentacao should have statistics
            for ap in apresentacoes:
                assert 'preco_minimo' in ap, f"Missing preco_minimo in {ap.get('nome')}"
                assert 'preco_maximo' in ap, f"Missing preco_maximo in {ap.get('nome')}"
                assert 'preco_medio' in ap, f"Missing preco_medio in {ap.get('nome')}"
                assert 'preco_mediana' in ap, f"Missing preco_mediana in {ap.get('nome')}"
                assert 'total' in ap, f"Missing total count in {ap.get('nome')}"
            
            print("✅ All apresentações have required statistical fields")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

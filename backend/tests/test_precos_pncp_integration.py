"""
Backend Tests for Preços Service - PNCP Integration v44+
Tests the improved PNCP Search API integration with:
- Multiple results volume (expecting 40+ results for Prolia)
- Different presentations (60MG, 120MG, 60MG/ML, SEM DOSAGEM)
- Outlier filtering (no results > R$50000)
- Realistic price averages (R$500-2000 range)
- Rate limiting handling
"""

import pytest
import requests
import os
import time

# Use public URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://dama-legal-1.preview.emergentagent.com').rstrip('/')


class TestPrecosSearchPNCP:
    """Tests for /api/precos/search endpoint with PNCP integration"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup before each test"""
        self.api_url = f"{BASE_URL}/api/precos/search"
        self.timeout = 90  # PNCP can be slow with 300+ editais
    
    def test_prolia_search_returns_many_results(self):
        """Test that Prolia search returns significantly more than 2 results"""
        response = requests.get(
            self.api_url,
            params={"q": "Prolia", "use_cache": "false", "limite": 200},
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Key assertion: Total results should be > 20 (was 2 before fix)
        total = data.get("total", 0)
        assert total > 20, f"Expected > 20 results, got {total}"
        print(f"✅ Prolia search returned {total} results (expected > 20)")
    
    def test_apresentacoes_has_different_dosages(self):
        """Test that response has multiple presentation groups"""
        response = requests.get(
            self.api_url,
            params={"q": "Prolia", "use_cache": "false"},
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        apresentacoes = data.get("apresentacoes", [])
        
        # Should have at least 3 different presentations
        assert len(apresentacoes) >= 3, f"Expected >= 3 presentations, got {len(apresentacoes)}"
        
        # Get presentation names
        nomes = [ap.get("nome", "") for ap in apresentacoes]
        print(f"✅ Found {len(apresentacoes)} presentations: {nomes}")
        
        # Check for expected variations
        has_60mg = any("60MG" in nome.upper() for nome in nomes)
        assert has_60mg, "Expected 60MG presentation not found"
        print(f"✅ 60MG presentation found")
    
    def test_120mg_presentation_exists_with_higher_prices(self):
        """Test that 120MG presentation exists and has higher prices than 60MG"""
        response = requests.get(
            self.api_url,
            params={"q": "Prolia", "use_cache": "false"},
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        apresentacoes = data.get("apresentacoes", [])
        
        # Find 120MG presentation
        ap_120mg = None
        ap_60mg = None
        for ap in apresentacoes:
            nome = ap.get("nome", "").upper()
            if "120" in nome:
                ap_120mg = ap
            elif "60MG" in nome and "ML" not in nome:
                ap_60mg = ap
        
        assert ap_120mg is not None, "120MG presentation not found"
        
        preco_120mg = ap_120mg.get("preco_medio", 0)
        print(f"✅ 120MG presentation found with average price R$ {preco_120mg:.2f}")
        
        # 120MG should have higher price than 60MG (different product)
        if ap_60mg:
            preco_60mg = ap_60mg.get("preco_medio", 0)
            assert preco_120mg > preco_60mg, f"120MG ({preco_120mg}) should be higher than 60MG ({preco_60mg})"
            print(f"✅ 120MG (R$ {preco_120mg:.2f}) > 60MG (R$ {preco_60mg:.2f})")
    
    def test_outlier_filtering_no_extreme_values(self):
        """Test that outlier filtering removes values > 10x median (no R$100000+ results)"""
        response = requests.get(
            self.api_url,
            params={"q": "Prolia", "use_cache": "false"},
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        apresentacoes = data.get("apresentacoes", [])
        
        # Check all items for outliers
        outliers = []
        for ap in apresentacoes:
            for item in ap.get("itens", []):
                valor = item.get("valor_unitario", 0)
                if valor > 50000:  # Outlier threshold
                    outliers.append({
                        "apresentacao": ap.get("nome"),
                        "valor": valor,
                        "descricao": item.get("descricao", "")[:50]
                    })
        
        assert len(outliers) == 0, f"Found {len(outliers)} outliers > R$50000: {outliers}"
        print(f"✅ No outliers found (all values < R$50000)")
    
    def test_realistic_average_price(self):
        """Test that average price is realistic (R$500-2000 for Prolia/Denosumabe)"""
        response = requests.get(
            self.api_url,
            params={"q": "Prolia", "use_cache": "false"},
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        agregacoes = data.get("agregacoes", {})
        preco_medio = agregacoes.get("medio", 0)
        
        # Realistic range for Prolia (Denosumabe 60mg is ~R$700-1000)
        assert 500 <= preco_medio <= 2000, f"Average price R$ {preco_medio:.2f} outside realistic range (500-2000)"
        print(f"✅ Average price R$ {preco_medio:.2f} is within realistic range")
    
    def test_no_429_errors_in_response(self):
        """Test that rate limiting is handled properly (no 429 errors visible)"""
        response = requests.get(
            self.api_url,
            params={"q": "Prolia", "use_cache": "false"},
            timeout=self.timeout
        )
        
        # Should not get 429 (rate limited)
        assert response.status_code != 429, "Got 429 rate limit error"
        assert response.status_code == 200
        
        data = response.json()
        # Should have results, not an error response
        assert "total" in data, "Response missing 'total' field"
        print(f"✅ No rate limiting errors, got {data.get('total', 0)} results")
    
    def test_agregacoes_format_correct(self):
        """Test that aggregations have correct numeric format"""
        response = requests.get(
            self.api_url,
            params={"q": "Prolia", "use_cache": "false"},
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        agregacoes = data.get("agregacoes", {})
        
        # All agregações should be numeric
        for key in ["minimo", "maximo", "medio", "mediana"]:
            assert key in agregacoes, f"Missing '{key}' in agregacoes"
            valor = agregacoes[key]
            assert isinstance(valor, (int, float)), f"'{key}' should be numeric, got {type(valor)}"
            assert valor > 0, f"'{key}' should be positive, got {valor}"
        
        # Min should be < Medio < Max
        assert agregacoes["minimo"] <= agregacoes["medio"] <= agregacoes["maximo"], \
            "Price order incorrect: min <= medio <= max"
        
        print(f"✅ Aggregations format correct: Min={agregacoes['minimo']}, Med={agregacoes['medio']}, Max={agregacoes['maximo']}")
    
    def test_apresentacoes_structure(self):
        """Test that apresentacoes array has correct structure"""
        response = requests.get(
            self.api_url,
            params={"q": "Prolia", "use_cache": "false"},
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        apresentacoes = data.get("apresentacoes", [])
        assert len(apresentacoes) > 0, "No apresentacoes in response"
        
        # Check structure of first apresentacao
        ap = apresentacoes[0]
        required_fields = ["nome", "total", "preco_minimo", "preco_maximo", "preco_medio", "preco_mediana", "itens"]
        
        for field in required_fields:
            assert field in ap, f"Missing '{field}' in apresentacao"
        
        # Check items structure
        assert len(ap["itens"]) > 0, "Apresentacao has no itens"
        item = ap["itens"][0]
        
        item_fields = ["orgao", "uf", "descricao", "valor_unitario", "data_homologacao", "fonte"]
        for field in item_fields:
            assert field in item, f"Missing '{field}' in item"
        
        print(f"✅ Apresentação structure correct with {len(ap['itens'])} items")


class TestPrecosSearchValidation:
    """Tests for input validation and edge cases"""
    
    def test_empty_query_returns_error(self):
        """Test that empty query returns 422"""
        response = requests.get(
            f"{BASE_URL}/api/precos/search",
            params={"use_cache": "false"},  # Missing 'q'
            timeout=30
        )
        
        # FastAPI returns 422 for missing required params
        assert response.status_code == 422
        print(f"✅ Empty query correctly returns 422")
    
    def test_uf_filter_works(self):
        """Test that UF filter restricts results to specific state"""
        response = requests.get(
            f"{BASE_URL}/api/precos/search",
            params={"q": "Prolia", "uf": "SP", "use_cache": "false"},
            timeout=90
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All items should be from SP
        apresentacoes = data.get("apresentacoes", [])
        for ap in apresentacoes:
            for item in ap.get("itens", []):
                uf = item.get("uf", "")
                # Allow empty UF (some PNCP records don't have it)
                if uf:
                    assert uf == "SP", f"Item has UF '{uf}' but expected 'SP'"
        
        print(f"✅ UF filter working correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

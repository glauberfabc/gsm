"""
Test Suite for /api/search/unified endpoint v74.0
================================================
Tests the unified search that combines PNCP real-time API + local cache.

Features tested:
1. Endpoint response structure
2. 'insulina' search returns 11000+ results
3. 'canabidiol' search returns multi-source results
4. Response contains required fields (portal_captura, orgao, objeto, link_documento, uf, modalidade)
5. 'fontes' field shows pncp_tempo_real > 0
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestUnifiedSearchEndpoint:
    """Test /api/search/unified endpoint"""
    
    def test_api_health(self):
        """Test that API is accessible"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"API not accessible: {response.status_code}"
        data = response.json()
        assert 'message' in data
        print(f"✅ API Health OK: {data.get('message', '')[:50]}")
    
    def test_search_insulina_returns_results(self):
        """Test that searching 'insulina' returns 11000+ results"""
        response = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={'q': 'insulina', 'limit': 10}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify total > 11000 (per requirements: 11000+ editais encontrados)
        total = data.get('total', 0)
        assert total > 11000, f"Expected total > 11000, got {total}"
        print(f"✅ Insulina search returned {total} results (expected > 11000)")
        
        # Verify resultados is not empty
        resultados = data.get('resultados', [])
        assert len(resultados) > 0, "Expected non-empty resultados"
        print(f"✅ Got {len(resultados)} results in response")
    
    def test_search_response_has_required_fields(self):
        """Test that search results have all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={'q': 'insulina', 'limit': 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields in response
        assert 'total' in data, "Missing 'total' field"
        assert 'resultados' in data, "Missing 'resultados' field"
        assert 'fontes' in data, "Missing 'fontes' field"
        
        # Verify fontes structure
        fontes = data.get('fontes', {})
        assert 'pncp_tempo_real' in fontes, "Missing 'pncp_tempo_real' in fontes"
        print(f"✅ Response has correct structure with fontes: {fontes}")
        
        # Check each result has required fields
        resultados = data.get('resultados', [])
        required_fields = ['portal_captura', 'orgao', 'objeto', 'link_documento', 'uf', 'modalidade']
        
        for idx, result in enumerate(resultados):
            for field in required_fields:
                assert field in result, f"Result {idx} missing '{field}' field"
            print(f"✅ Result {idx}: portal={result.get('portal_captura')}, uf={result.get('uf')}, modalidade={result.get('modalidade')}")
    
    def test_pncp_tempo_real_is_positive(self):
        """Test that fontes.pncp_tempo_real > 0"""
        response = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={'q': 'insulina', 'limit': 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        fontes = data.get('fontes', {})
        pncp_tempo_real = fontes.get('pncp_tempo_real', 0)
        
        assert pncp_tempo_real > 0, f"Expected pncp_tempo_real > 0, got {pncp_tempo_real}"
        print(f"✅ pncp_tempo_real = {pncp_tempo_real} (expected > 0)")
    
    def test_link_documento_contains_pncp(self):
        """Test that link_documento contains pncp.gov.br for PNCP results"""
        response = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={'q': 'insulina', 'limit': 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        resultados = data.get('resultados', [])
        pncp_links_found = 0
        
        for result in resultados:
            link = result.get('link_documento', '')
            if 'pncp.gov.br' in link:
                pncp_links_found += 1
        
        assert pncp_links_found > 0, "Expected at least one link with pncp.gov.br"
        print(f"✅ Found {pncp_links_found} results with pncp.gov.br links out of {len(resultados)}")
    
    def test_search_canabidiol_multi_source(self):
        """Test that 'canabidiol' search returns multi-source results (PNCP + cache local)"""
        response = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={'q': 'canabidiol', 'limit': 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        total = data.get('total', 0)
        assert total > 0, f"Expected total > 0, got {total}"
        print(f"✅ Canabidiol search returned {total} results")
        
        fontes = data.get('fontes', {})
        pncp_real = fontes.get('pncp_tempo_real', 0)
        cache_local = fontes.get('cache_local', 0)
        
        # PNCP tempo real should have results
        assert pncp_real > 0, f"Expected pncp_tempo_real > 0, got {pncp_real}"
        print(f"✅ Sources: pncp_tempo_real={pncp_real}, cache_local={cache_local}")
    
    def test_portal_captura_shows_pncp(self):
        """Test that portal_captura field shows 'PNCP' for PNCP results"""
        response = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={'q': 'insulina', 'limit': 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        resultados = data.get('resultados', [])
        pncp_portals = [r for r in resultados if r.get('portal_captura') == 'PNCP']
        
        assert len(pncp_portals) > 0, "Expected at least one result with portal_captura='PNCP'"
        print(f"✅ Found {len(pncp_portals)} results with portal_captura='PNCP'")
    
    def test_short_query_returns_400(self):
        """Test that queries shorter than 2 chars return 400 error"""
        response = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={'q': 'a', 'limit': 5}
        )
        
        assert response.status_code == 400, f"Expected 400 for short query, got {response.status_code}"
        print("✅ Short query correctly returns 400 error")
    
    def test_empty_query_returns_400(self):
        """Test that empty query returns 400 error"""
        response = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={'q': '', 'limit': 5}
        )
        
        # Either 400 or 422 is acceptable
        assert response.status_code in [400, 422], f"Expected 400/422 for empty query, got {response.status_code}"
        print("✅ Empty query correctly returns error")


class TestNoEffectiReferences:
    """Test that no Effecti references appear in API responses"""
    
    def test_root_endpoint_no_effecti(self):
        """Test that root endpoint has no Effecti references"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        text = response.text.lower()
        assert 'effecti' not in text, f"Found 'effecti' in root response: {response.text[:200]}"
        print("✅ No 'effecti' in root endpoint response")
    
    def test_search_results_no_effecti(self):
        """Test that search results have no Effecti references"""
        response = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={'q': 'insulina', 'limit': 5}
        )
        
        assert response.status_code == 200
        text = response.text.lower()
        
        assert 'effecti' not in text, f"Found 'effecti' in search results"
        print("✅ No 'effecti' in search results")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

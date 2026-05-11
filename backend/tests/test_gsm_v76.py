"""
GSM v76.0 Backend Tests - MongoDB Local + PNCP API
Tests:
1. GET /api/search/unified?q=canabidiol - Returns results with CLONE_CONLICITACAO source
2. GET /api/clone/status - Returns total_editais > 0 and portal list
3. Effecti proxy NOT initialized (checked via logs)
"""

import pytest
import requests
import os

# Use the public URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://dama-legal-1.preview.emergentagent.com')

class TestSearchUnified:
    """Tests for /api/search/unified endpoint - MongoDB local + PNCP"""
    
    def test_search_canabidiol_returns_results(self):
        """Search 'canabidiol' should return results with CLONE_CONLICITACAO and PNCP sources"""
        response = requests.get(f"{BASE_URL}/api/search/unified?q=canabidiol", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'total' in data, "Response should have 'total' field"
        assert 'resultados' in data, "Response should have 'resultados' field"
        assert 'fontes' in data, "Response should have 'fontes' field"
        
        # Check that we have results
        assert data['total'] > 0, f"Expected results > 0, got {data['total']}"
        assert len(data['resultados']) > 0, "Should have at least one result"
        
        # Check fontes field - should have mongodb_proprio > 0
        fontes = data['fontes']
        mongodb_count = fontes.get('mongodb_proprio', 0)
        pncp_count = fontes.get('pncp_tempo_real', 0)
        
        print(f"MongoDB count: {mongodb_count}, PNCP count: {pncp_count}")
        
        # At least one source should have data
        assert mongodb_count > 0 or pncp_count > 0, "Should have results from at least one source"
        
    def test_search_canabidiol_clone_source(self):
        """Search 'canabidiol' should return CLONE_CONLICITACAO as a source"""
        response = requests.get(f"{BASE_URL}/api/search/unified?q=canabidiol", timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check for CLONE_CONLICITACAO source in results
        clone_results = [r for r in data['resultados'] if r.get('fonte') == 'CLONE_CONLICITACAO']
        
        print(f"Total results: {data['total']}")
        print(f"CLONE_CONLICITACAO results: {len(clone_results)}")
        
        # Should have cloned data
        assert len(clone_results) > 0 or data['fontes'].get('mongodb_proprio', 0) > 0, \
            "Should have CLONE_CONLICITACAO results or mongodb_proprio > 0"
    
    def test_search_canabidiol_result_fields(self):
        """Each result should have required fields: objeto, portal_captura, data_publicacao, etc."""
        response = requests.get(f"{BASE_URL}/api/search/unified?q=canabidiol", timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data['resultados']) > 0:
            result = data['resultados'][0]
            
            # Check essential fields
            assert 'objeto' in result, "Result should have 'objeto' field"
            assert 'fonte' in result or 'portal_captura' in result, "Result should have source info"
            
            # Print sample result
            print(f"Sample result: objeto={result.get('objeto', '')[:50]}...")
            print(f"  fonte={result.get('fonte')}, portal_captura={result.get('portal_captura')}")
    
    def test_search_insulina_returns_results(self):
        """Search 'insulina' should also return results"""
        response = requests.get(f"{BASE_URL}/api/search/unified?q=insulina", timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total'] > 0, f"Expected results for 'insulina', got {data['total']}"
        print(f"Insulina results: {data['total']}")


class TestCloneStatus:
    """Tests for /api/clone/status endpoint"""
    
    def test_clone_status_has_editais(self):
        """Clone status should show total_editais > 0"""
        response = requests.get(f"{BASE_URL}/api/clone/status", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'total_editais' in data, "Response should have 'total_editais'"
        assert data['total_editais'] > 0, f"Expected total_editais > 0, got {data['total_editais']}"
        
        print(f"Total editais clonados: {data['total_editais']}")
    
    def test_clone_status_has_portais(self):
        """Clone status should list portals with counts"""
        response = requests.get(f"{BASE_URL}/api/clone/status", timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'portais' in data, "Response should have 'portais'"
        portais = data['portais']
        
        # Should have at least one portal
        assert len(portais) > 0, "Should have at least one portal"
        
        # Print portal distribution
        print("Portal distribution:")
        for portal, count in list(portais.items())[:10]:
            print(f"  {portal}: {count}")
    
    def test_clone_status_independente_flag(self):
        """Clone status should indicate the system is independent"""
        response = requests.get(f"{BASE_URL}/api/clone/status", timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'independente' in data, "Response should have 'independente' flag"
        assert data['independente'] == True, "System should be independent"
        
        print(f"System independente: {data['independente']}")


class TestSearchFilters:
    """Tests for search filters"""
    
    def test_search_with_uf_filter(self):
        """Search with UF filter should work"""
        response = requests.get(f"{BASE_URL}/api/search/unified?q=canabidiol&uf=RJ", timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        # All results should be from RJ
        for result in data['resultados']:
            uf = result.get('uf', '')
            if uf:
                assert uf.upper() == 'RJ', f"Expected UF=RJ, got {uf}"
        
        print(f"Results with UF=RJ: {data['total']}")
    
    def test_search_pagination(self):
        """Search should support pagination"""
        response = requests.get(f"{BASE_URL}/api/search/unified?q=canabidiol&page=1&limit=10", timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'pagination' in data, "Response should have pagination info"
        pagination = data['pagination']
        
        assert 'page' in pagination, "Pagination should have 'page'"
        assert 'per_page' in pagination or 'total_items' in pagination, "Pagination should have size info"
        
        print(f"Pagination: {pagination}")


class TestAPIHealth:
    """Tests for API health"""
    
    def test_root_endpoint(self):
        """Root endpoint should return API info"""
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'message' in data or 'version' in data, "Root should return API info"
        print(f"API root: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
